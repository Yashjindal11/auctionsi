"""The unit of work that a marketplace auctions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from auctionsi.errors import ValidationError
from auctionsi.security import (
    check_identifier,
    check_mapping,
    check_number,
    check_text,
)


@dataclass(frozen=True, slots=True)
class Task:
    """A unit of work that can be auctioned.

    Large inputs are never embedded: put a reference (path, URL, object key) in
    ``input_reference`` and let the executing agent resolve it.

    Money-like fields (``budget``, ``value``) are in abstract ``unit`` units; AuctionSI
    never assumes a currency. ``deadline`` is a duration in seconds measured from
    the moment the contract is created.
    """

    task_id: str
    task_type: str
    description: str = ""
    requirements: Mapping[str, Any] = field(default_factory=dict)
    constraints: Mapping[str, Any] = field(default_factory=dict)
    priority: int = 0
    deadline: float | None = None
    budget: float | None = None
    min_quality: float | None = None
    value: float | None = None
    unit: str = "credits"
    created_at: float = 0.0
    input_reference: str | None = None
    expected_output_schema: Mapping[str, Any] | None = None
    verification_policy: str | None = None
    payment_policy: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    reserve_price: float | None = None

    def __post_init__(self) -> None:
        check_identifier(self.task_id, "task_id")
        check_identifier(self.task_type, "task_type")
        check_text(self.description, "description")
        set_ = object.__setattr__
        set_(self, "requirements", check_mapping(self.requirements, "requirements"))
        set_(self, "constraints", check_mapping(self.constraints, "constraints"))
        set_(self, "metadata", check_mapping(self.metadata, "metadata"))
        if isinstance(self.priority, bool) or not isinstance(self.priority, int):
            raise ValidationError("priority must be an integer")
        # Spec-style constraints {"max_cost": .., "max_latency": ..} fill the explicit fields.
        budget = self.budget if self.budget is not None else self.constraints.get("max_cost")
        deadline = (
            self.deadline if self.deadline is not None else self.constraints.get("max_latency")
        )
        min_quality = (
            self.min_quality
            if self.min_quality is not None
            else self.constraints.get("min_quality")
        )
        set_(self, "budget", check_number(budget, "budget", minimum=0, allow_none=True))
        set_(self, "deadline", check_number(deadline, "deadline", minimum=0, allow_none=True))
        set_(
            self,
            "min_quality",
            check_number(min_quality, "min_quality", minimum=0, maximum=1, allow_none=True),
        )
        set_(self, "value", check_number(self.value, "value", allow_none=True))
        set_(
            self,
            "reserve_price",
            check_number(self.reserve_price, "reserve_price", minimum=0, allow_none=True),
        )
        set_(self, "created_at", check_number(self.created_at, "created_at", minimum=0))
        check_identifier(self.unit, "unit")
        if self.input_reference is not None:
            check_text(self.input_reference, "input_reference")
        if self.expected_output_schema is not None:
            set_(
                self,
                "expected_output_schema",
                check_mapping(self.expected_output_schema, "expected_output_schema"),
            )
        for name in ("verification_policy", "payment_policy"):
            policy = getattr(self, name)
            if policy is not None:
                check_identifier(policy, name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "description": self.description,
            "requirements": dict(self.requirements),
            "constraints": dict(self.constraints),
            "priority": self.priority,
            "deadline": self.deadline,
            "budget": self.budget,
            "min_quality": self.min_quality,
            "value": self.value,
            "unit": self.unit,
            "created_at": self.created_at,
            "input_reference": self.input_reference,
            "expected_output_schema": (
                dict(self.expected_output_schema) if self.expected_output_schema else None
            ),
            "verification_policy": self.verification_policy,
            "payment_policy": self.payment_policy,
            "metadata": dict(self.metadata),
            "reserve_price": self.reserve_price,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Task:
        known = set(cls.__dataclass_fields__)
        unknown = set(data) - known
        if unknown:
            raise ValidationError(f"unknown task fields: {sorted(unknown)}")
        return cls(**dict(data))
