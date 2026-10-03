"""Experiment configuration (validated with Pydantic; unknown keys are errors)."""

from __future__ import annotations

import copy
import itertools
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from auctionsi.errors import ConfigurationError

Spec = str | dict[str, Any]

FACTOR_COMPONENTS = frozenset({"mechanism", "policy", "reputation", "settlement"})

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


class AdversariesConfig(_Strict):
    """Turn some generated agents adversarial (the first agents of the population)."""

    colluders: int = Field(0, ge=0)
    winner_markup: float = 0.6
    cover_markup: float = 1.2
    sybil_copies: int = Field(0, ge=0)
    overstaters: int = Field(0, ge=0)
    overstate_quality: float = 0.2


CHANGEABLE = frozenset(
    {
        "reliability",
        "available",
        "quality_report_bias",
        "latency_report_bias",
        "latency_mean",
        "quality",
    }
)


class ChangeConfig(_Strict):
    """Something that happens mid-run to some agents: change attributes or leave.

    ``agents`` is a count (the first N generated agents) or a list of agent ids.
    Timing is ``at`` (simulated seconds) or ``at_task`` (when that task arrives).
    """

    at: float | None = Field(None, ge=0)
    at_task: int | None = Field(None, ge=0)
    agents: int | list[str] = 1
    set: dict[str, Any] = Field(default_factory=dict)
    leave: bool = False

    @field_validator("set")
    @classmethod
    def _known_attributes(cls, values: dict[str, Any]) -> dict[str, Any]:
        unknown = set(values) - CHANGEABLE
        if unknown:
            raise ValueError(f"cannot change {sorted(unknown)}; allowed: {sorted(CHANGEABLE)}")
        return values

    def model_post_init(self, context: Any) -> None:
        if (self.at is None) == (self.at_task is None):
            raise ValueError("give exactly one of 'at' or 'at_task'")
        if not self.set and not self.leave:
            raise ValueError("a change needs 'set' or 'leave: true'")


class EnvironmentConfig(_Strict):
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    tasks: TasksConfig = Field(default_factory=TasksConfig)
    adversaries: AdversariesConfig = Field(default_factory=AdversariesConfig)
    changes: list[ChangeConfig] = Field(default_factory=list)


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
    factors: dict[str, list[Any]] = Field(default_factory=dict)
    baseline: str | None = None
    metrics: list[str] = Field(default_factory=lambda: list(DEFAULT_METRICS))

    @field_validator("arms")
    @classmethod
    def _unique_arm_names(cls, arms: list[ArmConfig]) -> list[ArmConfig]:
        names = [a.name for a in arms]
        if len(names) != len(set(names)):
            raise ValueError("arm names must be unique")
        return arms

    @field_validator("factors")
    @classmethod
    def _known_factors(cls, factors: dict[str, list[Any]]) -> dict[str, list[Any]]:
        for key, values in factors.items():
            if key not in FACTOR_COMPONENTS and not key.startswith("environment."):
                raise ValueError(
                    f"factor {key!r} must be one of {sorted(FACTOR_COMPONENTS)} or 'environment.<path>'"
                )
            if not values:
                raise ValueError(f"factor {key!r} needs at least one level")
        return factors

    def resolved_arms(self) -> list[ArmConfig]:
        """Explicit arms (or one default arm), crossed with every factor level."""
        base = self.arms or [ArmConfig(name="default")]
        if not self.factors:
            return base
        keys = list(self.factors)
        arms = []
        for arm in base:
            for levels in itertools.product(*(self.factors[k] for k in keys)):
                data = arm.model_dump()
                labels = []
                for key, level in zip(keys, levels, strict=True):
                    labels.append(f"{key.removeprefix('environment.')}={_label(level)}")
                    if key in FACTOR_COMPONENTS:
                        data[key] = level
                    else:
                        path = key.split(".")[1:]
                        data["environment"] = deep_merge(data["environment"], _nest(path, level))
                prefix = "" if not self.arms else f"{arm.name}|"
                data["name"] = prefix + ",".join(labels)
                arms.append(ArmConfig.model_validate(data))
        names = [a.name for a in arms]
        if len(names) != len(set(names)):
            raise ConfigurationError("factor levels produce duplicate arm names")
        return arms

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


def _label(level: Any) -> str:
    if isinstance(level, Mapping):
        return str(level.get("name", level))
    return str(level)


def _nest(path: list[str], value: Any) -> dict[str, Any]:
    out: Any = value
    for part in reversed(path):
        out = {part: out}
    return dict(out)


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
