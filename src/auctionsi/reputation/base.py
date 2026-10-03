"""Multi-dimensional reputation with optional decay.

Reputation is deliberately *not* a single opaque score. Each agent has a profile
of separately measured dimensions (success, quality, timeliness, calibration of
its own estimates, contract violations), overall and per task type. Selection
policies read a small, explicit :class:`AgentFeatures` snapshot of it, and that
snapshot is recorded with every winner decision so it can be replayed.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

from auctionsi.errors import ValidationError


@dataclass(frozen=True, slots=True)
class Observation:
    """The measured outcome of one contract, fed to the reputation system."""

    agent_id: str
    task_type: str
    success: bool
    quality: float
    on_time: bool
    latency: float
    price: float
    estimated_quality: float | None = None
    estimated_latency: float | None = None
    violation: bool = False
    timestamp: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Observation:
        return cls(**dict(data))


@dataclass(frozen=True, slots=True)
class AgentFeatures:
    """The reputation inputs a selection policy may use. ``None`` means "no history"."""

    agent_id: str
    observations: int = 0
    success_estimate: float | None = None
    avg_quality: float | None = None
    quality_bias: float | None = None
    on_time_rate: float | None = None
    latency_error: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AgentFeatures:
        return cls(**dict(data))


@dataclass(frozen=True, slots=True)
class ReputationProfile:
    """All tracked dimensions for one agent (optionally restricted to one task type).

    Rates are weighted by the decay policy; ``completed``/``failed`` are raw counts.
    ``quality_estimate_bias`` is mean(estimated - actual): positive means the agent
    over-promises. ``latency_estimate_error`` is mean(|estimated - actual| / actual).
    """

    agent_id: str
    task_type: str | None
    observations: int
    completed: int
    failed: int
    effective_weight: float
    success_rate: float | None
    success_estimate: float | None
    avg_quality: float | None
    on_time_rate: float | None
    quality_estimate_error: float | None
    quality_estimate_bias: float | None
    latency_estimate_error: float | None
    violations: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def features(self) -> AgentFeatures:
        return AgentFeatures(
            agent_id=self.agent_id,
            observations=self.observations,
            success_estimate=self.success_estimate,
            avg_quality=self.avg_quality,
            quality_bias=self.quality_estimate_bias,
            on_time_rate=self.on_time_rate,
            latency_error=self.latency_estimate_error,
        )


# --------------------------------------------------------------------------- decay


@dataclass(frozen=True, slots=True)
class NoDecay:
    """Every observation counts equally (a plain average over the full history)."""

    def to_spec(self) -> dict[str, Any]:
        return {"name": "none"}


@dataclass(frozen=True, slots=True)
class ExponentialDecay:
    """Exponentially weighted average: an observation ``half_life`` observations old
    counts half as much as the newest one. Decay is per observation (not wall time)
    so results do not depend on clock speed."""

    half_life: float = 50.0

    def __post_init__(self) -> None:
        if self.half_life <= 0:
            raise ValidationError("half_life must be positive")

    @property
    def factor(self) -> float:
        return float(0.5 ** (1.0 / self.half_life))

    def to_spec(self) -> dict[str, Any]:
        return {"name": "exponential", "half_life": self.half_life}


@dataclass(frozen=True, slots=True)
class RollingWindow:
    """Only the most recent ``size`` observations count, equally weighted."""

    size: int = 100

    def __post_init__(self) -> None:
        if self.size < 1:
            raise ValidationError("window size must be >= 1")

    def to_spec(self) -> dict[str, Any]:
        return {"name": "rolling", "size": self.size}


Decay = NoDecay | ExponentialDecay | RollingWindow


def decay_from_spec(spec: Mapping[str, Any] | str | None) -> Decay:
    if spec is None:
        return NoDecay()
    if isinstance(spec, str):
        spec = {"name": spec}
    params = {k: v for k, v in spec.items() if k != "name"}
    name = spec.get("name", "none")
    if name in ("none", "no_decay"):
        return NoDecay()
    if name == "exponential":
        return ExponentialDecay(**params)
    if name in ("rolling", "rolling_window"):
        return RollingWindow(**params)
    raise ValidationError(f"unknown reputation decay {name!r}")


# ----------------------------------------------------------------------- systems


class ReputationSystem(ABC):
    """Plugin interface for reputation."""

    name: str = "reputation"

    @abstractmethod
    def record(self, observation: Observation) -> None: ...

    @abstractmethod
    def features(self, agent_id: str, task_type: str | None) -> AgentFeatures: ...

    def profile(self, agent_id: str, task_type: str | None = None) -> ReputationProfile | None:
        return None

    def to_spec(self) -> dict[str, Any]:
        return {"name": self.name}


class NoReputation(ReputationSystem):
    """Ignores history entirely: every agent always looks like a newcomer."""

    name = "none"

    def record(self, observation: Observation) -> None:
        return None

    def features(self, agent_id: str, task_type: str | None) -> AgentFeatures:
        return AgentFeatures(agent_id=agent_id)


class StaticReputation(ReputationSystem):
    """Fixed, externally supplied features that never update (a research baseline)."""

    name = "static"

    def __init__(self, features: Mapping[str, AgentFeatures | Mapping[str, Any]]) -> None:
        self._features = {
            agent_id: (f if isinstance(f, AgentFeatures) else AgentFeatures.from_dict(f))
            for agent_id, f in features.items()
        }

    def record(self, observation: Observation) -> None:
        return None

    def features(self, agent_id: str, task_type: str | None) -> AgentFeatures:
        return self._features.get(agent_id, AgentFeatures(agent_id=agent_id))


@dataclass(slots=True)
class _Accumulator:
    observations: int = 0
    completed: int = 0
    failed: int = 0
    weight: float = 0.0
    successes: float = 0.0
    quality: float = 0.0
    on_time: float = 0.0
    violations: float = 0.0
    q_weight: float = 0.0
    q_abs: float = 0.0
    q_signed: float = 0.0
    l_weight: float = 0.0
    l_rel: float = 0.0
    samples: deque[Observation] = field(default_factory=deque)

    def scale(self, factor: float) -> None:
        for name in (
            "weight",
            "successes",
            "quality",
            "on_time",
            "violations",
            "q_weight",
            "q_abs",
            "q_signed",
            "l_weight",
            "l_rel",
        ):
            setattr(self, name, getattr(self, name) * factor)

    def add(self, obs: Observation, sign: float = 1.0) -> None:
        count = 1 if sign > 0 else -1
        self.observations += count
        if obs.success:
            self.completed += count
        else:
            self.failed += count
        self.weight += sign
        self.successes += sign * obs.success
        self.quality += sign * obs.quality
        self.on_time += sign * obs.on_time
        self.violations += sign * obs.violation
        if obs.estimated_quality is not None:
            error = obs.estimated_quality - obs.quality
            self.q_weight += sign
            self.q_abs += sign * abs(error)
            self.q_signed += sign * error
        if obs.estimated_latency is not None and obs.latency > 0:
            self.l_weight += sign
            self.l_rel += sign * abs(obs.estimated_latency - obs.latency) / obs.latency


class MultiDimensionalReputation(ReputationSystem):
    """The default reputation system.

    ``success_estimate`` is the posterior mean of a Beta(prior_successes,
    prior_failures) prior updated with (decay-weighted) successes and failures, so a
    newcomer starts at ``prior_successes / (prior_successes + prior_failures)``
    rather than at an extreme. With ``task_specific=True`` selection features use
    only the agent's history on the same task type.
    """

    name = "multi_dimensional"

    def __init__(
        self,
        *,
        decay: Decay | None = None,
        prior_successes: float = 1.0,
        prior_failures: float = 1.0,
        task_specific: bool = True,
    ) -> None:
        if prior_successes <= 0 or prior_failures <= 0:
            raise ValidationError("Beta prior parameters must be positive")
        self.decay: Decay = decay or NoDecay()
        self.prior_successes = prior_successes
        self.prior_failures = prior_failures
        self.task_specific = task_specific
        self._acc: dict[tuple[str, str | None], _Accumulator] = {}

    def record(self, observation: Observation) -> None:
        for key in ((observation.agent_id, None), (observation.agent_id, observation.task_type)):
            acc = self._acc.setdefault(key, _Accumulator())
            if isinstance(self.decay, ExponentialDecay):
                acc.scale(self.decay.factor)
            acc.add(observation)
            if isinstance(self.decay, RollingWindow):
                acc.samples.append(observation)
                if len(acc.samples) > self.decay.size:
                    acc.add(acc.samples.popleft(), sign=-1.0)

    def profile(self, agent_id: str, task_type: str | None = None) -> ReputationProfile | None:
        acc = self._acc.get((agent_id, task_type))
        if acc is None or acc.observations == 0:
            return None
        w = acc.weight
        return ReputationProfile(
            agent_id=agent_id,
            task_type=task_type,
            observations=acc.observations,
            completed=acc.completed,
            failed=acc.failed,
            effective_weight=w,
            success_rate=_clip(acc.successes / w) if w > 0 else None,
            success_estimate=_clip(
                (acc.successes + self.prior_successes)
                / (w + self.prior_successes + self.prior_failures)
            ),
            avg_quality=_clip(acc.quality / w) if w > 0 else None,
            on_time_rate=_clip(acc.on_time / w) if w > 0 else None,
            quality_estimate_error=acc.q_abs / acc.q_weight if acc.q_weight > 1e-12 else None,
            quality_estimate_bias=acc.q_signed / acc.q_weight if acc.q_weight > 1e-12 else None,
            latency_estimate_error=acc.l_rel / acc.l_weight if acc.l_weight > 1e-12 else None,
            violations=max(acc.violations, 0.0),
        )

    def features(self, agent_id: str, task_type: str | None) -> AgentFeatures:
        profile = self.profile(agent_id, task_type if self.task_specific else None)
        if profile is None:
            return AgentFeatures(
                agent_id=agent_id,
                success_estimate=self.prior_successes
                / (self.prior_successes + self.prior_failures),
            )
        return profile.features()

    def task_types(self, agent_id: str) -> list[str]:
        return sorted(t for (a, t) in self._acc if a == agent_id and t is not None)

    def agents(self) -> list[str]:
        return sorted({a for (a, _) in self._acc})

    def to_spec(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "decay": self.decay.to_spec(),
            "prior_successes": self.prior_successes,
            "prior_failures": self.prior_failures,
            "task_specific": self.task_specific,
        }


def _clip(value: float) -> float:
    return min(1.0, max(0.0, value))
