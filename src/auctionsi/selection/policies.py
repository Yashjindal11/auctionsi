"""Winner-selection policies.

A policy turns a set of valid bids into scores, and every score is broken down
into named ``contributions`` that sum to it, so the winner can always be
explained. Higher score is better. Ties are broken deterministically by lower
price, then earlier bid, then agent id.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any

from auctionsi.core.bid import Bid
from auctionsi.core.task import Task
from auctionsi.errors import ValidationError
from auctionsi.reputation.base import AgentFeatures

Features = Mapping[str, AgentFeatures]


@dataclass(frozen=True, slots=True)
class ScoredBid:
    bid: Bid
    score: float
    contributions: dict[str, float]
    effective_cost: float | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def agent_id(self) -> str:
        return self.bid.agent_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "bid_id": self.bid.bid_id,
            "agent_id": self.bid.agent_id,
            "price": self.bid.price,
            "score": self.score,
            "contributions": dict(self.contributions),
            "effective_cost": self.effective_cost,
            "details": dict(self.details),
        }

    def explain(self) -> str:
        lines = [f"agent {self.agent_id}: score {self.score:.6g}"]
        for name, value in self.contributions.items():
            lines.append(f"  {name:<22} {value + 0.0:+.6g}")
        if self.effective_cost is not None:
            lines.append(f"  effective cost          {self.effective_cost:.6g}")
        for name, value in self.details.items():
            lines.append(f"  ({name}: {value})")
        return "\n".join(lines)


def ranking_key(scored: ScoredBid) -> tuple[float, float, float, str]:
    return (-scored.score, scored.bid.price, scored.bid.timestamp, scored.bid.agent_id)


class SelectionPolicy(ABC):
    """Plugin interface. Implementations must be pure functions of their inputs so
    that recorded auctions can be replayed exactly."""

    name: str = "policy"

    @abstractmethod
    def score(self, bids: Sequence[Bid], task: Task, features: Features) -> list[ScoredBid]:
        """Score every bid (same order as ``bids``)."""

    def rank(self, bids: Sequence[Bid], task: Task, features: Features) -> list[ScoredBid]:
        return sorted(self.score(bids, task, features), key=ranking_key)

    @property
    def price_only(self) -> bool:
        """True when the ranking depends on price alone (needed by some mechanisms)."""
        return False

    def to_spec(self) -> dict[str, Any]:
        params: dict[str, Any] = asdict(self) if is_dataclass(self) else {}
        return {"name": self.name, **params}


def _features(features: Features, agent_id: str) -> AgentFeatures:
    return features.get(agent_id) or AgentFeatures(agent_id=agent_id)


QUALITY_SOURCES = ("estimate", "reputation", "calibrated")


def quality_estimate(bid: Bid, feats: AgentFeatures, source: str) -> tuple[float, str]:
    """Quality used for scoring, and which source actually supplied it.

    ``estimate`` trusts the bid; ``reputation`` uses observed average quality;
    ``calibrated`` subtracts the agent's historical over-promise from its estimate.
    Falls back to the bid estimate (or 0) when history is missing.
    """
    claimed = bid.estimated_quality
    if source == "reputation" and feats.avg_quality is not None:
        return feats.avg_quality, "reputation"
    if source == "calibrated" and claimed is not None and feats.quality_bias is not None:
        return min(1.0, max(0.0, claimed - feats.quality_bias)), "calibrated"
    if claimed is not None:
        return min(1.0, max(0.0, claimed)), "estimate"
    return 0.0, "missing"


def _latency(bid: Bid, task: Task) -> tuple[float, str]:
    if bid.estimated_latency is not None:
        return bid.estimated_latency, "estimate"
    if task.deadline is not None:
        return task.deadline, "deadline (no estimate)"
    return 1e9, "missing"


def _check_quality_source(source: str) -> None:
    if source not in QUALITY_SOURCES:
        raise ValidationError(f"quality_source must be one of {QUALITY_SOURCES}")


@dataclass(frozen=True)
class LowestPrice(SelectionPolicy):
    name = "lowest_price"

    @property
    def price_only(self) -> bool:
        return True

    def score(self, bids: Sequence[Bid], task: Task, features: Features) -> list[ScoredBid]:
        return [ScoredBid(b, -b.price, {"price": -b.price}) for b in bids]


@dataclass(frozen=True)
class HighestQuality(SelectionPolicy):
    quality_source: str = "calibrated"
    name = "highest_quality"

    def __post_init__(self) -> None:
        _check_quality_source(self.quality_source)

    def score(self, bids: Sequence[Bid], task: Task, features: Features) -> list[ScoredBid]:
        out = []
        for b in bids:
            q, src = quality_estimate(b, _features(features, b.agent_id), self.quality_source)
            out.append(ScoredBid(b, q, {"quality": q}, details={"quality_source": src}))
        return out


@dataclass(frozen=True)
class LowestLatency(SelectionPolicy):
    name = "lowest_latency"

    def score(self, bids: Sequence[Bid], task: Task, features: Features) -> list[ScoredBid]:
        out = []
        for b in bids:
            latency, src = _latency(b, task)
            out.append(
                ScoredBid(b, -latency, {"latency": -latency}, details={"latency_source": src})
            )
        return out


@dataclass(frozen=True)
class WeightedScore(SelectionPolicy):
    """``score = w_p*price_term + w_q*quality + w_l*latency_term + w_r*reputation``.

    Price and latency terms are min-max normalised *within the auction* to [0, 1]
    (1 = cheapest/fastest; all equal -> 1). Quality is used on its absolute [0, 1]
    scale. Reputation is the agent's ``success_estimate`` (0.5 when unknown).
    Because of the within-auction normalisation, adding or removing a rival bid
    can change how two other bids compare: weighted scores are relative, not
    absolute.
    """

    price_weight: float = 0.4
    quality_weight: float = 0.4
    latency_weight: float = 0.2
    reputation_weight: float = 0.0
    quality_source: str = "calibrated"
    name = "weighted_score"

    def __post_init__(self) -> None:
        _check_quality_source(self.quality_source)
        weights = (
            self.price_weight,
            self.quality_weight,
            self.latency_weight,
            self.reputation_weight,
        )
        if any(w < 0 for w in weights) or sum(weights) <= 0:
            raise ValidationError("weights must be non-negative and not all zero")

    def score(self, bids: Sequence[Bid], task: Task, features: Features) -> list[ScoredBid]:
        if not bids:
            return []
        prices = [b.price for b in bids]
        latencies = [_latency(b, task)[0] for b in bids]
        out = []
        for b, latency in zip(bids, latencies, strict=True):
            feats = _features(features, b.agent_id)
            q, q_src = quality_estimate(b, feats, self.quality_source)
            rep = feats.success_estimate if feats.success_estimate is not None else 0.5
            contributions = {
                "price": self.price_weight * _normalise_low_is_good(b.price, prices),
                "quality": self.quality_weight * q,
                "latency": self.latency_weight * _normalise_low_is_good(latency, latencies),
                "reputation": self.reputation_weight * rep,
            }
            out.append(
                ScoredBid(
                    b,
                    sum(contributions.values()),
                    contributions,
                    details={"quality_source": q_src, "reputation_used": rep},
                )
            )
        return out


@dataclass(frozen=True)
class RiskAdjustedCost(SelectionPolicy):
    """Lowest expected cost to the buyer, accounting for the chance of failure.

    ``effective_cost = price + verification_cost + p_fail * failure_cost
    + latency_penalty * estimated_latency`` and ``score = -effective_cost``.

    ``p_fail`` comes from reputation (``1 - success_estimate``) once the agent has
    at least ``min_observations`` recorded outcomes; before that from
    ``newcomer_failure_probability`` if set, else from the bid's own
    ``1 - confidence``, else 0. ``failure_cost`` defaults to the task budget (or
    the bid price when there is no budget) as a stand-in for the cost of a failed
    attempt (re-procurement, delay); set it explicitly when you know it.
    """

    failure_cost: float | None = None
    verification_cost: float = 0.0
    latency_penalty: float = 0.0
    min_observations: int = 0
    newcomer_failure_probability: float | None = None
    name = "risk_adjusted_cost"

    def score(self, bids: Sequence[Bid], task: Task, features: Features) -> list[ScoredBid]:
        out = []
        for b in bids:
            feats = _features(features, b.agent_id)
            p_fail, source = self.failure_probability(b, feats)
            failure_cost = self.failure_cost
            if failure_cost is None:
                failure_cost = task.budget if task.budget is not None else b.price
            latency, _ = _latency(b, task)
            parts = {
                "price": -b.price,
                "verification": -self.verification_cost,
                "expected_failure": -p_fail * failure_cost,
                "latency": -self.latency_penalty * latency,
            }
            cost = -sum(parts.values())
            out.append(
                ScoredBid(
                    b,
                    -cost,
                    parts,
                    effective_cost=cost,
                    details={
                        "failure_probability": p_fail,
                        "failure_probability_source": source,
                        "failure_cost": failure_cost,
                    },
                )
            )
        return out

    def failure_probability(self, bid: Bid, feats: AgentFeatures) -> tuple[float, str]:
        if feats.success_estimate is not None and feats.observations >= self.min_observations:
            return 1.0 - feats.success_estimate, "reputation"
        if self.newcomer_failure_probability is not None:
            return self.newcomer_failure_probability, "newcomer_default"
        if bid.confidence is not None:
            return 1.0 - min(1.0, max(0.0, bid.confidence)), "bid_confidence"
        return 0.0, "assumed_reliable"


@dataclass(frozen=True)
class ReputationAdjustedCost(SelectionPolicy):
    """``adjusted = price / max(floor, success_estimate)`` (optionally also divided by
    quality); ``score = -adjusted``. Assumes non-negative prices. Unknown agents use
    a success estimate of 1, i.e. they are judged on price alone."""

    floor: float = 0.05
    include_quality: bool = False
    quality_source: str = "reputation"
    name = "reputation_adjusted_cost"

    def __post_init__(self) -> None:
        _check_quality_source(self.quality_source)
        if not 0 < self.floor <= 1:
            raise ValidationError("floor must be in (0, 1]")

    def score(self, bids: Sequence[Bid], task: Task, features: Features) -> list[ScoredBid]:
        out = []
        for b in bids:
            feats = _features(features, b.agent_id)
            success = feats.success_estimate if feats.success_estimate is not None else 1.0
            divisor = max(self.floor, success)
            details: dict[str, Any] = {"success_estimate": success}
            if self.include_quality:
                q, src = quality_estimate(b, feats, self.quality_source)
                divisor *= max(self.floor, q)
                details.update(quality=q, quality_source=src)
            adjusted = b.price / divisor
            out.append(
                ScoredBid(
                    b,
                    -adjusted,
                    {"price": -b.price, "reputation_markup": -(adjusted - b.price)},
                    effective_cost=adjusted,
                    details=details,
                )
            )
        return out


ScoreFn = Callable[[Bid, Task, AgentFeatures], tuple[float, Mapping[str, float]]]


class ExplorationBonus(SelectionPolicy):
    """Wraps another policy and adds ``weight / sqrt(1 + observations)`` to each score,
    so agents with little history still win some work and can build a reputation.

    The bonus is in the base policy's score units: pick ``weight`` relative to typical
    score differences (prices for cost policies, 0-1 for weighted scores).
    """

    name = "exploration_bonus"

    def __init__(self, base: SelectionPolicy, weight: float = 0.01) -> None:
        if weight < 0:
            raise ValidationError("weight must be non-negative")
        self.base = base
        self.weight = weight

    def score(self, bids: Sequence[Bid], task: Task, features: Features) -> list[ScoredBid]:
        out = []
        for scored in self.base.score(bids, task, features):
            observed = _features(features, scored.agent_id).observations
            bonus = self.weight / math.sqrt(1 + observed)
            out.append(
                ScoredBid(
                    scored.bid,
                    scored.score + bonus,
                    {**scored.contributions, "exploration": bonus},
                    scored.effective_cost,
                    {**scored.details, "observations": observed},
                )
            )
        return out

    def to_spec(self) -> dict[str, Any]:
        return {"name": self.name, "base": self.base.to_spec(), "weight": self.weight}


class CallablePolicy(SelectionPolicy):
    """Wrap ``fn(bid, task, features) -> (score, contributions)`` as a policy."""

    def __init__(self, name: str, fn: ScoreFn) -> None:
        self.name = name
        self.fn = fn

    def score(self, bids: Sequence[Bid], task: Task, features: Features) -> list[ScoredBid]:
        out = []
        for b in bids:
            value, contributions = self.fn(b, task, _features(features, b.agent_id))
            out.append(ScoredBid(b, float(value), dict(contributions)))
        return out

    def to_spec(self) -> dict[str, Any]:
        return {"name": self.name, "callable": True}


def _normalise_low_is_good(value: float, values: Sequence[float]) -> float:
    lo, hi = min(values), max(values)
    if hi - lo <= 1e-12:
        return 1.0
    return (hi - value) / (hi - lo)
