"""Optional adapter for OpenAI-compatible chat-completion endpoints.

Works with any server that implements ``POST {base_url}/chat/completions`` (local
servers such as Ollama, vLLM or llama.cpp, or hosted providers). Nothing in
AuctionSI requires it, no SDK is imported, and no key is needed unless the
endpoint asks for one (read from the environment variable named in ``api_key_env``).

An LLM's own claims about quality are just bids; pair this agent with a
deterministic verifier wherever the task allows.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from auctionsi.adapters.http_client import HTTPAdapterError, check_base_url, post_json
from auctionsi.core.agent import Agent, BidContext
from auctionsi.core.bid import BidProposal
from auctionsi.core.capability import Capability
from auctionsi.core.contract import Contract
from auctionsi.core.execution import ExecutionResult
from auctionsi.core.task import Task

DEFAULT_TEMPLATE = "Task type: {task_type}\n\n{description}\n\nRequirements: {requirements}"


class OpenAICompatibleAgent(Agent):
    def __init__(
        self,
        agent_id: str,
        *,
        base_url: str,
        model: str,
        capabilities: Iterable[Capability | str | Mapping[str, Any]],
        price: float | Callable[[Task], float | None],
        api_key_env: str | None = None,
        system_prompt: str = "You are a careful assistant. Answer the task precisely.",
        prompt_template: str = DEFAULT_TEMPLATE,
        temperature: float = 0.0,
        estimated_latency: float | None = None,
        estimated_quality: float | None = None,
        timeout: float = 60.0,
        max_response_bytes: int = 2 * 1024 * 1024,
        **kwargs: Any,
    ) -> None:
        super().__init__(agent_id, capabilities=capabilities, **kwargs)
        self.base_url = check_base_url(base_url)
        self.model = model
        self.price = price
        self.api_key_env = api_key_env
        self.system_prompt = system_prompt
        self.prompt_template = prompt_template
        self.temperature = temperature
        self.estimated_latency = estimated_latency
        self.estimated_quality = estimated_quality
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes

    def bid(self, task: Task, context: BidContext) -> BidProposal | None:
        price = self.price(task) if callable(self.price) else self.price
        if price is None:
            return None
        return BidProposal(
            price=price,
            estimated_latency=self.estimated_latency,
            estimated_quality=self.estimated_quality,
        )

    def prompt(self, task: Task) -> str:
        return self.prompt_template.format(
            task_type=task.task_type,
            description=task.description,
            requirements=dict(task.requirements),
        )

    def execute(self, task: Task, contract: Contract) -> ExecutionResult:
        headers = {}
        if self.api_key_env and os.environ.get(self.api_key_env):
            headers["Authorization"] = f"Bearer {os.environ[self.api_key_env]}"
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": self.prompt(task)},
            ],
        }
        start = time.perf_counter()
        try:
            reply = post_json(
                f"{self.base_url}/chat/completions",
                payload,
                timeout=self.timeout,
                max_bytes=self.max_response_bytes,
                headers=headers,
            )
            text = reply["choices"][0]["message"]["content"]
        except HTTPAdapterError as exc:
            return ExecutionResult.failure(str(exc), latency=time.perf_counter() - start)
        except (KeyError, IndexError, TypeError):
            return ExecutionResult.failure(
                "unexpected chat-completions response shape", latency=time.perf_counter() - start
            )
        usage = reply.get("usage") if isinstance(reply, dict) else None
        return ExecutionResult(
            success=isinstance(text, str),
            output={"text": text},
            latency=time.perf_counter() - start,
            metadata={"usage": usage} if isinstance(usage, dict) else {},
        )

    def describe(self) -> dict[str, Any]:
        return {**super().describe(), "endpoint": self.base_url, "model": self.model}
