"""Bids: what an agent proposes, and the stamped record the marketplace keeps."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from auctionsi.security import (
    check_identifier,
    check_mapping,
    check_number,
    require_number,
)


@dataclass(frozen=True, slots=True)
class BidProposal:
    """What an agent returns when asked to bid.

    The agent never chooses its own ``bid_id``, ``task_id``, ``agent_id`` or
    timestamp: the marketplace stamps those so an agent cannot impersonate
    another agent or bid on a task it was not invited to.

    All self-reported estimates (quality, latency, cost, confidence) are claims,
    not facts. Selection policies decide how far to trust them; reputation
    measures how accurate they turned out to be.
    """

    price: float
    estimated_latency: float | None = None
    estimated_quality: float | None = None
    estimated_cost: float | None = None
    confidence: float | None = None
    capacity: int | None = None
    valid_for: float | None = None
    constraints: Mapping[str, Any] = field(default_factory=dict)
    terms: Mapping[str, Any] = field(default_factory=dict)
    signature: str | None = None


@dataclass(frozen=True, slots=True)
class Bid:
    """A validated-shape, marketplace-stamped bid. Created by the marketplace, not by agents."""

    bid_id: str
    task_id: str
    agent_id: str
    auction_id: str
    price: float
    estimated_latency: float | None = None
    estimated_quality: float | None = None
    estimated_cost: float | None = None
    confidence: float | None = None
    capacity: int | None = None
    valid_until: float | None = None
    constraints: Mapping[str, Any] = field(default_factory=dict)
    terms: Mapping[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0
    revision: int = 0
    signature: str | None = None

    def __post_init__(self) -> None:
        for name in ("bid_id", "task_id", "agent_id", "auction_id"):
            check_identifier(getattr(self, name), name)
        set_ = object.__setattr__
        # Price may legitimately be negative in some research markets, so only finiteness
        # is enforced here; sign rules belong to bid validation policy.
        set_(self, "price", require_number(self.price, "price"))
        set_(
            self,
            "estimated_latency",
            check_number(self.estimated_latency, "estimated_latency", allow_none=True),
        )
        set_(
            self,
            "estimated_quality",
            check_number(self.estimated_quality, "estimated_quality", allow_none=True),
        )
        set_(
            self,
            "estimated_cost",
            check_number(self.estimated_cost, "estimated_cost", allow_none=True),
        )
        set_(self, "confidence", check_number(self.confidence, "confidence", allow_none=True))
        set_(self, "valid_until", check_number(self.valid_until, "valid_until", allow_none=True))
        set_(self, "constraints", check_mapping(self.constraints, "bid constraints"))
        set_(self, "terms", check_mapping(self.terms, "bid terms"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "bid_id": self.bid_id,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "auction_id": self.auction_id,
            "price": self.price,
            "estimated_latency": self.estimated_latency,
            "estimated_quality": self.estimated_quality,
            "estimated_cost": self.estimated_cost,
            "confidence": self.confidence,
            "capacity": self.capacity,
            "valid_until": self.valid_until,
            "constraints": dict(self.constraints),
            "terms": dict(self.terms),
            "timestamp": self.timestamp,
            "revision": self.revision,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Bid:
        return cls(**dict(data))


class RejectionCode(StrEnum):
    UNKNOWN_TASK = "unknown_task"
    AGENT_NOT_ELIGIBLE = "agent_not_eligible"
    CAPABILITY_MISMATCH = "capability_mismatch"
    MALFORMED = "malformed"
    INVALID_PRICE = "invalid_price"
    OVER_BUDGET = "over_budget"
    BELOW_RESERVE = "below_reserve"
    INVALID_LATENCY = "invalid_latency"
    DEADLINE_INFEASIBLE = "deadline_infeasible"
    INVALID_ESTIMATE = "invalid_estimate"
    BELOW_MIN_QUALITY = "below_min_quality"
    EXPIRED = "expired"
    DUPLICATE_BID = "duplicate_bid"
    NOT_IMPROVING = "not_improving"
    TOO_MANY_BIDS = "too_many_bids"
    TIMEOUT = "timeout"
    BAD_SIGNATURE = "bad_signature"
    AGENT_ERROR = "agent_error"


@dataclass(frozen=True, slots=True)
class BidRejection:
    """One structured reason a bid was refused."""

    code: RejectionCode
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code.value, "message": self.message}
