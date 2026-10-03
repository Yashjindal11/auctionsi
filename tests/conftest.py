from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from auctionsi.core import (
    Agent,
    AuctionNotice,
    BidContext,
    BidProposal,
    Contract,
    ExecutionResult,
    OpenAuctionView,
    Task,
)
from auctionsi.market import IdGenerator, ManualClock, Marketplace


class ScriptedAgent(Agent):
    """Deterministic test agent with configurable bid and behaviour."""

    def __init__(
        self,
        agent_id: str,
        price: float | None,
        *,
        capabilities: tuple[str, ...] = ("analysis",),
        latency: float = 1.0,
        quality: float | None = 0.9,
        confidence: float | None = None,
        output: Any = None,
        fail: bool | int = False,
        floor: float | None = None,
        bid_error: Exception | None = None,
        proposal: object = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(agent_id, capabilities=capabilities, **kwargs)
        self.price = price
        self.latency = latency
        self.quality = quality
        self.confidence = confidence
        self.output = output
        self.fail = fail
        self.floor = floor
        self.bid_error = bid_error
        self.proposal = proposal
        self.executions = 0
        self.notices: list[AuctionNotice] = []

    def bid(self, task: Task, context: BidContext) -> BidProposal | None:
        if self.bid_error is not None:
            raise self.bid_error
        if self.proposal is not None:
            return self.proposal  # type: ignore[return-value]
        if self.price is None:
            return None
        return BidProposal(
            price=self.price,
            estimated_latency=self.latency,
            estimated_quality=self.quality,
            confidence=self.confidence,
        )

    def revise_bid(self, task: Task, view: OpenAuctionView) -> BidProposal | None:
        if self.floor is None or view.best_price is None or view.own_bid is None:
            return None
        if view.own_bid.price <= view.best_price:
            return None
        target = round(view.best_price - 0.01, 10)
        if target < self.floor:
            return None
        return BidProposal(price=target, estimated_latency=self.latency)

    def execute(self, task: Task, contract: Contract) -> ExecutionResult:
        self.executions += 1
        failing = self.fail if isinstance(self.fail, bool) else self.executions <= self.fail
        if failing:
            return ExecutionResult(success=False, error="simulated failure", latency=self.latency)
        output = self.output if self.output is not None else {"quality": self.quality}
        return ExecutionResult(success=True, output=output, latency=self.latency)

    def observe(self, notice: AuctionNotice) -> None:
        self.notices.append(notice)


MarketFactory = Callable[..., Marketplace]


@pytest.fixture
def market_factory() -> MarketFactory:
    def build(**kwargs: Any) -> Marketplace:
        kwargs.setdefault("clock", ManualClock())
        kwargs.setdefault("ids", IdGenerator())
        return Marketplace(**kwargs)

    return build


def task(task_id: str = "task-001", **kwargs: Any) -> Task:
    kwargs.setdefault("task_type", "analysis")
    return Task(task_id=task_id, **kwargs)
