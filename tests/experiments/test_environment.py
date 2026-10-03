from __future__ import annotations

import pytest

from auctionsi.errors import ConfigurationError
from auctionsi.experiments import ExperimentConfig, run_experiment
from auctionsi.experiments.environment import build_population
from auctionsi.simulation import simulate_market
from auctionsi.simulation.adversarial import CollusiveStrategy

ENV = {"agents": {"count": 6}, "tasks": {"count": 30}}


def test_factor_levels_with_the_same_name_get_distinct_labels() -> None:
    cfg = ExperimentConfig.from_mapping(
        {
            "factors": {
                "environment.agents.reliability_distribution": [
                    {"name": "uniform", "low": 0.9, "high": 1.0},
                    {"name": "uniform", "low": 0.4, "high": 1.0},
                ]
            }
        }
    )
    assert [a.name for a in cfg.resolved_arms()] == [
        "agents.reliability_distribution=uniform(low=0.9,high=1.0)",
        "agents.reliability_distribution=uniform(low=0.4,high=1.0)",
    ]


def test_factors_cross_with_arms() -> None:
    cfg = ExperimentConfig.from_mapping(
        {
            "environment": ENV,
            "factors": {
                "mechanism": ["first_price_reverse", "second_price_reverse"],
                "environment.agents.count": [5, 10],
            },
        }
    )
    arms = cfg.resolved_arms()
    assert [a.name for a in arms] == [
        "mechanism=first_price_reverse,agents.count=5",
        "mechanism=first_price_reverse,agents.count=10",
        "mechanism=second_price_reverse,agents.count=5",
        "mechanism=second_price_reverse,agents.count=10",
    ]
    assert cfg.environment_for(arms[1]).agents.count == 10
    crossed = ExperimentConfig.from_mapping(
        {
            "arms": [{"name": "a"}, {"name": "b", "policy": "risk_adjusted_cost"}],
            "factors": {"policy": [{"name": "weighted_score", "price_weight": 1}]},
        }
    )
    assert [a.name for a in crossed.resolved_arms()] == [
        "a|policy=weighted_score(price_weight=1)",
        "b|policy=weighted_score(price_weight=1)",
    ]


@pytest.mark.parametrize(
    "data",
    [
        {"factors": {"colour": ["red"]}},
        {"factors": {"mechanism": []}},
        {"environment": {"changes": [{"agents": 1, "set": {"reliability": 0.1}}]}},
        {"environment": {"changes": [{"at": 1, "at_task": 2, "leave": True}]}},
        {"environment": {"changes": [{"at": 1, "set": {"cost_model": 1}}]}},
        {"environment": {"changes": [{"at": 1}]}},
    ],
)
def test_invalid_factor_and_change_configs(data: dict[str, object]) -> None:
    with pytest.raises(ConfigurationError):
        ExperimentConfig.from_mapping(data)


def test_population_with_adversaries_and_changes() -> None:
    cfg = ExperimentConfig.from_mapping(
        {
            "environment": {
                **ENV,
                "adversaries": {"colluders": 3, "sybil_copies": 2, "overstaters": 1},
                "changes": [
                    {"at_task": 10, "agents": 2, "set": {"reliability": 0.0}},
                    {"at": 5.0, "agents": ["agent-00005"], "leave": True},
                ],
            }
        }
    )
    agents, tasks, changes = build_population(cfg.environment, seed=1)
    assert len(agents) == 8
    assert sum(isinstance(a.strategy, CollusiveStrategy) for a in agents) == 3  # type: ignore[attr-defined]
    assert agents[0].quality_report_bias == 0.2  # type: ignore[attr-defined]
    assert len(changes) == 3
    result = simulate_market(agents, tasks, changes=changes)
    late = [r for r in result.records if r.created_at > tasks_sorted_at(tasks, 10)]
    assert all("agent-00005" not in r.bidders for r in result.records if r.created_at > 5.0)
    first_two = {"agent-00000", "agent-00001"}
    assert not any(set(r.winners) & first_two for r in late)
    bad = ExperimentConfig.from_mapping(
        {"environment": {**ENV, "changes": [{"at_task": 999, "leave": True}]}}
    )
    with pytest.raises(ConfigurationError):
        build_population(bad.environment, seed=1)


def tasks_sorted_at(tasks: list, index: int) -> float:  # type: ignore[type-arg]
    return sorted(t.created_at for t in tasks)[index]


def test_new_metrics_flow_through_experiments() -> None:
    result = run_experiment(
        {
            "replications": 2,
            "environment": ENV,
            "metrics": ["average_winning_markup", "bid_cv", "relative_distance"],
        }
    )
    values = result.values("default", "average_winning_markup")
    assert len(values) == 2
    assert all(0.1 < v < 0.3 for v in values)  # cost-plus 20% bidders
