from __future__ import annotations

import math
from dataclasses import replace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from auctionsi.core import Bid, Task
from auctionsi.errors import ValidationError
from auctionsi.mechanisms import (
    FirstPriceReverseAuction,
    MultiWinnerReverseAuction,
    SecondPriceReverseAuction,
)
from auctionsi.selection import LowestPrice, WeightedScore

TASK = Task(task_id="t", task_type="x", budget=0.10)
NO_BUDGET = Task(task_id="t", task_type="x")


def bid(agent: str, price: float, quality: float | None = None, latency: float = 5) -> Bid:
    return Bid(
        bid_id=f"b-{agent}",
        task_id="t",
        agent_id=agent,
        auction_id="x",
        price=price,
        estimated_quality=quality,
        estimated_latency=latency,
    )


SPEC = [bid("A", 0.05), bid("B", 0.07), bid("C", 0.03)]


def test_first_price_lowest_bid_wins_and_pays_own_price() -> None:
    outcome = FirstPriceReverseAuction().determine_winners(SPEC, TASK, LowestPrice(), {})
    assert [a.agent_id for a in outcome.awards] == ["C"]
    assert outcome.awards[0].payment == 0.03
    assert [s.agent_id for s in outcome.backups] == ["A", "B"]


def test_second_price_pays_runner_up() -> None:
    outcome = SecondPriceReverseAuction().determine_winners(SPEC, TASK, LowestPrice(), {})
    award = outcome.awards[0]
    assert award.agent_id == "C"
    assert award.payment == 0.05
    assert "runner-up A" in award.payment_rule


def test_second_price_single_bid_rules() -> None:
    lone = [bid("A", 0.04)]
    reserve = SecondPriceReverseAuction().determine_winners(lone, TASK, LowestPrice(), {})
    assert reserve.awards[0].payment == 0.10
    own = SecondPriceReverseAuction(single_bid_payment="bid").determine_winners(
        lone, TASK, LowestPrice(), {}
    )
    assert own.awards[0].payment == 0.04
    no_budget = SecondPriceReverseAuction().determine_winners(lone, NO_BUDGET, LowestPrice(), {})
    assert no_budget.awards[0].payment == 0.04
    with pytest.raises(ValidationError):
        SecondPriceReverseAuction(single_bid_payment="x")


def test_critical_price_with_weighted_score_is_the_switching_point() -> None:
    policy = WeightedScore(price_weight=0.2, quality_weight=0.8, latency_weight=0.0)
    bids = [
        bid("hq", 0.05, quality=0.95),
        bid("cheap", 0.03, quality=0.85),
        bid("anchor", 0.10, quality=0.0),
    ]
    mech = SecondPriceReverseAuction()
    outcome = mech.determine_winners(bids, TASK, policy, {})
    award = outcome.awards[0]
    assert award.agent_id == "hq"
    # hq keeps winning while 0.2 * (0.10 - p) / 0.07 + 0.76 > 0.88, i.e. p < 0.058
    assert award.payment == pytest.approx(0.058, abs=1e-6)
    others = [b for b in bids if b.agent_id != "hq"]
    at = [*others, replace(bids[0], price=award.payment)]
    assert policy.rank(at, TASK, {})[0].agent_id == "hq"
    above = [*others, replace(bids[0], price=award.payment + 1e-6)]
    assert policy.rank(above, TASK, {})[0].agent_id == "cheap"


def test_multi_winner_pay_as_bid_and_uniform() -> None:
    bids = [bid("A", 0.05), bid("B", 0.07), bid("C", 0.03), bid("D", 0.09)]
    pab = MultiWinnerReverseAuction(winners=2).determine_winners(bids, TASK, LowestPrice(), {})
    assert [(a.agent_id, a.payment) for a in pab.awards] == [("C", 0.03), ("A", 0.05)]
    uni = MultiWinnerReverseAuction(winners=2, pricing="uniform").determine_winners(
        bids, TASK, LowestPrice(), {}
    )
    assert [(a.agent_id, a.payment) for a in uni.awards] == [("C", 0.07), ("A", 0.07)]
    short = MultiWinnerReverseAuction(winners=5).determine_winners(bids, TASK, LowestPrice(), {})
    assert len(short.awards) == 4
    assert "only 4 of 5" in short.notes[0]
    with pytest.raises(ValidationError):
        MultiWinnerReverseAuction(pricing="uniform").determine_winners(
            bids, TASK, WeightedScore(), {}
        )
    with pytest.raises(ValidationError):
        MultiWinnerReverseAuction(winners=0)


def test_specs_are_serialisable() -> None:
    assert FirstPriceReverseAuction().to_spec() == {"name": "first_price_reverse"}
    assert MultiWinnerReverseAuction(winners=3).to_spec()["winners"] == 3


prices = st.lists(
    st.floats(0, 0.1, allow_nan=False).map(lambda p: round(p, 4)),
    min_size=1,
    max_size=10,
)


@given(prices)
def test_mechanism_invariants(values: list[float]) -> None:
    bids = [bid(f"a{i}", p) for i, p in enumerate(values)]
    for mech in (FirstPriceReverseAuction(), SecondPriceReverseAuction()):
        outcome = mech.determine_winners(bids, TASK, LowestPrice(), {})
        award = outcome.awards[0]
        assert award.bid in bids
        assert award.bid.price == min(values)
        assert award.payment >= award.bid.price
        if isinstance(mech, FirstPriceReverseAuction):
            assert award.payment == award.bid.price
        else:
            ordered = sorted(values)
            expected = ordered[1] if len(ordered) > 1 else TASK.budget
            assert math.isclose(award.payment, min(expected, TASK.budget))  # type: ignore[type-var]
