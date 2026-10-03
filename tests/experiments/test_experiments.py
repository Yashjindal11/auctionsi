from __future__ import annotations

import json
from pathlib import Path

import pytest

from auctionsi.errors import ConfigurationError
from auctionsi.experiments import (
    ExperimentConfig,
    ExperimentResult,
    build_manifest,
    compare_mechanisms,
    run_experiment,
)
from auctionsi.mechanisms import FirstPriceReverseAuction, SecondPriceReverseAuction
from auctionsi.reports import experiment_report

SMALL_ENV = {"agents": {"count": 8}, "tasks": {"count": 40}}


def test_compact_config_shape_is_accepted() -> None:
    cfg = ExperimentConfig.from_mapping(
        {
            "experiment": {"replications": 3, "seed": 42},
            "environment": {"agents": 10, "tasks": 50},
            "auction": {"mechanisms": ["first_price_reverse", "second_price_reverse"]},
            "metrics": ["total_cost", "average_quality"],
        }
    )
    assert cfg.replications == 3
    assert cfg.environment.agents.count == 10
    assert [a.name for a in cfg.arms] == ["first_price_reverse", "second_price_reverse"]
    assert cfg.baseline_arm() == "first_price_reverse"


@pytest.mark.parametrize(
    "data",
    [
        {"replications": 0},
        {"surprise": 1},
        {"environment": {"agents": {"count": 10, "colour": "red"}}},
        {"arms": [{"name": "a"}, {"name": "a"}]},
    ],
)
def test_invalid_configs_are_rejected(data: dict[str, object]) -> None:
    with pytest.raises(ConfigurationError):
        ExperimentConfig.from_mapping(data)


def test_bad_baseline_and_metric() -> None:
    cfg = ExperimentConfig.from_mapping({"arms": [{"name": "a"}], "baseline": "zzz"})
    with pytest.raises(ConfigurationError):
        cfg.baseline_arm()
    with pytest.raises(ConfigurationError):
        run_experiment({"replications": 1, "environment": SMALL_ENV, "metrics": ["vibes"]})


def test_arm_environment_overrides_merge() -> None:
    cfg = ExperimentConfig.from_mapping(
        {"environment": SMALL_ENV, "arms": [{"name": "big", "environment": {"agents": 30}}]}
    )
    env = cfg.environment_for(cfg.arms[0])
    assert env.agents.count == 30
    assert env.tasks.count == 40


@pytest.mark.integration
def test_run_experiment_is_reproducible_and_paired(tmp_path: Path) -> None:
    data = {
        "name": "fp-vs-sp",
        "hypothesis": "Second-price raises buyer cost.",
        "seed": 7,
        "replications": 4,
        "environment": SMALL_ENV,
        "arms": [
            {"name": "fp", "mechanism": "first_price_reverse"},
            {"name": "sp", "mechanism": "second_price_reverse"},
            {"name": "risk", "policy": {"name": "risk_adjusted_cost"}},
        ],
        "metrics": ["total_cost", "completion_rate", "average_quality"],
    }
    calls: list[int] = []
    first = run_experiment(data, progress=lambda arm, done, total: calls.append(done))
    second = run_experiment(data)
    assert calls[-1] == 12
    assert [r.metrics for r in first.runs] == [r.metrics for r in second.runs]
    # Common random numbers: arms in the same replication share a seed.
    seeds = {(r.replication, r.seed) for r in first.runs}
    assert len(seeds) == 4
    fp = first.values("fp", "total_cost")
    sp = first.values("sp", "total_cost")
    assert all(s >= f - 1e-12 for f, s in zip(fp, sp, strict=True))
    comparisons = first.comparisons()
    assert {(c.treatment, c.metric) for c in comparisons} >= {("sp", "total_cost")}
    assert all(c.p_adjusted is not None or c.p_value is None for c in comparisons)

    out = first.save(tmp_path / "run")
    manifest = json.loads((out / "manifest.json").read_text())
    for key in ("auctionsi_version", "python_version", "git_commit", "seed", "config"):
        assert key in manifest
    report = (out / "report.md").read_text()
    for heading in (
        "## Hypothesis",
        "## Experimental setup",
        "## Results",
        "## Statistical tests",
        "## Limitations",
        "## Conclusion",
    ):
        assert heading in report
    assert "Second-price raises buyer cost." in report
    loaded = ExperimentResult.load(out)
    assert loaded.values("sp", "total_cost") == sp


def test_compare_mechanisms_with_instances() -> None:
    result = compare_mechanisms(
        [FirstPriceReverseAuction(), SecondPriceReverseAuction()],
        environment=SMALL_ENV,
        replications=2,
        metrics=["total_cost"],
    )
    assert result.arms == ["first_price_reverse", "second_price_reverse"]
    assert len(result.runs) == 4
    assert "first_price_reverse" in experiment_report(result)


def test_manifest_contents() -> None:
    manifest = build_manifest({"seed": 3, "environment": {"agents": {"count": 1}}})
    assert manifest["seed"] == 3
    assert manifest["agent_generation"] == {"count": 1}
    assert manifest["dependencies"]["scipy"]
