"""Capacity (multi-unit) procurement: reserve future work from several agents."""

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
class CapacityAuction(AuctionMechanism):
    """The task asks for ``requirements["units"]`` units of future capacity (e.g. 100
    tasks over the next hour). Each bid's ``price`` is a *per-unit* price and
    ``capacity`` (or ``terms["units"]``) is how many units the agent offers.

    Units are filled from the cheapest per-unit offers up; the last winner may be
    partially filled. ``pricing="pay_as_bid"`` pays each winner its own unit price;
    ``"uniform"`` pays every winner the first rejected unit price (the clearing
    price), or the budget per unit / own price when supply runs out. Award
    ``quantity`` is the units reserved; ``payment`` is the total for them.
    """

    pricing: str = "pay_as_bid"
    name = "capacity"

    def __post_init__(self) -> None:
        if self.pricing not in ("pay_as_bid", "uniform"):
            raise ValidationError("pricing must be 'pay_as_bid' or 'uniform'")

    def determine_winners(
        self,
        bids: Sequence[Bid],
        task: Task,
        policy: SelectionPolicy,
        features: Mapping[str, AgentFeatures],
    ) -> MechanismOutcome:
        needed = task.requirements.get("units")
        if isinstance(needed, bool) or not isinstance(needed, int | float) or needed <= 0:
            raise ValidationError("capacity tasks need a positive requirements['units']")
        ranking = sorted(
            (ScoredBid(b, -b.price, {"unit_price": -b.price}) for b in bids), key=ranking_key
        )
        remaining = float(needed)
        fills: list[tuple[ScoredBid, float]] = []
        clearing: float | None = None
        for scored in ranking:
            offered = _units(scored.bid)
            if offered <= 0:
                continue
            if remaining <= 1e-12:
                clearing = scored.bid.price
                break
            take = min(offered, remaining)
            fills.append((scored, take))
            remaining -= take
        notes = []
        if remaining > 1e-12:
            notes.append(f"only {needed - remaining:g} of {needed:g} units offered")
        awards = []
        for rank, (scored, units) in enumerate(fills):
            unit_price = scored.bid.price
            rule = f"pay-as-bid: {units:g} units at {unit_price:g}"
            if self.pricing == "uniform":
                if clearing is None:
                    per_unit_budget = None if task.budget is None else task.budget / needed
                    clearing_price = per_unit_budget if per_unit_budget is not None else unit_price
                else:
                    clearing_price = clearing
                unit_price = max(unit_price, clearing_price)
                rule = f"uniform clearing price {unit_price:g} for {units:g} units"
            awards.append(Award(scored, unit_price * units, rank, rule, quantity=units))
        return MechanismOutcome(ranking, awards, notes)


def _units(bid: Bid) -> float:
    raw = bid.capacity if bid.capacity is not None else bid.terms.get("units", 0)
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        return 0.0
    return float(raw)
