"""Dialect-neutral SQL persistence shared by the SQLite and PostgreSQL stores.

Everything is stored as plain columns plus JSON text; nothing is pickled, so a
database can never execute code when it is read. Queries are written with ``?``
placeholders and translated per dialect.
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any

from auctionsi.market.events import Event
from auctionsi.reputation.base import Observation

TABLES = (
    "agents",
    "tasks",
    "auctions",
    "bids",
    "contracts",
    "events",
    "observations",
    "experiments",
)


def _dumps(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), default=str)


class SQLStore(ABC):
    """Implements :class:`~auctionsi.storage.base.MarketStore` over a DB-API connection."""

    path: str
    run_id: str
    migrations: Sequence[tuple[int, str]]

    def __init__(self) -> None:
        self._batch_depth = 0

    # ---------------------------------------------------------------- dialect

    @abstractmethod
    def _execute(self, sql: str, params: Sequence[Any] = ()) -> Any: ...

    @abstractmethod
    def _rows(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]: ...

    @abstractmethod
    def _run_script(self, sql: str) -> None: ...

    @abstractmethod
    def _commit_now(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    def _one(self, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
        rows = self._rows(sql, params)
        return rows[0] if rows else None

    def _scalar(self, sql: str, params: Sequence[Any] = ()) -> Any:
        row = self._one(sql, params)
        return None if row is None else next(iter(row.values()))

    # ----------------------------------------------------------------- schema

    def schema_version(self) -> int:
        self._execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
        return int(self._scalar("SELECT MAX(version) AS v FROM schema_version") or 0)

    def migrate(self) -> int:
        current = self.schema_version()
        for version, sql in self.migrations:
            if version > current:
                self._run_script(sql)
                self._execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
                self._commit_now()
                current = version
        self._commit_now()
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
                self._commit_now()

    def _commit(self) -> None:
        if self._batch_depth == 0:
            self._commit_now()

    def __enter__(self) -> SQLStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ----------------------------------------------------------------- writes

    def record_event(self, event: Event) -> None:
        self._execute(
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
        self._execute(
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
        cur = self._execute("DELETE FROM agents WHERE agent_id = ?", (agent_id,))
        self._commit()
        return bool(cur.rowcount > 0)

    def save_task(self, task: Mapping[str, Any]) -> None:
        self._execute(
            "INSERT INTO tasks (task_id, task_type, data, saved_at) VALUES (?, ?, ?, ?)"
            " ON CONFLICT(task_id) DO UPDATE SET task_type = excluded.task_type,"
            " data = excluded.data",
            (task["task_id"], task["task_type"], _dumps(dict(task)), time.time()),
        )
        self._commit()

    def save_auction(self, record: Mapping[str, Any]) -> None:
        auction_id = record["auction_id"]
        self._execute(
            "INSERT INTO auctions (auction_id, task_id, status, mechanism, parent_auction_id,"
            " record, saved_at) VALUES (?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(auction_id) DO UPDATE SET status = excluded.status,"
            " record = excluded.record, saved_at = excluded.saved_at",
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
            self._execute(
                "INSERT INTO bids (bid_id, auction_id, agent_id, price, data) VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT(bid_id) DO NOTHING",
                (bid["bid_id"], auction_id, bid["agent_id"], bid["price"], _dumps(bid)),
            )
        for outcome in record.get("contracts", []):
            contract = outcome["contract"]
            settlement = outcome["settlement"]
            self._execute(
                "INSERT INTO contracts (contract_id, auction_id, agent_id, status, data)"
                " VALUES (?, ?, ?, ?, ?) ON CONFLICT(contract_id) DO UPDATE SET"
                " status = excluded.status, data = excluded.data",
                (
                    contract["contract_id"],
                    auction_id,
                    contract["agent_id"],
                    contract["status"],
                    _dumps(outcome),
                ),
            )
            self._execute(
                "INSERT INTO settlements (contract_id, agent_id, buyer_cost, data)"
                " VALUES (?, ?, ?, ?) ON CONFLICT(contract_id) DO UPDATE SET"
                " buyer_cost = excluded.buyer_cost, data = excluded.data",
                (
                    contract["contract_id"],
                    contract["agent_id"],
                    settlement["buyer_cost"],
                    _dumps(settlement),
                ),
            )
        self._commit()

    def save_observation(self, observation: Observation) -> None:
        self._execute(
            "INSERT INTO observations (agent_id, task_type, data) VALUES (?, ?, ?)",
            (observation.agent_id, observation.task_type, _dumps(observation.to_dict())),
        )
        self._commit()

    def save_experiment(
        self, experiment_id: str, name: str, manifest: Mapping[str, Any], results: Mapping[str, Any]
    ) -> None:
        self._execute(
            "INSERT INTO experiments (experiment_id, name, manifest, results, saved_at)"
            " VALUES (?, ?, ?, ?, ?) ON CONFLICT(experiment_id) DO UPDATE SET"
            " name = excluded.name, manifest = excluded.manifest, results = excluded.results,"
            " saved_at = excluded.saved_at",
            (experiment_id, name, _dumps(dict(manifest)), _dumps(dict(results)), time.time()),
        )
        self._commit()

    # ------------------------------------------------------------------ reads

    @staticmethod
    def _agent(row: Mapping[str, Any]) -> dict[str, Any]:
        return {
            **json.loads(row["profile"]),
            "spec": json.loads(row["spec"]) if row["spec"] else None,
        }

    def list_agents(self) -> list[dict[str, Any]]:
        return [
            self._agent(r) for r in self._rows("SELECT profile, spec FROM agents ORDER BY agent_id")
        ]

    def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        row = self._one("SELECT profile, spec FROM agents WHERE agent_id = ?", (agent_id,))
        return None if row is None else self._agent(row)

    def has_task(self, task_id: str) -> bool:
        return self._one("SELECT 1 AS found FROM tasks WHERE task_id = ?", (task_id,)) is not None

    def list_tasks(self, limit: int = 1000) -> list[dict[str, Any]]:
        rows = self._rows(
            "SELECT data FROM tasks ORDER BY saved_at DESC, task_id DESC LIMIT ?", (limit,)
        )
        return [json.loads(r["data"]) for r in rows]

    def list_auctions(
        self, *, status: str | None = None, limit: int = 1000
    ) -> list[dict[str, Any]]:
        sql = "SELECT auction_id, task_id, status, mechanism, parent_auction_id, saved_at FROM auctions"
        params: tuple[Any, ...] = ()
        if status is not None:
            sql += " WHERE status = ?"
            params = (status,)
        sql += " ORDER BY saved_at DESC, auction_id DESC LIMIT ?"
        return self._rows(sql, (*params, limit))

    def get_auction(self, auction_id: str) -> dict[str, Any] | None:
        row = self._one("SELECT record FROM auctions WHERE auction_id = ?", (auction_id,))
        return None if row is None else dict(json.loads(row["record"]))

    def agent_bids(self, agent_id: str, limit: int = 200) -> list[dict[str, Any]]:
        return self._rows(
            "SELECT b.auction_id AS auction_id, b.price AS price FROM bids b"
            " JOIN auctions a ON a.auction_id = b.auction_id WHERE b.agent_id = ?"
            " ORDER BY a.saved_at DESC, b.bid_id DESC LIMIT ?",
            (agent_id, limit),
        )

    def fulfilled_contracts(self, agent_id: str) -> int:
        return int(
            self._scalar(
                "SELECT COUNT(*) AS n FROM contracts WHERE agent_id = ? AND status = 'fulfilled'",
                (agent_id,),
            )
            or 0
        )

    def events(self, auction_id: str | None = None) -> list[Event]:
        if auction_id is None:
            rows = self._rows("SELECT * FROM events ORDER BY id")
        else:
            rows = self._rows(
                "SELECT * FROM events WHERE auction_id = ? ORDER BY id", (auction_id,)
            )
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
            rows = self._rows("SELECT data FROM observations ORDER BY id")
        else:
            rows = self._rows(
                "SELECT data FROM observations WHERE agent_id = ? ORDER BY id", (agent_id,)
            )
        return [Observation.from_dict(json.loads(r["data"])) for r in rows]

    def list_experiments(self) -> list[dict[str, Any]]:
        return self._rows(
            "SELECT experiment_id, name, saved_at FROM experiments ORDER BY saved_at DESC"
        )

    def status(self) -> dict[str, Any]:
        counts = {
            table: int(self._scalar(f"SELECT COUNT(*) AS n FROM {table}") or 0)  # noqa: S608 - fixed table names
            for table in TABLES
        }
        by_status = {
            r["status"]: int(r["n"])
            for r in self._rows("SELECT status, COUNT(*) AS n FROM auctions GROUP BY status")
        }
        spend = self._scalar("SELECT COALESCE(SUM(buyer_cost), 0) AS total FROM settlements")
        return {
            "path": self.path,
            "schema_version": self.schema_version(),
            "counts": counts,
            "auctions_by_status": by_status,
            "total_buyer_cost": float(spend or 0),
        }
