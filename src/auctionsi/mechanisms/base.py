"""Auction mechanism plugin interface.

A mechanism owns two decisions: how bids are *collected* (sealed or open rounds)
and how valid bids become *awards* (who wins and what each winner is paid).
Ranking itself is delegated to a :class:`~auctionsi.selection.SelectionPolicy`,
so "first-price vs second-price" and "price vs quality" are independent choices.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import TYPE_CHECKING, Any, Literal

from auctionsi.core.bid import Bid
from auctionsi.core.task import Task
from auctionsi.reputation.base import AgentFeatures
from auctionsi.selection.policies import ScoredBid, SelectionPolicy

if TYPE_CHECKING:
    from auctionsi.core.agent import Agent
    from auctionsi.core.auction import Auction
    from auctionsi.market.intake import BidIntake


@dataclass(frozen=True, slots=True)
class Award:
    scored: ScoredBid
    payment: float
    rank: int
    payment_rule: str

    @property
    def bid(self) -> Bid:
        return self.scored.bid

    @property
    def agent_id(self) -> str:
        return self.scored.bid.agent_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "bid_id": self.bid.bid_id,
            "bid_price": self.bid.price,
            "payment": self.payment,
            "rank": self.rank,
            "payment_rule": self.payment_rule,
            "score": self.scored.score,
        }


@dataclass(frozen=True, slots=True)
class MechanismOutcome:
    ranking: list[ScoredBid]
    awards: list[Award]
    notes: list[str] = field(default_factory=list)

    @property
    def backups(self) -> list[ScoredBid]:
        """Ranked bids that did not win, best first: candidates for fail-over."""
        winners = {a.agent_id for a in self.awards}
        return [s for s in self.ranking if s.agent_id not in winners]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ranking": [s.to_dict() for s in self.ranking],
            "awards": [a.to_dict() for a in self.awards],
            "notes": list(self.notes),
        }


class AuctionMechanism(ABC):
    """Plugin interface for auction mechanisms."""

    name: str = "mechanism"
    #: Whether bidders are shown any information about rival bids while bidding.
    sealed: bool = True
    #: "reverse" = agents compete to sell work to a buyer (procurement).
    #: "forward" = agents compete to buy a resource; reserved for future mechanisms.
    direction: Literal["reverse", "forward"] = "reverse"

    def collect_bids(self, auction: Auction, bidders: Sequence[Agent], intake: BidIntake) -> None:
        """Sealed collection: each eligible agent is asked once and is never shown
        another agent's bid. Bids are recorded in agent-id order."""
        intake.solicit_all(bidders)

    @abstractmethod
    def determine_winners(
        self,
        bids: Sequence[Bid],
        task: Task,
        policy: SelectionPolicy,
        features: Mapping[str, AgentFeatures],
    ) -> MechanismOutcome:
        """Rank valid bids and decide awards and payments. Must be deterministic."""

    def to_spec(self) -> dict[str, Any]:
        params: dict[str, Any] = asdict(self) if is_dataclass(self) else {}
        return {"name": self.name, **params}
