from __future__ import annotations

from auctionsi.market import Marketplace, WallClock
from conftest import ScriptedAgent, task


class FrozenWallClock(WallClock):
    """A real (non-simulated) clock whose reading does not advance, like a coarse OS timer."""

    def now(self) -> float:
        return 1000.0


def test_real_clock_does_not_hold_capacity_after_synchronous_execution() -> None:
    market = Marketplace(clock=FrozenWallClock())
    market.register(ScriptedAgent("a", 1.0, latency=5.0))
    assert market.submit_task(task("t1")).winner == "a"
    assert market.submit_task(task("t2")).winner == "a"
