"""The settlement record produced after verification."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Settlement:
    """Money-like flows for one contract, in ``unit`` units.

    ``payment`` and ``bonus`` flow buyer -> agent; ``penalty`` flows agent -> buyer.
    ``refund`` is the part of the escrowed ``payment_price`` the buyer gets back.
    ``buyer_cost = payment + bonus - penalty``; ``agent_revenue`` is the same amount
    from the agent's side.
    """

    contract_id: str
    agent_id: str
    task_id: str
    unit: str
    payment: float
    penalty: float
    bonus: float
    refund: float
    quality_score: float
    passed: bool
    on_time: bool
    reason: str
    policy: str

    @property
    def buyer_cost(self) -> float:
        return self.payment + self.bonus - self.penalty

    @property
    def agent_revenue(self) -> float:
        return self.buyer_cost

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["buyer_cost"] = self.buyer_cost
        return data
