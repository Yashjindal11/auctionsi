"""Typed request bodies for the REST API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaskIn(_Body):
    task_id: str | None = Field(None, description="generated when omitted")
    task_type: str
    description: str = ""
    requirements: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)
    priority: int = 0
    deadline: float | None = None
    budget: float | None = None
    min_quality: float | None = None
    value: float | None = None
    reserve_price: float | None = None
    unit: str | None = None
    input_reference: str | None = None
    expected_output_schema: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BidIn(_Body):
    agent_id: str
    price: float
    estimated_latency: float | None = None
    estimated_quality: float | None = None
    estimated_cost: float | None = None
    confidence: float | None = None
    capacity: int | None = None
    valid_for: float | None = None
    terms: dict[str, Any] = Field(default_factory=dict)
    signature: str | None = None


class SimulateIn(_Body):
    agents: int = Field(20, ge=1, le=2_000)
    tasks: int = Field(200, ge=1, le=20_000)
    seed: int = 0
    mechanism: str | dict[str, Any] | None = None
    policy: str | dict[str, Any] | None = None
    strategy: str | dict[str, Any] = "cost_plus"
