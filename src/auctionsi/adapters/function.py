"""Wrap a plain Python function as a marketplace agent."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from auctionsi.core.agent import Agent, BidContext
from auctionsi.core.bid import BidProposal
from auctionsi.core.capability import Capability
from auctionsi.core.contract import Contract
from auctionsi.core.execution import ExecutionResult
from auctionsi.core.task import Task

PriceRule = float | Callable[[Task], float | None]


class PythonFunctionAgent(Agent):
    """``fn(task, contract) -> output`` becomes an agent.

    ``price`` is either a constant or ``price(task) -> float | None`` (``None``
    abstains). Latency is measured with a monotonic clock, so it is real elapsed
    time and therefore not reproducible across runs.
    """

    def __init__(
        self,
        agent_id: str,
        fn: Callable[[Task, Contract], Any],
        *,
        capabilities: Iterable[Capability | str | Mapping[str, Any]],
        price: PriceRule,
        estimated_latency: float | None = None,
        estimated_quality: float | None = None,
        confidence: float | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(agent_id, capabilities=capabilities, **kwargs)
        self.fn = fn
        self.price = price
        self.estimated_latency = estimated_latency
        self.estimated_quality = estimated_quality
        self.confidence = confidence

    def bid(self, task: Task, context: BidContext) -> BidProposal | None:
        price = self.price(task) if callable(self.price) else self.price
        if price is None:
            return None
        return BidProposal(
            price=price,
            estimated_latency=self.estimated_latency,
            estimated_quality=self.estimated_quality,
            confidence=self.confidence,
        )

    def execute(self, task: Task, contract: Contract) -> ExecutionResult:
        start = time.perf_counter()
        output = self.fn(task, contract)
        return ExecutionResult(success=True, output=output, latency=time.perf_counter() - start)
