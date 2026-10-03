"""Descriptive statistics and comparisons for experiment results.

Comparisons are reported as effect sizes with confidence intervals first; p-values
are secondary and Holm-adjusted across the comparisons in one report so running
many metrics does not manufacture "significant" findings.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from statistics import fmean, median
from typing import Any

from scipy import stats


def _clean(value: float) -> float | None:
    return None if value is None or not math.isfinite(value) else float(value)


@dataclass(frozen=True, slots=True)
class Summary:
    n: int
    mean: float
    median: float
    variance: float
    sd: float
    ci_low: float
    ci_high: float
    confidence: float
    min: float
    max: float
    q05: float
    q25: float
    q75: float
    q95: float

    def to_dict(self) -> dict[str, Any]:
        return {k: (_clean(v) if isinstance(v, float) else v) for k, v in asdict(self).items()}


def quantile(sorted_values: Sequence[float], q: float) -> float:
    """Linear-interpolation quantile (NumPy's default "linear" method)."""
    if not sorted_values:
        raise ValueError("no values")
    pos = (len(sorted_values) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    frac = pos - lo
    lo_value = sorted_values[lo]
    return lo_value + (sorted_values[hi] - lo_value) * frac


def summarize(values: Sequence[float], confidence: float = 0.95) -> Summary:
    """Mean with a Student-t confidence interval, plus spread and quantiles."""
    data = sorted(float(v) for v in values)
    n = len(data)
    if n == 0:
        raise ValueError("cannot summarise an empty sample")
    mean = fmean(data)
    variance = sum((x - mean) ** 2 for x in data) / (n - 1) if n > 1 else 0.0
    sd = math.sqrt(variance)
    if n > 1 and sd > 0:
        half = float(stats.t.ppf((1 + confidence) / 2, n - 1)) * sd / math.sqrt(n)
    else:
        half = 0.0
    return Summary(
        n=n,
        mean=mean,
        median=median(data),
        variance=variance,
        sd=sd,
        ci_low=mean - half,
        ci_high=mean + half,
        confidence=confidence,
        min=data[0],
        max=data[-1],
        q05=quantile(data, 0.05),
        q25=quantile(data, 0.25),
        q75=quantile(data, 0.75),
        q95=quantile(data, 0.95),
    )


@dataclass(frozen=True, slots=True)
class Comparison:
    """``treatment - baseline``. ``effect_size`` is Cohen's d_z for paired designs
    (mean difference / SD of differences) and Hedges' g for independent samples."""

    metric: str
    baseline: str
    treatment: str
    design: str
    n: int
    mean_diff: float
    ci_low: float
    ci_high: float
    statistic: float | None
    p_value: float | None
    effect_size: float | None
    p_adjusted: float | None = None
    relative_diff: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: (_clean(v) if isinstance(v, float) else v) for k, v in asdict(self).items()}

    def significant(self, alpha: float = 0.05) -> bool:
        p = self.p_adjusted if self.p_adjusted is not None else self.p_value
        return p is not None and p < alpha


def paired_comparison(
    baseline: Sequence[float],
    treatment: Sequence[float],
    *,
    metric: str = "",
    baseline_name: str = "baseline",
    treatment_name: str = "treatment",
    confidence: float = 0.95,
) -> Comparison:
    """Paired t-test on per-replication differences (arms share random numbers)."""
    if len(baseline) != len(treatment):
        raise ValueError("paired samples must have equal length")
    diffs = [t - b for b, t in zip(baseline, treatment, strict=True)]
    n = len(diffs)
    if n == 0:
        raise ValueError("no pairs")
    s = summarize(diffs, confidence)
    base_mean = fmean(baseline)
    relative = s.mean / base_mean if base_mean else None
    if n < 2:
        statistic = p = effect = None
    elif s.sd == 0:
        statistic = None
        p = 1.0 if s.mean == 0 else 0.0
        effect = None
    else:
        statistic = s.mean / (s.sd / math.sqrt(n))
        p = float(2 * stats.t.sf(abs(statistic), n - 1))
        effect = s.mean / s.sd
    return Comparison(
        metric,
        baseline_name,
        treatment_name,
        "paired",
        n,
        s.mean,
        s.ci_low,
        s.ci_high,
        statistic,
        p,
        effect,
        relative_diff=relative,
    )


def welch_comparison(
    baseline: Sequence[float],
    treatment: Sequence[float],
    *,
    metric: str = "",
    baseline_name: str = "baseline",
    treatment_name: str = "treatment",
    confidence: float = 0.95,
) -> Comparison:
    """Welch's unequal-variance t-test for independent samples."""
    a, b = summarize(baseline, confidence), summarize(treatment, confidence)
    diff = b.mean - a.mean
    se2 = a.variance / a.n + b.variance / b.n
    if a.n < 2 or b.n < 2 or se2 == 0:
        return Comparison(
            metric,
            baseline_name,
            treatment_name,
            "independent",
            a.n + b.n,
            diff,
            diff,
            diff,
            None,
            None,
            None,
        )
    se = math.sqrt(se2)
    df = se2**2 / ((a.variance / a.n) ** 2 / (a.n - 1) + (b.variance / b.n) ** 2 / (b.n - 1))
    half = float(stats.t.ppf((1 + confidence) / 2, df)) * se
    statistic = diff / se
    p = float(2 * stats.t.sf(abs(statistic), df))
    pooled = math.sqrt(((a.n - 1) * a.variance + (b.n - 1) * b.variance) / (a.n + b.n - 2))
    correction = 1 - 3 / (4 * (a.n + b.n) - 9)
    g = diff / pooled * correction if pooled > 0 else None
    return Comparison(
        metric,
        baseline_name,
        treatment_name,
        "independent",
        a.n + b.n,
        diff,
        diff - half,
        diff + half,
        statistic,
        p,
        g,
        relative_diff=diff / a.mean if a.mean else None,
    )


def holm(p_values: Sequence[float | None]) -> list[float | None]:
    """Holm-Bonferroni adjusted p-values (``None`` entries are left out)."""
    indexed = sorted((p, i) for i, p in enumerate(p_values) if p is not None)
    m = len(indexed)
    adjusted: list[float | None] = [None] * len(p_values)
    running = 0.0
    for rank, (p, i) in enumerate(indexed):
        running = max(running, min(1.0, (m - rank) * p))
        adjusted[i] = running
    return adjusted


def adjust(comparisons: Sequence[Comparison]) -> list[Comparison]:
    adjusted = holm([c.p_value for c in comparisons])
    return [replace(c, p_adjusted=p) for c, p in zip(comparisons, adjusted, strict=True)]
