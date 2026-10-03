"""Build the agents, tasks and mid-run changes for one replication of an environment."""

from __future__ import annotations

from auctionsi.core.agent import Agent
from auctionsi.core.task import Task
from auctionsi.errors import ConfigurationError
from auctionsi.experiments.config import ChangeConfig, EnvironmentConfig
from auctionsi.simulation.adversarial import (
    CollusionRing,
    form_ring,
    make_sybils,
    overstate_quality,
)
from auctionsi.simulation.agents import SimulatedAgent
from auctionsi.simulation.generators import derive_seed, generate_agents, generate_tasks
from auctionsi.simulation.market import MarketChange, agent_changes, agent_leaves


def build_population(
    env: EnvironmentConfig, seed: int
) -> tuple[list[Agent], list[Task], list[MarketChange]]:
    """Same seed and environment -> identical population (common random numbers)."""
    agents: list[SimulatedAgent] = generate_agents(
        env.agents.count, seed=derive_seed(seed, "agents"), **env.agents.options()
    )
    tasks = generate_tasks(env.tasks.count, seed=derive_seed(seed, "tasks"), **env.tasks.options())
    adv = env.adversaries
    # Sybils clone the last agent, which the other attacks (taken from the front) never touch.
    if adv.sybil_copies and agents:
        agents.extend(make_sybils(agents[-1], adv.sybil_copies))
    if adv.colluders:
        form_ring(
            agents[: adv.colluders],
            CollusionRing(winner_markup=adv.winner_markup, cover_markup=adv.cover_markup),
        )
    if adv.overstaters:
        overstate_quality(agents[: adv.overstaters], adv.overstate_quality)
    ordered = sorted(tasks, key=lambda t: (t.created_at, t.task_id))
    changes = [c for change in env.changes for c in _changes(change, agents, ordered)]
    return list(agents), tasks, changes


def _changes(
    change: ChangeConfig, agents: list[SimulatedAgent], tasks: list[Task]
) -> list[MarketChange]:
    if change.at_task is not None:
        if change.at_task >= len(tasks):
            raise ConfigurationError(f"at_task {change.at_task} is beyond the {len(tasks)} tasks")
        at = tasks[change.at_task].created_at
    else:
        assert change.at is not None
        at = change.at
    if isinstance(change.agents, int):
        ids = [a.agent_id for a in agents[: change.agents]]
    else:
        known = {a.agent_id for a in agents}
        missing = set(change.agents) - known
        if missing:
            raise ConfigurationError(f"unknown agents in change: {sorted(missing)}")
        ids = list(change.agents)
    if change.leave:
        return [agent_leaves(at, agent_id) for agent_id in ids]
    return [agent_changes(at, agent_id, **change.set) for agent_id in ids]
