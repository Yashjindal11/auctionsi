"""SQLite persistence with versioned migrations.

Everything is stored as plain columns plus JSON text; nothing is pickled, so a
database file can never execute code when it is read.
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from auctionsi.market.events import Event
from auctionsi.reputation.base import Observation

MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        """
        CREATE TABLE agents (
            agent_id TEXT PRIMARY KEY,
            profile TEXT NOT NULL,
            spec TEXT,
            registered_at REAL NOT NULL
        );
        CREATE TABLE tasks (
            task_id TEXT PRIMARY KEY,
            task_type TEXT NOT NULL,
            data TEXT NOT NULL
        );
        CREATE TABLE auctions (
            auction_id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            status TEXT NOT NULL,
            mechanism TEXT NOT NULL,
            parent_auction_id TEXT,
            record TEXT NOT NULL,
            saved_at REAL NOT NULL
        );
        CREATE INDEX auctions_task ON auctions(task_id);
        CREATE TABLE bids (
            bid_id TEXT PRIMARY KEY,
            auction_id TEXT NOT NULL REFERENCES auctions(auction_id) ON DELETE CASCADE,
            agent_id TEXT NOT NULL,
            price REAL NOT NULL,
            data TEXT NOT NULL
        );
        CREATE INDEX bids_auction ON bids(auction_id);
        CREATE TABLE contracts (
            contract_id TEXT PRIMARY KEY,
            auction_id TEXT NOT NULL REFERENCES auctions(auction_id) ON DELETE CASCADE,
            agent_id TEXT NOT NULL,
            status TEXT NOT NULL,
            data TEXT NOT NULL
        );
        CREATE TABLE settlements (
            contract_id TEXT PRIMARY KEY REFERENCES contracts(contract_id) ON DELETE CASCADE,
            agent_id TEXT NOT NULL,
            buyer_cost REAL NOT NULL,
            data TEXT NOT NULL
        );
        CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            seq INTEGER NOT NULL,
            type TEXT NOT NULL,
            timestamp REAL NOT NULL,
            auction_id TEXT,
            task_id TEXT,
            agent_id TEXT,
            bid_id TEXT,
            contract_id TEXT,
            data TEXT NOT NULL
        );
        CREATE INDEX events_auction ON events(auction_id);
        CREATE TABLE observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            task_type TEXT NOT NULL,
            data TEXT NOT NULL
        );
        CREATE INDEX observations_agent ON observations(agent_id);
        CREATE TABLE experiments (
            experiment_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            manifest TEXT NOT NULL,
            results TEXT NOT NULL,
            saved_at REAL NOT NULL
        );
        """,
    ),
]


def _dumps(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), default=str)


class SQLiteStore:
    """Implements :class:`~auctionsi.storage.base.MarketStore` on SQLite.

    ``check_same_thread=False`` allows use from a server's worker threads; callers
    must then serialise access themselves (the API does so with a lock).
    """

    def __init__(
        self,
        path: str | Path = ":memory:",
        *,
        run_id: str = "default",
        check_same_thread: bool = True,
    ) -> None:
        self.path = str(path)
        self.run_id = run_id
        self.conn = sqlite3.connect(self.path, check_same_thread=check_same_thread)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        if self.path != ":memory:":
            self.conn.execute("PRAGMA journal_mode = WAL")
        self._batch_depth = 0
        self.migrate()

    # ----------------------------------------------------------------- schema

    def schema_version(self) -> int:
        self.conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
        row = self.conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
        return int(row["v"] or 0)

    def migrate(self) -> int:
        current = self.schema_version()
        for version, sql in MIGRATIONS:
            if version > current:
                with self.conn:
                    self.conn.executescript(sql)
                    self.conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
                current = version
        return current

    @contextmanager
    def batch(self) -> Iterator[None]:
        """Group many writes into one transaction (much faster for simulations)."""
        self._batch_depth += 1
        try:
            yield
        finally:
            self._batch_depth -= 1
            if self._batch_depth == 0:
                self.conn.commit()

    def _commit(self) -> None:
        if self._batch_depth == 0:
            self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> SQLiteStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ----------------------------------------------------------------- writes

    def record_event(self, event: Event) -> None:
        self.conn.execute(
            "INSERT INTO events (run_id, seq, type, timestamp, auction_id, task_id, agent_id,"
            " bid_id, contract_id, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                self.run_id,
                event.seq,
                event.type.value,
                event.timestamp,
                event.auction_id,
                event.task_id,
                event.agent_id,
                event.bid_id,
                event.contract_id,
                _dumps(dict(event.data)),
            ),
        )
        self._commit()

    def save_agent(self, profile: Mapping[str, Any], spec: Mapping[str, Any] | None = None) -> None:
        self.conn.execute(
            "INSERT INTO agents (agent_id, profile, spec, registered_at) VALUES (?, ?, ?, ?)"
            " ON CONFLICT(agent_id) DO UPDATE SET profile = excluded.profile,"
            " spec = COALESCE(excluded.spec, agents.spec)",
            (
                profile["agent_id"],
                _dumps(dict(profile)),
                None if spec is None else _dumps(dict(spec)),
                time.time(),
            ),
        )
        self._commit()

    def delete_agent(self, agent_id: str) -> bool:
        cur = self.conn.execute("DELETE FROM agents WHERE agent_id = ?", (agent_id,))
        self._commit()
        return cur.rowcount > 0

    def save_task(self, task: Mapping[str, Any]) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO tasks (task_id, task_type, data) VALUES (?, ?, ?)",
            (task["task_id"], task["task_type"], _dumps(dict(task))),
        )
        self._commit()

    def save_auction(self, record: Mapping[str, Any]) -> None:
        auction_id = record["auction_id"]
        self.conn.execute(
            "INSERT OR REPLACE INTO auctions (auction_id, task_id, status, mechanism,"
            " parent_auction_id, record, saved_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                auction_id,
                record["task"]["task_id"],
                record["status"],
                record["mechanism"],
                record.get("parent_auction_id"),
                _dumps(dict(record)),
                time.time(),
            ),
        )
        for bid in record.get("bids", []):
            self.conn.execute(
                "INSERT OR REPLACE INTO bids (bid_id, auction_id, agent_id, price, data)"
                " VALUES (?, ?, ?, ?, ?)",
                (bid["bid_id"], auction_id, bid["agent_id"], bid["price"], _dumps(bid)),
            )
        for outcome in record.get("contracts", []):
            contract = outcome["contract"]
            settlement = outcome["settlement"]
            self.conn.execute(
                "INSERT OR REPLACE INTO contracts (contract_id, auction_id, agent_id, status, data)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    contract["contract_id"],
                    auction_id,
                    contract["agent_id"],
                    contract["status"],
                    _dumps(outcome),
                ),
            )
            self.conn.execute(
                "INSERT OR REPLACE INTO settlements (contract_id, agent_id, buyer_cost, data)"
                " VALUES (?, ?, ?, ?)",
                (
                    contract["contract_id"],
                    contract["agent_id"],
                    settlement["buyer_cost"],
                    _dumps(settlement),
                ),
            )
        self._commit()

    def save_observation(self, observation: Observation) -> None:
        self.conn.execute(
            "INSERT INTO observations (agent_id, task_type, data) VALUES (?, ?, ?)",
            (observation.agent_id, observation.task_type, _dumps(observation.to_dict())),
        )
        self._commit()

    def save_experiment(
        self, experiment_id: str, name: str, manifest: Mapping[str, Any], results: Mapping[str, Any]
    ) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO experiments (experiment_id, name, manifest, results, saved_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (experiment_id, name, _dumps(dict(manifest)), _dumps(dict(results)), time.time()),
        )
        self._commit()

    # ------------------------------------------------------------------ reads

    def list_agents(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT profile, spec FROM agents ORDER BY agent_id").fetchall()
        return [
            {**json.loads(r["profile"]), "spec": json.loads(r["spec"]) if r["spec"] else None}
            for r in rows
        ]

    def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT profile, spec FROM agents WHERE agent_id = ?", (agent_id,)
        ).fetchone()
        if row is None:
            return None
        return {
            **json.loads(row["profile"]),
            "spec": json.loads(row["spec"]) if row["spec"] else None,
        }

    def has_task(self, task_id: str) -> bool:
        row = self.conn.execute("SELECT 1 FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        return row is not None

    def list_tasks(self, limit: int = 1000) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT data FROM tasks ORDER BY rowid DESC LIMIT ?", (limit,)
        ).fetchall()
        return [json.loads(r["data"]) for r in rows]

    def list_auctions(
        self, *, status: str | None = None, limit: int = 1000
    ) -> list[dict[str, Any]]:
        sql = (
            "SELECT auction_id, task_id, status, mechanism, parent_auction_id, saved_at"
            " FROM auctions"
        )
        params: tuple[Any, ...] = ()
        if status is not None:
            sql += " WHERE status = ?"
            params = (status,)
        sql += " ORDER BY saved_at DESC, auction_id DESC LIMIT ?"
        rows = self.conn.execute(sql, (*params, limit)).fetchall()
        return [dict(r) for r in rows]

    def get_auction(self, auction_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT record FROM auctions WHERE auction_id = ?", (auction_id,)
        ).fetchone()
        return None if row is None else dict(json.loads(row["record"]))

    def events(self, auction_id: str | None = None) -> list[Event]:
        if auction_id is None:
            rows = self.conn.execute("SELECT * FROM events ORDER BY id").fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM events WHERE auction_id = ? ORDER BY id", (auction_id,)
            ).fetchall()
        return [
            Event.from_dict(
                {
                    "seq": r["seq"],
                    "type": r["type"],
                    "timestamp": r["timestamp"],
                    "auction_id": r["auction_id"],
                    "task_id": r["task_id"],
                    "agent_id": r["agent_id"],
                    "bid_id": r["bid_id"],
                    "contract_id": r["contract_id"],
                    "data": json.loads(r["data"]),
                }
            )
            for r in rows
        ]

    def observations(self, agent_id: str | None = None) -> list[Observation]:
        if agent_id is None:
            rows = self.conn.execute("SELECT data FROM observations ORDER BY id").fetchall()
        else:
            rows = self.conn.execute(
                "SELECT data FROM observations WHERE agent_id = ? ORDER BY id", (agent_id,)
            ).fetchall()
        return [Observation.from_dict(json.loads(r["data"])) for r in rows]

    def list_experiments(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT experiment_id, name, saved_at FROM experiments ORDER BY saved_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def status(self) -> dict[str, Any]:
        counts = {
            table: self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608 - fixed table names
            for table in (
                "agents",
                "tasks",
                "auctions",
                "bids",
                "contracts",
                "events",
                "observations",
                "experiments",
            )
        }
        by_status = {
            r["status"]: r["n"]
            for r in self.conn.execute(
                "SELECT status, COUNT(*) AS n FROM auctions GROUP BY status"
            ).fetchall()
        }
        spend = self.conn.execute(
            "SELECT COALESCE(SUM(buyer_cost), 0) FROM settlements"
        ).fetchone()[0]
        return {
            "path": self.path,
            "schema_version": self.schema_version(),
            "counts": counts,
            "auctions_by_status": by_status,
            "total_buyer_cost": spend,
        }
