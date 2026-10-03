"""Run a whole synthetic market on a simulated clock."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from auctionsi.core.agent import Agent
from auctionsi.core.task import Task
from auctionsi.market.clock import IdGenerator, ManualClock
from auctionsi.market.marketplace import Marketplace
from auctionsi.market.recovery import RecoveryPolicy
from auctionsi.market.result import AuctionResult
from auctionsi.market.validation import BidValidationConfig
from auctionsi.mechanisms.base import AuctionMechanism
from auctionsi.reputation.base import ReputationSystem
from auctionsi.selection.policies import SelectionPolicy
from auctionsi.settlement.policies import SettlementPolicy
from auctionsi.simulation.agents import SimulatedAgent
from auctionsi.simulation.generators import derive_seed, generate_agents, generate_tasks
from auctionsi.simulation.metrics import MarketMetrics, TaskRecord, compute_metrics
from auctionsi.simulation.verifier import SimulatedQualityVerifier
from auctionsi.verification.verifiers import Verifier


@dataclass(frozen=True)
class MarketChange:
    """Something that happens to the market at simulated time ``at``."""

    at: float
    apply: Callable[[Marketplace], None]
    description: str = ""


def agent_joins(at: float, agent: Agent) -> MarketChange:
    return MarketChange(at, lambda m: m.register(agent), f"{agent.agent_id} joins")


def agent_leaves(at: float, agent_id: str) -> MarketChange:
    def apply(market: Marketplace) -> None:
        market.unregister(agent_id)

    return MarketChange(at, apply, f"{agent_id} leaves")


def agent_changes(at: float, agent_id: str, **attributes: Any) -> MarketChange:
    """Change attributes of a registered agent (``available``, ``reliability``,
    ``cost_model``, ``strategy``, capabilities via ``capabilities=[...]``...)."""

    def apply(market: Marketplace) -> None:
        agent = market.get_agent(agent_id)
        for name, value in attributes.items():
            if name == "capabilities":
                agent.set_capabilities(value)
            elif not hasattr(agent, name):
                raise AttributeError(f"agent {agent_id} has no attribute {name!r}")
            else:
                setattr(agent, name, value)
        market.agent_updated(agent_id, **attributes)

    return MarketChange(at, apply, f"{agent_id} changes {sorted(attributes)}")


@dataclass
class SimulationResult:
    records: list[TaskRecord]
    market: Marketplace
    agents: list[Agent]
    seed: int
    wall_seconds: float
    auction_wall_seconds: list[float] = field(default_factory=list)
    _metrics: MarketMetrics | None = None

    @property
    def metrics(self) -> MarketMetrics:
        if self._metrics is None:
            ids = {a.agent_id for a in self.agents} | {a.agent_id for a in self.market.agents}
            self._metrics = compute_metrics(self.records, ids)
        return self._metrics

    def performance(self) -> dict[str, float]:
        """Wall-clock measurements. Not reproducible: excluded from seeded comparisons."""
        n = len(self.auction_wall_seconds)
        return {
            "wall_seconds": self.wall_seconds,
            "auctions_per_second": n / self.wall_seconds if self.wall_seconds > 0 else 0.0,
            "mean_auction_ms": 1000 * sum(self.auction_wall_seconds) / n if n else 0.0,
        }


def record_for(result: AuctionResult, agents: dict[str, Agent]) -> TaskRecord:
    task = result.task
    chain = result.chain()
    first = chain[0]
    awarded = tuple(a.agent_id for a in first.outcome.awards) if first.outcome else ()
    contracts = result.all_contracts
    eligible = [agents[a] for a in first.auction.participants if a in agents]
    true_costs = [a.expected_cost(task) for a in eligible if isinstance(a, SimulatedAgent)]
    winner = agents.get(awarded[0]) if awarded else None
    return TaskRecord(
        task_id=task.task_id,
        task_type=task.task_type,
        created_at=task.created_at,
        status=result.final.status.value,
        succeeded=result.succeeded,
        eligible=len(first.auction.participants),
        bids=len(first.auction.bids),
        rejected=len(first.auction.rejected),
        awarded=awarded,
        winners=tuple(result.winners),
        awarded_price=first.outcome.awards[0].bid.price
        if first.outcome and first.outcome.awards
        else None,
        buyer_cost=result.buyer_cost,
        quality=result.quality,
        latency=result.latency,
        attempts=len(contracts),
        value=task.value or 0.0,
        revenue_by_agent=tuple(
            (c.contract.agent_id, c.settlement.agent_revenue) for c in contracts
        ),
        cost_by_agent=tuple(
            (c.contract.agent_id, c.execution.actual_cost or 0.0) for c in contracts
        ),
        winner_true_cost=winner.expected_cost(task) if isinstance(winner, SimulatedAgent) else None,
        min_true_cost=min(true_costs) if true_costs else None,
        bidders=tuple(sorted(first.auction.bids)),
    )


def simulate_market(
    agents: int | Sequence[Agent] = 20,
    tasks: int | Sequence[Task] = 200,
    *,
    seed: int = 0,
    mechanism: AuctionMechanism | None = None,
    policy: SelectionPolicy | None = None,
    reputation: ReputationSystem | None = None,
    settlement: SettlementPolicy | None = None,
    recovery: RecoveryPolicy | None = None,
    verifier: Verifier | None = None,
    validation: BidValidationConfig | None = None,
    changes: Sequence[MarketChange] = (),
    keep_events: bool = False,
    disclose_clearing_price: bool = True,
    agent_options: dict[str, Any] | None = None,
    task_options: dict[str, Any] | None = None,
) -> SimulationResult:
    """Simulate a market. Integers generate agents/tasks with seeds derived from
    ``seed``; sequences are used as given. Runs are deterministic for a given seed
    and inputs (wall-clock performance numbers aside)."""
    agent_list = (
        generate_agents(agents, seed=derive_seed(seed, "agents"), **(agent_options or {}))
        if isinstance(agents, int)
        else list(agents)
    )
    task_list = (
        generate_tasks(tasks, seed=derive_seed(seed, "tasks"), **(task_options or {}))
        if isinstance(tasks, int)
        else list(tasks)
    )
    clock = ManualClock()
    market = Marketplace(
        "simulation",
        mechanism=mechanism,
        policy=policy,
        reputation=reputation,
        settlement=settlement,
        recovery=recovery,
        verifier=verifier or SimulatedQualityVerifier(),
        validation=validation,
        clock=clock,
        ids=IdGenerator(),
        keep_events=keep_events,
        retain_results=keep_events,
        disclose_clearing_price=disclose_clearing_price,
    )
    for agent in agent_list:
        market.register(agent)
    everyone: dict[str, Agent] = {a.agent_id: a for a in agent_list}
    pending = sorted(changes, key=lambda c: c.at)
    records = []
    timings = []
    started = time.perf_counter()
    for task in sorted(task_list, key=lambda t: (t.created_at, t.task_id)):
        while pending and pending[0].at <= task.created_at:
            change = pending.pop(0)
            clock.set(max(clock.now(), change.at))
            change.apply(market)
            everyone.update({a.agent_id: a for a in market.agents})
        clock.set(max(clock.now(), task.created_at))
        t0 = time.perf_counter()
        result = market.submit_task(task)
        timings.append(time.perf_counter() - t0)
        records.append(record_for(result, everyone))
    return SimulationResult(
        records=records,
        market=market,
        agents=list(everyone.values()),
        seed=seed,
        wall_seconds=time.perf_counter() - started,
        auction_wall_seconds=timings,
    )
