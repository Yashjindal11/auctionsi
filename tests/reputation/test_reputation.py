from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from auctionsi.errors import ValidationError
from auctionsi.reputation import (
    AgentFeatures,
    ExponentialDecay,
    MultiDimensionalReputation,
    NoReputation,
    Observation,
    RollingWindow,
    StaticReputation,
    decay_from_spec,
)


def obs(
    success: bool = True,
    quality: float = 0.9,
    *,
    agent: str = "a",
    task_type: str = "sql",
    est_q: float | None = None,
    latency: float = 10.0,
    est_l: float | None = None,
    on_time: bool = True,
) -> Observation:
    return Observation(
        agent_id=agent,
        task_type=task_type,
        success=success,
        quality=quality,
        on_time=on_time,
        latency=latency,
        price=1.0,
        estimated_quality=est_q,
        estimated_latency=est_l,
        violation=not success,
    )


def test_profile_counts_and_rates() -> None:
    rep = MultiDimensionalReputation()
    for success in [True, True, True, False]:
        rep.record(obs(success, 0.8 if success else 0.0, est_q=0.9, est_l=12.0))
    profile = rep.profile("a")
    assert profile is not None
    assert profile.completed == 3
    assert profile.failed == 1
    assert profile.success_rate == pytest.approx(0.75)
    # Beta(1,1) posterior mean: (3 + 1) / (4 + 2)
    assert profile.success_estimate == pytest.approx(4 / 6)
    assert profile.avg_quality == pytest.approx(0.6)
    assert profile.quality_estimate_bias == pytest.approx((0.1 * 3 + 0.9) / 4)
    assert profile.latency_estimate_error == pytest.approx(0.2)
    assert profile.violations == pytest.approx(1)


def test_undelivered_work_does_not_count_toward_quality_or_calibration() -> None:
    rep = MultiDimensionalReputation()
    rep.record(obs(True, 0.8, est_q=0.9, est_l=12.0))
    undelivered = Observation(
        agent_id="a",
        task_type="sql",
        success=False,
        quality=0.0,
        on_time=False,
        latency=3.0,
        price=1.0,
        estimated_quality=0.9,
        estimated_latency=12.0,
        violation=True,
        delivered=False,
    )
    rep.record(undelivered)
    profile = rep.profile("a")
    assert profile is not None
    assert profile.success_rate == pytest.approx(0.5)
    assert profile.avg_quality == pytest.approx(0.8)
    assert profile.quality_estimate_bias == pytest.approx(0.1)
    assert profile.latency_estimate_error == pytest.approx(0.2)


def test_newcomer_gets_prior_and_unknown_profile() -> None:
    rep = MultiDimensionalReputation(prior_successes=3, prior_failures=1)
    assert rep.profile("nobody") is None
    features = rep.features("nobody", "sql")
    assert features.observations == 0
    assert features.success_estimate == pytest.approx(0.75)
    assert features.avg_quality is None


def test_task_specific_reputation() -> None:
    rep = MultiDimensionalReputation(task_specific=True)
    for _ in range(5):
        rep.record(obs(True, task_type="sql"))
        rep.record(obs(False, 0.0, task_type="research"))
    assert rep.features("a", "sql").success_estimate == pytest.approx(6 / 7)
    assert rep.features("a", "research").success_estimate == pytest.approx(1 / 7)
    assert rep.task_types("a") == ["research", "sql"]
    overall = MultiDimensionalReputation(task_specific=False)
    for _ in range(5):
        overall.record(obs(True, task_type="sql"))
        overall.record(obs(False, 0.0, task_type="research"))
    assert overall.features("a", "sql").success_estimate == pytest.approx(0.5)


def test_exponential_decay_favours_recent_performance() -> None:
    plain = MultiDimensionalReputation()
    decayed = MultiDimensionalReputation(decay=ExponentialDecay(half_life=2))
    history = [True] * 20 + [False] * 5
    for success in history:
        plain.record(obs(success))
        decayed.record(obs(success))
    p_plain = plain.profile("a")
    p_decay = decayed.profile("a")
    assert p_plain is not None
    assert p_decay is not None
    assert p_decay.success_rate is not None
    assert p_plain.success_rate == pytest.approx(0.8)
    assert p_decay.success_rate < 0.3


def test_exponential_weights_match_closed_form() -> None:
    rep = MultiDimensionalReputation(decay=ExponentialDecay(half_life=1))
    rep.record(obs(True))
    rep.record(obs(False, 0.0))
    profile = rep.profile("a")
    assert profile is not None
    # weights 0.5 (old success) and 1.0 (new failure)
    assert profile.success_rate == pytest.approx(0.5 / 1.5)


def test_rolling_window_matches_recomputation() -> None:
    rep = MultiDimensionalReputation(decay=RollingWindow(size=3))
    pattern = [True, False, True, True, False, False]
    for success in pattern:
        rep.record(obs(success, 1.0 if success else 0.0))
    profile = rep.profile("a")
    assert profile is not None
    assert profile.observations == 3
    assert profile.success_rate == pytest.approx(1 / 3)
    assert profile.avg_quality == pytest.approx(1 / 3)


def test_decay_specs() -> None:
    assert decay_from_spec(None).to_spec() == {"name": "none"}
    assert decay_from_spec({"name": "exponential", "half_life": 5}).to_spec()["half_life"] == 5
    assert decay_from_spec("rolling").to_spec()["name"] == "rolling"
    with pytest.raises(ValidationError):
        decay_from_spec("bogus")
    with pytest.raises(ValidationError):
        ExponentialDecay(half_life=0)


def test_baseline_systems() -> None:
    none = NoReputation()
    none.record(obs())
    assert none.features("a", "sql") == AgentFeatures(agent_id="a")
    static = StaticReputation({"a": {"agent_id": "a", "success_estimate": 0.9}})
    static.record(obs(False))
    assert static.features("a", None).success_estimate == 0.9
    assert static.features("b", None).success_estimate is None


@given(
    st.lists(
        st.tuples(st.booleans(), st.floats(0, 1), st.floats(0, 1), st.booleans()),
        min_size=1,
        max_size=60,
    ),
    st.sampled_from(["none", "exponential", "rolling"]),
)
def test_reputation_values_stay_in_range(
    history: list[tuple[bool, float, float, bool]], decay: str
) -> None:
    rep = MultiDimensionalReputation(decay=decay_from_spec({"name": decay}))
    for success, quality, estimate, on_time in history:
        rep.record(obs(success, quality, est_q=estimate, on_time=on_time))
    profile = rep.profile("a")
    assert profile is not None
    for value in (
        profile.success_rate,
        profile.success_estimate,
        profile.avg_quality,
        profile.on_time_rate,
        profile.quality_estimate_error,
    ):
        assert value is not None
        assert -1e-9 <= value <= 1 + 1e-9
    assert profile.quality_estimate_bias is not None
    assert -1 - 1e-9 <= profile.quality_estimate_bias <= 1 + 1e-9
