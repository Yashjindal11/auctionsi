from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from auctionsi.core import Bid, Task
from auctionsi.errors import ValidationError
from auctionsi.reputation import AgentFeatures
from auctionsi.selection import (
    CallablePolicy,
    HighestQuality,
    LowestLatency,
    LowestPrice,
    ReputationAdjustedCost,
    RiskAdjustedCost,
    SelectionPolicy,
    WeightedScore,
)

TASK = Task(task_id="t", task_type="x", budget=0.10, deadline=60)


def bid(
    agent: str,
    price: float,
    *,
    latency: float | None = None,
    quality: float | None = None,
    confidence: float | None = None,
    ts: float = 0.0,
) -> Bid:
    return Bid(
        bid_id=f"b-{agent}",
        task_id="t",
        agent_id=agent,
        auction_id="x",
        price=price,
        estimated_latency=latency,
        estimated_quality=quality,
        confidence=confidence,
        timestamp=ts,
    )


SPEC_BIDS = [
    bid("A", 0.04, latency=8, quality=0.95),
    bid("B", 0.02, latency=20, quality=0.88),
    bid("C", 0.07, latency=4, quality=0.98),
]


def winner(policy: SelectionPolicy, bids: list[Bid], features: dict[str, AgentFeatures]) -> str:
    return policy.rank(bids, TASK, features)[0].agent_id


def test_single_dimension_policies() -> None:
    assert winner(LowestPrice(), SPEC_BIDS, {}) == "B"
    assert winner(LowestLatency(), SPEC_BIDS, {}) == "C"
    assert winner(HighestQuality(), SPEC_BIDS, {}) == "C"


def test_weighted_score_is_decomposed() -> None:
    policy = WeightedScore(price_weight=0.4, quality_weight=0.4, latency_weight=0.2)
    ranked = policy.rank(SPEC_BIDS, TASK, {})
    for scored in ranked:
        assert sum(scored.contributions.values()) == pytest.approx(scored.score)
    by_agent = {s.agent_id: s for s in ranked}
    # A: price (0.07-0.04)/0.05=0.6 -> 0.24; quality 0.38; latency (20-8)/16=0.75 -> 0.15
    assert by_agent["A"].contributions["price"] == pytest.approx(0.24)
    assert by_agent["A"].contributions["quality"] == pytest.approx(0.38)
    assert by_agent["A"].contributions["latency"] == pytest.approx(0.15)
    assert ranked[0].agent_id == "A"
    assert "score" in ranked[0].explain()


def test_risk_adjusted_cost_prefers_reliable_agent() -> None:
    bids = [bid("A", 0.02), bid("B", 0.04)]
    features = {
        "A": AgentFeatures("A", observations=50, success_estimate=0.80),
        "B": AgentFeatures("B", observations=50, success_estimate=0.98),
    }
    assert winner(LowestPrice(), bids, features) == "A"
    policy = RiskAdjustedCost(failure_cost=0.20)
    ranked = policy.rank(bids, TASK, features)
    assert ranked[0].agent_id == "B"
    assert ranked[0].effective_cost == pytest.approx(0.04 + 0.02 * 0.20)
    assert ranked[1].effective_cost == pytest.approx(0.02 + 0.20 * 0.20)
    assert ranked[0].details["failure_probability_source"] == "reputation"


def test_risk_adjusted_fallbacks_for_newcomers() -> None:
    policy = RiskAdjustedCost(min_observations=5)
    newcomer = AgentFeatures("A", observations=0, success_estimate=0.5)
    p, source = policy.failure_probability(bid("A", 1, confidence=0.9), newcomer)
    assert (p, source) == (pytest.approx(0.1), "bid_confidence")
    p, source = RiskAdjustedCost(
        min_observations=5, newcomer_failure_probability=0.3
    ).failure_probability(bid("A", 1), newcomer)
    assert (p, source) == (0.3, "newcomer_default")
    assert policy.failure_probability(bid("A", 1), newcomer) == (0.0, "assumed_reliable")


def test_calibrated_quality_discounts_overpromisers() -> None:
    bids = [bid("liar", 0.05, quality=0.99), bid("honest", 0.05, quality=0.90)]
    features = {
        "liar": AgentFeatures("liar", observations=20, quality_bias=0.30, avg_quality=0.69),
        "honest": AgentFeatures("honest", observations=20, quality_bias=0.0, avg_quality=0.9),
    }
    assert winner(HighestQuality(quality_source="estimate"), bids, features) == "liar"
    assert winner(HighestQuality(quality_source="calibrated"), bids, features) == "honest"
    assert winner(HighestQuality(quality_source="reputation"), bids, features) == "honest"


def test_reputation_adjusted_cost() -> None:
    bids = [bid("A", 0.03), bid("B", 0.04)]
    features = {
        "A": AgentFeatures("A", observations=10, success_estimate=0.5),
        "B": AgentFeatures("B", observations=10, success_estimate=0.95),
    }
    ranked = ReputationAdjustedCost().rank(bids, TASK, features)
    assert ranked[0].agent_id == "B"
    assert ranked[1].effective_cost == pytest.approx(0.06)


def test_ties_break_by_price_then_time_then_agent() -> None:
    bids = [bid("b", 1.0, ts=1), bid("a", 1.0, ts=1), bid("c", 1.0, ts=0)]
    assert [s.agent_id for s in LowestPrice().rank(bids, TASK, {})] == ["c", "a", "b"]


def test_callable_policy_and_specs() -> None:
    policy = CallablePolicy("custom", lambda b, t, f: (b.price, {"price": b.price}))
    assert winner(policy, SPEC_BIDS, {}) == "C"
    assert policy.to_spec()["name"] == "custom"
    spec = WeightedScore(reputation_weight=0.1).to_spec()
    assert spec["name"] == "weighted_score"
    assert spec["reputation_weight"] == 0.1


@pytest.mark.parametrize(
    "factory",
    [
        lambda: WeightedScore(price_weight=0, quality_weight=0, latency_weight=0),
        lambda: WeightedScore(price_weight=-1),
        lambda: HighestQuality(quality_source="vibes"),
        lambda: ReputationAdjustedCost(floor=0),
    ],
)
def test_invalid_policy_parameters(factory: object) -> None:
    with pytest.raises(ValidationError):
        factory()  # type: ignore[operator]


bid_strategy = st.builds(
    lambda i, p, lat, q, c: bid(f"a{i}", p, latency=lat, quality=q, confidence=c),
    st.integers(0, 1000),
    st.floats(0, 10),
    st.one_of(st.none(), st.floats(0.1, 100)),
    st.one_of(st.none(), st.floats(0, 1)),
    st.one_of(st.none(), st.floats(0, 1)),
)
POLICIES: list[SelectionPolicy] = [
    LowestPrice(),
    HighestQuality(),
    LowestLatency(),
    WeightedScore(reputation_weight=0.2),
    RiskAdjustedCost(),
    ReputationAdjustedCost(include_quality=True),
]


@given(st.lists(bid_strategy, min_size=1, max_size=8, unique_by=lambda b: b.agent_id))
def test_contributions_always_explain_the_score(bids: list[Bid]) -> None:
    for policy in POLICIES:
        ranked = policy.rank(bids, TASK, {})
        assert len(ranked) == len(bids)
        assert all(ranked[i].score >= ranked[i + 1].score for i in range(len(ranked) - 1))
        for scored in ranked:
            assert sum(scored.contributions.values()) == pytest.approx(scored.score, abs=1e-9)
