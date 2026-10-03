"""Second-price (critical-value) reverse auction."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from auctionsi.core.bid import Bid
from auctionsi.core.task import Task
from auctionsi.errors import ValidationError
from auctionsi.mechanisms.base import AuctionMechanism, Award, MechanismOutcome
from auctionsi.reputation.base import AgentFeatures
from auctionsi.selection.policies import SelectionPolicy


@dataclass(frozen=True)
class SecondPriceReverseAuction(AuctionMechanism):
    """Sealed-bid procurement auction in which the winner is paid its *critical
    value*: the highest price it could have bid and still ranked first, holding every
    other bid fixed, capped at the task budget.

    * With a price-only policy (``LowestPrice``) this is the runner-up's price, the
      classic reverse Vickrey rule.
    * With multi-dimensional policies the critical price is found by bisection. This
      assumes the policy's score never increases when only the price rises (true for
      every built-in policy). The search is capped at the task budget, or at the
      highest submitted price when there is no budget.
    * With a single valid bid, ``single_bid_payment="reserve"`` pays the task budget
      (if set) and ``"bid"`` pays the bid price.

    The payment is never below the winner's own bid. Truthfulness is only claimed
    in the narrow setting documented in ``docs/mechanisms.md``.
    """

    single_bid_payment: str = "reserve"
    tolerance: float = 1e-9
    name = "second_price_reverse"

    def __post_init__(self) -> None:
        if self.single_bid_payment not in ("reserve", "bid"):
            raise ValidationError("single_bid_payment must be 'reserve' or 'bid'")

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
        own = top.bid.price
        if len(ranking) == 1:
            if self.single_bid_payment == "reserve" and task.budget is not None:
                payment, rule = task.budget, "single bid: paid the reserve (task budget)"
            else:
                payment, rule = own, "single bid: paid own price"
            return MechanismOutcome(ranking, [Award(top, max(payment, own), 0, rule)])
        if policy.price_only:
            payment = ranking[1].bid.price
            rule = f"second price: runner-up {ranking[1].agent_id} bid {payment}"
            if task.budget is not None and payment > task.budget:
                payment, rule = task.budget, rule + " (capped at budget)"
        else:
            payment = self.critical_price(top.bid, bids, task, policy, features)
            rule = "critical value: highest price at which the winner still ranks first"
        return MechanismOutcome(ranking, [Award(top, max(payment, own), 0, rule)])

    def critical_price(
        self,
        winner: Bid,
        bids: Sequence[Bid],
        task: Task,
        policy: SelectionPolicy,
        features: Mapping[str, AgentFeatures],
    ) -> float:
        cap = task.budget if task.budget is not None else max(b.price for b in bids)
        others = [b for b in bids if b.agent_id != winner.agent_id]

        def still_wins(price: float) -> bool:
            trial = [*others, replace(winner, price=price)]
            return policy.rank(trial, task, features)[0].agent_id == winner.agent_id

        lo, hi = winner.price, cap
        if hi <= lo:
            return lo
        if still_wins(hi):
            return hi
        for _ in range(200):
            if hi - lo <= self.tolerance * max(1.0, abs(hi)):
                break
            mid = (lo + hi) / 2
            if still_wins(mid):
                lo = mid
            else:
                hi = mid
        return lo
