from __future__ import annotations

import random

import pytest

from auctionsi.core import CostModel
from auctionsi.errors import ConfigurationError
from auctionsi.market import BidValidationConfig
from auctionsi.mechanisms import OpenReverseAuction, SecondPriceReverseAuction
from auctionsi.reputation import NoReputation
from auctionsi.selection import RiskAdjustedCost
from auctionsi.simulation import (
    Beta,
    Choice,
    Constant,
    LogNormal,
    Normal,
    SimulatedAgent,
    TaskRecord,
    Uniform,
    agent_changes,
    agent_joins,
    agent_leaves,
    as_distribution,
    compute_metrics,
    concentration_over_time,
    derive_seed,
    generate_agents,
    generate_tasks,
    simulate_market,
)
from auctionsi.simulation.adversarial import (
    add_fake_capability,
    exit_scam,
    form_ring,
    make_sybils,
    operator_hhi,
    overstate_quality,
    price_inflation,
)
from auctionsi.statistics.concentration import gini, hhi, shares, top_share


def test_distributions() -> None:
    rng = random.Random(0)
    assert Constant(2).sample(rng) == 2
    assert 1 <= Uniform(1, 2).sample(rng) <= 2
    assert -1 <= Normal(0, 10, low=-1, high=1).sample(rng) <= 1
    assert LogNormal(1, 0).sample(rng) == pytest.approx(1)
    assert 2 <= Beta(2, 2, low=2, high=3).sample(rng) <= 3
    assert Choice([1, 2], [0, 1]).sample(rng) == 2
    assert as_distribution(3).sample(rng) == 3
    assert isinstance(as_distribution({"name": "uniform", "low": 0, "high": 1}), Uniform)
    assert as_distribution({"name": "beta", "a": 2, "b": 3}).to_spec()["a"] == 2
    for bad in ("nope", {"name": "nope"}, {"name": "uniform", "x": 1}, [1]):
        with pytest.raises(ConfigurationError):
            as_distribution(bad)  # type: ignore[arg-type]


def test_generators_are_deterministic_and_respect_options() -> None:
    a = generate_agents(20, seed=3)
    b = generate_agents(20, seed=3)
    assert [x.spec() for x in a] == [y.spec() for y in b]
    assert [x.spec() for x in generate_agents(20, seed=4)] != [x.spec() for x in a]
    specialists = generate_agents(8, capability_distribution="specialist")
    assert all(len(x.capabilities) == 1 for x in specialists)
    generalists = generate_agents(3, capability_distribution="generalist", capabilities=["a", "b"])
    assert all(len(x.capabilities) == 2 for x in generalists)
    with pytest.raises(ConfigurationError):
        generate_agents(1, capability_distribution="weird")
    with pytest.raises(ConfigurationError):
        generate_agents(1, strategy="bogus")

    tasks = generate_tasks(50, seed=1, arrival_rate=2.0, min_quality=0.7)
    assert tasks == generate_tasks(50, seed=1, arrival_rate=2.0, min_quality=0.7)
    times = [t.created_at for t in tasks]
    assert times == sorted(times)
    assert all(t.min_quality == 0.7 for t in tasks)
    assert all(t.value == pytest.approx(1.5 * t.budget) for t in tasks)  # type: ignore[operator]


def test_simulated_agent_behaviour() -> None:
    agent = SimulatedAgent(
        "s",
        capabilities=["x"],
        cost_model=CostModel(fixed_cost=0.01, variable_cost_per_second=0.001),
        quality=0.8,
        reliability=1.0,
        latency_mean=10,
        latency_sigma=0,
        quality_report_bias=0.1,
    )
    from auctionsi.core import BidContext, Contract, Task

    task = Task(task_id="t", task_type="x", requirements={"complexity": 2})
    assert agent.expected_latency(task) == 20
    assert agent.expected_cost(task) == pytest.approx(0.03)
    proposal = agent.bid(task, BidContext("a", "m", 0, True, "credits"))
    assert proposal is not None
    assert proposal.estimated_quality == pytest.approx(0.9)
    contract = Contract("c", "a", "t", "s", "b", 1, 1, "credits", 0)
    result = agent.execute(task, contract)
    assert result.success
    assert result.latency == 20
    assert agent.metadata["operator"] == "s"


@pytest.mark.integration
def test_simulate_market_is_reproducible() -> None:
    first = simulate_market(15, 120, seed=11)
    second = simulate_market(15, 120, seed=11)
    assert [r.to_dict() for r in first.records] == [r.to_dict() for r in second.records]
    assert first.metrics.scalars() == second.metrics.scalars()
    other = simulate_market(15, 120, seed=12)
    assert [r.to_dict() for r in other.records] != [r.to_dict() for r in first.records]


@pytest.mark.integration
def test_simulation_metrics_are_consistent() -> None:
    result = simulate_market(20, 200, seed=5)
    m = result.metrics
    assert m.total_tasks == 200
    assert m.successful_tasks + m.failed_tasks + m.no_bid_tasks == 200
    assert 0 < m.completion_rate <= 1
    assert 0 <= m.hhi <= 1
    assert 0 <= m.revenue_gini <= 1
    assert m.cost_efficiency is not None
    assert 0 < m.cost_efficiency <= 1 + 1e-9
    assert sum(m.agent_utilization.values()) == pytest.approx(1)
    assert m.total_surplus == pytest.approx(m.buyer_utility + m.agent_utility)
    assert m.average_quality is not None
    assert 0 <= m.average_quality <= 1
    perf = result.performance()
    assert perf["auctions_per_second"] > 0
    assert len(concentration_over_time(result.records, 50)) == 4


def test_other_mechanisms_run_in_simulation() -> None:
    for mechanism in (SecondPriceReverseAuction(), OpenReverseAuction(max_rounds=5)):
        result = simulate_market(10, 40, seed=2, mechanism=mechanism, policy=RiskAdjustedCost())
        assert result.metrics.total_tasks == 40


def test_market_changes_apply_on_the_simulated_clock() -> None:
    agents = generate_agents(4, seed=1, capability_distribution="generalist")
    newcomer = generate_agents(1, seed=2, capability_distribution="generalist", prefix="new")[0]
    tasks = generate_tasks(60, seed=1, arrival_rate=1.0)
    midpoint = tasks[30].created_at
    result = simulate_market(
        agents,
        tasks,
        changes=[
            agent_leaves(midpoint, agents[0].agent_id),
            agent_joins(midpoint, newcomer),
            agent_changes(0.0, agents[1].agent_id, available=False),
        ],
    )
    late = result.records[31:]
    assert all(agents[0].agent_id not in r.bidders for r in late)
    assert all(agents[1].agent_id not in r.bidders for r in result.records)
    assert any(newcomer.agent_id in r.bidders for r in late)
    assert all(newcomer.agent_id not in r.bidders for r in result.records[:30])


def test_concentration_measures() -> None:
    assert hhi({"a": 1, "b": 1}) == pytest.approx(0.5)
    assert hhi([5]) == 1.0
    assert hhi([]) == 0.0
    assert gini([1, 1, 1, 1]) == pytest.approx(0)
    assert gini([0, 0, 0, 10]) == pytest.approx(0.75)
    with pytest.raises(ValueError):
        gini([-1, 2])
    assert top_share({"a": 3, "b": 1}) == pytest.approx(0.75)
    assert shares({"a": 0}) == {"a": 0.0}


def test_compute_metrics_by_hand() -> None:
    def rec(i: int, winner: str | None, cost: float, quality: float | None) -> TaskRecord:
        return TaskRecord(
            task_id=f"t{i}",
            task_type="x",
            created_at=i,
            status="settled" if winner else "no_bids",
            succeeded=winner is not None,
            eligible=2,
            bids=2 if winner else 0,
            rejected=0,
            awarded=(winner,) if winner else (),
            winners=(winner,) if winner else (),
            awarded_price=cost if winner else None,
            buyer_cost=cost,
            quality=quality,
            latency=1.0 if winner else None,
            attempts=1 if winner else 0,
            value=1.0,
            revenue_by_agent=((winner, cost),) if winner else (),
            cost_by_agent=((winner, cost / 2),) if winner else (),
            winner_true_cost=cost / 2 if winner else None,
            min_true_cost=0.1 if winner else None,
            bidders=("a", "b") if winner else (),
        )

    records = [rec(0, "a", 0.4, 0.9), rec(1, "a", 0.2, 0.7), rec(2, None, 0.0, None)]
    m = compute_metrics(records, ["a", "b", "c"])
    assert m.completion_rate == pytest.approx(2 / 3)
    assert m.total_cost == pytest.approx(0.6)
    assert m.average_cost == pytest.approx(0.3)
    assert m.average_quality == pytest.approx(0.8)
    assert m.hhi == 1.0
    assert m.buyer_utility == pytest.approx(2 - 0.6)
    assert m.agent_utility == pytest.approx(0.3)
    assert m.total_surplus == pytest.approx(2 - 0.3)
    assert m.cost_efficiency == pytest.approx((0.1 / 0.2 + 0.1 / 0.1) / 2)
    assert m.participation_rate == pytest.approx(2 / 3)
    assert m.opportunity_rate == pytest.approx(1 / 3)
    assert m.revenue_gini == pytest.approx(2 / 3)


@pytest.mark.integration
def test_collusion_inflates_prices() -> None:
    options = {"capability_distribution": "generalist", "capabilities": ["x"]}
    task_opts = {"task_types": ["x"], "budget_distribution": 1.0}
    baseline = simulate_market(6, 150, seed=9, agent_options=options, task_options=task_opts)
    # Same agents and tasks as the baseline, but the agents now collude.
    agents = generate_agents(6, seed=derive_seed(9, "agents"), **options)  # type: ignore[arg-type]
    form_ring(agents)
    tasks = generate_tasks(150, seed=derive_seed(9, "tasks"), **task_opts)  # type: ignore[arg-type]
    colluding = simulate_market(agents, tasks, seed=9)
    inflation = price_inflation(baseline.metrics, colluding.metrics)
    assert inflation is not None
    assert inflation > 0.2


def test_sybil_defence_limits_bids_per_operator() -> None:
    def population() -> list[SimulatedAgent]:
        template = generate_agents(1, seed=1, capability_distribution="generalist")[0]
        honest = generate_agents(2, seed=5, capability_distribution="generalist", prefix="h")
        return [template, *make_sybils(template, 3), *honest]

    open_market = simulate_market(population(), generate_tasks(30, seed=1))
    assert max(r.bids for r in open_market.records) == 6
    defended = simulate_market(
        population(),
        generate_tasks(30, seed=1),
        validation=BidValidationConfig(max_bids_per_operator=1),
    )
    assert max(r.bids for r in defended.records) == 3
    assert 0 <= operator_hhi(defended.records, defended.agents) <= 1


def test_dishonesty_helpers() -> None:
    agents = generate_agents(2, seed=1, capabilities=["x"])
    overstate_quality(agents, 0.2)
    assert all(a.quality_report_bias == 0.2 for a in agents)
    add_fake_capability(agents[0], "surgery")
    assert agents[0].capability("surgery") is not None
    assert agents[0].true_quality("surgery") == pytest.approx(0.05)
    change = exit_scam(agents[0].agent_id, at=5.0)
    assert change.at == 5.0


def test_reputation_can_be_disabled_in_simulation() -> None:
    result = simulate_market(5, 20, seed=1, reputation=NoReputation())
    assert result.market.reputation.profile("agent-00000") is None
