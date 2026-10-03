"""Bid strategies: how an agent turns its private cost into a price.

Strategies are research instruments. None of them is claimed to be optimal; the
point is to compare how markets behave when bidders behave differently.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any

from auctionsi.core.agent import AuctionNotice, OpenAuctionView
from auctionsi.core.task import Task
from auctionsi.errors import ValidationError


@dataclass(frozen=True, slots=True)
class BidInputs:
    """What a bidder knows privately when pricing a task."""

    task: Task
    cost: float
    quality: float
    latency: float
    reliability: float
    rng: random.Random = field(default_factory=random.Random, compare=False)


class BidStrategy(ABC):
    name: str = "strategy"
    #: Fraction by which an open-auction revision undercuts the standing best price.
    undercut: float = 0.02

    @abstractmethod
    def price(self, inputs: BidInputs) -> float | None:
        """Return a price, or ``None`` to abstain."""

    def floor(self, inputs: BidInputs) -> float:
        """Lowest price this strategy will revise down to in an open auction."""
        return inputs.cost

    def revise(self, inputs: BidInputs, view: OpenAuctionView) -> float | None:
        """Default open-auction behaviour: undercut the standing best price while it
        stays above :meth:`floor`; otherwise stand pat."""
        if view.own_bid is None or view.best_price is None:
            return None
        if view.own_bid.price <= view.best_price:
            return None
        target = view.best_price * (1 - self.undercut)
        floor = self.floor(inputs)
        if target < floor:
            return floor if floor < view.own_bid.price else None
        return target

    def observe(self, notice: AuctionNotice) -> None:
        return None

    def to_spec(self) -> dict[str, Any]:
        params: dict[str, Any] = asdict(self) if is_dataclass(self) else {}
        return {"name": self.name, **params}


@dataclass
class TruthfulBid(BidStrategy):
    """Bids its own estimated cost ("truthful-ish": the estimate itself may be wrong)."""

    name = "truthful"

    def price(self, inputs: BidInputs) -> float | None:
        return inputs.cost


@dataclass
class FixedBid(BidStrategy):
    amount: float = 1.0
    name = "fixed"

    def price(self, inputs: BidInputs) -> float | None:
        return self.amount

    def floor(self, inputs: BidInputs) -> float:
        return self.amount


@dataclass
class CostPlus(BidStrategy):
    markup: float = 0.2
    name = "cost_plus"

    def price(self, inputs: BidInputs) -> float | None:
        return inputs.cost * (1 + self.markup)


@dataclass
class AggressiveBid(CostPlus):
    """Small or negative markup: deliberately under-bids to win volume."""

    markup: float = -0.05
    name = "aggressive"

    def floor(self, inputs: BidInputs) -> float:
        return inputs.cost * (1 + min(self.markup, 0.0))


@dataclass
class ConservativeBid(CostPlus):
    """Large markup: wins rarely, but profitably."""

    markup: float = 0.6
    name = "conservative"

    def floor(self, inputs: BidInputs) -> float:
        return inputs.cost * (1 + self.markup / 2)


@dataclass
class RandomMarkup(BidStrategy):
    low: float = 0.0
    high: float = 0.5
    name = "random"

    def __post_init__(self) -> None:
        if self.high < self.low:
            raise ValidationError("high must be >= low")

    def price(self, inputs: BidInputs) -> float | None:
        return inputs.cost * (1 + inputs.rng.uniform(self.low, self.high))


@dataclass
class GreedyBid(BidStrategy):
    """Bids close to the buyer's budget (strategic over-bidding)."""

    fraction: float = 0.95
    fallback_markup: float = 1.0
    name = "greedy"

    def price(self, inputs: BidInputs) -> float | None:
        budget = inputs.task.budget
        if budget is None:
            return inputs.cost * (1 + self.fallback_markup)
        price = budget * self.fraction
        return price if price >= inputs.cost else None


@dataclass
class QualityAwareBid(BidStrategy):
    """Charges a premium for (self-assessed) quality above 0.5."""

    base_markup: float = 0.1
    quality_premium: float = 0.5
    name = "quality_aware"

    def price(self, inputs: BidInputs) -> float | None:
        premium = self.quality_premium * max(0.0, inputs.quality - 0.5)
        return inputs.cost * (1 + self.base_markup + premium)


@dataclass
class LatencyAwareBid(BidStrategy):
    """Charges more the more slack it leaves before the deadline."""

    base_markup: float = 0.1
    speed_premium: float = 0.3
    name = "latency_aware"

    def price(self, inputs: BidInputs) -> float | None:
        deadline = inputs.task.deadline
        slack = 0.0
        if deadline:
            slack = min(1.0, max(0.0, 1 - inputs.latency / deadline))
        return inputs.cost * (1 + self.base_markup + self.speed_premium * slack)


@dataclass
class RiskAwareBid(BidStrategy):
    """Prices in its own failure risk: under pay-on-pass settlement, expected revenue
    ``reliability * price`` must cover ``cost * (1 + markup)``."""

    markup: float = 0.1
    name = "risk_aware"

    def price(self, inputs: BidInputs) -> float | None:
        return inputs.cost * (1 + self.markup) / max(inputs.reliability, 0.05)


@dataclass
class AdaptiveMarkup(BidStrategy):
    """Profit-seeking learner: raises its markup after a win, lowers it after a loss."""

    initial_markup: float = 0.2
    step: float = 0.05
    min_markup: float = 0.0
    max_markup: float = 1.0
    markup: float = field(default=-1.0)
    name = "profit_maximizing"

    def __post_init__(self) -> None:
        if self.markup < 0:
            self.markup = self.initial_markup

    def price(self, inputs: BidInputs) -> float | None:
        return inputs.cost * (1 + self.markup)

    def observe(self, notice: AuctionNotice) -> None:
        delta = self.step if notice.won else -self.step
        self.markup = min(self.max_markup, max(self.min_markup, self.markup + delta))


@dataclass
class ReputationMaximizingBid(BidStrategy):
    """Protects its reputation: abstains from tasks whose required quality it does not
    believe it can meet, and bids a thin margin otherwise."""

    markup: float = 0.05
    name = "reputation_maximizing"

    def price(self, inputs: BidInputs) -> float | None:
        required = inputs.task.min_quality
        if required is not None and inputs.quality < required:
            return None
        return inputs.cost * (1 + self.markup)


BUILTIN_STRATEGIES: dict[str, Callable[..., BidStrategy]] = {
    cls.name: cls
    for cls in (
        TruthfulBid,
        FixedBid,
        CostPlus,
        AggressiveBid,
        ConservativeBid,
        RandomMarkup,
        GreedyBid,
        QualityAwareBid,
        LatencyAwareBid,
        RiskAwareBid,
        AdaptiveMarkup,
        ReputationMaximizingBid,
    )
}
