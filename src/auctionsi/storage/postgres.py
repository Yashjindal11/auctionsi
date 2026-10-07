"""PostgreSQL persistence (``pip install "auctionsi[postgres]"``).

Same schema and behaviour as the SQLite store, so experiments and markets can move
between them. Pass a libpq connection string, e.g.
``PostgresStore("postgresql://user@localhost/auctionsi")``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from auctionsi.errors import OptionalDependencyError
from auctionsi.storage.sql import SQLStore

MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        """
        CREATE TABLE agents (
            agent_id TEXT PRIMARY KEY,
            profile TEXT NOT NULL,
            spec TEXT,
            registered_at DOUBLE PRECISION NOT NULL
        );
        CREATE TABLE tasks (
            task_id TEXT PRIMARY KEY,
            task_type TEXT NOT NULL,
            data TEXT NOT NULL,
            saved_at DOUBLE PRECISION NOT NULL DEFAULT 0
        );
        CREATE TABLE auctions (
            auction_id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            status TEXT NOT NULL,
            mechanism TEXT NOT NULL,
            parent_auction_id TEXT,
            record TEXT NOT NULL,
            saved_at DOUBLE PRECISION NOT NULL
        );
        CREATE INDEX auctions_task ON auctions(task_id);
        CREATE TABLE bids (
            bid_id TEXT PRIMARY KEY,
            auction_id TEXT NOT NULL REFERENCES auctions(auction_id) ON DELETE CASCADE,
            agent_id TEXT NOT NULL,
            price DOUBLE PRECISION NOT NULL,
            data TEXT NOT NULL
        );
        CREATE INDEX bids_auction ON bids(auction_id);
        CREATE INDEX bids_agent ON bids(agent_id);
        CREATE TABLE contracts (
            contract_id TEXT PRIMARY KEY,
            auction_id TEXT NOT NULL REFERENCES auctions(auction_id) ON DELETE CASCADE,
            agent_id TEXT NOT NULL,
            status TEXT NOT NULL,
            data TEXT NOT NULL
        );
        CREATE INDEX contracts_agent ON contracts(agent_id);
        CREATE TABLE settlements (
            contract_id TEXT PRIMARY KEY REFERENCES contracts(contract_id) ON DELETE CASCADE,
            agent_id TEXT NOT NULL,
            buyer_cost DOUBLE PRECISION NOT NULL,
            data TEXT NOT NULL
        );
        CREATE TABLE events (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            run_id TEXT NOT NULL,
            seq BIGINT NOT NULL,
            type TEXT NOT NULL,
            timestamp DOUBLE PRECISION NOT NULL,
            auction_id TEXT,
            task_id TEXT,
            agent_id TEXT,
            bid_id TEXT,
            contract_id TEXT,
            data TEXT NOT NULL
        );
        CREATE INDEX events_auction ON events(auction_id);
        CREATE TABLE observations (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
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
            saved_at DOUBLE PRECISION NOT NULL
        );
        """,
    ),
    # Version 2 exists for SQLite only; kept so both stores report the same schema version.
    (2, "SELECT 1;"),
]


def public_location(dsn: str) -> str:
    """``host:port/dbname`` for status output: never the user, password or options,
    whether the DSN is a URL or ``key=value`` pairs."""
    from psycopg.conninfo import conninfo_to_dict

    parts = conninfo_to_dict(dsn)
    host = str(parts.get("host") or "localhost")
    port = f":{parts['port']}" if parts.get("port") else ""
    return f"{host}{port}/{parts.get('dbname') or ''}"


class PostgresStore(SQLStore):
    migrations = MIGRATIONS

    def __init__(self, dsn: str, *, run_id: str = "default") -> None:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise OptionalDependencyError(
                'PostgreSQL support needs psycopg: pip install "auctionsi[postgres]"'
            ) from exc
        super().__init__()
        self.path = public_location(dsn)
        self.run_id = run_id
        self.conn = psycopg.connect(dsn, row_factory=dict_row)
        self.migrate()

    @staticmethod
    def _sql(sql: str) -> str:
        return sql.replace("?", "%s")

    def _execute(self, sql: str, params: Sequence[Any] = ()) -> Any:
        return self.conn.execute(self._sql(sql), tuple(params))

    def _rows(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        return [dict(r) for r in self._execute(sql, params).fetchall()]

    def _run_script(self, sql: str) -> None:
        for statement in (s.strip() for s in sql.split(";")):
            if statement:
                self.conn.execute(statement)

    def _commit_now(self) -> None:
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
