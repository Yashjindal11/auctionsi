"""Market concentration measures.

* HHI (Herfindahl-Hirschman index) = sum of squared shares, on a 0-1 scale
  (1 = monopoly, 1/n = n equal participants). Multiply by 10,000 for the
  antitrust convention.
* Gini coefficient of a non-negative quantity (0 = perfectly equal, approaching 1
  = one participant has everything). Include zero-valued participants explicitly:
  agents that never win matter for fairness questions.
* Top-k share = combined share of the k largest participants.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def shares(values: Mapping[str, float]) -> dict[str, float]:
    total = sum(values.values())
    if total <= 0:
        return {k: 0.0 for k in values}
    return {k: v / total for k, v in values.items()}


def hhi(values: Mapping[str, float] | Sequence[float]) -> float:
    vals = list(values.values()) if isinstance(values, Mapping) else list(values)
    total = sum(vals)
    if total <= 0:
        return 0.0
    return sum((v / total) ** 2 for v in vals)


def gini(values: Sequence[float]) -> float:
    vals = sorted(values)
    n = len(vals)
    total = sum(vals)
    if n == 0 or total <= 0:
        return 0.0
    if any(v < 0 for v in vals):
        raise ValueError("gini is defined here for non-negative values only")
    weighted = sum((i + 1) * v for i, v in enumerate(vals))
    return (2 * weighted) / (n * total) - (n + 1) / n


def top_share(values: Mapping[str, float] | Sequence[float], k: int = 1) -> float:
    vals = sorted(values.values() if isinstance(values, Mapping) else values, reverse=True)
    total = sum(vals)
    if total <= 0:
        return 0.0
    return sum(vals[:k]) / total
