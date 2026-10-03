from __future__ import annotations

import time
from typing import Any

from auctionsi.core import BidContext, BidProposal, Contract, ExecutionResult, RejectionCode, Task
from auctionsi.market import ManualClock, Marketplace
from conftest import ScriptedAgent, task


class SlowBidder(ScriptedAgent):
    def __init__(self, *args: Any, delay: float, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.delay = delay

    def bid(self, task: Task, context: BidContext) -> BidProposal | None:
        time.sleep(self.delay)
        return super().bid(task, context)


class SlowWorker(ScriptedAgent):
    def execute(self, task: Task, contract: Contract) -> ExecutionResult:
        time.sleep(0.5)
        return super().execute(task, contract)


def test_bidding_window_rejects_late_bids_and_keeps_order() -> None:
    market = Marketplace(bid_timeout=0.2)
    market.register(SlowBidder("late", 0.01, delay=1.0))
    for name, price in [("b", 0.03), ("a", 0.05)]:
        market.register(SlowBidder(name, price, delay=0.05))
    start = time.perf_counter()
    result = market.submit_task(task())
    assert time.perf_counter() - start < 0.9
    assert result.winner == "b"
    assert [b.agent_id for b in result.auction.bid_log] == ["a", "b"]
    codes = {r.agent_id: r.reasons[0].code for r in result.auction.rejected}
    assert codes == {"late": RejectionCode.TIMEOUT}
    market.close()


def test_bidding_window_is_enforced_on_real_clocks_only() -> None:
    assert Marketplace(bidding_window=5).bid_timeout == 5
    assert Marketplace(bidding_window=5, clock=ManualClock()).bid_timeout is None
    assert Marketplace(bidding_window=5, bid_timeout=1).bid_timeout == 1


def test_execution_timeout_becomes_a_failure() -> None:
    market = Marketplace(execution_timeout=0.1)
    market.register(SlowWorker("slow", 0.01))
    result = market.submit_task(task())
    assert not result.succeeded
    assert "timed out" in (result.contracts[0].execution.error or "")
    market.close()


def test_capability_changes_are_reindexed() -> None:
    market = Marketplace(clock=ManualClock())
    agent = ScriptedAgent("a", 1.0, capabilities=("research",))
    market.register(agent)
    first = market.submit_task(task("t1"))
    assert first.status.value == "no_bids"
    assert first.discovery.not_capable == 1
    agent.set_capabilities(["research", "analysis"])
    assert market.submit_task(task("t2")).winner == "a"
