"""Repository interface. Backends (in-memory, SQLite, later PostgreSQL) implement it
without the marketplace knowing which one is in use."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from auctionsi.market.events import Event
from auctionsi.reputation.base import Observation


@runtime_checkable
class MarketStore(Protocol):
    def record_event(self, event: Event) -> None: ...

    def save_agent(
        self, profile: Mapping[str, Any], spec: Mapping[str, Any] | None = None
    ) -> None: ...

    def save_task(self, task: Mapping[str, Any]) -> None: ...

    def save_auction(self, record: Mapping[str, Any]) -> None: ...

    def save_observation(self, observation: Observation) -> None: ...
