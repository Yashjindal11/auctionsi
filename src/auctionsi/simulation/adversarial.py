"""Adversarial and strategic market participants, for robustness research.

These helpers model *market* misbehaviour (misreporting, collusion, identity
inflation, reputation gaming) inside a simulation so that mechanisms and defences
can be compared. They contain no networking or exploitation code.
"""

from __future__ import annotations

import copy
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from auctionsi.bidding.strategies import BUILTIN_STRATEGIES, BidInputs, BidStrategy
from auctionsi.core.agent import Agent
from auctionsi.core.capability import Capability
from auctionsi.simulation.agents import SimulatedAgent
from auctionsi.simulation.generators import derive_seed
from auctionsi.simulation.market import MarketChange, agent_changes
from auctionsi.simulation.metrics import MarketMetrics, TaskRecord
from auctionsi.statistics.concentration import hhi


@dataclass
class CollusionRing:
    """Members agree in advance who should win each task (rotating by task id among
    members able to do it). The designated member bids ``winner_markup`` over cost;
    the others submit cover bids at ``cover_markup`` (or abstain)."""

    winner_markup: float = 0.6
    cover_markup: float = 1.2
    abstain_instead_of_cover: bool = False
    members: dict[str, frozenset[str]] = field(default_factory=dict)

    def designated(self, task_id: str, task_type: str) -> str | None:
        able = sorted(m for m, caps in self.members.items() if task_type in caps)
        if not able:
            return None
        return able[derive_seed(0, "ring", task_id) % len(able)]


@dataclass
class CollusiveStrategy(BidStrategy):
    ring: CollusionRing = field(default_factory=CollusionRing)
    member_id: str = ""
    name = "collusive"

    def price(self, inputs: BidInputs) -> float | None:
        chosen = self.ring.designated(inputs.task.task_id, inputs.task.task_type)
        if chosen == self.member_id:
            return inputs.cost * (1 + self.ring.winner_markup)
        if self.ring.abstain_instead_of_cover:
            return None
        return inputs.cost * (1 + self.ring.cover_markup)

    def revise(self, inputs: BidInputs, view: Any) -> float | None:
        return None

    def to_spec(self) -> dict[str, Any]:
        return {"name": self.name, "member_id": self.member_id}


def form_ring(agents: Iterable[SimulatedAgent], ring: CollusionRing | None = None) -> CollusionRing:
    """Turn ``agents`` into colluding ring members (replaces their strategies)."""
    ring = ring or CollusionRing()
    for agent in agents:
        ring.members[agent.agent_id] = frozenset(c.name for c in agent.capabilities)
        agent.strategy = CollusiveStrategy(ring=ring, member_id=agent.agent_id)
    return ring


def make_sybils(
    template: SimulatedAgent, count: int, *, prefix: str | None = None
) -> list[SimulatedAgent]:
    """``count`` extra identities controlled by the same operator as ``template``.
    They share its quality, cost, reliability and strategy type, and declare the same
    ``metadata["operator"]`` (which a defence can only use if identities are verified)."""
    out = []
    base = prefix or f"{template.agent_id}-sybil"
    for i in range(count):
        out.append(
            SimulatedAgent(
                f"{base}-{i}",
                capabilities=template.capabilities,
                cost_model=template.cost_model,
                quality=template.quality,
                quality_sd=template.quality_sd,
                reliability=template.reliability,
                latency_mean=template.latency_mean,
                latency_sigma=template.latency_sigma,
                strategy=_copy_strategy(template.strategy),
                quality_report_bias=template.quality_report_bias,
                seed=derive_seed(template.seed, "sybil", i),
                operator=template.operator,
                max_concurrent_tasks=template.max_concurrent_tasks,
            )
        )
    return out


def _copy_strategy(strategy: BidStrategy) -> BidStrategy:
    """Fresh (unlearned) copy for built-in strategies; a deep copy otherwise."""
    spec = strategy.to_spec()
    factory = BUILTIN_STRATEGIES.get(spec.get("name", ""))
    if factory is not None:
        return factory(**{k: v for k, v in spec.items() if k != "name"})
    return copy.deepcopy(strategy)


def overstate_quality(agents: Iterable[SimulatedAgent], amount: float) -> None:
    """Agents claim ``amount`` more quality (and confidence) than they deliver."""
    for agent in agents:
        agent.quality_report_bias = amount


def add_fake_capability(agent: SimulatedAgent, capability: str, true_quality: float = 0.05) -> None:
    """The agent claims ``capability`` but its real quality on it is ``true_quality``."""
    qualities = (
        dict(agent.quality)
        if not isinstance(agent.quality, int | float)
        else {c.name: float(agent.quality) for c in agent.capabilities}
    )
    qualities[capability] = true_quality
    agent.quality = qualities
    agent.set_capabilities([*agent.capabilities, Capability(name=capability)])


def exit_scam(agent_id: str, at: float, reliability: float = 0.05) -> MarketChange:
    """Reputation attack: behave well, then collapse reliability at time ``at``."""
    return agent_changes(at, agent_id, reliability=reliability)


def operator_hhi(records: Sequence[TaskRecord], agents: Iterable[Agent]) -> float:
    """HHI of successful wins aggregated by *operator* rather than by identity."""
    operator = {a.agent_id: str(a.metadata.get("operator", a.agent_id)) for a in agents}
    wins: Counter[str] = Counter()
    for r in records:
        for w in r.winners:
            wins[operator.get(w, w)] += 1
    return hhi({k: float(v) for k, v in wins.items()})


def price_inflation(baseline: MarketMetrics, treated: MarketMetrics) -> float | None:
    """Relative change in average cost per successful task: treated / baseline - 1."""
    if not baseline.average_cost or treated.average_cost is None:
        return None
    return treated.average_cost / baseline.average_cost - 1
