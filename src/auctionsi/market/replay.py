"""Reconstruct an auction from its event history and re-derive the decision.

Replay re-runs winner determination from the *recorded* inputs (final bids,
reputation features snapshot, mechanism and policy specs) with freshly built
plugins, and checks that the same winners and payments come out. It does not
re-execute agents: execution, verification and settlement are reported from the
record, because agents are external and may not be deterministic.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from auctionsi.core.bid import Bid
from auctionsi.core.task import Task
from auctionsi.errors import NotFoundError
from auctionsi.market.events import Event, EventType
from auctionsi.market.trace import format_trace
from auctionsi.plugins import PluginRegistry, default_registry
from auctionsi.reputation.base import AgentFeatures

E = EventType


@dataclass
class ReplayReport:
    auction_id: str
    trace: list[str]
    recorded_awards: list[dict[str, Any]] = field(default_factory=list)
    replayed_awards: list[dict[str, Any]] = field(default_factory=list)
    recorded_ranking: list[str] = field(default_factory=list)
    replayed_ranking: list[str] = field(default_factory=list)
    replayable: bool = True
    differences: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def matches(self) -> bool:
        return self.replayable and not self.differences

    def to_text(self) -> str:
        lines = [f"Replay of {self.auction_id}", "", *self.trace, ""]
        if not self.replayable:
            lines.append("Decision not replayable: " + "; ".join(self.notes))
            return "\n".join(lines)
        lines.append("Recorded awards: " + _awards(self.recorded_awards))
        lines.append("Replayed awards: " + _awards(self.replayed_awards))
        if self.matches:
            lines.append("Result: the recorded decision was reproduced exactly.")
        else:
            lines.append("Result: MISMATCH")
            lines += [f"  - {d}" for d in self.differences]
        lines += [f"Note: {n}" for n in self.notes]
        return "\n".join(lines)


def _awards(awards: list[dict[str, Any]]) -> str:
    if not awards:
        return "none"
    return ", ".join(f"{a['agent_id']} @ {a['payment']:.6g}" for a in awards)


def _first(events: Sequence[Event], type: EventType) -> Event | None:
    return next((e for e in events if e.type == type), None)


def replay_auction(
    events: Sequence[Event], *, plugins: PluginRegistry | None = None
) -> ReplayReport:
    """Rebuild and verify an auction from the events that carry its ``auction_id``."""
    if not events:
        raise NotFoundError("no events to replay")
    ordered = sorted(events, key=lambda e: e.seq)
    created = _first(ordered, E.AUCTION_CREATED)
    if created is None or created.auction_id is None:
        raise NotFoundError("event history has no AuctionCreated event")
    report = ReplayReport(created.auction_id, format_trace(ordered))
    closed = _first(ordered, E.AUCTION_CLOSED)
    selected = _first(ordered, E.WINNER_SELECTED)
    if closed is None:
        report.replayable = False
        report.notes.append("auction never closed")
        return report
    if selected is None:
        report.notes.append("no winner was selected; nothing to re-derive")
        if closed.data.get("valid", 0):
            report.differences.append("valid bids existed but no WinnerSelected event")
        return report

    recorded = selected.data["outcome"]
    report.recorded_awards = [
        {"agent_id": a["agent_id"], "payment": a["payment"]} for a in recorded["awards"]
    ]
    report.recorded_ranking = [s["agent_id"] for s in recorded["ranking"]]

    policy_spec = dict(selected.data["policy"])
    if policy_spec.pop("callable", False):
        report.replayable = False
        report.notes.append(f"policy {policy_spec['name']!r} is a Python callable without a spec")
        return report
    registry = plugins or default_registry()
    try:
        mechanism = registry.mechanisms.create(selected.data["mechanism"])
        policy = registry.policies.create(selected.data["policy"])
    except Exception as exc:
        report.replayable = False
        report.notes.append(f"cannot rebuild plugins: {exc}")
        return report

    task = Task.from_dict(created.data["task"])
    bids = [Bid.from_dict(b) for b in closed.data["final_bids"]]
    features = {k: AgentFeatures.from_dict(v) for k, v in selected.data["features"].items()}
    outcome = mechanism.determine_winners(bids, task, policy, features)
    report.replayed_awards = [
        {"agent_id": a.agent_id, "payment": a.payment} for a in outcome.awards
    ]
    report.replayed_ranking = [s.agent_id for s in outcome.ranking]

    if report.replayed_ranking != report.recorded_ranking:
        report.differences.append(
            f"ranking differs: recorded {report.recorded_ranking}, replayed {report.replayed_ranking}"
        )
    if len(report.replayed_awards) != len(report.recorded_awards):
        report.differences.append("different number of awards")
    for rec, rep in zip(report.recorded_awards, report.replayed_awards, strict=False):
        if rec["agent_id"] != rep["agent_id"]:
            report.differences.append(f"winner {rec['agent_id']} replayed as {rep['agent_id']}")
        elif not math.isclose(rec["payment"], rep["payment"], rel_tol=1e-9, abs_tol=1e-12):
            report.differences.append(
                f"payment to {rec['agent_id']}: recorded {rec['payment']}, replayed {rep['payment']}"
            )
    return report
