"""The same behavioural checks against every available SQL backend.

PostgreSQL runs only when ``AUCTIONSI_TEST_POSTGRES`` holds a connection URL to a
disposable database (CI provides one); its tables are dropped first.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from auctionsi.market import ManualClock, Marketplace
from auctionsi.market.replay import replay_auction
from auctionsi.storage import SQLStore, open_store
from auctionsi.storage.sql import TABLES
from conftest import ScriptedAgent, task

PG_URL = os.environ.get("AUCTIONSI_TEST_POSTGRES")
BACKENDS = [
    "sqlite",
    pytest.param("postgres", marks=pytest.mark.skipif(not PG_URL, reason="no test postgres")),
]


@pytest.fixture(params=BACKENDS)
def store(request: pytest.FixtureRequest, tmp_path: object) -> Iterator[SQLStore]:
    if request.param == "postgres":
        assert PG_URL is not None
        import psycopg

        with psycopg.connect(PG_URL, autocommit=True) as conn:
            for table in (*TABLES, "settlements", "schema_version"):
                conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        s = open_store(PG_URL, run_id="test")
    else:
        s = open_store(":memory:", run_id="test")
    yield s
    s.close()


def test_backend_round_trip(store: SQLStore) -> None:
    assert store.schema_version() == 2
    market = Marketplace(clock=ManualClock(), store=store)
    market.register(ScriptedAgent("a", 0.05), spec={"kind": "x"})
    market.register(ScriptedAgent("b", 0.03, fail=True))
    first = market.submit_task(task("t1", budget=0.1))
    market.clock.set(10)  # type: ignore[attr-defined]
    market.submit_task(task("t2", budget=0.1))
    store.save_experiment("e1", "demo", {"seed": 1}, {"runs": []})

    assert [a["agent_id"] for a in store.list_agents()] == ["a", "b"]
    assert store.get_agent("a")["spec"] == {"kind": "x"}  # type: ignore[index]
    assert store.has_task("t1") and not store.has_task("zzz")
    assert {t["task_id"] for t in store.list_tasks()} == {"t1", "t2"}
    assert store.get_auction(first.auction_id)["status"] == "failed"  # type: ignore[index]
    assert len(store.list_auctions(status="failed")) == 2
    assert len(store.agent_bids("a")) == 2
    assert store.fulfilled_contracts("b") == 0
    assert len(store.observations("b")) == 2
    assert replay_auction(store.events(first.auction_id)).matches
    status = store.status()
    assert status["counts"]["auctions"] == 2
    assert status["counts"]["experiments"] == 1
    assert store.list_experiments()[0]["name"] == "demo"
    assert store.delete_agent("a")


def test_postgres_status_hides_credentials() -> None:
    if not PG_URL:
        pytest.skip("no test postgres")
    s = open_store(PG_URL)
    assert "@" not in s.status()["path"] and "password" not in s.status()["path"]
    s.close()
