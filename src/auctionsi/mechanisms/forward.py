"""Forward auction: agents compete to *acquire* something (compute, data, a slot)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from auctionsi.core.bid import Bid
from auctionsi.core.task import Task
from auctionsi.errors import ValidationError
from auctionsi.mechanisms.base import AuctionMechanism, Award, MechanismOutcome
from auctionsi.reputation.base import AgentFeatures
from auctionsi.selection.policies import ScoredBid, SelectionPolicy, ranking_key


@dataclass(frozen=True)
class ForwardAuction(AuctionMechanism):
    """Sealed-bid forward auction. The task describes what is on offer, its
    ``reserve_price`` is the minimum acceptable bid, and the highest bid wins.

    ``pricing="first"`` charges the winner its bid; ``"second"`` charges the larger
    of the runner-up bid and the reserve (a Vickrey auction for one item, under the
    usual private-value, single-shot assumptions). The selection policy is not used:
    forward ranking is by price, highest first, so the decision stays a pure
    function of the bids.
    """

    pricing: str = "first"
    name = "forward"
    direction = "forward"

    def __post_init__(self) -> None:
        if self.pricing not in ("first", "second"):
            raise ValidationError("pricing must be 'first' or 'second'")

    def determine_winners(
        self,
        bids: Sequence[Bid],
        task: Task,
        policy: SelectionPolicy,
        features: Mapping[str, AgentFeatures],
    ) -> MechanismOutcome:
        ranking = sorted((ScoredBid(b, b.price, {"price": b.price}) for b in bids), key=ranking_key)
        if not ranking:
            return MechanismOutcome([], [], ["no valid bids"])
        top = ranking[0]
        if self.pricing == "first":
            return MechanismOutcome(ranking, [Award(top, top.bid.price, 0, "pays own bid")])
        floor = task.reserve_price or 0.0
        runner_up = ranking[1].bid.price if len(ranking) > 1 else floor
        payment = min(top.bid.price, max(runner_up, floor))
        rule = "second price: max(runner-up bid, reserve)"
        return MechanismOutcome(ranking, [Award(top, payment, 0, rule)])
