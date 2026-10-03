"""Structured JSON logging and counters, both driven by the event bus."""

from __future__ import annotations

import json
import sys
from collections import Counter
from typing import Any, TextIO

from auctionsi.market.events import Event, EventBus, EventType

E = EventType

_STATUS = {
    E.AUCTION_SETTLED: "settled",
    E.AUCTION_FAILED: "failed",
    E.AUCTION_CANCELLED: "cancelled",
    E.NO_BIDS: "no_bids",
    E.VERIFICATION_PASSED: "passed",
    E.VERIFICATION_FAILED: "failed",
}


class JsonEventLogger:
    """Writes one JSON object per event.

    Only a fixed set of fields is logged (timestamp, event, ids, status, latency,
    price). Event payloads are excluded unless ``include_data=True``; AuctionSI never
    puts credentials into events, and this keeps task inputs out of logs by default.
    """

    def __init__(self, stream: TextIO | None = None, *, include_data: bool = False) -> None:
        self.stream = stream or sys.stderr
        self.include_data = include_data

    def record(self, event: Event) -> dict[str, Any]:
        d = event.data
        row: dict[str, Any] = {
            "timestamp": event.timestamp,
            "seq": event.seq,
            "event": event.type.value,
            "task_id": event.task_id,
            "auction_id": event.auction_id,
            "agent_id": event.agent_id,
            "bid_id": event.bid_id,
            "contract_id": event.contract_id,
        }
        if event.type in _STATUS:
            row["status"] = _STATUS[event.type]
        if "latency" in d:
            row["latency"] = d["latency"]
        if isinstance(d.get("bid"), dict):
            row["price"] = d["bid"].get("price")
        if self.include_data:
            row["data"] = dict(d)
        return {k: v for k, v in row.items() if v is not None}

    def __call__(self, event: Event) -> None:
        self.stream.write(json.dumps(self.record(event), default=str) + "\n")

    def attach(self, bus: EventBus) -> None:
        bus.subscribe(self)


class MarketCounters:
    """Running counters for dashboards and health checks."""

    def __init__(self) -> None:
        self.counts: Counter[EventType] = Counter()
        self._opened: dict[str, float] = {}
        self._durations: list[float] = []
        self._bids_per_auction: Counter[str] = Counter()

    def __call__(self, event: Event) -> None:
        self.counts[event.type] += 1
        if event.type == E.AUCTION_OPENED and event.auction_id:
            self._opened[event.auction_id] = event.timestamp
        if event.type in (E.BID_SUBMITTED, E.BID_REVISED) and event.auction_id:
            self._bids_per_auction[event.auction_id] += 1
        if event.type == E.AUCTION_CLOSED and event.auction_id in self._opened:
            self._durations.append(event.timestamp - self._opened.pop(event.auction_id))

    def attach(self, bus: EventBus) -> None:
        bus.subscribe(self)

    def snapshot(self) -> dict[str, float]:
        c = self.counts
        verifications = c[E.VERIFICATION_PASSED] + c[E.VERIFICATION_FAILED]
        closed = c[E.AUCTION_CLOSED]
        return {
            "auctions_created": c[E.AUCTION_CREATED],
            "auctions_completed": c[E.AUCTION_SETTLED],
            "auctions_failed": c[E.AUCTION_FAILED] + c[E.NO_BIDS],
            "auctions_cancelled": c[E.AUCTION_CANCELLED],
            "bids_submitted": c[E.BID_SUBMITTED] + c[E.BID_REVISED],
            "bids_rejected": c[E.BID_REJECTED],
            "tasks_completed": c[E.TASK_COMPLETED],
            "tasks_failed": c[E.TASK_FAILED],
            "average_auction_duration": (
                sum(self._durations) / len(self._durations) if self._durations else 0.0
            ),
            "average_bid_count": (sum(self._bids_per_auction.values()) / closed if closed else 0.0),
            "verification_failure_rate": (
                c[E.VERIFICATION_FAILED] / verifications if verifications else 0.0
            ),
        }
