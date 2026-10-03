"""Experiment configuration (validated with Pydantic; unknown keys are errors)."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from auctionsi.errors import ConfigurationError

Spec = str | dict[str, Any]

DEFAULT_METRICS = [
    "completion_rate",
    "average_cost",
    "total_cost",
    "average_quality",
    "average_latency",
    "hhi",
    "cost_efficiency",
    "buyer_utility",
    "total_surplus",
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentsConfig(_Strict):
    count: int = Field(20, ge=1, le=100_000)
    capabilities: list[str] = Field(
        default_factory=lambda: ["research", "data_analysis", "sql", "optimization"]
    )
    capability_distribution: str = "mixed"
    capabilities_per_agent: tuple[int, int] = (1, 3)
    cost_distribution: Any = "lognormal"
    variable_cost_ratio: float = 0.01
    quality_distribution: Any = "beta"
    quality_spread: float = 0.05
    latency_distribution: Any = "lognormal"
    reliability_distribution: Any = "beta"
    capacity_distribution: Any = 1
    strategy: Spec = "cost_plus"
    quality_report_bias: float = 0.0

    def options(self) -> dict[str, Any]:
        return self.model_dump(exclude={"count"})


class TasksConfig(_Strict):
    count: int = Field(200, ge=1, le=1_000_000)
    task_types: list[str] = Field(
        default_factory=lambda: ["research", "data_analysis", "sql", "optimization"]
    )
    arrival_rate: float = Field(1.0, gt=0)
    budget_distribution: Any = "lognormal"
    deadline_distribution: Any = "uniform"
    complexity_distribution: Any = "lognormal"
    min_quality: Any = None
    value_multiplier: float = 1.5

    def options(self) -> dict[str, Any]:
        return self.model_dump(exclude={"count"})


class EnvironmentConfig(_Strict):
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    tasks: TasksConfig = Field(default_factory=TasksConfig)


class ArmConfig(_Strict):
    """One experimental condition. Unset components inherit the experiment defaults;
    ``environment`` holds overrides deep-merged into the base environment."""

    name: str
    mechanism: Spec | None = None
    policy: Spec | None = None
    reputation: Spec | None = None
    settlement: Spec | None = None
    recovery: dict[str, int] | None = None
    validation: dict[str, Any] | None = None
    environment: dict[str, Any] = Field(default_factory=dict)


class ExperimentConfig(_Strict):
    name: str = "experiment"
    description: str = ""
    hypothesis: str = ""
    limitations: list[str] = Field(default_factory=list)
    seed: int = 0
    replications: int = Field(10, ge=1, le=100_000)
    confidence: float = Field(0.95, gt=0, lt=1)
    alpha: float = Field(0.05, gt=0, lt=1)
    environment: EnvironmentConfig = Field(default_factory=EnvironmentConfig)
    mechanism: Spec = "first_price_reverse"
    policy: Spec = "lowest_price"
    reputation: Spec = "multi_dimensional"
    settlement: Spec = "pay_on_pass"
    recovery: dict[str, int] = Field(default_factory=dict)
    validation: dict[str, Any] = Field(default_factory=dict)
    arms: list[ArmConfig] = Field(default_factory=list)
    baseline: str | None = None
    metrics: list[str] = Field(default_factory=lambda: list(DEFAULT_METRICS))

    @field_validator("arms")
    @classmethod
    def _unique_arm_names(cls, arms: list[ArmConfig]) -> list[ArmConfig]:
        names = [a.name for a in arms]
        if len(names) != len(set(names)):
            raise ValueError("arm names must be unique")
        return arms

    def resolved_arms(self) -> list[ArmConfig]:
        return self.arms or [ArmConfig(name="default")]

    def baseline_arm(self) -> str:
        arms = self.resolved_arms()
        if self.baseline is None:
            return arms[0].name
        if self.baseline not in {a.name for a in arms}:
            raise ConfigurationError(f"baseline {self.baseline!r} is not an arm")
        return self.baseline

    def environment_for(self, arm: ArmConfig) -> EnvironmentConfig:
        merged = deep_merge(self.environment.model_dump(), arm.environment)
        return EnvironmentConfig.model_validate(merged)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> ExperimentConfig:
        """Accept the canonical shape, or the compact shape::

        experiment: {name, replications, seed}
        environment: {agents: 100, tasks: 5000}
        auction: {mechanisms: [first_price_reverse, second_price_reverse]}
        metrics: [...]
        """
        raw = dict(data)
        if "experiment" in raw:
            raw = {**dict(raw.pop("experiment") or {}), **raw}
        env = raw.get("environment")
        if isinstance(env, Mapping):
            env = dict(env)
            for key in ("agents", "tasks"):
                if isinstance(env.get(key), int):
                    env[key] = {"count": env[key]}
            raw["environment"] = env
        auction = raw.pop("auction", None)
        if isinstance(auction, Mapping):
            mechanisms = auction.get("mechanisms")
            if mechanisms and "arms" not in raw:
                raw["arms"] = [
                    {"name": m if isinstance(m, str) else m["name"], "mechanism": m}
                    for m in mechanisms
                ]
            elif auction.get("mechanism"):
                raw["mechanism"] = auction["mechanism"]
        try:
            return cls.model_validate(raw)
        except ValueError as exc:
            raise ConfigurationError(f"invalid experiment config: {exc}") from exc


def deep_merge(base: dict[str, Any], overrides: Mapping[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, Mapping) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        elif (
            isinstance(value, int) and key in ("agents", "tasks") and isinstance(out.get(key), dict)
        ):
            out[key] = {**out[key], "count": value}
        else:
            out[key] = copy.deepcopy(value)
    return out
