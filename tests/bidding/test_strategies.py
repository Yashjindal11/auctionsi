from __future__ import annotations

import random

import pytest

from auctionsi.bidding import (
    AdaptiveMarkup,
    AggressiveBid,
    BidInputs,
    ConservativeBid,
    CostPlus,
    FixedBid,
    GreedyBid,
    LatencyAwareBid,
    QualityAwareBid,
    RandomMarkup,
    ReputationMaximizingBid,
    RiskAwareBid,
    TruthfulBid,
)
from auctionsi.core import AuctionNotice, Bid, OpenAuctionView, Task
from auctionsi.errors import ValidationError

TASK = Task(task_id="t", task_type="x", budget=1.0, deadline=100, min_quality=0.8)


def inputs(**kw: object) -> BidInputs:
    base: dict[str, object] = {
        "task": TASK,
        "cost": 0.5,
        "quality": 0.9,
        "latency": 25.0,
        "reliability": 0.8,
        "rng": random.Random(1),
    }
    base.update(kw)
    return BidInputs(**base)  # type: ignore[arg-type]


def test_static_strategies() -> None:
    assert TruthfulBid().price(inputs()) == 0.5
    assert FixedBid(0.3).price(inputs()) == 0.3
    assert CostPlus(0.2).price(inputs()) == pytest.approx(0.6)
    assert AggressiveBid().price(inputs()) == pytest.approx(0.475)
    assert ConservativeBid().price(inputs()) == pytest.approx(0.8)
    assert GreedyBid(0.95).price(inputs()) == pytest.approx(0.95)
    assert GreedyBid(0.95).price(inputs(cost=2.0)) is None
    assert QualityAwareBid(0.1, 0.5).price(inputs()) == pytest.approx(0.5 * (1 + 0.1 + 0.2))
    assert LatencyAwareBid(0.1, 0.4).price(inputs()) == pytest.approx(0.5 * (1 + 0.1 + 0.3))
    assert RiskAwareBid(0.0).price(inputs()) == pytest.approx(0.625)
    assert ReputationMaximizingBid().price(inputs(quality=0.5)) is None
    assert ReputationMaximizingBid(0.0).price(inputs()) == 0.5


def test_random_markup_is_seeded() -> None:
    a = RandomMarkup(0, 1).price(inputs(rng=random.Random(7)))
    b = RandomMarkup(0, 1).price(inputs(rng=random.Random(7)))
    assert a == b
    assert 0.5 <= a <= 1.0  # type: ignore[operator]
    with pytest.raises(ValidationError):
        RandomMarkup(1, 0)


def notice(won: bool) -> AuctionNotice:
    return AuctionNotice("a", TASK, None, won, None, None)


def test_adaptive_markup_learns_within_bounds() -> None:
    strat = AdaptiveMarkup(initial_markup=0.2, step=0.1, min_markup=0.0, max_markup=0.3)
    strat.observe(notice(True))
    strat.observe(notice(True))
    assert strat.markup == pytest.approx(0.3)
    for _ in range(10):
        strat.observe(notice(False))
    assert strat.markup == 0.0


def test_default_open_auction_revision() -> None:
    own = Bid(bid_id="b", task_id="t", agent_id="a", auction_id="x", price=0.9)
    view = OpenAuctionView("x", 1, best_price=0.7, bid_count=2, own_bid=own, now=0)
    assert CostPlus().revise(inputs(), view) == pytest.approx(0.7 * 0.98)
    assert CostPlus().revise(inputs(cost=0.69), view) == pytest.approx(0.69)
    assert CostPlus().revise(inputs(cost=0.95), view) is None
    leading = OpenAuctionView("x", 1, best_price=0.9, bid_count=2, own_bid=own, now=0)
    assert CostPlus().revise(inputs(), leading) is None


def test_specs() -> None:
    assert CostPlus(0.3).to_spec() == {"name": "cost_plus", "markup": 0.3}
    assert AdaptiveMarkup().to_spec()["name"] == "profit_maximizing"
