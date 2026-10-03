"""The experiment engine: replicated, seeded comparisons between market designs.

Arms share *common random numbers*: in replication ``r`` every arm whose
environment is identical sees exactly the same agents and tasks, so differences
between arms come from the market design rather than from sampling noise. That is
why arms are compared with paired tests.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from auctionsi.errors import ConfigurationError
from auctionsi.experiments.config import (
    ArmConfig,
    EnvironmentConfig,
    ExperimentConfig,
)
from auctionsi.experiments.environment import build_population
from auctionsi.experiments.manifest import build_manifest
from auctionsi.market.recovery import RecoveryPolicy
from auctionsi.market.validation import BidValidationConfig
from auctionsi.mechanisms.base import AuctionMechanism
from auctionsi.plugins import PluginRegistry, default_registry
from auctionsi.simulation.generators import derive_seed
from auctionsi.simulation.market import simulate_market
from auctionsi.simulation.metrics import MarketMetrics
from auctionsi.statistics.summary import Comparison, Summary, adjust, paired_comparison, summarize


@dataclass(frozen=True)
class ArmRun:
    arm: str
    replication: int
    seed: int
    metrics: dict[str, float | None]
    performance: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm": self.arm,
            "replication": self.replication,
            "seed": self.seed,
            "metrics": self.metrics,
            "performance": self.performance,
        }


@dataclass
class ExperimentResult:
    config: ExperimentConfig
    manifest: dict[str, Any]
    runs: list[ArmRun] = field(default_factory=list)

    @property
    def arms(self) -> list[str]:
        return [a.name for a in self.config.resolved_arms()]

    def values(self, arm: str, metric: str) -> list[float]:
        """Per-replication values (replications where the metric is undefined are skipped)."""
        out = []
        for run in sorted(self.runs, key=lambda r: r.replication):
            value = run.metrics.get(metric)
            if run.arm == arm and value is not None:
                out.append(float(value))
        return out

    def summary(self) -> dict[str, dict[str, Summary]]:
        out: dict[str, dict[str, Summary]] = {}
        for arm in self.arms:
            out[arm] = {}
            for metric in self.config.metrics:
                values = self.values(arm, metric)
                if values:
                    out[arm][metric] = summarize(values, self.config.confidence)
        return out

    def comparisons(self) -> list[Comparison]:
        """Each non-baseline arm vs the baseline on every metric (paired on the
        replications where both are defined), Holm-adjusted across all of them."""
        base = self.config.baseline_arm()
        found = []
        for arm in self.arms:
            if arm == base:
                continue
            for metric in self.config.metrics:
                pairs = self._pairs(base, arm, metric)
                if len(pairs) < 2:
                    continue
                found.append(
                    paired_comparison(
                        [p[0] for p in pairs],
                        [p[1] for p in pairs],
                        metric=metric,
                        baseline_name=base,
                        treatment_name=arm,
                        confidence=self.config.confidence,
                    )
                )
        return adjust(found)

    def _pairs(self, base: str, arm: str, metric: str) -> list[tuple[float, float]]:
        by_rep: dict[int, dict[str, float]] = {}
        for run in self.runs:
            value = run.metrics.get(metric)
            if run.arm in (base, arm) and value is not None:
                by_rep.setdefault(run.replication, {})[run.arm] = float(value)
        return [(v[base], v[arm]) for _, v in sorted(by_rep.items()) if base in v and arm in v]

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest": self.manifest,
            "summary": {
                arm: {m: s.to_dict() for m, s in metrics.items()}
                for arm, metrics in self.summary().items()
            },
            "comparisons": [c.to_dict() for c in self.comparisons()],
            "runs": [r.to_dict() for r in self.runs],
        }

    def save(self, directory: str | Path) -> Path:
        """Write ``manifest.json``, ``results.json`` and ``report.md`` into ``directory``."""
        from auctionsi.reports.markdown import experiment_report

        out = Path(directory)
        out.mkdir(parents=True, exist_ok=True)
        (out / "manifest.json").write_text(
            json.dumps(self.manifest, indent=2, default=str), encoding="utf-8"
        )
        (out / "results.json").write_text(
            json.dumps(self.to_dict(), indent=2, default=str), encoding="utf-8"
        )
        (out / "report.md").write_text(experiment_report(self), encoding="utf-8")
        return out

    @classmethod
    def load(cls, directory: str | Path) -> ExperimentResult:
        data = json.loads((Path(directory) / "results.json").read_text(encoding="utf-8"))
        manifest = data["manifest"]
        config = ExperimentConfig.model_validate(manifest["config"])
        runs = [ArmRun(**r) for r in data["runs"]]
        return cls(config, manifest, runs)


Progress = Callable[[str, int, int], None]


def _component(registry: Any, spec: Any, kind: str) -> Any:
    try:
        return registry.create(spec)
    except Exception as exc:
        raise ConfigurationError(f"{kind}: {exc}") from exc


def run_arm(
    config: ExperimentConfig,
    arm: ArmConfig,
    env: EnvironmentConfig,
    replication: int,
    plugins: PluginRegistry,
    mechanism_override: AuctionMechanism | None = None,
) -> ArmRun:
    rep_seed = derive_seed(config.seed, "replication", replication)
    mechanism = mechanism_override or _component(
        plugins.mechanisms, arm.mechanism or config.mechanism, "mechanism"
    )
    policy = _component(plugins.policies, arm.policy or config.policy, "policy")
    reputation = _component(plugins.reputations, arm.reputation or config.reputation, "reputation")
    settlement = _component(plugins.settlements, arm.settlement or config.settlement, "settlement")
    recovery = RecoveryPolicy(**(arm.recovery if arm.recovery is not None else config.recovery))
    validation = BidValidationConfig(
        **(arm.validation if arm.validation is not None else config.validation)
    )
    agents, tasks, changes = build_population(env, rep_seed)
    result = simulate_market(
        agents,
        tasks,
        seed=rep_seed,
        mechanism=mechanism,
        policy=policy,
        reputation=reputation,
        settlement=settlement,
        recovery=recovery,
        validation=validation,
        changes=changes,
    )
    scalars = result.metrics.scalars()
    return ArmRun(
        arm=arm.name,
        replication=replication,
        seed=rep_seed,
        metrics={m: scalars[m] for m in config.metrics},
        performance=result.performance(),
    )


def run_experiment(
    config: ExperimentConfig | Mapping[str, Any],
    *,
    plugins: PluginRegistry | None = None,
    progress: Progress | None = None,
    mechanisms: Mapping[str, AuctionMechanism] | None = None,
) -> ExperimentResult:
    """Run every arm for every replication and return the collected results."""
    cfg = config if isinstance(config, ExperimentConfig) else ExperimentConfig.from_mapping(config)
    registry = plugins or default_registry()
    cfg.baseline_arm()
    unknown = set(cfg.metrics) - set(MarketMetrics.SCALARS)
    if unknown:
        raise ConfigurationError(
            f"unknown metrics {sorted(unknown)}; known: {list(MarketMetrics.SCALARS)}"
        )
    result = ExperimentResult(cfg, build_manifest(cfg.model_dump(mode="json")))
    arms = cfg.resolved_arms()
    envs = {arm.name: cfg.environment_for(arm) for arm in arms}
    total = cfg.replications * len(arms)
    done = 0
    for replication in range(cfg.replications):
        for arm in arms:
            override = (mechanisms or {}).get(arm.name)
            result.runs.append(run_arm(cfg, arm, envs[arm.name], replication, registry, override))
            done += 1
            if progress is not None:
                progress(arm.name, done, total)
    return result


def compare_mechanisms(
    mechanisms: Sequence[AuctionMechanism],
    *,
    environment: EnvironmentConfig | Mapping[str, Any] | None = None,
    replications: int = 10,
    seed: int = 0,
    policy: str | dict[str, Any] = "lowest_price",
    metrics: Sequence[str] | None = None,
    **config: Any,
) -> ExperimentResult:
    """Convenience wrapper: one arm per mechanism instance, first one is the baseline."""
    names = []
    for mech in mechanisms:
        name = mech.name
        while name in names:
            name += "'"
        names.append(name)
    env = (
        environment.model_dump()
        if isinstance(environment, EnvironmentConfig)
        else dict(environment or {})
    )
    data: dict[str, Any] = {
        "seed": seed,
        "replications": replications,
        "environment": env,
        "policy": policy,
        "arms": [
            {"name": n, "mechanism": m.to_spec()} for n, m in zip(names, mechanisms, strict=True)
        ],
        **config,
    }
    if metrics is not None:
        data["metrics"] = list(metrics)
    cfg = ExperimentConfig.from_mapping(data)
    return run_experiment(cfg, mechanisms=dict(zip(names, mechanisms, strict=True)))
