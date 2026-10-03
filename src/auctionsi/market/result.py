"""Result objects returned by the marketplace."""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import fmean
from typing import Any

from auctionsi.core.auction import Auction, AuctionStatus
from auctionsi.core.contract import Contract
from auctionsi.core.execution import ExecutionResult
from auctionsi.core.settlement import Settlement
from auctionsi.core.task import Task
from auctionsi.market.discovery import DiscoveryResult
from auctionsi.market.events import Event
from auctionsi.market.trace import format_trace
from auctionsi.mechanisms.base import MechanismOutcome
from auctionsi.reputation.base import AgentFeatures, Observation
from auctionsi.verification.verifiers import VerificationResult


@dataclass(frozen=True, slots=True)
class ContractOutcome:
    contract: Contract
    execution: ExecutionResult
    verification: VerificationResult
    settlement: Settlement
    observation: Observation

    @property
    def passed(self) -> bool:
        return self.verification.passed

    def to_dict(self) -> dict[str, Any]:
        execution = self.execution.to_dict()
        execution.pop("output", None)
        return {
            "contract": self.contract.to_dict(),
            "execution": execution,
            "verification": self.verification.to_dict(),
            "settlement": self.settlement.to_dict(),
        }


@dataclass
class AuctionResult:
    auction: Auction
    discovery: DiscoveryResult
    features: dict[str, AgentFeatures] = field(default_factory=dict)
    outcome: MechanismOutcome | None = None
    contracts: list[ContractOutcome] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    child: AuctionResult | None = None
    reason: str = ""

    @property
    def auction_id(self) -> str:
        return self.auction.auction_id

    @property
    def task(self) -> Task:
        return self.auction.task

    @property
    def status(self) -> AuctionStatus:
        return self.auction.status

    @property
    def final(self) -> AuctionResult:
        """The last auction in a re-open chain (``self`` if nothing was re-opened)."""
        result = self
        while result.child is not None:
            result = result.child
        return result

    def chain(self) -> list[AuctionResult]:
        out, result = [self], self
        while result.child is not None:
            result = result.child
            out.append(result)
        return out

    @property
    def succeeded(self) -> bool:
        return self.final.status == AuctionStatus.SETTLED

    @property
    def all_contracts(self) -> list[ContractOutcome]:
        return [c for r in self.chain() for c in r.contracts]

    @property
    def winners(self) -> list[str]:
        """Agents whose delivered work passed verification."""
        return [c.contract.agent_id for c in self.all_contracts if c.passed]

    @property
    def winner(self) -> str | None:
        winners = self.winners
        return winners[0] if winners else None

    @property
    def buyer_cost(self) -> float:
        return sum(c.settlement.buyer_cost for c in self.all_contracts)

    @property
    def quality(self) -> float | None:
        passed = [c.verification.quality_score for c in self.all_contracts if c.passed]
        return fmean(passed) if passed else None

    @property
    def latency(self) -> float | None:
        """Total execution time across every attempt (retries add up)."""
        attempts = self.all_contracts
        return sum(c.execution.latency for c in attempts) if attempts else None

    def explain(self) -> str:
        lines = [f"Auction {self.auction_id} for task {self.task.task_id}: {self.status.value}"]
        if self.outcome is None or not self.outcome.ranking:
            lines.append(self.reason or "no valid bids")
            return "\n".join(lines)
        for award in self.outcome.awards:
            lines.append(
                f"Winner: {award.agent_id} (paid {award.payment:.6g}: {award.payment_rule})"
            )
        lines.append("Ranking:")
        for i, scored in enumerate(self.outcome.ranking, start=1):
            body = scored.explain().replace("\n", "\n     ")
            lines.append(f"  {i}. {body}")
        for note in self.outcome.notes:
            lines.append(f"Note: {note}")
        for c in self.contracts:
            verdict = "passed" if c.passed else "failed"
            lines.append(
                f"Contract {c.contract.contract_id} ({c.contract.agent_id}, attempt "
                f"{c.contract.attempt}): verification {verdict}, quality "
                f"{c.verification.quality_score:.3f}, buyer cost {c.settlement.buyer_cost:.6g}"
            )
        if self.child is not None:
            lines.append(f"Re-opened as {self.child.auction_id}:")
            lines.append(self.child.explain())
        return "\n".join(lines)

    def trace(self) -> list[str]:
        return [line for r in self.chain() for line in format_trace(r.events)]

    def to_dict(self) -> dict[str, Any]:
        a = self.auction
        return {
            "auction_id": a.auction_id,
            "task": a.task.to_dict(),
            "mechanism": a.mechanism,
            "status": a.status.value,
            "parent_auction_id": a.parent_auction_id,
            "history": [[s.value, t] for s, t in a.history],
            "participants": list(a.participants),
            "excluded": dict(a.excluded),
            "bids": [b.to_dict() for b in a.bid_log],
            "rejected": [r.to_dict() for r in a.rejected],
            "features": {k: f.to_dict() for k, f in self.features.items()},
            "outcome": self.outcome.to_dict() if self.outcome else None,
            "contracts": [c.to_dict() for c in self.contracts],
            "child_auction_id": self.child.auction_id if self.child else None,
            "reason": self.reason,
        }
