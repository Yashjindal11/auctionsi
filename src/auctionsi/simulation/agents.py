"""Simulated agents with hidden ground truth (cost, quality, reliability, latency)."""

from __future__ import annotations

import math
import random
from collections.abc import Iterable, Mapping
from typing import Any

from auctionsi.bidding.strategies import BidInputs, BidStrategy, CostPlus
from auctionsi.core.agent import Agent, AuctionNotice, BidContext, CostModel, OpenAuctionView
from auctionsi.core.bid import BidProposal
from auctionsi.core.capability import Capability
from auctionsi.core.contract import Contract
from auctionsi.core.execution import ExecutionResult
from auctionsi.core.task import Task
from auctionsi.errors import ValidationError


class SimulatedAgent(Agent):
    """An agent whose behaviour is drawn from seeded distributions.

    Ground truth (``quality``, ``reliability``, ``latency_mean``, ``cost_model``) is
    hidden from the marketplace; it only sees bids and outcomes. Optional *report
    biases* make the agent misstate its quality or latency in bids, which is how
    dishonest agents are modelled.

    Task ``requirements["complexity"]`` (default 1) scales latency, and therefore
    the variable part of cost.
    """

    def __init__(
        self,
        agent_id: str,
        *,
        capabilities: Iterable[Capability | str | Mapping[str, Any]],
        cost_model: CostModel,
        quality: float | Mapping[str, float] = 0.8,
        quality_sd: float = 0.05,
        reliability: float = 0.95,
        latency_mean: float = 10.0,
        latency_sigma: float = 0.25,
        strategy: BidStrategy | None = None,
        quality_report_bias: float = 0.0,
        latency_report_bias: float = 0.0,
        seed: int = 0,
        operator: str | None = None,
        **kwargs: Any,
    ) -> None:
        metadata = {**(kwargs.pop("metadata", None) or {}), "operator": operator or agent_id}
        super().__init__(
            agent_id, capabilities=capabilities, cost_model=cost_model, metadata=metadata, **kwargs
        )
        if not 0 <= reliability <= 1:
            raise ValidationError("reliability must be in [0, 1]")
        if latency_mean <= 0:
            raise ValidationError("latency_mean must be positive")
        self.quality = quality
        self.quality_sd = quality_sd
        self.reliability = reliability
        self.latency_mean = latency_mean
        self.latency_sigma = latency_sigma
        self.strategy = strategy or CostPlus()
        self.quality_report_bias = quality_report_bias
        self.latency_report_bias = latency_report_bias
        self.seed = seed
        self.operator = operator or agent_id
        self.rng = random.Random(seed)

    # ------------------------------------------------------------- ground truth

    def true_quality(self, task_type: str) -> float:
        if isinstance(self.quality, Mapping):
            return float(self.quality.get(task_type, 0.0))
        return float(self.quality)

    def expected_latency(self, task: Task) -> float:
        complexity = task.requirements.get("complexity", 1.0)
        if not isinstance(complexity, int | float) or complexity <= 0:
            complexity = 1.0
        return self.latency_mean * float(complexity)

    def expected_cost(self, task: Task) -> float:
        return self.cost_model.cost(self.expected_latency(task))

    def _inputs(self, task: Task) -> BidInputs:
        return BidInputs(
            task=task,
            cost=self.expected_cost(task),
            quality=self.true_quality(task.task_type),
            latency=self.expected_latency(task),
            reliability=self.reliability,
            rng=self.rng,
        )

    # --------------------------------------------------------------- behaviour

    def _proposal(self, inputs: BidInputs, price: float) -> BidProposal:
        reported_quality = min(1.0, max(0.0, inputs.quality + self.quality_report_bias))
        confidence = min(1.0, max(0.0, self.reliability + self.quality_report_bias))
        return BidProposal(
            price=price,
            estimated_latency=inputs.latency * max(0.0, 1 + self.latency_report_bias),
            estimated_quality=reported_quality,
            estimated_cost=inputs.cost,
            confidence=confidence,
        )

    def bid(self, task: Task, context: BidContext) -> BidProposal | None:
        inputs = self._inputs(task)
        price = self.strategy.price(inputs)
        return None if price is None else self._proposal(inputs, price)

    def revise_bid(self, task: Task, view: OpenAuctionView) -> BidProposal | None:
        inputs = self._inputs(task)
        price = self.strategy.revise(inputs, view)
        return None if price is None else self._proposal(inputs, price)

    def execute(self, task: Task, contract: Contract) -> ExecutionResult:
        expected = self.expected_latency(task)
        sigma = self.latency_sigma
        latency = expected * math.exp(self.rng.gauss(-(sigma**2) / 2, sigma)) if sigma else expected
        cost = self.cost_model.cost(latency)
        if self.rng.random() >= self.reliability:
            return ExecutionResult(
                success=False, latency=latency, actual_cost=cost, error="simulated failure"
            )
        quality = min(
            1.0, max(0.0, self.rng.gauss(self.true_quality(task.task_type), self.quality_sd))
        )
        return ExecutionResult(
            success=True,
            output={"quality": quality, "agent_id": self.agent_id},
            latency=latency,
            actual_cost=cost,
        )

    def observe(self, notice: AuctionNotice) -> None:
        self.strategy.observe(notice)

    def spec(self) -> dict[str, Any]:
        """Everything needed to rebuild this agent with :func:`agent_from_spec`."""
        return {
            "agent_id": self.agent_id,
            "capabilities": [c.to_dict() for c in self.capabilities],
            "cost_model": self.cost_model.to_dict(),
            "quality": dict(self.quality) if isinstance(self.quality, Mapping) else self.quality,
            "quality_sd": self.quality_sd,
            "reliability": self.reliability,
            "latency_mean": self.latency_mean,
            "latency_sigma": self.latency_sigma,
            "strategy": self.strategy.to_spec(),
            "quality_report_bias": self.quality_report_bias,
            "latency_report_bias": self.latency_report_bias,
            "seed": self.seed,
            "operator": self.operator,
            "max_concurrent_tasks": self.max_concurrent_tasks,
        }


_SPEC_KEYS = {
    "agent_id",
    "name",
    "capabilities",
    "cost_model",
    "quality",
    "quality_sd",
    "reliability",
    "latency_mean",
    "latency_sigma",
    "strategy",
    "quality_report_bias",
    "latency_report_bias",
    "seed",
    "operator",
    "max_concurrent_tasks",
}


def agent_from_spec(spec: Mapping[str, Any]) -> SimulatedAgent:
    """Build a simulated agent from a (validated) declarative spec, as found in YAML."""
    from auctionsi.bidding.strategies import BUILTIN_STRATEGIES

    if not isinstance(spec, Mapping):
        raise ValidationError("agent spec must be a mapping")
    unknown = set(spec) - _SPEC_KEYS
    if unknown:
        raise ValidationError(f"unknown agent spec fields: {sorted(unknown)}")
    if "agent_id" not in spec or "capabilities" not in spec:
        raise ValidationError("agent spec needs agent_id and capabilities")
    values = dict(spec)
    cost = values.pop("cost_model", {}) or {}
    if not isinstance(cost, Mapping):
        raise ValidationError("cost_model must be a mapping")
    strategy_spec = values.pop("strategy", "cost_plus")
    if isinstance(strategy_spec, str):
        strategy_spec = {"name": strategy_spec}
    if (
        not isinstance(strategy_spec, Mapping)
        or strategy_spec.get("name") not in BUILTIN_STRATEGIES
    ):
        raise ValidationError(f"unknown strategy {strategy_spec!r}")
    params = {k: v for k, v in strategy_spec.items() if k != "name"}
    try:
        strategy = BUILTIN_STRATEGIES[strategy_spec["name"]](**params)
        return SimulatedAgent(
            values.pop("agent_id"),
            cost_model=CostModel(**cost),
            strategy=strategy,
            **values,
        )
    except TypeError as exc:
        raise ValidationError(f"invalid agent spec: {exc}") from exc
