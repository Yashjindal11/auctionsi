"""Calibration: how well agents' claims (quality, latency) match what they delivered."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from statistics import fmean
from typing import Any

from auctionsi.reputation.base import Observation

QUALITY_BINS = ((0.0, 0.5), (0.5, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0001))


def calibration_table(observations: Iterable[Observation]) -> list[dict[str, Any]]:
    """Per agent: claimed vs delivered quality and latency over all observations."""
    by_agent: defaultdict[str, list[Observation]] = defaultdict(list)
    for obs in observations:
        by_agent[obs.agent_id].append(obs)
    rows = []
    for agent_id in sorted(by_agent):
        history = by_agent[agent_id]
        delivered = [o for o in history if o.delivered]
        q = [(o.estimated_quality, o.quality) for o in delivered if o.estimated_quality is not None]
        lat = [
            abs(o.estimated_latency - o.latency) / o.latency
            for o in delivered
            if o.estimated_latency is not None and o.latency > 0
        ]
        rows.append(
            {
                "agent_id": agent_id,
                "observations": len(history),
                "success_rate": fmean(o.success for o in history),
                "claimed_quality": fmean(c for c, _ in q) if q else None,
                "delivered_quality": fmean(a for _, a in q) if q else None,
                "quality_bias": fmean(c - a for c, a in q) if q else None,
                "quality_mae": fmean(abs(c - a) for c, a in q) if q else None,
                "latency_relative_error": fmean(lat) if lat else None,
            }
        )
    return rows


def reliability_bins(observations: Iterable[Observation]) -> list[dict[str, Any]]:
    """Delivered quality grouped by claimed quality (a reliability diagram in a table)."""
    rows = []
    pairs = [
        (o.estimated_quality, o.quality)
        for o in observations
        if o.estimated_quality is not None and o.delivered
    ]
    for lo, hi in QUALITY_BINS:
        members = [(c, a) for c, a in pairs if lo <= c < hi]
        rows.append(
            {
                "claimed_from": lo,
                "claimed_to": min(hi, 1.0),
                "count": len(members),
                "mean_claimed": fmean(c for c, _ in members) if members else None,
                "mean_delivered": fmean(a for _, a in members) if members else None,
            }
        )
    return rows


def _f(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def calibration_report(observations: Sequence[Observation]) -> str:
    lines = [
        "# Calibration report",
        "",
        "Claims come from bids; delivered quality comes from verification. Positive bias means",
        "the agent promised more than it delivered.",
        "",
        "| agent | n | success | claimed q | delivered q | bias | MAE | latency error |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in calibration_table(observations):
        lines.append(
            f"| {r['agent_id']} | {r['observations']} | {_f(r['success_rate'])} | "
            f"{_f(r['claimed_quality'])} | {_f(r['delivered_quality'])} | {_f(r['quality_bias'])} | "
            f"{_f(r['quality_mae'])} | {_f(r['latency_relative_error'])} |"
        )
    lines += [
        "",
        "## Delivered quality by claimed quality",
        "",
        "| claimed | n | mean claimed | mean delivered |",
        "|---|---|---|---|",
    ]
    for b in reliability_bins(observations):
        lines.append(
            f"| {b['claimed_from']:.1f}-{b['claimed_to']:.1f} | {b['count']} | "
            f"{_f(b['mean_claimed'])} | {_f(b['mean_delivered'])} |"
        )
    lines.append("")
    return "\n".join(lines)
