"""Bundle (combinatorial) reverse auction: agents bid on any subset of a task's items."""

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
class BundleReverseAuction(AuctionMechanism):
    """The task lists its items in ``requirements["items"]``. Each bid covers the items
    in ``terms["items"]`` (all items when absent). Winner determination picks the set
    of non-overlapping bids that covers every item at the lowest total price, solved
    exactly by dynamic programming over item subsets (so ``items`` is capped at
    ``max_items``). Winners are paid their own bids; each gets its own contract.

    Ties between equally cheap covers are broken by the selection policy's ranking.
    Pay-as-bid bundle auctions invite strategic bidding (e.g. inflating bundle bids);
    no incentive property is claimed.
    """

    max_items: int = 12
    name = "bundle_reverse"

    def determine_winners(
        self,
        bids: Sequence[Bid],
        task: Task,
        policy: SelectionPolicy,
        features: Mapping[str, AgentFeatures],
    ) -> MechanismOutcome:
        items = task.requirements.get("items")
        if (
            not isinstance(items, list)
            or not items
            or not all(isinstance(i, str) for i in items)
            or len(set(items)) != len(items)
        ):
            raise ValidationError("bundle tasks need requirements['items']: a list of unique names")
        if len(items) > self.max_items:
            raise ValidationError(f"bundle has {len(items)} items; the limit is {self.max_items}")
        index = {item: i for i, item in enumerate(items)}
        full = (1 << len(items)) - 1
        ranking = policy.rank(bids, task, features)
        order = {s.bid.bid_id: r for r, s in enumerate(ranking)}
        notes: list[str] = []
        masks: list[tuple[int, int]] = []
        for scored in ranking:
            covered = scored.bid.terms.get("items", items)
            if not isinstance(covered, list) or not covered or any(c not in index for c in covered):
                notes.append(f"bid from {scored.agent_id} names unknown items; ignored")
                continue
            mask = 0
            for c in covered:
                mask |= 1 << index[c]
            masks.append((mask, order[scored.bid.bid_id]))

        best: dict[int, tuple[float, tuple[int, ...]]] = {0: (0.0, ())}
        for mask in range(full + 1):
            if mask not in best:
                continue
            cost, chosen = best[mask]
            if mask == full:
                continue
            lowest = (~mask & full) & -(~mask & full)
            for bid_mask, rank in masks:
                if bid_mask & lowest and not bid_mask & mask:
                    price = ranking[rank].bid.price
                    candidate = (cost + price, (*chosen, rank))
                    target = mask | bid_mask
                    if target not in best or _better(candidate, best[target]):
                        best[target] = candidate
        if full not in best:
            notes.append("no combination of bids covers every item")
            return MechanismOutcome(ranking, [], notes)
        total, chosen = best[full]
        awards = []
        for rank in chosen:
            scored = ranking[rank]
            covered = scored.bid.terms.get("items", items)
            rule = f"pay-as-bid for items {', '.join(covered)} (cover total {total:.6g})"
            awards.append(Award(scored, scored.bid.price, rank, rule))
        return MechanismOutcome(ranking, awards, notes)


def _better(a: tuple[float, tuple[int, ...]], b: tuple[float, tuple[int, ...]]) -> bool:
    if abs(a[0] - b[0]) > 1e-12:
        return a[0] < b[0]
    return sorted(a[1]) < sorted(b[1])
