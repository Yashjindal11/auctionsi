from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from auctionsi.errors import NotFoundError
from auctionsi.market import EventType
from auctionsi.market.events import Event
from auctionsi.market.replay import replay_auction
from auctionsi.mechanisms import SecondPriceReverseAuction
from auctionsi.selection import CallablePolicy, WeightedScore
from auctionsi.simulation import simulate_market
from auctionsi.storage import InMemoryStore, SQLiteStore
from auctionsi.storage.sqlite import MIGRATIONS
from conftest import MarketFactory, ScriptedAgent, task


def populated(market_factory: MarketFactory, store: object, **kwargs: object) -> object:
    market = market_factory(store=store, **kwargs)
    market.register(ScriptedAgent("A", 0.05), spec={"kind": "scripted"})
    market.register(ScriptedAgent("B", 0.07))
    market.register(ScriptedAgent("C", 0.03, fail=True))
    return market


@pytest.mark.integration
def test_sqlite_round_trip(tmp_path: Path, market_factory: MarketFactory) -> None:
    path = tmp_path / "market.db"
    store = SQLiteStore(path, run_id="r1")
    market = populated(market_factory, store)
    result = market.submit_task(task(budget=0.10))  # type: ignore[attr-defined]
    market.clock.set(5.0)  # type: ignore[attr-defined]  # C is busy until its failed run ends
    market.submit_task(task("task-002", budget=0.10))  # type: ignore[attr-defined]
    store.close()

    reopened = SQLiteStore(path)
    assert reopened.schema_version() == MIGRATIONS[-1][0]
    agents = reopened.list_agents()
    assert [a["agent_id"] for a in agents] == ["A", "B", "C"]
    assert reopened.get_agent("A")["spec"] == {"kind": "scripted"}  # type: ignore[index]
    assert reopened.get_agent("missing") is None
    assert {t["task_id"] for t in reopened.list_tasks()} == {"task-001", "task-002"}
    record = reopened.get_auction(result.auction_id)
    assert record is not None
    assert record["status"] == "failed"
    assert len(record["bids"]) == 3
    events = reopened.events(result.auction_id)
    assert events[0].type == EventType.AUCTION_CREATED
    assert [e.seq for e in events] == sorted(e.seq for e in events)
    assert len(reopened.observations("C")) == 2
    status = reopened.status()
    assert status["counts"]["auctions"] == 2
    assert status["auctions_by_status"] == {"failed": 2}
    assert reopened.list_auctions(status="failed")[0]["status"] == "failed"
    reopened.save_experiment("exp-1", "demo", {"seed": 1}, {"runs": []})
    assert reopened.list_experiments()[0]["name"] == "demo"
    assert reopened.delete_agent("A")
    reopened.close()


def test_migrations_are_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "m.db"
    SQLiteStore(path).close()
    with SQLiteStore(path) as again:
        assert again.migrate() == MIGRATIONS[-1][0]


def test_batch_commits_once(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "b.db")
    with store.batch():
        store.save_task({"task_id": "x", "task_type": "y"})
        assert store.conn.in_transaction
    assert not store.conn.in_transaction


@pytest.mark.integration
def test_replay_reproduces_recorded_decisions(market_factory: MarketFactory) -> None:
    store = SQLiteStore()
    market = populated(
        market_factory,
        store,
        mechanism=SecondPriceReverseAuction(),
        policy=WeightedScore(reputation_weight=0.3),
    )
    first = market.submit_task(task("t1", budget=0.10))  # type: ignore[attr-defined]
    second = market.submit_task(task("t2", budget=0.10))  # type: ignore[attr-defined]
    for result in (first, second):
        report = replay_auction(store.events(result.auction_id))
        assert report.replayable
        assert report.matches, report.differences
        assert report.recorded_awards == report.replayed_awards
        assert "reproduced exactly" in report.to_text()


def test_replay_detects_tampering(market_factory: MarketFactory) -> None:
    store = InMemoryStore()
    market = populated(market_factory, store)
    result = market.submit_task(task(budget=0.10))  # type: ignore[attr-defined]
    events = store.events(result.auction_id)
    tampered: list[Event] = []
    for e in events:
        if e.type == EventType.AUCTION_CLOSED:
            bids = [dict(b) for b in e.data["final_bids"]]
            for b in bids:
                if b["agent_id"] == "B":
                    b["price"] = 0.001
            e = replace(e, data={**e.data, "final_bids": bids})
        tampered.append(e)
    report = replay_auction(tampered)
    assert not report.matches
    assert any("winner" in d or "ranking" in d for d in report.differences)
    assert "MISMATCH" in report.to_text()


def test_replay_edge_cases(market_factory: MarketFactory) -> None:
    with pytest.raises(NotFoundError):
        replay_auction([])
    store = InMemoryStore()
    market = market_factory(store=store)
    market.register(ScriptedAgent("silent", None))
    empty = market.submit_task(task())
    report = replay_auction(store.events(empty.auction_id))
    assert report.matches
    assert "nothing to re-derive" in report.notes[0]

    custom = market_factory(
        store=(s2 := InMemoryStore()),
        policy=CallablePolicy("mine", lambda b, t, f: (-b.price, {"price": -b.price})),
    )
    custom.register(ScriptedAgent("a", 1.0))
    r = custom.submit_task(task())
    assert not replay_auction(s2.events(r.auction_id)).replayable


def _edit(events: list[Event], kind: EventType, change: dict[str, object]) -> list[Event]:
    return [replace(e, data={**e.data, **change}) if e.type == kind else e for e in events]


def test_replay_reports_open_and_unrebuildable_auctions(market_factory: MarketFactory) -> None:
    store = InMemoryStore()
    market = populated(market_factory, store)
    opened = market.open_auction(task("open"))  # type: ignore[attr-defined]
    report = replay_auction(store.events(opened.auction_id))
    assert not report.replayable
    assert report.notes == ["auction never closed"]
    assert "Decision not replayable: auction never closed" in report.to_text()

    with pytest.raises(NotFoundError):
        replay_auction(
            [e for e in store.events(opened.auction_id) if e.type != EventType.AUCTION_CREATED]
        )

    done = market.submit_task(task("done", budget=0.10))  # type: ignore[attr-defined]
    events = store.events(done.auction_id)
    unknown = _edit(events, EventType.WINNER_SELECTED, {"mechanism": {"name": "no_such_mechanism"}})
    report = replay_auction(unknown)
    assert not report.replayable
    assert report.notes[0].startswith("cannot rebuild plugins")


def test_replay_detects_award_and_payment_changes(market_factory: MarketFactory) -> None:
    store = InMemoryStore()
    market = populated(market_factory, store)
    result = market.submit_task(task(budget=0.10))  # type: ignore[attr-defined]
    events = store.events(result.auction_id)
    selected = next(e for e in events if e.type == EventType.WINNER_SELECTED)
    outcome = selected.data["outcome"]

    paid_more = {
        **outcome,
        "awards": [{**a, "payment": a["payment"] + 1} for a in outcome["awards"]],
    }
    report = replay_auction(_edit(events, EventType.WINNER_SELECTED, {"outcome": paid_more}))
    assert any(d.startswith("payment to") for d in report.differences)

    extra = {**outcome, "awards": [*outcome["awards"], outcome["awards"][0]]}
    report = replay_auction(_edit(events, EventType.WINNER_SELECTED, {"outcome": extra}))
    assert "different number of awards" in report.differences

    without_selection = [e for e in events if e.type != EventType.WINNER_SELECTED]
    report = replay_auction(without_selection)
    assert report.differences == ["valid bids existed but no WinnerSelected event"]
    assert not report.matches


def test_simulation_can_persist(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "sim.db")
    from auctionsi.market import Marketplace
    from auctionsi.simulation import generate_agents, generate_tasks

    market = Marketplace(store=store)
    for agent in generate_agents(5, seed=1):
        market.register(agent)
    with store.batch():
        for t in generate_tasks(10, seed=1):
            market.submit_task(t)
    assert store.status()["counts"]["auctions"] >= 10
    assert simulate_market(3, 5).metrics.total_tasks == 5
