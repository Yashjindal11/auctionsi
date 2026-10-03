from __future__ import annotations

import itertools
import math
import random
import statistics

import pytest
from hypothesis import given
from hypothesis import strategies as st
from scipy import stats as sp

from auctionsi.statistics import (
    adjust,
    holm,
    paired_comparison,
    quantile,
    summarize,
    welch_comparison,
)


def test_summary_matches_scipy() -> None:
    rng = random.Random(0)
    data = [rng.gauss(10, 2) for _ in range(30)]
    s = summarize(data, 0.95)
    lo, hi = sp.t.interval(0.95, len(data) - 1, loc=s.mean, scale=sp.sem(data))
    assert s.ci_low == pytest.approx(lo)
    assert s.ci_high == pytest.approx(hi)
    assert s.sd == pytest.approx(sp.tstd(data))
    q = statistics.quantiles(data, n=4, method="inclusive")
    assert s.q25 == pytest.approx(q[0])
    assert s.q75 == pytest.approx(q[2])


def test_summary_edge_cases() -> None:
    one = summarize([3.0])
    assert one.ci_low == one.ci_high == 3.0
    constant = summarize([2.0, 2.0, 2.0])
    assert constant.sd == 0
    with pytest.raises(ValueError):
        summarize([])
    assert quantile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.5


def test_paired_comparison_matches_scipy() -> None:
    rng = random.Random(1)
    a = [rng.gauss(0, 1) for _ in range(20)]
    b = [x + 0.5 + rng.gauss(0, 0.3) for x in a]
    c = paired_comparison(a, b, metric="m")
    ref = sp.ttest_rel(b, a)
    assert c.statistic == pytest.approx(ref.statistic)
    assert c.p_value == pytest.approx(ref.pvalue)
    diffs = [y - x for x, y in zip(a, b, strict=True)]
    assert c.effect_size == pytest.approx(sum(diffs) / len(diffs) / sp.tstd(diffs))
    assert c.ci_low < c.mean_diff < c.ci_high
    assert c.significant()


def test_paired_degenerate_cases() -> None:
    same = paired_comparison([1, 2, 3], [1, 2, 3])
    assert same.p_value == 1.0
    shifted = paired_comparison([1, 2, 3], [2, 3, 4])
    assert shifted.p_value == 0.0
    assert shifted.relative_diff == pytest.approx(0.5)
    with pytest.raises(ValueError):
        paired_comparison([1], [1, 2])


def test_welch_matches_scipy() -> None:
    rng = random.Random(2)
    a = [rng.gauss(0, 1) for _ in range(15)]
    b = [rng.gauss(1, 3) for _ in range(25)]
    c = welch_comparison(a, b)
    ref = sp.ttest_ind(b, a, equal_var=False)
    assert c.statistic == pytest.approx(ref.statistic)
    assert c.p_value == pytest.approx(ref.pvalue)
    assert c.effect_size is not None


def test_holm() -> None:
    assert holm([0.01, 0.04, 0.03, None]) == [
        pytest.approx(0.03),
        pytest.approx(0.06),
        pytest.approx(0.06),
        None,
    ]
    comps = adjust([paired_comparison([1, 2, 3], [2, 3, 5])])
    assert comps[0].p_adjusted == comps[0].p_value


@given(st.lists(st.floats(0, 1), min_size=1, max_size=20))
def test_holm_is_monotone_and_bounded(ps: list[float]) -> None:
    adjusted = holm(ps)
    for p, q in zip(ps, adjusted, strict=True):
        assert q is not None
        assert p - 1e-12 <= q <= 1.0
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    values = [adjusted[i] for i in order]
    assert all(x <= y + 1e-12 for x, y in itertools.pairwise(values))  # type: ignore[operator]


@given(st.lists(st.floats(-1e6, 1e6), min_size=2, max_size=50))
def test_summary_invariants(values: list[float]) -> None:
    s = summarize(values)
    assert s.min <= s.q05 <= s.q25 <= s.median <= s.q75 <= s.q95 <= s.max
    assert s.ci_low <= s.mean + 1e-6 * max(1, abs(s.mean))
    assert math.isfinite(s.variance)
