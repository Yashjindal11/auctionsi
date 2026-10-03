"""Immutable, timestamped marketplace events and an in-process event bus.

Events are plain records (type + ids + JSON data) rather than one class per event
so they serialise uniformly, persist to any store and can later back full event
sourcing. ``seq`` gives a total order within one marketplace.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

logger = logging.getLogger("auctionsi.events")


class EventType(StrEnum):
    AGENT_REGISTERED = "AgentRegistered"
    AGENT_UNREGISTERED = "AgentUnregistered"
    AGENT_UPDATED = "AgentUpdated"
    TASK_CREATED = "TaskCreated"
    AUCTION_CREATED = "AuctionCreated"
    AGENTS_DISCOVERED = "AgentsDiscovered"
    TASK_ANNOUNCED = "TaskAnnounced"
    AUCTION_OPENED = "AuctionOpened"
    BID_SUBMITTED = "BidSubmitted"
    BID_REVISED = "BidRevised"
    BID_REJECTED = "BidRejected"
    AUCTION_CLOSED = "AuctionClosed"
    NO_BIDS = "NoBids"
    WINNER_SELECTED = "WinnerSelected"
    CONTRACT_CREATED = "ContractCreated"
    TASK_STARTED = "TaskStarted"
    TASK_COMPLETED = "TaskCompleted"
    TASK_FAILED = "TaskFailed"
    VERIFICATION_PASSED = "VerificationPassed"
    VERIFICATION_FAILED = "VerificationFailed"
    SETTLEMENT_COMPLETED = "SettlementCompleted"
    REPUTATION_UPDATED = "ReputationUpdated"
    RECOVERY_STARTED = "RecoveryStarted"
    AUCTION_SETTLED = "AuctionSettled"
    AUCTION_FAILED = "AuctionFailed"
    AUCTION_CANCELLED = "AuctionCancelled"


@dataclass(frozen=True, slots=True)
class Event:
    seq: int
    type: EventType
    timestamp: float
    auction_id: str | None = None
    task_id: str | None = None
    agent_id: str | None = None
    bid_id: str | None = None
    contract_id: str | None = None
    data: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "type": self.type.value,
            "timestamp": self.timestamp,
            "auction_id": self.auction_id,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "bid_id": self.bid_id,
            "contract_id": self.contract_id,
            "data": dict(self.data),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Event:
        values = dict(data)
        values["type"] = EventType(values["type"])
        return cls(**values)


Handler = Callable[[Event], None]


class EventBus:
    """Synchronous publish/subscribe.

    A failing subscriber must not corrupt an auction in progress, so handler
    exceptions are logged and counted in :attr:`handler_errors` rather than
    re-raised, unless ``strict=True`` (useful in tests).
    """

    def __init__(self, *, strict: bool = False) -> None:
        self.strict = strict
        self.handler_errors = 0
        self._seq = 0
        self._handlers: list[tuple[frozenset[EventType] | None, Handler]] = []

    def subscribe(
        self, handler: Handler, types: Iterable[EventType] | None = None
    ) -> Callable[[], None]:
        entry = (frozenset(types) if types is not None else None, handler)
        self._handlers.append(entry)

        def unsubscribe() -> None:
            if entry in self._handlers:
                self._handlers.remove(entry)

        return unsubscribe

    def publish(
        self,
        type: EventType,
        timestamp: float,
        *,
        auction_id: str | None = None,
        task_id: str | None = None,
        agent_id: str | None = None,
        bid_id: str | None = None,
        contract_id: str | None = None,
        data: Mapping[str, Any] | None = None,
    ) -> Event:
        self._seq += 1
        event = Event(
            seq=self._seq,
            type=type,
            timestamp=timestamp,
            auction_id=auction_id,
            task_id=task_id,
            agent_id=agent_id,
            bid_id=bid_id,
            contract_id=contract_id,
            data=dict(data or {}),
        )
        for types, handler in list(self._handlers):
            if types is not None and event.type not in types:
                continue
            try:
                handler(event)
            except Exception:
                if self.strict:
                    raise
                self.handler_errors += 1
                logger.exception("event handler failed for %s", event.type)
        return event


class EventLog:
    """Keeps events in memory, optionally bounded to the most recent ``max_events``."""

    def __init__(self, max_events: int | None = None) -> None:
        self.max_events = max_events
        self.events: list[Event] = []

    def __call__(self, event: Event) -> None:
        self.events.append(event)
        if self.max_events is not None and len(self.events) > self.max_events:
            del self.events[: len(self.events) - self.max_events]

    def for_auction(self, auction_id: str) -> list[Event]:
        return [e for e in self.events if e.auction_id == auction_id]

    def of_type(self, type: EventType) -> list[Event]:
        return [e for e in self.events if e.type == type]
