"""Build agents from declarative specs (YAML/JSON registries, CLI, API)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from auctionsi.adapters.http import HTTPAgent
from auctionsi.core.agent import Agent
from auctionsi.errors import ValidationError
from auctionsi.simulation.agents import SimulatedAgent, agent_from_spec

HTTP_KEYS = {
    "kind",
    "agent_id",
    "base_url",
    "capabilities",
    "timeout",
    "max_response_bytes",
    "token_env",
    "max_concurrent_tasks",
    "name",
}


def build_agent(spec: Mapping[str, Any]) -> Agent:
    """``kind: http`` builds an :class:`HTTPAgent`; ``kind: simulated`` (default) a
    :class:`SimulatedAgent`. Python-function and human agents are code, not specs."""
    if not isinstance(spec, Mapping):
        raise ValidationError("agent spec must be a mapping")
    kind = spec.get("kind", "simulated")
    if kind == "http":
        unknown = set(spec) - HTTP_KEYS
        if unknown:
            raise ValidationError(f"unknown http agent fields: {sorted(unknown)}")
        values = {k: v for k, v in spec.items() if k != "kind"}
        try:
            return HTTPAgent(values.pop("agent_id"), values.pop("base_url"), **values)
        except (KeyError, TypeError) as exc:
            raise ValidationError(f"invalid http agent spec: {exc}") from exc
    if kind == "simulated":
        return agent_from_spec({k: v for k, v in spec.items() if k != "kind"})
    raise ValidationError(f"unknown agent kind {kind!r}; use 'simulated' or 'http'")


def agent_spec(agent: Agent) -> dict[str, Any]:
    if isinstance(agent, SimulatedAgent):
        return {"kind": "simulated", **agent.spec()}
    if isinstance(agent, HTTPAgent):
        return agent.spec()
    raise ValidationError(f"{type(agent).__name__} cannot be stored as a spec")
