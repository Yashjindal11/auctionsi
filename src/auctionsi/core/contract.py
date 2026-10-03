"""Contracts between the marketplace and a winning agent."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from auctionsi.errors import InvalidTransitionError


class ContractStatus(StrEnum):
    CREATED = "created"
    EXECUTING = "executing"
    DELIVERED = "delivered"
    FULFILLED = "fulfilled"
    BREACHED = "breached"
    CANCELLED = "cancelled"


_CONTRACT_TRANSITIONS: dict[ContractStatus, frozenset[ContractStatus]] = {
    ContractStatus.CREATED: frozenset({ContractStatus.EXECUTING, ContractStatus.CANCELLED}),
    ContractStatus.EXECUTING: frozenset(
        {ContractStatus.DELIVERED, ContractStatus.BREACHED, ContractStatus.CANCELLED}
    ),
    ContractStatus.DELIVERED: frozenset({ContractStatus.FULFILLED, ContractStatus.BREACHED}),
    ContractStatus.FULFILLED: frozenset(),
    ContractStatus.BREACHED: frozenset(),
    ContractStatus.CANCELLED: frozenset(),
}


@dataclass(slots=True)
class Contract:
    """The agreement created when a bid wins.

    ``agreed_price`` is what the agent bid; ``payment_price`` is what the auction
    mechanism says the agent is owed on success (they differ in, for example,
    second-price auctions). A retry of the same agent creates a new contract
    with ``attempt`` incremented, so contracts only ever move forward.
    """

    contract_id: str
    auction_id: str
    task_id: str
    agent_id: str
    bid_id: str
    agreed_price: float
    payment_price: float
    unit: str
    created_at: float
    deadline: float | None = None
    min_quality: float | None = None
    output_requirements: Mapping[str, Any] | None = None
    verification_method: str = "default"
    penalty_policy: str = "default"
    cancellation_policy: str = "free_before_execution"
    estimated_quality: float | None = None
    estimated_latency: float | None = None
    attempt: int = 1
    status: ContractStatus = ContractStatus.CREATED
    history: list[tuple[str, float]] = field(default_factory=list)

    @property
    def due_at(self) -> float | None:
        return None if self.deadline is None else self.created_at + self.deadline

    def transition(self, new: ContractStatus, at: float) -> None:
        if new not in _CONTRACT_TRANSITIONS[self.status]:
            raise InvalidTransitionError(
                f"contract {self.contract_id}: cannot move from {self.status} to {new}"
            )
        self.status = new
        self.history.append((new.value, at))

    def start(self, at: float) -> None:
        self.transition(ContractStatus.EXECUTING, at)

    def cancel(self, at: float) -> None:
        self.transition(ContractStatus.CANCELLED, at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "auction_id": self.auction_id,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "bid_id": self.bid_id,
            "agreed_price": self.agreed_price,
            "payment_price": self.payment_price,
            "unit": self.unit,
            "created_at": self.created_at,
            "deadline": self.deadline,
            "min_quality": self.min_quality,
            "output_requirements": (
                dict(self.output_requirements) if self.output_requirements else None
            ),
            "verification_method": self.verification_method,
            "penalty_policy": self.penalty_policy,
            "cancellation_policy": self.cancellation_policy,
            "estimated_quality": self.estimated_quality,
            "estimated_latency": self.estimated_latency,
            "attempt": self.attempt,
            "status": self.status.value,
            "history": [list(item) for item in self.history],
        }
