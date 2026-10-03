"""Bid intake: asks agents for bids, validates them, stamps them and records events."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from concurrent.futures import Executor, wait
from dataclasses import fields
from typing import Any

from auctionsi.core.agent import Agent, BidContext, OpenAuctionView
from auctionsi.core.auction import Auction, RejectedBid
from auctionsi.core.bid import Bid, BidProposal, BidRejection, RejectionCode
from auctionsi.errors import ValidationError
from auctionsi.market.clock import Clock, IdGenerator
from auctionsi.market.events import EventBus, EventType
from auctionsi.market.validation import BidValidationConfig, validate_proposal
from auctionsi.security import DEFAULT_LIMITS, Limits

R = RejectionCode


class BidIntake:
    """The only path by which a bid enters an auction.

    Mechanisms call :meth:`solicit` / :meth:`solicit_revision`; external callers
    (API, human workflows) call :meth:`submit`. All three share validation.
    """

    def __init__(
        self,
        auction: Auction,
        agents: Mapping[str, Agent],
        *,
        clock: Clock,
        ids: IdGenerator,
        bus: EventBus,
        config: BidValidationConfig,
        sealed: bool,
        limits: Limits = DEFAULT_LIMITS,
        timeout: float | None = None,
        executor: Executor | None = None,
    ) -> None:
        self.auction = auction
        self.agents = agents
        self.clock = clock
        self.ids = ids
        self.bus = bus
        self.config = config
        self.sealed = sealed
        self.limits = limits
        self.timeout = timeout
        self.executor = executor
        self._revisions: dict[str, int] = {}

    def context(self, round: int = 0) -> BidContext:
        return BidContext(
            auction_id=self.auction.auction_id,
            mechanism=self.auction.mechanism,
            now=self.clock.now(),
            sealed=self.sealed,
            unit=self.auction.task.unit,
            round=round,
        )

    def solicit(self, agent: Agent, round: int = 0) -> Bid | None:
        try:
            proposal = agent.bid(self.auction.task, self.context(round))
        except Exception as exc:
            self._reject(agent.agent_id, None, [_agent_error(exc)])
            return None
        if proposal is None:
            return None
        return self.submit(agent.agent_id, proposal)

    def solicit_all(self, agents: Sequence[Agent], round: int = 0) -> list[Bid]:
        """Ask every agent for a bid. With a timeout, agents are asked concurrently and
        replies arriving after the deadline are rejected; accepted bids are still
        recorded in agent order so outcomes do not depend on thread timing."""
        if self.timeout is None or self.executor is None:
            return [b for agent in agents if (b := self.solicit(agent, round)) is not None]
        context = self.context(round)
        futures = {
            a.agent_id: self.executor.submit(a.bid, self.auction.task, context) for a in agents
        }
        wait(futures.values(), timeout=self.timeout)
        bids = []
        for agent in agents:
            future = futures[agent.agent_id]
            if not future.done():
                future.cancel()
                message = f"no bid within the {self.timeout}s bidding window"
                self._reject(agent.agent_id, None, [BidRejection(R.TIMEOUT, message)])
                continue
            exc = future.exception()
            if exc is not None:
                self._reject(agent.agent_id, None, [_agent_error(exc)])
                continue
            proposal = future.result()
            if proposal is not None and (bid := self.submit(agent.agent_id, proposal)) is not None:
                bids.append(bid)
        return bids

    def solicit_revision(self, agent: Agent, view: OpenAuctionView) -> Bid | None:
        try:
            proposal = agent.revise_bid(self.auction.task, view)
        except Exception as exc:
            self._reject(agent.agent_id, None, [_agent_error(exc)])
            return None
        if proposal is None:
            return None
        return self.submit(agent.agent_id, proposal, revision=True, round=view.round)

    def submit(
        self, agent_id: str, proposal: object, *, revision: bool = False, round: int = 0
    ) -> Bid | None:
        auction = self.auction
        now = self.clock.now()
        agent = self.agents.get(agent_id)
        reasons = validate_proposal(
            proposal,
            auction.task,
            agent,
            eligible=agent_id in auction.participants,
            now=now,
            config=self.config,
        )
        previous = auction.bids.get(agent_id)
        if not reasons and len(auction.bid_log) >= self.limits.max_bids_per_auction:
            reasons = [BidRejection(R.TOO_MANY_BIDS, "auction bid limit reached")]
        limit = self.config.max_bids_per_operator
        if not reasons and previous is None and limit is not None and agent is not None:
            operator = agent.metadata.get("operator", agent_id)
            same = sum(
                1
                for other in auction.bids
                if other in self.agents
                and self.agents[other].metadata.get("operator", other) == operator
            )
            if same >= limit:
                reasons = [
                    BidRejection(
                        R.TOO_MANY_BIDS, f"operator {operator!r} already has {same} bid(s)"
                    )
                ]
        if not reasons and previous is not None:
            if not revision:
                reasons = [BidRejection(R.DUPLICATE_BID, "agent already has a bid")]
            elif self._revisions.get(agent_id, 0) >= self.limits.max_revisions_per_agent:
                reasons = [BidRejection(R.TOO_MANY_BIDS, "revision limit reached")]
            elif isinstance(proposal, BidProposal) and proposal.price >= previous.price:
                reasons = [BidRejection(R.NOT_IMPROVING, "revision must lower the price")]
        if reasons:
            self._reject(agent_id, proposal, reasons)
            return None
        assert isinstance(proposal, BidProposal)
        try:
            bid = Bid(
                bid_id=self.ids.next("bid"),
                task_id=auction.task_id,
                agent_id=agent_id,
                auction_id=auction.auction_id,
                price=proposal.price,
                estimated_latency=proposal.estimated_latency,
                estimated_quality=proposal.estimated_quality,
                estimated_cost=proposal.estimated_cost,
                confidence=proposal.confidence,
                capacity=proposal.capacity,
                valid_until=None if proposal.valid_for is None else now + proposal.valid_for,
                constraints=proposal.constraints,
                terms=proposal.terms,
                timestamp=now,
                revision=0 if previous is None else previous.revision + 1,
                signature=proposal.signature,
            )
        except ValidationError as exc:
            self._reject(agent_id, proposal, [BidRejection(R.MALFORMED, str(exc)[:300])])
            return None
        auction.record_bid(bid)
        if previous is not None:
            self._revisions[agent_id] = self._revisions.get(agent_id, 0) + 1
        self.bus.publish(
            EventType.BID_REVISED if previous is not None else EventType.BID_SUBMITTED,
            now,
            auction_id=auction.auction_id,
            task_id=auction.task_id,
            agent_id=agent_id,
            bid_id=bid.bid_id,
            data={"bid": bid.to_dict(), "round": round},
        )
        return bid

    def expire_stale(self) -> None:
        """Drop bids whose ``valid_until`` has passed (called when the auction closes)."""
        now = self.clock.now()
        for agent_id, bid in list(self.auction.bids.items()):
            if bid.valid_until is not None and bid.valid_until < now:
                del self.auction.bids[agent_id]
                self._reject(
                    agent_id,
                    _proposal_dict(bid),
                    [BidRejection(R.EXPIRED, f"bid expired at {bid.valid_until}")],
                )

    def _reject(self, agent_id: str, proposal: object, reasons: list[BidRejection]) -> None:
        now = self.clock.now()
        record = RejectedBid(agent_id, _proposal_dict(proposal), tuple(reasons), now)
        self.auction.rejected.append(record)
        self.bus.publish(
            EventType.BID_REJECTED,
            now,
            auction_id=self.auction.auction_id,
            task_id=self.auction.task_id,
            agent_id=agent_id,
            data=record.to_dict(),
        )


def _agent_error(exc: BaseException) -> BidRejection:
    return BidRejection(R.AGENT_ERROR, f"{type(exc).__name__}: {exc}"[:300])


def _proposal_dict(proposal: object) -> dict[str, Any] | None:
    """A JSON-safe summary of whatever the agent sent."""
    if isinstance(proposal, BidProposal | Bid):
        out: dict[str, Any] = {}
        for f in fields(proposal):
            value = getattr(proposal, f.name)
            if value is None or isinstance(value, bool | int | float | str):
                if isinstance(value, float) and value != value:  # NaN
                    value = "nan"
                elif isinstance(value, float) and value in (float("inf"), float("-inf")):
                    value = str(value)
                out[f.name] = value
            else:
                out[f.name] = repr(value)[:200]
        return out
    if proposal is None:
        return None
    return {"repr": repr(proposal)[:200]}
