from __future__ import annotations

import pytest

from auctionsi.core import Bid, BidContext, BidProposal, Task
from auctionsi.errors import ValidationError
from auctionsi.market import ManualClock, Marketplace
from auctionsi.mechanisms import CapacityAuction
from auctionsi.selection import LowestPrice
from conftest import ScriptedAgent, task

TASK = Task(task_id="t", task_type="x", requirements={"units": 100}, budget=150.0)


def bid(agent: str, unit_price: float, units: int) -> Bid:
    return Bid(
        bid_id=f"b-{agent}",
        task_id="t",
        agent_id=agent,
        auction_id="x",
        price=unit_price,
        capacity=units,
    )


BIDS = [bid("a", 1.0, 60), bid("b", 1.2, 30), bid("c", 1.5, 50), bid("d", 2.0, 40)]


def awards(pricing: str, bids: list[Bid] = BIDS) -> list[tuple[str, float, float | None]]:
    outcome = CapacityAuction(pricing=pricing).determine_winners(bids, TASK, LowestPrice(), {})
    return [(a.agent_id, round(a.payment, 6), a.quantity) for a in outcome.awards]


def test_fills_cheapest_units_first_with_partial_last_fill() -> None:
    assert awards("pay_as_bid") == [("a", 60.0, 60), ("b", 36.0, 30), ("c", 15.0, 10)]


def test_uniform_pays_first_rejected_price() -> None:
    assert awards("uniform") == [("a", 120.0, 60), ("b", 60.0, 30), ("c", 20.0, 10)]


def test_shortfall_and_validation() -> None:
    outcome = CapacityAuction(pricing="uniform").determine_winners(
        [bid("a", 1.0, 30)], TASK, LowestPrice(), {}
    )
    assert outcome.awards[0].quantity == 30
    assert outcome.awards[0].payment == pytest.approx(30 * 1.5)  # budget per unit
    assert "only 30 of 100" in outcome.notes[0]
    with pytest.raises(ValidationError):
        CapacityAuction().determine_winners(
            BIDS, Task(task_id="t", task_type="x"), LowestPrice(), {}
        )
    with pytest.raises(ValidationError):
        CapacityAuction(pricing="dutch")


class CapacityBidder(ScriptedAgent):
    def __init__(self, agent_id: str, unit_price: float, units: int) -> None:
        super().__init__(agent_id, unit_price)
        self.units = units

    def bid(self, task: Task, context: BidContext) -> BidProposal | None:
        return BidProposal(price=self.price or 0, capacity=self.units)


def test_capacity_auction_end_to_end() -> None:
    market = Marketplace(clock=ManualClock(), mechanism=CapacityAuction())
    market.register(CapacityBidder("big", 1.0, 80))
    market.register(CapacityBidder("small", 1.5, 50))
    result = market.submit_task(task(requirements={"units": 100}, budget=200))
    assert sorted(result.winners) == ["big", "small"]
    assert result.buyer_cost == pytest.approx(80 + 30)
