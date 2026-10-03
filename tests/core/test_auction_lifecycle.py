from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from auctionsi.core import Task
from auctionsi.core.auction import TERMINAL, TRANSITIONS, Auction, AuctionStatus
from auctionsi.errors import InvalidTransitionError

S = AuctionStatus

HAPPY_PATH = [
    S.ANNOUNCED,
    S.OPEN,
    S.BID_COLLECTION,
    S.CLOSED,
    S.EVALUATION,
    S.AWARDED,
    S.CONTRACTED,
    S.EXECUTING,
    S.VERIFYING,
    S.SETTLED,
]


def _auction() -> Auction:
    return Auction(
        auction_id="auc-1",
        task=Task(task_id="t", task_type="x"),
        mechanism="first_price_reverse",
        created_at=0.0,
    )


def test_happy_path_lifecycle() -> None:
    auction = _auction()
    for i, status in enumerate(HAPPY_PATH, start=1):
        auction.transition(status, float(i))
    assert auction.is_terminal
    assert auction.start_time == 2.0
    assert auction.end_time == float(len(HAPPY_PATH))
    assert auction.history[0][0] == S.CREATED


def test_cannot_settle_before_closing() -> None:
    auction = _auction()
    auction.transition(S.ANNOUNCED, 0)
    auction.transition(S.OPEN, 0)
    with pytest.raises(InvalidTransitionError):
        auction.transition(S.SETTLED, 0)


def test_terminal_states_have_no_exits() -> None:
    assert {S.SETTLED, S.FAILED, S.CANCELLED, S.EXPIRED, S.NO_BIDS} == TERMINAL


def test_every_state_is_reachable_from_created() -> None:
    seen = {S.CREATED}
    frontier = [S.CREATED]
    while frontier:
        for nxt in TRANSITIONS[frontier.pop()]:
            if nxt not in seen:
                seen.add(nxt)
                frontier.append(nxt)
    assert seen == set(S)


@given(st.lists(st.sampled_from(list(S)), max_size=30))
def test_random_walks_never_break_the_transition_table(steps: list[AuctionStatus]) -> None:
    auction = _auction()
    for step in steps:
        before = auction.status
        if step in TRANSITIONS[before]:
            auction.transition(step, 0.0)
            assert auction.status == step
        else:
            with pytest.raises(InvalidTransitionError):
                auction.transition(step, 0.0)
            assert auction.status == before
    for (a, _), (b, _) in zip(auction.history, auction.history[1:], strict=False):
        assert b in TRANSITIONS[a]
