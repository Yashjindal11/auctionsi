"""A human-in-the-loop agent: a person decides whether to bid and does the work."""

from __future__ import annotations

import json
import math
import time
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from auctionsi.core.agent import Agent, BidContext
from auctionsi.core.bid import BidProposal
from auctionsi.core.capability import Capability
from auctionsi.core.contract import Contract
from auctionsi.core.execution import ExecutionResult
from auctionsi.core.task import Task


class HumanAgent(Agent):
    """Prompts through ``ask`` (``input`` by default). A blank price abstains. The
    submitted result is parsed as JSON when possible, otherwise kept as text."""

    def __init__(
        self,
        agent_id: str,
        *,
        capabilities: Iterable[Capability | str | Mapping[str, Any]],
        ask: Callable[[str], str] = input,
        estimated_latency: float | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(agent_id, capabilities=capabilities, **kwargs)
        self.ask = ask
        self.estimated_latency = estimated_latency

    def bid(self, task: Task, context: BidContext) -> BidProposal | None:
        budget = "" if task.budget is None else f" (budget {task.budget} {task.unit})"
        answer = self.ask(
            f"[{self.agent_id}] Task {task.task_id} ({task.task_type}){budget}: "
            f"{task.description}\nYour price (blank to skip): "
        ).strip()
        if not answer:
            return None
        try:
            price = float(answer)
        except ValueError:
            return None
        if not math.isfinite(price):
            return None
        return BidProposal(price=price, estimated_latency=self.estimated_latency)

    def execute(self, task: Task, contract: Contract) -> ExecutionResult:
        start = time.perf_counter()
        answer = self.ask(
            f"[{self.agent_id}] You won {task.task_id} at {contract.payment_price} "
            f"{contract.unit}. Enter your result: "
        )
        try:
            output: Any = json.loads(answer)
        except json.JSONDecodeError:
            output = answer
        return ExecutionResult(success=True, output=output, latency=time.perf_counter() - start)
