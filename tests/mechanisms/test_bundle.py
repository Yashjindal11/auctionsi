from __future__ import annotations

import itertools

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from auctionsi.core import Bid, BidContext, BidProposal, Task
from auctionsi.errors import ValidationError
from auctionsi.market import ManualClock, Marketplace
from auctionsi.mechanisms import BundleReverseAuction
from auctionsi.selection import LowestPrice
from conftest import ScriptedAgent, task

ITEMS = ["a", "b", "c"]
TASK = Task(task_id="t", task_type="x", requirements={"items": ITEMS})


def bid(agent: str, price: float, items: list[str] | None = None) -> Bid:
    terms = {} if items is None else {"items": items}
    return Bid(
        bid_id=f"b-{agent}", task_id="t", agent_id=agent, auction_id="x", price=price, terms=terms
    )


def winners(bids: list[Bid], task: Task = TASK) -> list[tuple[str, float]]:
    outcome = BundleReverseAuction().determine_winners(bids, task, LowestPrice(), {})
    return sorted((a.agent_id, a.payment) for a in outcome.awards)


def test_picks_cheapest_cover() -> None:
    bids = [
        bid("whole", 10.0),
        bid("ab", 4.0, ["a", "b"]),
        bid("c", 3.0, ["c"]),
        bid("a", 1.0, ["a"]),
    ]
    assert winners(bids) == [("ab", 4.0), ("c", 3.0)]
    assert winners([*bids, bid("cheap-whole", 6.5)]) == [("cheap-whole", 6.5)]


def test_no_cover_and_bad_inputs() -> None:
    outcome = BundleReverseAuction().determine_winners(
        [bid("a", 1.0, ["a"]), bid("bogus", 0.1, ["z"])], TASK, LowestPrice(), {}
    )
    assert outcome.awards == []
    assert any("unknown items" in n for n in outcome.notes)
    assert any("covers every item" in n for n in outcome.notes)
    with pytest.raises(ValidationError):
        winners([bid("a", 1.0)], Task(task_id="t", task_type="x"))
    with pytest.raises(ValidationError):
        BundleReverseAuction(max_items=2).determine_winners([bid("a", 1)], TASK, LowestPrice(), {})


@settings(max_examples=60)
@given(
    st.lists(
        st.tuples(
            st.lists(st.sampled_from(ITEMS), min_size=1, max_size=3, unique=True),
            st.integers(1, 20),
        ),
        min_size=1,
        max_size=6,
    )
)
def test_matches_brute_force(offers: list[tuple[list[str], int]]) -> None:
    bids = [bid(f"g{i}", float(p), items) for i, (items, p) in enumerate(offers)]
    best = None
    for r in range(1, len(bids) + 1):
        for combo in itertools.combinations(bids, r):
            covered = [i for b in combo for i in b.terms["items"]]
            if sorted(covered) == sorted(ITEMS):
                cost = sum(b.price for b in combo)
                best = cost if best is None else min(best, cost)
    got = winners(bids)
    if best is None:
        assert got == []
    else:
        assert sum(p for _, p in got) == pytest.approx(best)


class ItemBidder(ScriptedAgent):
    def __init__(self, agent_id: str, price: float, items: list[str]) -> None:
        super().__init__(agent_id, price)
        self.items = items

    def bid(self, task: Task, context: BidContext) -> BidProposal | None:
        return BidProposal(price=self.price or 0, terms={"items": self.items})


def test_bundle_auction_runs_one_contract_per_winning_bid() -> None:
    market = Marketplace(clock=ManualClock(), mechanism=BundleReverseAuction())
    market.register(ItemBidder("ab", 4.0, ["a", "b"]))
    market.register(ItemBidder("c", 3.0, ["c"]))
    market.register(ItemBidder("all", 9.0, ITEMS))
    result = market.submit_task(task(requirements={"items": ITEMS}))
    assert result.succeeded
    assert sorted(result.winners) == ["ab", "c"]
    assert result.buyer_cost == pytest.approx(7.0)
