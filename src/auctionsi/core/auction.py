"""The auction record and its lifecycle state machine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from auctionsi.errors import InvalidTransitionError

if TYPE_CHECKING:
    from auctionsi.core.bid import Bid, BidRejection
    from auctionsi.core.contract import Contract
    from auctionsi.core.task import Task


class AuctionStatus(StrEnum):
    CREATED = "created"
    ANNOUNCED = "announced"
    OPEN = "open"
    BID_COLLECTION = "bid_collection"
    CLOSED = "closed"
    EVALUATION = "evaluation"
    AWARDED = "awarded"
    CONTRACTED = "contracted"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    SETTLED = "settled"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    NO_BIDS = "no_bids"


S = AuctionStatus

#: Allowed transitions. Recovery loops back from VERIFYING to EXECUTING (retry the
#: same agent, or the next contract of a multi-winner auction) or to AWARDED
#: (fail over to a backup bid). Re-opening creates a *new* auction instead.
TRANSITIONS: dict[AuctionStatus, frozenset[AuctionStatus]] = {
    S.CREATED: frozenset({S.ANNOUNCED, S.CANCELLED}),
    S.ANNOUNCED: frozenset({S.OPEN, S.CANCELLED}),
    S.OPEN: frozenset({S.BID_COLLECTION, S.CANCELLED, S.EXPIRED}),
    S.BID_COLLECTION: frozenset({S.CLOSED, S.CANCELLED, S.EXPIRED}),
    S.CLOSED: frozenset({S.EVALUATION, S.NO_BIDS, S.CANCELLED}),
    S.EVALUATION: frozenset({S.AWARDED, S.NO_BIDS, S.FAILED, S.CANCELLED}),
    S.AWARDED: frozenset({S.CONTRACTED, S.CANCELLED}),
    S.CONTRACTED: frozenset({S.EXECUTING, S.CANCELLED}),
    S.EXECUTING: frozenset({S.VERIFYING, S.FAILED}),
    S.VERIFYING: frozenset({S.SETTLED, S.FAILED, S.EXECUTING, S.AWARDED}),
    S.SETTLED: frozenset(),
    S.FAILED: frozenset(),
    S.CANCELLED: frozenset(),
    S.EXPIRED: frozenset(),
    S.NO_BIDS: frozenset(),
}

TERMINAL: frozenset[AuctionStatus] = frozenset(s for s, nxt in TRANSITIONS.items() if not nxt)


@dataclass(frozen=True, slots=True)
class RejectedBid:
    agent_id: str
    proposal: dict[str, Any] | None
    reasons: tuple[BidRejection, ...]
    timestamp: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "proposal": self.proposal,
            "reasons": [r.to_dict() for r in self.reasons],
            "timestamp": self.timestamp,
        }


@dataclass(slots=True)
class Auction:
    """Mutable record of one auction. Status changes only through :meth:`transition`."""

    auction_id: str
    task: Task
    mechanism: str
    created_at: float
    bidding_window: float | None = None
    parent_auction_id: str | None = None
    status: AuctionStatus = AuctionStatus.CREATED
    history: list[tuple[AuctionStatus, float]] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    excluded: dict[str, list[str]] = field(default_factory=dict)
    bids: dict[str, Bid] = field(default_factory=dict)
    bid_log: list[Bid] = field(default_factory=list)
    rejected: list[RejectedBid] = field(default_factory=list)
    contracts: list[Contract] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.history:
            self.history.append((self.status, self.created_at))

    @property
    def task_id(self) -> str:
        return self.task.task_id

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL

    @property
    def start_time(self) -> float | None:
        return self.time_of(AuctionStatus.OPEN)

    @property
    def end_time(self) -> float | None:
        return self.history[-1][1] if self.is_terminal else None

    def time_of(self, status: AuctionStatus) -> float | None:
        return next((t for s, t in self.history if s == status), None)

    def can_transition(self, new: AuctionStatus) -> bool:
        return new in TRANSITIONS[self.status]

    def transition(self, new: AuctionStatus, at: float) -> None:
        if not self.can_transition(new):
            raise InvalidTransitionError(
                f"auction {self.auction_id}: cannot move from {self.status} to {new}"
            )
        self.status = new
        self.history.append((new, at))

    def record_bid(self, bid: Bid) -> None:
        self.bids[bid.agent_id] = bid
        self.bid_log.append(bid)

    @property
    def valid_bids(self) -> list[Bid]:
        return list(self.bids.values())
