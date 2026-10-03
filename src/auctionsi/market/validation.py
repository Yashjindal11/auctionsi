"""Validation of bid proposals submitted by (untrusted) agents."""

from __future__ import annotations

import math
from dataclasses import dataclass

from auctionsi.core.agent import Agent
from auctionsi.core.bid import BidProposal, BidRejection, RejectionCode
from auctionsi.core.task import Task

R = RejectionCode


@dataclass(frozen=True, slots=True)
class BidValidationConfig:
    """Which rules reject a bid. All on by default."""

    enforce_budget: bool = True
    enforce_deadline: bool = True
    enforce_min_quality: bool = True
    allow_negative_prices: bool = False
    require_latency_estimate: bool = False


def _num(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def validate_proposal(
    proposal: object,
    task: Task | None,
    agent: Agent | None,
    *,
    eligible: bool,
    now: float,
    config: BidValidationConfig,
) -> list[BidRejection]:
    """Return every reason the proposal is invalid (empty list = valid)."""
    if task is None:
        return [BidRejection(R.UNKNOWN_TASK, "task does not exist")]
    if agent is None or not eligible:
        return [BidRejection(R.AGENT_NOT_ELIGIBLE, "agent is not an eligible participant")]
    if not isinstance(proposal, BidProposal):
        return [BidRejection(R.MALFORMED, f"expected BidProposal, got {type(proposal).__name__}")]
    if agent.capability(task.task_type) is None:
        return [BidRejection(R.CAPABILITY_MISMATCH, f"agent lacks capability {task.task_type!r}")]

    out: list[BidRejection] = []
    if not _num(proposal.price):
        out.append(BidRejection(R.INVALID_PRICE, "price must be a finite number"))
    else:
        if proposal.price < 0 and not config.allow_negative_prices:
            out.append(BidRejection(R.INVALID_PRICE, "negative prices are not allowed"))
        if config.enforce_budget and task.budget is not None and proposal.price > task.budget:
            out.append(
                BidRejection(R.OVER_BUDGET, f"price {proposal.price} exceeds budget {task.budget}")
            )

    latency = proposal.estimated_latency
    if latency is None:
        if config.require_latency_estimate:
            out.append(BidRejection(R.INVALID_LATENCY, "a latency estimate is required"))
    elif not _num(latency) or latency < 0:
        out.append(BidRejection(R.INVALID_LATENCY, "estimated_latency must be >= 0"))
    elif config.enforce_deadline and task.deadline is not None and latency > task.deadline:
        out.append(
            BidRejection(
                R.DEADLINE_INFEASIBLE,
                f"estimated latency {latency} exceeds deadline {task.deadline}",
            )
        )

    for name in ("estimated_quality", "confidence"):
        value = getattr(proposal, name)
        if value is not None and (not _num(value) or not 0 <= value <= 1):
            out.append(BidRejection(R.INVALID_ESTIMATE, f"{name} must be in [0, 1]"))
    if proposal.estimated_cost is not None and not _num(proposal.estimated_cost):
        out.append(BidRejection(R.INVALID_ESTIMATE, "estimated_cost must be finite"))
    if proposal.capacity is not None and (
        isinstance(proposal.capacity, bool)
        or not isinstance(proposal.capacity, int)
        or proposal.capacity < 0
    ):
        out.append(BidRejection(R.MALFORMED, "capacity must be a non-negative integer"))

    q = proposal.estimated_quality
    if (
        config.enforce_min_quality
        and task.min_quality is not None
        and _num(q)
        and q is not None
        and q < task.min_quality
    ):
        out.append(
            BidRejection(
                R.BELOW_MIN_QUALITY, f"estimated quality {q} below required {task.min_quality}"
            )
        )

    if proposal.valid_for is not None and (not _num(proposal.valid_for) or proposal.valid_for <= 0):
        out.append(BidRejection(R.EXPIRED, "valid_for must be positive"))
    return out
