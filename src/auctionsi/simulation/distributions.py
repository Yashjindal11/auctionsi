"""Seeded probability distributions used by the synthetic generators."""

from __future__ import annotations

import math
import random
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any

from auctionsi.errors import ConfigurationError


class Distribution(ABC):
    name: str = "distribution"

    @abstractmethod
    def sample(self, rng: random.Random) -> float: ...

    def to_spec(self) -> dict[str, Any]:
        params: dict[str, Any] = asdict(self) if is_dataclass(self) else {}
        return {"name": self.name, **params}


@dataclass(frozen=True)
class Constant(Distribution):
    value: float
    name = "constant"

    def sample(self, rng: random.Random) -> float:
        return self.value


@dataclass(frozen=True)
class Uniform(Distribution):
    low: float
    high: float
    name = "uniform"

    def __post_init__(self) -> None:
        if self.high < self.low:
            raise ConfigurationError("uniform: high must be >= low")

    def sample(self, rng: random.Random) -> float:
        return rng.uniform(self.low, self.high)


@dataclass(frozen=True)
class Normal(Distribution):
    """Normal, optionally clipped to ``[low, high]``."""

    mean: float
    sd: float
    low: float | None = None
    high: float | None = None
    name = "normal"

    def sample(self, rng: random.Random) -> float:
        value = rng.gauss(self.mean, self.sd)
        if self.low is not None:
            value = max(self.low, value)
        if self.high is not None:
            value = min(self.high, value)
        return value


@dataclass(frozen=True)
class LogNormal(Distribution):
    """Log-normal with the given *median* and log-scale ``sigma``."""

    median: float
    sigma: float
    name = "lognormal"

    def __post_init__(self) -> None:
        if self.median <= 0 or self.sigma < 0:
            raise ConfigurationError("lognormal: median must be > 0 and sigma >= 0")

    def sample(self, rng: random.Random) -> float:
        return rng.lognormvariate(math.log(self.median), self.sigma)


@dataclass(frozen=True)
class Beta(Distribution):
    """Beta(a, b) rescaled to ``[low, high]``."""

    a: float
    b: float
    low: float = 0.0
    high: float = 1.0
    name = "beta"

    def __post_init__(self) -> None:
        if self.a <= 0 or self.b <= 0:
            raise ConfigurationError("beta: a and b must be positive")

    def sample(self, rng: random.Random) -> float:
        return self.low + (self.high - self.low) * rng.betavariate(self.a, self.b)


@dataclass(frozen=True)
class Choice(Distribution):
    values: Sequence[float]
    weights: Sequence[float] | None = field(default=None)
    name = "choice"

    def __post_init__(self) -> None:
        if not self.values:
            raise ConfigurationError("choice: values must not be empty")

    def sample(self, rng: random.Random) -> float:
        return rng.choices(list(self.values), weights=self.weights)[0]

    def to_spec(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "values": list(self.values),
            "weights": None if self.weights is None else list(self.weights),
        }


_KINDS: dict[str, type[Distribution]] = {
    cls.name: cls for cls in (Constant, Uniform, Normal, LogNormal, Beta, Choice)
}

DistributionSpec = Distribution | float | int | str | Mapping[str, Any]


def as_distribution(
    spec: DistributionSpec, presets: Mapping[str, Distribution] | None = None
) -> Distribution:
    """Accept a Distribution, a number (constant), a preset name, or a spec mapping."""
    if isinstance(spec, Distribution):
        return spec
    if isinstance(spec, int | float) and not isinstance(spec, bool):
        return Constant(float(spec))
    if isinstance(spec, str):
        if presets and spec in presets:
            return presets[spec]
        raise ConfigurationError(f"unknown distribution preset {spec!r}")
    if isinstance(spec, Mapping):
        name = spec.get("name")
        if not isinstance(name, str) or name not in _KINDS:
            raise ConfigurationError(f"unknown distribution {name!r}; known: {sorted(_KINDS)}")
        params = {k: v for k, v in spec.items() if k != "name"}
        try:
            return _KINDS[name](**params)
        except TypeError as exc:
            raise ConfigurationError(f"bad parameters for {name}: {exc}") from exc
    raise ConfigurationError(f"cannot interpret {spec!r} as a distribution")
