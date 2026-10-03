"""The settlement record produced after verification."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Settlement:
    """Money-like flows for one contract, in ``unit`` units.

    Reverse (procurement): ``payment`` and ``bonus`` flow task owner -> agent.
    Forward (the agent acquires something): ``payment`` flows agent -> task owner.
    ``penalty`` always flows agent -> task owner. ``buyer_cost`` is the task owner's
    net outflow (negative when it earns money); ``agent_revenue`` is the same amount
    seen from the agent.
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
    direction: str = "reverse"

    @property
    def buyer_cost(self) -> float:
        signed = self.payment if self.direction == "reverse" else -self.payment
        return signed + self.bonus - self.penalty

    @property
    def agent_revenue(self) -> float:
        return self.buyer_cost

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["buyer_cost"] = self.buyer_cost
        return data
