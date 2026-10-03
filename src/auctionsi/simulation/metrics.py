"""Market-level metrics computed from simulation records.

Every metric has an explicit definition here (and in ``docs/metrics.md``). None of
them is *the* measure of a good market; they are inputs to a research question.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from statistics import fmean, median, pstdev, stdev
from typing import Any

from auctionsi.statistics.concentration import gini, hhi, shares, top_share


@dataclass(frozen=True, slots=True)
class TaskRecord:
    """One task's outcome in a simulation, including simulator-only ground truth."""

    task_id: str
    task_type: str
    created_at: float
    status: str
    succeeded: bool
    eligible: int
    bids: int
    rejected: int
    awarded: tuple[str, ...]
    winners: tuple[str, ...]
    awarded_price: float | None
    buyer_cost: float
    quality: float | None
    latency: float | None
    attempts: int
    value: float
    revenue_by_agent: tuple[tuple[str, float], ...]
    cost_by_agent: tuple[tuple[str, float], ...]
    winner_true_cost: float | None
    min_true_cost: float | None
    bidders: tuple[str, ...]
    bid_prices: tuple[float, ...] = ()
    verification_cost: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MarketMetrics:
    """Definitions (all over the tasks in one run):

    - ``completion_rate`` = successful tasks / tasks.
    - ``total_cost`` = sum of buyer cost (payments + bonuses - penalties) over all
      tasks, including failed attempts that were partially paid.
    - ``average_cost`` / ``median_cost`` = buyer cost per *successful* task.
    - ``average_quality`` = mean verified quality over successful tasks.
    - ``average_latency`` = mean total execution time over tasks with an award.
    - ``agent_utilization`` = each agent's share of all contracts executed.
    - ``hhi`` / ``top_agent_share`` = concentration of *successful* wins.
    - ``revenue_gini`` = Gini of revenue across *all* agents (zeros included).
    - ``buyer_utility`` = sum(value of successful tasks) - total_cost - verification cost.
    - ``agent_utility`` = sum(agent revenue) - sum(agent execution cost).
    - ``total_surplus`` = buyer_utility + agent_utility
      (= value delivered - real resources consumed; payments cancel out).
    - ``cost_efficiency`` = mean over awarded tasks of
      (lowest true expected cost among eligible agents) / (awarded agent's true
      expected cost). 1.0 means the cheapest *capable* agent always won; it ignores
      quality and reliability on purpose, so read it alongside them.
    - ``quality_adjusted_cost`` = total_cost / sum(quality of successful tasks).
    - ``participation_rate`` = agents that bid at least once / agents.
    - ``opportunity_rate`` = agents that won at least once / agents.
    - ``average_winning_markup`` = mean over awarded tasks of
      (awarded bid price / awarded agent's true expected cost) - 1: how far winning
      bids sit above true cost (bid shading).
    - ``total_verification_cost`` = sum of verifier-reported costs.
    - ``bid_cv`` = mean coefficient of variation (sd / mean) of the valid bids in each
      auction with at least 3 bids. A classic collusion screen: unusually low or
      high dispersion is worth a look, never proof.
    - ``relative_distance`` = mean over auctions with at least 3 bids of
      (second-lowest - lowest) / sd(losing bids). Cover bidding tends to leave the
      designated winner far below a tight cluster of covers, raising it.
    """

    total_tasks: int
    successful_tasks: int
    failed_tasks: int
    no_bid_tasks: int
    completion_rate: float
    total_cost: float
    average_cost: float | None
    median_cost: float | None
    average_quality: float | None
    average_latency: float | None
    average_bid_count: float
    average_eligible: float
    average_attempts: float
    hhi: float
    top_agent_share: float
    revenue_gini: float
    buyer_utility: float
    agent_utility: float
    total_surplus: float
    cost_efficiency: float | None
    quality_adjusted_cost: float | None
    participation_rate: float
    opportunity_rate: float
    average_winning_markup: float | None = None
    total_verification_cost: float = 0.0
    bid_cv: float | None = None
    relative_distance: float | None = None
    agent_utilization: dict[str, float] = field(default_factory=dict)
    agent_wins: dict[str, int] = field(default_factory=dict)
    agent_revenue: dict[str, float] = field(default_factory=dict)
    agent_profit: dict[str, float] = field(default_factory=dict)

    SCALARS = (
        "total_tasks",
        "successful_tasks",
        "failed_tasks",
        "no_bid_tasks",
        "completion_rate",
        "total_cost",
        "average_cost",
        "median_cost",
        "average_quality",
        "average_latency",
        "average_bid_count",
        "average_eligible",
        "average_attempts",
        "hhi",
        "top_agent_share",
        "revenue_gini",
        "buyer_utility",
        "agent_utility",
        "total_surplus",
        "cost_efficiency",
        "quality_adjusted_cost",
        "participation_rate",
        "opportunity_rate",
        "average_winning_markup",
        "total_verification_cost",
        "bid_cv",
        "relative_distance",
    )

    def scalars(self) -> dict[str, float | None]:
        return {name: getattr(self, name) for name in self.SCALARS}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_metrics(records: Sequence[TaskRecord], agent_ids: Iterable[str]) -> MarketMetrics:
    agents = sorted(set(agent_ids))
    n = len(records)
    successes = [r for r in records if r.succeeded]
    no_bids = [r for r in records if r.bids == 0]
    awarded = [r for r in records if r.awarded]
    contracts: Counter[str] = Counter()
    wins: Counter[str] = Counter()
    revenue: defaultdict[str, float] = defaultdict(float)
    costs: defaultdict[str, float] = defaultdict(float)
    bidders: set[str] = set()
    for r in records:
        for agent_id, amount in r.revenue_by_agent:
            revenue[agent_id] += amount
            contracts[agent_id] += 1
        for agent_id, amount in r.cost_by_agent:
            costs[agent_id] += amount
        for agent_id in r.winners:
            wins[agent_id] += 1
        bidders.update(r.bidders)
    total_cost = sum(r.buyer_cost for r in records)
    success_costs = [r.buyer_cost for r in successes]
    qualities = [r.quality for r in successes if r.quality is not None]
    efficiencies = [
        r.min_true_cost / r.winner_true_cost
        for r in awarded
        if r.min_true_cost is not None and r.winner_true_cost
    ]
    value = sum(r.value for r in successes)
    verification = sum(r.verification_cost for r in records)
    agent_utility = sum(revenue.values()) - sum(costs.values())
    buyer_utility = value - total_cost - verification
    markups = [
        r.awarded_price / r.winner_true_cost - 1
        for r in awarded
        if r.awarded_price is not None and r.winner_true_cost
    ]
    cvs, distances = [], []
    for r in records:
        if len(r.bid_prices) < 3:
            continue
        prices = sorted(r.bid_prices)
        mean = fmean(prices)
        if mean > 0:
            cvs.append(pstdev(prices) / mean)
        losing_sd = stdev(prices[1:])
        if losing_sd > 0:
            distances.append((prices[1] - prices[0]) / losing_sd)
    win_counts = {a: float(wins.get(a, 0)) for a in agents} or dict(wins)
    return MarketMetrics(
        total_tasks=n,
        successful_tasks=len(successes),
        failed_tasks=n - len(successes) - len(no_bids),
        no_bid_tasks=len(no_bids),
        completion_rate=len(successes) / n if n else 0.0,
        total_cost=total_cost,
        average_cost=fmean(success_costs) if success_costs else None,
        median_cost=median(success_costs) if success_costs else None,
        average_quality=fmean(qualities) if qualities else None,
        average_latency=fmean([r.latency for r in awarded if r.latency is not None])
        if awarded
        else None,
        average_bid_count=fmean([r.bids for r in records]) if records else 0.0,
        average_eligible=fmean([r.eligible for r in records]) if records else 0.0,
        average_attempts=fmean([r.attempts for r in awarded]) if awarded else 0.0,
        hhi=hhi(win_counts),
        top_agent_share=top_share(win_counts),
        revenue_gini=gini([max(0.0, revenue.get(a, 0.0)) for a in agents]),
        buyer_utility=buyer_utility,
        agent_utility=agent_utility,
        total_surplus=buyer_utility + agent_utility,
        cost_efficiency=fmean(efficiencies) if efficiencies else None,
        quality_adjusted_cost=total_cost / sum(qualities) if sum(qualities) > 0 else None,
        participation_rate=len(bidders & set(agents)) / len(agents) if agents else 0.0,
        opportunity_rate=sum(1 for a in agents if wins.get(a)) / len(agents) if agents else 0.0,
        average_winning_markup=fmean(markups) if markups else None,
        total_verification_cost=verification,
        bid_cv=fmean(cvs) if cvs else None,
        relative_distance=fmean(distances) if distances else None,
        agent_utilization=shares({a: float(c) for a, c in contracts.items()}),
        agent_wins=dict(wins),
        agent_revenue=dict(revenue),
        agent_profit={
            a: revenue.get(a, 0.0) - costs.get(a, 0.0) for a in set(revenue) | set(costs)
        },
    )


def concentration_over_time(records: Sequence[TaskRecord], window: int = 100) -> list[float]:
    """HHI of successful wins in consecutive windows of ``window`` tasks."""
    out = []
    for start in range(0, len(records), window):
        chunk = records[start : start + window]
        counts = Counter(w for r in chunk for w in r.winners)
        out.append(hhi({k: float(v) for k, v in counts.items()}))
    return out
