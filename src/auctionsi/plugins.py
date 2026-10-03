"""Name-based plugin registries so mechanisms, policies, verifiers and the rest can be
selected from configuration files and rebuilt from recorded specs during replay."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from auctionsi.errors import ConfigurationError, NotFoundError, ValidationError

T = TypeVar("T")


class Registry(Generic[T]):
    def __init__(self, kind: str) -> None:
        self.kind = kind
        self._factories: dict[str, Callable[..., T]] = {}

    def register(self, name: str, factory: Callable[..., T], *, replace: bool = False) -> None:
        if name in self._factories and not replace:
            raise ConfigurationError(f"{self.kind} {name!r} is already registered")
        self._factories[name] = factory

    def names(self) -> list[str]:
        return sorted(self._factories)

    def __contains__(self, name: object) -> bool:
        return name in self._factories

    def create(self, spec: str | Mapping[str, Any]) -> T:
        """Build from ``"name"`` or ``{"name": ..., **params}``."""
        if isinstance(spec, str):
            name, params = spec, {}
        elif isinstance(spec, Mapping) and isinstance(spec.get("name"), str):
            name = spec["name"]
            params = {k: v for k, v in spec.items() if k != "name"}
        else:
            raise ConfigurationError(f"invalid {self.kind} spec {spec!r}")
        if name not in self._factories:
            raise NotFoundError(f"unknown {self.kind} {name!r}; known: {self.names()}")
        try:
            return self._factories[name](**params)
        except (TypeError, ValidationError) as exc:
            raise ConfigurationError(f"cannot build {self.kind} {name!r}: {exc}") from exc


@dataclass
class PluginRegistry:
    mechanisms: Registry[Any] = field(default_factory=lambda: Registry("auction mechanism"))
    policies: Registry[Any] = field(default_factory=lambda: Registry("selection policy"))
    verifiers: Registry[Any] = field(default_factory=lambda: Registry("verifier"))
    settlements: Registry[Any] = field(default_factory=lambda: Registry("settlement policy"))
    reputations: Registry[Any] = field(default_factory=lambda: Registry("reputation system"))
    strategies: Registry[Any] = field(default_factory=lambda: Registry("bid strategy"))


def _reputation(**params: Any) -> Any:
    from auctionsi.reputation import MultiDimensionalReputation, decay_from_spec

    decay = decay_from_spec(params.pop("decay", None))
    return MultiDimensionalReputation(decay=decay, **params)


def default_registry() -> PluginRegistry:
    """A fresh registry populated with every built-in plugin."""
    from auctionsi import mechanisms as m
    from auctionsi import selection as s
    from auctionsi import settlement as st
    from auctionsi import verification as v
    from auctionsi.bidding import strategies as bs
    from auctionsi.reputation import NoReputation, StaticReputation
    from auctionsi.simulation.verifier import SimulatedQualityVerifier

    reg = PluginRegistry()
    for cls in (
        m.FirstPriceReverseAuction,
        m.SecondPriceReverseAuction,
        m.MultiWinnerReverseAuction,
        m.OpenReverseAuction,
        m.ForwardAuction,
        m.BundleReverseAuction,
        m.CapacityAuction,
    ):
        reg.mechanisms.register(cls.name, cls)
    for pcls in (
        s.LowestPrice,
        s.HighestQuality,
        s.LowestLatency,
        s.WeightedScore,
        s.RiskAdjustedCost,
        s.ReputationAdjustedCost,
    ):
        reg.policies.register(pcls.name, pcls)

    def exploration(base: Any = "lowest_price", weight: float = 0.01) -> Any:
        return s.ExplorationBonus(reg.policies.create(base), weight)

    reg.policies.register(s.ExplorationBonus.name, exploration)
    for vname, vfactory in (
        ("accept", v.AcceptVerifier),
        ("schema", v.SchemaVerifier),
        ("exact_match", v.ExactMatchVerifier),
        ("tolerance", v.ToleranceVerifier),
        ("metric_threshold", v.MetricThresholdVerifier),
        ("simulated_quality", SimulatedQualityVerifier),
    ):
        reg.verifiers.register(vname, vfactory)
    for scls in (st.PayOnPass, st.QualityProportionalPayment, st.PartialPaymentOnFailure):
        reg.settlements.register(scls.name, scls)
    reg.reputations.register("multi_dimensional", _reputation)
    reg.reputations.register("none", NoReputation)
    reg.reputations.register("static", StaticReputation)
    for name, factory in bs.BUILTIN_STRATEGIES.items():
        reg.strategies.register(name, factory)
    return reg
