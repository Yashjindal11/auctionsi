"""Multi-winner reverse auction: award the top ``winners`` bids."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from auctionsi.core.bid import Bid
from auctionsi.core.task import Task
from auctionsi.errors import ValidationError
from auctionsi.mechanisms.base import AuctionMechanism, Award, MechanismOutcome
from auctionsi.reputation.base import AgentFeatures
from auctionsi.selection.policies import SelectionPolicy


@dataclass(frozen=True)
class MultiWinnerReverseAuction(AuctionMechanism):
    """Select up to ``winners`` distinct agents (one award per agent, so work is
    diversified across agents).

    ``pricing="pay_as_bid"``: each winner is paid its own price.
    ``pricing="uniform"``: every winner is paid the price of the best *losing* bid
    (the (k+1)-th price), or the task budget / own price when there is no losing
    bid. Uniform pricing is only defined for price-only policies.
    """

    winners: int = 2
    pricing: str = "pay_as_bid"
    name = "multi_winner_reverse"

    def __post_init__(self) -> None:
        if self.winners < 1:
            raise ValidationError("winners must be >= 1")
        if self.pricing not in ("pay_as_bid", "uniform"):
            raise ValidationError("pricing must be 'pay_as_bid' or 'uniform'")

    def determine_winners(
        self,
        bids: Sequence[Bid],
        task: Task,
        policy: SelectionPolicy,
        features: Mapping[str, AgentFeatures],
    ) -> MechanismOutcome:
        if self.pricing == "uniform" and not policy.price_only:
            raise ValidationError("uniform pricing requires a price-only selection policy")
        ranking = policy.rank(bids, task, features)
        top = ranking[: self.winners]
        notes = []
        if len(top) < self.winners:
            notes.append(f"only {len(top)} of {self.winners} requested winners available")
        awards = []
        for rank, scored in enumerate(top):
            own = scored.bid.price
            if self.pricing == "pay_as_bid":
                awards.append(Award(scored, own, rank, "pay-as-bid"))
                continue
            if len(ranking) > self.winners:
                clearing = ranking[self.winners].bid.price
                rule = f"uniform: best losing bid {clearing}"
            elif task.budget is not None:
                clearing, rule = task.budget, "uniform: no losing bid, paid the reserve"
            else:
                clearing, rule = own, "uniform: no losing bid, paid own price"
            if task.budget is not None and clearing > task.budget:
                clearing, rule = task.budget, rule + " (capped at budget)"
            awards.append(Award(scored, max(clearing, own), rank, rule))
        return MechanismOutcome(ranking, awards, notes)
