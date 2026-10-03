"""Synthetic agent and task generators. Same arguments + same seed = same output."""

from __future__ import annotations

import hashlib
import random
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from auctionsi.bidding.strategies import BUILTIN_STRATEGIES, BidStrategy
from auctionsi.core.agent import CostModel
from auctionsi.core.task import Task
from auctionsi.errors import ConfigurationError
from auctionsi.simulation.agents import SimulatedAgent
from auctionsi.simulation.distributions import (
    Beta,
    Constant,
    Distribution,
    DistributionSpec,
    LogNormal,
    Uniform,
    as_distribution,
)

DEFAULT_TASK_TYPES: tuple[str, ...] = ("research", "data_analysis", "sql", "optimization")

COST_PRESETS: dict[str, Distribution] = {
    "lognormal": LogNormal(median=0.03, sigma=0.5),
    "uniform": Uniform(0.01, 0.06),
    "constant": Constant(0.03),
}
QUALITY_PRESETS: dict[str, Distribution] = {
    "beta": Beta(8, 2),
    "uniform": Uniform(0.5, 1.0),
    "high": Beta(18, 2),
}
LATENCY_PRESETS: dict[str, Distribution] = {
    "lognormal": LogNormal(median=10.0, sigma=0.5),
    "uniform": Uniform(2.0, 20.0),
}
RELIABILITY_PRESETS: dict[str, Distribution] = {
    "beta": Beta(18, 2),
    "uniform": Uniform(0.7, 1.0),
    "perfect": Constant(1.0),
}
BUDGET_PRESETS: dict[str, Distribution] = {
    "lognormal": LogNormal(median=0.12, sigma=0.3),
    "uniform": Uniform(0.06, 0.2),
}
DEADLINE_PRESETS: dict[str, Distribution] = {"uniform": Uniform(20.0, 60.0)}
COMPLEXITY_PRESETS: dict[str, Distribution] = {
    "lognormal": LogNormal(median=1.0, sigma=0.3),
    "constant": Constant(1.0),
}


def derive_seed(seed: int, *labels: object) -> int:
    """Stable child seed (independent of ``PYTHONHASHSEED``)."""
    text = ":".join([str(seed), *map(str, labels)])
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big")


StrategySpec = str | Mapping[str, Any] | BidStrategy | Callable[[int, random.Random], BidStrategy]


def _strategy_factory(spec: StrategySpec) -> Callable[[int, random.Random], BidStrategy]:
    if callable(spec) and not isinstance(spec, BidStrategy):
        return spec
    if isinstance(spec, BidStrategy):
        raise ConfigurationError(
            "pass a strategy name/spec or a factory: one strategy instance cannot be "
            "shared by many agents because adaptive strategies keep state"
        )
    if isinstance(spec, str):
        spec = {"name": spec}
    name = spec.get("name")
    if name not in BUILTIN_STRATEGIES:
        raise ConfigurationError(f"unknown strategy {name!r}; known: {sorted(BUILTIN_STRATEGIES)}")
    params = {k: v for k, v in spec.items() if k != "name"}
    factory = BUILTIN_STRATEGIES[str(name)]
    return lambda i, rng: factory(**params)


def generate_agents(
    count: int,
    *,
    seed: int = 0,
    capabilities: Sequence[str] = DEFAULT_TASK_TYPES,
    capability_distribution: str = "mixed",
    capabilities_per_agent: tuple[int, int] = (1, 3),
    cost_distribution: DistributionSpec = "lognormal",
    variable_cost_ratio: float = 0.01,
    quality_distribution: DistributionSpec = "beta",
    quality_spread: float = 0.05,
    latency_distribution: DistributionSpec = "lognormal",
    reliability_distribution: DistributionSpec = "beta",
    capacity_distribution: DistributionSpec = 1,
    strategy: StrategySpec = "cost_plus",
    quality_report_bias: float = 0.0,
    prefix: str = "agent",
) -> list[SimulatedAgent]:
    """Generate ``count`` simulated agents.

    ``capability_distribution``: ``"mixed"`` (each agent gets a random subset of
    size within ``capabilities_per_agent``), ``"specialist"`` (exactly one) or
    ``"generalist"`` (all). Fixed cost is drawn from ``cost_distribution``; the
    per-second cost is ``variable_cost_ratio`` times an independent draw from it.
    Per-capability quality is the agent's base quality plus N(0, ``quality_spread``).
    """
    if count < 0:
        raise ConfigurationError("count must be >= 0")
    if not capabilities:
        raise ConfigurationError("capabilities must not be empty")
    cost = as_distribution(cost_distribution, COST_PRESETS)
    quality = as_distribution(quality_distribution, QUALITY_PRESETS)
    latency = as_distribution(latency_distribution, LATENCY_PRESETS)
    reliability = as_distribution(reliability_distribution, RELIABILITY_PRESETS)
    capacity = as_distribution(capacity_distribution)
    make_strategy = _strategy_factory(strategy)
    rng = random.Random(derive_seed(seed, "agents"))
    lo, hi = capabilities_per_agent
    agents = []
    for i in range(count):
        if capability_distribution == "generalist":
            caps = list(capabilities)
        elif capability_distribution == "specialist":
            caps = [capabilities[i % len(capabilities)]]
        elif capability_distribution == "mixed":
            k = rng.randint(max(1, lo), max(1, min(hi, len(capabilities))))
            caps = sorted(rng.sample(list(capabilities), k))
        else:
            raise ConfigurationError(f"unknown capability_distribution {capability_distribution!r}")
        base_q = quality.sample(rng)
        qualities = {c: min(1.0, max(0.0, base_q + rng.gauss(0, quality_spread))) for c in caps}
        agents.append(
            SimulatedAgent(
                f"{prefix}-{i:05d}",
                capabilities=caps,
                cost_model=CostModel(
                    fixed_cost=max(0.0, cost.sample(rng)),
                    variable_cost_per_second=max(0.0, cost.sample(rng) * variable_cost_ratio),
                ),
                quality=qualities,
                reliability=min(1.0, max(0.0, reliability.sample(rng))),
                latency_mean=max(0.01, latency.sample(rng)),
                strategy=make_strategy(i, rng),
                quality_report_bias=quality_report_bias,
                seed=derive_seed(seed, "agent", i),
                max_concurrent_tasks=max(1, round(capacity.sample(rng))),
            )
        )
    return agents


def generate_tasks(
    count: int,
    *,
    seed: int = 0,
    task_types: Sequence[str] = DEFAULT_TASK_TYPES,
    arrival_rate: float = 1.0,
    budget_distribution: DistributionSpec = "lognormal",
    deadline_distribution: DistributionSpec | None = "uniform",
    complexity_distribution: DistributionSpec = "lognormal",
    min_quality: DistributionSpec | None = None,
    value_multiplier: float = 1.5,
    unit: str = "credits",
    prefix: str = "task",
) -> list[Task]:
    """Generate ``count`` tasks arriving as a Poisson process with ``arrival_rate``
    tasks per second. Each task's ``value`` (used for welfare metrics) is
    ``value_multiplier * budget``."""
    if count < 0:
        raise ConfigurationError("count must be >= 0")
    if arrival_rate <= 0:
        raise ConfigurationError("arrival_rate must be positive")
    budget = as_distribution(budget_distribution, BUDGET_PRESETS)
    deadline = (
        None
        if deadline_distribution is None
        else as_distribution(deadline_distribution, DEADLINE_PRESETS)
    )
    complexity = as_distribution(complexity_distribution, COMPLEXITY_PRESETS)
    quality = None if min_quality is None else as_distribution(min_quality)
    rng = random.Random(derive_seed(seed, "tasks"))
    now = 0.0
    tasks = []
    for i in range(count):
        now += rng.expovariate(arrival_rate)
        b = max(0.0, budget.sample(rng))
        tasks.append(
            Task(
                task_id=f"{prefix}-{i:06d}",
                task_type=rng.choice(list(task_types)),
                requirements={"complexity": max(0.05, complexity.sample(rng))},
                budget=b,
                deadline=None if deadline is None else max(0.1, deadline.sample(rng)),
                min_quality=None if quality is None else min(1.0, max(0.0, quality.sample(rng))),
                value=b * value_multiplier,
                unit=unit,
                created_at=now,
            )
        )
    return tasks
