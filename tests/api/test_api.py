from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from auctionsi.api import create_app
from auctionsi.api.app import _offer
from auctionsi.config import MarketConfig

AGENT = {
    "agent_id": "agent-a",
    "capabilities": ["analysis"],
    "cost_model": {"fixed_cost": 0.02},
    "reliability": 1.0,
    "latency_sigma": 0.0,
}


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(tmp_path / "api.db", static_dir=None)
    with TestClient(app) as c:
        yield c


def test_full_flow(client: TestClient) -> None:
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.post("/api/agents", json=AGENT).status_code == 201
    assert (
        client.post(
            "/api/agents", json={**AGENT, "agent_id": "agent-b", "cost_model": {"fixed_cost": 0.05}}
        ).status_code
        == 201
    )
    assert [a["agent_id"] for a in client.get("/api/agents").json()] == ["agent-a", "agent-b"]

    res = client.post("/api/tasks", json={"task_type": "analysis", "budget": 0.2})
    assert res.status_code == 201
    body = res.json()
    assert body["succeeded"]
    assert body["winners"] == ["agent-a"]
    assert "Winner: agent-a" in body["explanation"]

    auction_id = body["auction_id"]
    detail = client.get(f"/api/auctions/{auction_id}").json()
    assert detail["status"] == "settled"
    assert any("winner selected" in line for line in detail["trace"])
    assert client.get(f"/api/auctions/{auction_id}/replay").json()["matches"]
    profile = client.get("/api/agents/agent-a").json()
    assert profile["reputation"]["overall"]["completed"] == 1
    assert "spec" not in profile["agent"]
    assert client.get("/api/agents/agent-a/reputation").json()["overall"]["completed"] == 1
    assert len(client.get("/api/tasks").json()) == 1
    status = client.get("/api/status").json()
    assert status["counts"]["auctions"] == 1
    assert status["counters"]["auctions_completed"] == 1
    assert "forward" in client.get("/api/plugins").json()["mechanisms"]
    assert client.get("/api/calibration").json()["agents"][0]["agent_id"] == "agent-a"


def test_staged_auction_with_external_bids(client: TestClient) -> None:
    client.post("/api/agents", json=AGENT)
    opened = client.post(
        "/api/auctions?solicit=false", json={"task_type": "analysis", "budget": 1.0}
    ).json()
    auction_id = opened["auction_id"]
    assert opened["status"] == "bid_collection"
    assert (
        client.get("/api/auctions", params={"status": "bid_collection"}).json()[0]["auction_id"]
        == auction_id
    )
    ok = client.post(f"/api/auctions/{auction_id}/bids", json={"agent_id": "agent-a", "price": 0.5})
    assert ok.status_code == 201
    dup = client.post(
        f"/api/auctions/{auction_id}/bids", json={"agent_id": "agent-a", "price": 0.4}
    )
    assert dup.status_code == 422
    assert dup.json()["detail"]["rejected"][0]["code"] == "duplicate_bid"
    closed = client.post(f"/api/auctions/{auction_id}/close").json()
    assert closed["buyer_cost"] == pytest.approx(0.5)
    assert client.post(f"/api/auctions/{auction_id}/close").status_code == 409

    other = client.post("/api/auctions", json={"task_type": "analysis"}).json()["auction_id"]
    assert client.post(f"/api/auctions/{other}/cancel").json()["status"] == "cancelled"


def test_errors_and_limits(client: TestClient) -> None:
    assert client.get("/api/auctions/auction-nope").status_code == 404
    assert client.get("/api/agents/nobody").status_code == 404
    assert client.post("/api/agents", json={"kind": "rpc"}).status_code == 422
    assert client.post("/api/tasks", json={"task_type": "bad type!"}).status_code == 422
    assert client.post("/api/tasks", json={"task_type": "x", "evil": 1}).status_code == 422
    big = {"task_type": "x", "description": "x" * (1024 * 1024 + 10)}
    assert client.post("/api/tasks", json=big).status_code == 413


def test_simulate_endpoint(client: TestClient) -> None:
    res = client.post(
        "/api/simulate", json={"agents": 5, "tasks": 40, "mechanism": "second_price_reverse"}
    )
    body = res.json()
    assert body["metrics"]["total_tasks"] == 40
    assert body["hhi_over_time"]
    assert client.post("/api/simulate", json={"agents": 99999}).status_code == 422


def test_api_key_and_websocket(tmp_path: Path) -> None:
    app = create_app(tmp_path / "k.db", api_key="s3cret", static_dir=None)
    with TestClient(app) as c:
        assert c.get("/api/health").status_code == 200
        assert c.get("/api/status").status_code == 401
        headers = {"X-API-Key": "s3cret"}
        assert c.get("/api/status", headers=headers).status_code == 200
        c.post("/api/agents", json=AGENT, headers=headers)
        with c.websocket_connect("/api/events") as ws:
            ws.send_json({"type": "auth", "key": "s3cret"})
            c.post("/api/tasks", json={"task_type": "analysis"}, headers=headers)
            types = [ws.receive_json()["type"] for _ in range(4)]
        assert types[0] == "TaskCreated"
        with c.websocket_connect("/api/events", headers=headers) as ws:
            c.post("/api/tasks", json={"task_type": "analysis"}, headers=headers)
            assert ws.receive_json()["type"] == "TaskCreated"


@pytest.mark.parametrize(
    "first_message",
    [{"type": "auth", "key": "wrong"}, {"key": "s3cret"}, ["auth"], {"type": "auth", "key": 1}],
)
def test_websocket_rejects_bad_auth(tmp_path: Path, first_message: object) -> None:
    app = create_app(tmp_path / "k.db", api_key="s3cret", static_dir=None)
    with TestClient(app) as c, c.websocket_connect("/api/events") as ws:
        ws.send_json(first_message)
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
        assert exc.value.code == 4401


def test_websocket_rejects_wrong_header_and_non_ascii_keys(tmp_path: Path) -> None:
    app = create_app(tmp_path / "k.db", api_key="s3cret", static_dir=None)
    with TestClient(app) as c:
        with (
            c.websocket_connect("/api/events", headers={"X-API-Key": "nope"}) as ws,
            pytest.raises(WebSocketDisconnect),
        ):
            ws.receive_json()
        assert c.get("/api/status", headers={"X-API-Key": "clé".encode()}).status_code == 401


def test_slow_websocket_client_loses_oldest_events() -> None:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=2)
    for n in range(3):
        _offer(queue, {"n": n})
    assert [queue.get_nowait()["n"] for _ in range(2)] == [1, 2]


def test_remove_agent(client: TestClient) -> None:
    client.post("/api/agents", json=AGENT)
    client.post("/api/tasks", json={"task_type": "analysis"})
    assert client.delete("/api/agents/agent-a").status_code == 204
    assert client.get("/api/agents").json() == []
    assert client.get("/api/status").json()["agents_registered"] == 0
    assert client.delete("/api/agents/agent-a").status_code == 404
    assert not client.post("/api/tasks", json={"task_type": "analysis"}).json()["succeeded"]
    assert len(client.get("/api/auctions").json()) == 2


def test_agents_and_reputation_survive_restart(tmp_path: Path) -> None:
    db = tmp_path / "persist.db"
    with TestClient(create_app(db, static_dir=None)) as c:
        c.post("/api/agents", json=AGENT)
        c.post("/api/tasks", json={"task_type": "analysis"})
    config = MarketConfig.model_validate({"auction": {"mechanism": "second_price_reverse"}})
    with TestClient(create_app(db, config=config, static_dir=None)) as c:
        assert c.get("/api/status").json()["agents_registered"] == 1
        assert c.get("/api/status").json()["mechanism"]["name"] == "second_price_reverse"
        assert c.get("/api/agents/agent-a/reputation").json()["overall"]["completed"] == 1


def test_serves_dashboard_files(tmp_path: Path) -> None:
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<html>dash</html>", encoding="utf-8")
    (static / "assets" / "app.js").write_text("js", encoding="utf-8")
    with TestClient(create_app(tmp_path / "s.db", static_dir=static)) as c:
        assert c.get("/").text == "<html>dash</html>"
        assert c.get("/auctions/abc").text == "<html>dash</html>"
        assert c.get("/assets/app.js").text == "js"
        assert c.get("/../../etc/passwd").text == "<html>dash</html>"
