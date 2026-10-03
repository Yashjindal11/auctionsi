"""Persistence backends."""

from auctionsi.storage.base import MarketStore
from auctionsi.storage.memory import InMemoryStore
from auctionsi.storage.sql import SQLStore
from auctionsi.storage.sqlite import SQLiteStore

__all__ = ["InMemoryStore", "MarketStore", "SQLStore", "SQLiteStore", "open_store"]


def open_store(url: str, *, run_id: str = "default") -> SQLStore:
    """``postgresql://...`` opens a PostgresStore; anything else is a SQLite path."""
    if url.startswith(("postgresql://", "postgres://")):
        from auctionsi.storage.postgres import PostgresStore

        return PostgresStore(url, run_id=run_id)
    return SQLiteStore(url, run_id=run_id)
