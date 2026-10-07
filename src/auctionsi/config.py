"""Marketplace configuration files (YAML/JSON), validated with Pydantic."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from auctionsi.errors import ConfigurationError
from auctionsi.market.clock import Clock, IdGenerator
from auctionsi.market.marketplace import Marketplace
from auctionsi.market.recovery import RecoveryPolicy
from auctionsi.market.validation import BidValidationConfig
from auctionsi.plugins import PluginRegistry, default_registry
from auctionsi.reputation.base import NoReputation, ReputationSystem
from auctionsi.security.loading import load_config_file
from auctionsi.storage.base import MarketStore
from auctionsi.storage.sql import SQLStore

Spec = str | dict[str, Any]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MarketSection(_Strict):
    name: str = "market"
    disclose_clearing_price: bool = False


class AuctionSection(_Strict):
    mechanism: Spec = "first_price_reverse"
    bidding_window: float | None = Field(None, ge=0)


class SelectionSection(BaseModel):
    """``strategy`` names the policy; any other keys are its parameters."""

    model_config = ConfigDict(extra="allow")
    strategy: str = "lowest_price"

    def spec(self) -> dict[str, Any]:
        return {"name": self.strategy, **(self.model_extra or {})}


class ReputationSection(_Strict):
    enabled: bool = True
    decay: str = "none"
    half_life: float | None = None
    window: int | None = None
    task_specific: bool = True
    prior_successes: float = 1.0
    prior_failures: float = 1.0

    def spec(self) -> dict[str, Any]:
        decay: dict[str, Any] = {"name": self.decay}
        if self.half_life is not None:
            decay["half_life"] = self.half_life
        if self.window is not None:
            decay["size"] = self.window
        return {
            "name": "multi_dimensional",
            "decay": decay,
            "task_specific": self.task_specific,
            "prior_successes": self.prior_successes,
            "prior_failures": self.prior_failures,
        }


class VerificationSection(_Strict):
    required: bool = True
    verifier: Spec = "simulated_quality"


class SettlementSection(BaseModel):
    """``policy`` names the settlement policy; other keys (except ``currency``) are
    its parameters. ``currency`` is the default unit for tasks created by the CLI."""

    model_config = ConfigDict(extra="allow")
    currency: str = "credits"
    policy: str = "pay_on_pass"

    def spec(self) -> dict[str, Any]:
        return {"name": self.policy, **(self.model_extra or {})}


class RecoverySection(_Strict):
    retry_same: int = Field(0, ge=0)
    next_best: int = Field(0, ge=0)
    reopen: int = Field(0, ge=0)


class MarketConfig(_Strict):
    market: MarketSection = Field(default_factory=MarketSection)
    auction: AuctionSection = Field(default_factory=AuctionSection)
    selection: SelectionSection = Field(default_factory=SelectionSection)
    reputation: ReputationSection = Field(default_factory=ReputationSection)
    verification: VerificationSection = Field(default_factory=VerificationSection)
    settlement: SettlementSection = Field(default_factory=SettlementSection)
    recovery: RecoverySection = Field(default_factory=RecoverySection)
    validation: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path | None) -> MarketConfig:
        if path is None:
            return cls()
        data = load_config_file(path)
        try:
            return cls.model_validate(data or {})
        except ValidationError as exc:
            raise ConfigurationError(f"invalid market config {path}: {exc}") from exc

    def build_reputation(self, plugins: PluginRegistry) -> ReputationSystem:
        if not self.reputation.enabled:
            return NoReputation()
        result: ReputationSystem = plugins.reputations.create(self.reputation.spec())
        return result

    def build(
        self,
        *,
        store: MarketStore | None = None,
        plugins: PluginRegistry | None = None,
        clock: Clock | None = None,
        ids: IdGenerator | None = None,
        keep_events: bool = True,
    ) -> Marketplace:
        reg = plugins or default_registry()
        try:
            validation = BidValidationConfig(**self.validation)
        except TypeError as exc:
            raise ConfigurationError(f"invalid validation section: {exc}") from exc
        verifier = (
            reg.verifiers.create(self.verification.verifier)
            if self.verification.required
            else reg.verifiers.create("accept")
        )
        return Marketplace(
            self.market.name,
            mechanism=reg.mechanisms.create(self.auction.mechanism),
            policy=reg.policies.create(self.selection.spec()),
            verifier=verifier,
            settlement=reg.settlements.create(self.settlement.spec()),
            reputation=self.build_reputation(reg),
            recovery=RecoveryPolicy(**self.recovery.model_dump()),
            validation=validation,
            clock=clock,
            ids=ids,
            store=store,
            plugins=reg,
            keep_events=keep_events,
            disclose_clearing_price=self.market.disclose_clearing_price,
            bidding_window=self.auction.bidding_window,
        )

    def restore(self, store: SQLStore, *, ids: IdGenerator | None = None) -> Marketplace:
        """A marketplace with every stored agent that has a spec, and reputation rebuilt
        from stored observations. The store is attached after loading, so re-registering
        agents is not logged as new events."""
        from auctionsi.adapters.specs import build_agent

        market = self.build(ids=ids)
        for observation in store.observations():
            market.reputation.record(observation)
        for profile in store.list_agents():
            if profile.get("spec"):
                market.register(build_agent(profile["spec"]))
        market.attach_store(store)
        return market


DEFAULT_CONFIG_YAML = """\
# AuctionSI marketplace configuration
market:
  name: research_market
  disclose_clearing_price: false

auction:
  mechanism: first_price_reverse   # second_price_reverse, open_reverse, multi_winner_reverse
  bidding_window: 10

selection:
  strategy: risk_adjusted_cost      # lowest_price, weighted_score, highest_quality, ...
  failure_cost: 0.2

reputation:
  enabled: true
  decay: exponential                # none, exponential, rolling
  half_life: 50

verification:
  required: true
  verifier: simulated_quality       # schema, metric_threshold, exact_match, accept

settlement:
  currency: credits
  policy: pay_on_pass
  penalty_rate: 0.1

recovery:
  retry_same: 0
  next_best: 1
  reopen: 0
"""
