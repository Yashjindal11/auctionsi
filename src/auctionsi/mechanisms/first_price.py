"""First-price (pay-as-bid) reverse auction."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from auctionsi.core.bid import Bid
from auctionsi.core.task import Task
from auctionsi.mechanisms.base import AuctionMechanism, Award, MechanismOutcome
from auctionsi.reputation.base import AgentFeatures
from auctionsi.selection.policies import SelectionPolicy


@dataclass(frozen=True)
class FirstPriceReverseAuction(AuctionMechanism):
    """Sealed-bid procurement auction: the best-ranked valid bid wins and is paid
    its own bid price. With the default ``LowestPrice`` policy, the lowest valid bid
    wins. See ``docs/mechanisms.md`` for assumptions and strategic considerations."""

    name = "first_price_reverse"

    def determine_winners(
        self,
        bids: Sequence[Bid],
        task: Task,
        policy: SelectionPolicy,
        features: Mapping[str, AgentFeatures],
    ) -> MechanismOutcome:
        ranking = policy.rank(bids, task, features)
        if not ranking:
            return MechanismOutcome([], [], ["no valid bids"])
        top = ranking[0]
        award = Award(top, top.bid.price, 0, "pay-as-bid: winner is paid its own price")
        return MechanismOutcome(ranking, [award])
