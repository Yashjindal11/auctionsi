from __future__ import annotations

import pytest

from auctionsi.core import RejectionCode
from auctionsi.errors import ValidationError
from auctionsi.market import ManualClock, Marketplace
from auctionsi.mechanisms import ForwardAuction
from conftest import ScriptedAgent, task


def market(pricing: str = "first") -> Marketplace:
    m = Marketplace(clock=ManualClock(), mechanism=ForwardAuction(pricing=pricing))
    for name, price in [("low", 2.0), ("high", 5.0), ("mid", 4.0), ("cheap", 0.5)]:
        m.register(ScriptedAgent(name, price))
    return m


def test_highest_bid_wins_and_low_bids_are_below_reserve() -> None:
    result = market().submit_task(task(reserve_price=1.0, budget=3.0))
    assert result.winner == "high"
    assert result.contracts[0].contract.payment_price == 5.0
    codes = {r.agent_id: r.reasons[0].code for r in result.auction.rejected}
    assert codes == {"cheap": RejectionCode.BELOW_RESERVE}
    # Forward settlement: the agent pays the task owner, so the owner's cost is negative.
    assert result.buyer_cost == pytest.approx(-5.0)
    assert result.contracts[0].settlement.refund == 0.0


def test_second_price_forward() -> None:
    result = market("second").submit_task(task(reserve_price=1.0))
    assert result.winner == "high"
    assert result.contracts[0].contract.payment_price == 4.0
    lone = Marketplace(clock=ManualClock(), mechanism=ForwardAuction(pricing="second"))
    lone.register(ScriptedAgent("only", 3.0))
    assert lone.submit_task(task(reserve_price=1.5)).buyer_cost == pytest.approx(-1.5)
    with pytest.raises(ValidationError):
        ForwardAuction(pricing="dutch")
