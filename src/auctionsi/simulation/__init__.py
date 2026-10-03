"""Synthetic markets for large-scale, API-free experiments."""

from auctionsi.simulation.agents import SimulatedAgent
from auctionsi.simulation.distributions import (
    Beta,
    Choice,
    Constant,
    Distribution,
    LogNormal,
    Normal,
    Uniform,
    as_distribution,
)
from auctionsi.simulation.generators import derive_seed, generate_agents, generate_tasks
from auctionsi.simulation.market import (
    MarketChange,
    SimulationResult,
    agent_changes,
    agent_joins,
    agent_leaves,
    simulate_market,
)
from auctionsi.simulation.metrics import (
    MarketMetrics,
    TaskRecord,
    compute_metrics,
    concentration_over_time,
)
from auctionsi.simulation.verifier import SimulatedQualityVerifier

__all__ = [
    "Beta",
    "Choice",
    "Constant",
    "Distribution",
    "LogNormal",
    "MarketChange",
    "MarketMetrics",
    "Normal",
    "SimulatedAgent",
    "SimulatedQualityVerifier",
    "SimulationResult",
    "TaskRecord",
    "Uniform",
    "agent_changes",
    "agent_joins",
    "agent_leaves",
    "as_distribution",
    "compute_metrics",
    "concentration_over_time",
    "derive_seed",
    "generate_agents",
    "generate_tasks",
    "simulate_market",
]
