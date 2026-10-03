"""Local REST + WebSocket API (``pip install "auctionsi[api]"``; ``auctionsi serve``).

Single-process and single-market: every marketplace operation runs under one lock,
so the API is safe to call concurrently but processes one auction step at a time.
Set ``AUCTIONSI_API_KEY`` (or pass ``api_key``) to require an ``X-API-Key`` header.
"""

from __future__ import annotations

import asyncio
import hmac
import os
import threading
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import fields
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response

from auctionsi._version import __version__
from auctionsi.adapters.specs import agent_spec, build_agent
from auctionsi.api.schemas import BidIn, SimulateIn, TaskIn
from auctionsi.config import MarketConfig
from auctionsi.core.bid import BidProposal
from auctionsi.core.task import Task
from auctionsi.errors import AuctionSIError, InvalidTransitionError, NotFoundError
from auctionsi.market.clock import IdGenerator
from auctionsi.market.events import Event
from auctionsi.market.replay import replay_auction
from auctionsi.market.result import AuctionResult
from auctionsi.market.trace import format_trace
from auctionsi.observability import MarketCounters
from auctionsi.reputation.base import MultiDimensionalReputation
from auctionsi.storage import SQLStore, open_store
from auctionsi.storage.sqlite import SQLiteStore

STATIC_DIR = Path(__file__).parent / "static"
MAX_BODY_BYTES = 1024 * 1024


class MarketService:
    """Owns the store, the marketplace and the lock."""

    def __init__(self, db_path: str | Path, config: MarketConfig) -> None:
        self.lock = threading.RLock()
        self.config = config
        run_id = uuid.uuid4().hex[:8]
        self.store: SQLStore = (
            open_store(str(db_path), run_id=run_id)
            if str(db_path).startswith(("postgresql://", "postgres://"))
            else SQLiteStore(db_path, run_id=run_id, check_same_thread=False)
        )
        self.market = config.build(ids=IdGenerator(uuid.uuid4().hex[:6]))
        for observation in self.store.observations():
            self.market.reputation.record(observation)
        for profile in self.store.list_agents():
            if profile.get("spec"):
                self.market.register(build_agent(profile["spec"]))
        self.market.attach_store(self.store)
        self.counters = MarketCounters()
        self.counters.attach(self.market.bus)

    def close(self) -> None:
        self.market.close()
        self.store.close()


def create_app(
    db_path: str | Path = ":memory:",
    *,
    config: MarketConfig | None = None,
    api_key: str | None = None,
    static_dir: Path | None = STATIC_DIR,
) -> FastAPI:
    key = api_key if api_key is not None else os.environ.get("AUCTIONSI_API_KEY")
    service = MarketService(db_path, config or MarketConfig())
    clients: set[asyncio.Queue[dict[str, Any]]] = set()
    loop_holder: dict[str, asyncio.AbstractEventLoop] = {}

    def broadcast(event: Event) -> None:
        loop = loop_holder.get("loop")
        if loop is None:
            return
        payload = event.to_dict()
        for queue in list(clients):
            loop.call_soon_threadsafe(queue.put_nowait, payload)

    service.market.bus.subscribe(broadcast)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        loop_holder["loop"] = asyncio.get_running_loop()
        yield
        service.close()

    app = FastAPI(title="AuctionSI", version=__version__, lifespan=lifespan)
    app.state.service = service

    @app.middleware("http")
    async def guard(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path.startswith("/api/") and request.url.path != "/api/health":
            if key and not hmac.compare_digest(request.headers.get("x-api-key", ""), key):
                return JSONResponse({"detail": "missing or invalid X-API-Key"}, status_code=401)
            length = request.headers.get("content-length")
            if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
                return JSONResponse({"detail": "request body too large"}, status_code=413)
        return await call_next(request)

    @app.exception_handler(AuctionSIError)
    async def domain_error(request: Request, exc: AuctionSIError) -> JSONResponse:
        if isinstance(exc, NotFoundError):
            status = 404
        elif isinstance(exc, InvalidTransitionError):
            status = 409
        else:
            status = 422
        return JSONResponse({"detail": str(exc)}, status_code=status)

    market = service.market
    store = service.store

    # ------------------------------------------------------------------ status

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "version": __version__}

    @app.get("/api/status")
    def status() -> dict[str, Any]:
        with service.lock:
            return {
                **store.status(),
                "agents_registered": len(market.agents),
                "counters": service.counters.snapshot(),
                "mechanism": market.mechanism.to_spec(),
                "policy": market.policy.to_spec(),
            }

    # ------------------------------------------------------------------ agents

    @app.post("/api/agents", status_code=201)
    def register_agent(spec: dict[str, Any]) -> dict[str, Any]:
        with service.lock:
            agent = build_agent(spec)
            market.register(agent, spec=agent_spec(agent))
            return agent.describe()

    @app.get("/api/agents")
    def list_agents() -> list[dict[str, Any]]:
        with service.lock:
            return [{k: v for k, v in a.items() if k != "spec"} for a in store.list_agents()]

    def _reputation(agent_id: str) -> dict[str, Any]:
        rep = MultiDimensionalReputation()
        for obs in store.observations(agent_id):
            rep.record(obs)
        overall = rep.profile(agent_id)
        return {
            "overall": overall.to_dict() if overall else None,
            "by_task_type": {
                t: p.to_dict() for t in rep.task_types(agent_id) if (p := rep.profile(agent_id, t))
            },
        }

    @app.get("/api/agents/{agent_id}")
    def get_agent(agent_id: str) -> dict[str, Any]:
        with service.lock:
            agent = store.get_agent(agent_id)
            if agent is None:
                raise NotFoundError(f"agent {agent_id} is not registered")
            agent.pop("spec", None)
            return {
                "agent": agent,
                "reputation": _reputation(agent_id),
                "bids": store.agent_bids(agent_id),
                "fulfilled_contracts": store.fulfilled_contracts(agent_id),
            }

    @app.get("/api/agents/{agent_id}/reputation")
    def get_reputation(agent_id: str) -> dict[str, Any]:
        with service.lock:
            if store.get_agent(agent_id) is None:
                raise NotFoundError(f"agent {agent_id} is not registered")
            return _reputation(agent_id)

    # ------------------------------------------------------------------- tasks

    def _task(body: TaskIn) -> Task:
        data = body.model_dump()
        data["task_id"] = data["task_id"] or f"task-{uuid.uuid4().hex[:10]}"
        data["unit"] = data["unit"] or service.config.settlement.currency
        return Task.from_dict(data)

    def _result(result: AuctionResult) -> dict[str, Any]:
        record = result.to_dict()
        record["explanation"] = result.explain()
        record["trace"] = result.trace()
        record["succeeded"] = result.succeeded
        record["winners"] = result.winners
        record["buyer_cost"] = result.buyer_cost
        return record

    @app.post("/api/tasks", status_code=201)
    def submit_task(body: TaskIn) -> dict[str, Any]:
        with service.lock:
            return _result(market.submit_task(_task(body)))

    @app.get("/api/tasks")
    def list_tasks(limit: int = 200) -> list[dict[str, Any]]:
        with service.lock:
            return store.list_tasks(limit=min(limit, 5_000))

    # ---------------------------------------------------------------- auctions

    @app.post("/api/auctions", status_code=201)
    def open_auction(body: TaskIn, solicit: bool = True) -> dict[str, Any]:
        with service.lock:
            auction = market.open_auction(_task(body), solicit=solicit)
            return _open_summary(auction.auction_id)

    def _open_summary(auction_id: str) -> dict[str, Any]:
        auction = market.auctions[auction_id]
        return {
            "auction_id": auction.auction_id,
            "task": auction.task.to_dict(),
            "status": auction.status.value,
            "mechanism": auction.mechanism,
            "participants": auction.participants,
            "bids": [b.to_dict() for b in auction.valid_bids],
            "rejected": [r.to_dict() for r in auction.rejected],
        }

    @app.get("/api/auctions")
    def list_auctions(status: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        with service.lock:
            finished = store.list_auctions(status=status, limit=min(limit, 5_000))
            pending = [
                {
                    "auction_id": a.auction_id,
                    "task_id": a.task_id,
                    "status": a.status.value,
                    "mechanism": a.mechanism,
                    "parent_auction_id": a.parent_auction_id,
                }
                for a in market.auctions.values()
                if not a.is_terminal and (status is None or a.status.value == status)
            ]
            return pending + finished

    @app.get("/api/auctions/{auction_id}")
    def get_auction(auction_id: str) -> dict[str, Any]:
        with service.lock:
            record = store.get_auction(auction_id)
            if record is None:
                if auction_id not in market.auctions:
                    raise NotFoundError(f"auction {auction_id} not found")
                record = _open_summary(auction_id)
            events = store.events(auction_id)
            record["trace"] = format_trace(events)
            record["events"] = [e.to_dict() for e in events]
            return record

    @app.post("/api/auctions/{auction_id}/bids", status_code=201)
    def submit_bid(auction_id: str, body: BidIn) -> dict[str, Any]:
        with service.lock:
            values = body.model_dump()
            agent_id = values.pop("agent_id")
            names = {f.name for f in fields(BidProposal)}
            proposal = BidProposal(**{k: v for k, v in values.items() if k in names})
            bid = market.submit_bid(auction_id, agent_id, proposal)
            if bid is None:
                reasons = market.auctions[auction_id].rejected[-1].to_dict()["reasons"]
                raise HTTPException(status_code=422, detail={"rejected": reasons})
            return bid.to_dict()

    @app.post("/api/auctions/{auction_id}/close")
    def close_auction(auction_id: str) -> dict[str, Any]:
        with service.lock:
            return _result(market.close_auction(auction_id))

    @app.post("/api/auctions/{auction_id}/cancel")
    def cancel_auction(auction_id: str, reason: str = "cancelled via API") -> dict[str, Any]:
        with service.lock:
            auction = market.cancel_auction(auction_id, reason)
            return {"auction_id": auction.auction_id, "status": auction.status.value}

    @app.get("/api/auctions/{auction_id}/replay")
    def replay(auction_id: str) -> dict[str, Any]:
        with service.lock:
            report = replay_auction(store.events(auction_id))
            return {
                "auction_id": report.auction_id,
                "matches": report.matches,
                "replayable": report.replayable,
                "recorded_awards": report.recorded_awards,
                "replayed_awards": report.replayed_awards,
                "differences": report.differences,
                "notes": report.notes,
            }

    # --------------------------------------------------------- research views

    @app.post("/api/simulate")
    def simulate(body: SimulateIn) -> dict[str, Any]:
        from auctionsi.simulation.market import simulate_market
        from auctionsi.simulation.metrics import concentration_over_time

        reg = market.plugins
        result = simulate_market(
            body.agents,
            body.tasks,
            seed=body.seed,
            mechanism=reg.mechanisms.create(body.mechanism) if body.mechanism else None,
            policy=reg.policies.create(body.policy) if body.policy else None,
            agent_options={"strategy": body.strategy},
        )
        m = result.metrics
        top = sorted(m.agent_wins.items(), key=lambda kv: -kv[1])[:20]
        return {
            "metrics": m.scalars(),
            "performance": result.performance(),
            "market_share": [{"agent_id": a, "wins": w} for a, w in top],
            "winning_prices": [
                r.awarded_price for r in result.records if r.awarded_price is not None
            ],
            "quality_vs_cost": [
                {"cost": r.buyer_cost, "quality": r.quality}
                for r in result.records
                if r.quality is not None
            ],
            "hhi_over_time": concentration_over_time(result.records, max(1, body.tasks // 20)),
        }

    @app.get("/api/calibration")
    def calibration() -> dict[str, Any]:
        from auctionsi.reports.calibration import calibration_table, reliability_bins

        with service.lock:
            observations = store.observations()
        return {"agents": calibration_table(observations), "bins": reliability_bins(observations)}

    @app.get("/api/experiments")
    def experiments() -> list[dict[str, Any]]:
        with service.lock:
            return store.list_experiments()

    @app.get("/api/plugins")
    def plugins() -> dict[str, list[str]]:
        reg = market.plugins
        return {
            "mechanisms": reg.mechanisms.names(),
            "policies": reg.policies.names(),
            "verifiers": reg.verifiers.names(),
            "settlements": reg.settlements.names(),
            "strategies": reg.strategies.names(),
        }

    # -------------------------------------------------------------- websocket

    @app.websocket("/api/events")
    async def events(websocket: WebSocket) -> None:
        if key and not hmac.compare_digest(websocket.query_params.get("key", ""), key):
            await websocket.close(code=4401)
            return
        await websocket.accept()
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=10_000)
        clients.add(queue)
        try:
            while True:
                await websocket.send_json(await queue.get())
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            clients.discard(queue)

    # ----------------------------------------------------------------- static

    if static_dir is not None and (static_dir / "index.html").is_file():
        root = static_dir.resolve()

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            candidate = (root / path).resolve()
            if path and candidate.is_file() and root in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(root / "index.html")

    return app
