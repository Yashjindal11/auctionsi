"""Open (descending-price) reverse auction with bid revisions."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from auctionsi.core.agent import OpenAuctionView
from auctionsi.errors import ValidationError
from auctionsi.mechanisms.first_price import FirstPriceReverseAuction

if TYPE_CHECKING:
    from auctionsi.core.agent import Agent
    from auctionsi.core.auction import Auction
    from auctionsi.market.intake import BidIntake


@dataclass(frozen=True)
class OpenReverseAuction(FirstPriceReverseAuction):
    """Bidders see the standing best price after every round and may lower their
    own bid. Bidding stops after a round with no accepted revision, or after
    ``max_rounds``. Winners are then chosen and paid as in the first-price auction.

    Every revision is a new ``Bid`` (``revision`` incremented) and a ``BidRevised``
    event, so the full bid sequence and its timing can be analysed afterwards.
    Agents that did not bid in round 0 may still enter in later rounds.
    """

    max_rounds: int = 10
    name = "open_reverse"
    sealed = False

    def __post_init__(self) -> None:
        if self.max_rounds < 0:
            raise ValidationError("max_rounds must be >= 0")

    def collect_bids(self, auction: Auction, bidders: Sequence[Agent], intake: BidIntake) -> None:
        for agent in bidders:
            intake.solicit(agent, round=0)
        for round_no in range(1, self.max_rounds + 1):
            changed = False
            for agent in bidders:
                prices = [b.price for b in auction.bids.values()]
                view = OpenAuctionView(
                    auction_id=auction.auction_id,
                    round=round_no,
                    best_price=min(prices) if prices else None,
                    bid_count=len(prices),
                    own_bid=auction.bids.get(agent.agent_id),
                    now=intake.clock.now(),
                )
                if view.own_bid is None:
                    if intake.solicit(agent, round=round_no) is not None:
                        changed = True
                elif intake.solicit_revision(agent, view) is not None:
                    changed = True
            if not changed:
                break
