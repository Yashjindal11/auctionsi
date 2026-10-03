"""Capability discovery: who is *eligible* to bid. It never picks a winner."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from auctionsi.core.agent import Agent
from auctionsi.core.task import Task


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    candidates: list[Agent]
    excluded: dict[str, list[str]] = field(default_factory=dict)

    @property
    def candidate_ids(self) -> list[str]:
        return [a.agent_id for a in self.candidates]


def find_agents(
    task: Task,
    agents: Iterable[Agent],
    *,
    active_contracts: Mapping[str, int] | None = None,
    exclude: Iterable[str] = (),
    presorted: bool = False,
) -> DiscoveryResult:
    """Filter agents by availability, capability, formats, constraints and capacity.

    Candidates are returned sorted by agent id so discovery order never depends on
    registration order (pass ``presorted=True`` if ``agents`` already is).
    """
    active = active_contracts or {}
    banned = set(exclude)
    candidates: list[Agent] = []
    excluded: dict[str, list[str]] = {}
    ordered = agents if presorted else sorted(agents, key=lambda a: a.agent_id)
    for agent in ordered:
        reasons: list[str] = []
        if agent.agent_id in banned:
            reasons.append("excluded for this auction")
        if not agent.available:
            reasons.append("unavailable")
        capability = agent.capability(task.task_type)
        if capability is None:
            reasons.append(f"no capability {task.task_type!r}")
        else:
            reasons.extend(capability.incompatibilities(task))
        in_use = active.get(agent.agent_id, 0)
        if in_use >= agent.max_concurrent_tasks:
            reasons.append(f"at capacity ({in_use}/{agent.max_concurrent_tasks})")
        if reasons:
            excluded[agent.agent_id] = reasons
        else:
            candidates.append(agent)
    return DiscoveryResult(candidates, excluded)
