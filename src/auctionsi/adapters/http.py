"""Agents that live behind an HTTP endpoint.

The marketplace never runs remote agent code; it exchanges JSON with an endpoint
that you operate (or trust) across an explicit network boundary.

Protocol (both POST, JSON in and out):

* ``{base_url}/bid``      body ``{"task": {...}, "context": {...}}``
  reply ``{"price": 0.04, "estimated_latency": 8, ...}`` or ``{"abstain": true}``
* ``{base_url}/execute``  body ``{"task": {...}, "contract": {...}}``
  reply ``{"success": true, "output": ..., "error": null, "actual_cost": 0.01}``
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterable, Mapping
from typing import Any

from auctionsi.adapters.http_client import HTTPAdapterError, check_base_url, post_json
from auctionsi.core.agent import Agent, BidContext
from auctionsi.core.bid import BidProposal
from auctionsi.core.capability import Capability
from auctionsi.core.contract import Contract
from auctionsi.core.execution import ExecutionResult
from auctionsi.core.task import Task

_PROPOSAL_FIELDS = (
    "price",
    "estimated_latency",
    "estimated_quality",
    "estimated_cost",
    "confidence",
    "capacity",
    "valid_for",
    "constraints",
    "terms",
)


class HTTPAgent(Agent):
    """``token_env`` names an environment variable holding a bearer token; the token
    itself is never stored on the agent, logged or included in events."""

    def __init__(
        self,
        agent_id: str,
        base_url: str,
        *,
        capabilities: Iterable[Capability | str | Mapping[str, Any]],
        timeout: float = 10.0,
        max_response_bytes: int = 1024 * 1024,
        token_env: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(agent_id, capabilities=capabilities, **kwargs)
        self.base_url = check_base_url(base_url)
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes
        self.token_env = token_env

    def _headers(self) -> dict[str, str]:
        if self.token_env and os.environ.get(self.token_env):
            return {"Authorization": f"Bearer {os.environ[self.token_env]}"}
        return {}

    def _post(self, path: str, payload: Mapping[str, Any]) -> Any:
        return post_json(
            f"{self.base_url}/{path}",
            payload,
            timeout=self.timeout,
            max_bytes=self.max_response_bytes,
            headers=self._headers(),
        )

    def bid(self, task: Task, context: BidContext) -> BidProposal | None:
        reply = self._post(
            "bid",
            {
                "task": task.to_dict(),
                "context": {
                    "auction_id": context.auction_id,
                    "mechanism": context.mechanism,
                    "sealed": context.sealed,
                    "unit": context.unit,
                    "round": context.round,
                },
            },
        )
        if not isinstance(reply, dict):
            raise HTTPAdapterError("bid reply must be a JSON object")
        if reply.get("abstain"):
            return None
        # Only known fields are copied; the marketplace validates their values.
        return BidProposal(**{k: reply[k] for k in _PROPOSAL_FIELDS if k in reply})

    def execute(self, task: Task, contract: Contract) -> ExecutionResult:
        start = time.perf_counter()
        try:
            reply = self._post("execute", {"task": task.to_dict(), "contract": contract.to_dict()})
        except HTTPAdapterError as exc:
            return ExecutionResult.failure(str(exc), latency=time.perf_counter() - start)
        latency = time.perf_counter() - start
        if not isinstance(reply, dict):
            return ExecutionResult.failure("execute reply must be a JSON object", latency)
        cost = reply.get("actual_cost")
        return ExecutionResult(
            success=bool(reply.get("success", False)),
            output=reply.get("output"),
            latency=latency,
            actual_cost=float(cost) if isinstance(cost, int | float) else None,
            error=str(reply["error"])[:300] if reply.get("error") else None,
        )

    def describe(self) -> dict[str, Any]:
        return {**super().describe(), "endpoint": self.base_url}

    def spec(self) -> dict[str, Any]:
        """Declarative spec for registries; holds the env var *name*, never the token."""
        return {
            "kind": "http",
            "agent_id": self.agent_id,
            "base_url": self.base_url,
            "capabilities": [c.to_dict() for c in self.capabilities],
            "timeout": self.timeout,
            "max_response_bytes": self.max_response_bytes,
            "token_env": self.token_env,
            "max_concurrent_tasks": self.max_concurrent_tasks,
        }
