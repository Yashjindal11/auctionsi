from __future__ import annotations

import math

import pytest

from auctionsi.core import BidProposal, RejectionCode
from auctionsi.core.auction import AuctionStatus
from auctionsi.errors import InvalidTransitionError, NotFoundError, ValidationError
from auctionsi.market import EventType, RecoveryPolicy
from auctionsi.mechanisms import (
    MultiWinnerReverseAuction,
    OpenReverseAuction,
    SecondPriceReverseAuction,
)
from auctionsi.settlement import PayOnPass
from auctionsi.verification import ExactMatchVerifier, MetricThresholdVerifier
from conftest import MarketFactory, ScriptedAgent, task

S = AuctionStatus


def spec_market(factory: MarketFactory, **kwargs: object) -> tuple[object, list[ScriptedAgent]]:
    market = factory(**kwargs)
    agents = [ScriptedAgent("A", 0.05), ScriptedAgent("B", 0.07), ScriptedAgent("C", 0.03)]
    for agent in agents:
        market.register(agent)
    return market, agents


@pytest.mark.integration
def test_full_lifecycle_first_price(market_factory: MarketFactory) -> None:
    market, _ = spec_market(market_factory)
    result = market.submit_task(task(budget=0.10))  # type: ignore[attr-defined]
    assert result.status == S.SETTLED
    assert result.succeeded
    assert result.winner == "C"
    assert result.buyer_cost == pytest.approx(0.03)
    assert [s for s, _ in result.auction.history] == [
        S.CREATED,
        S.ANNOUNCED,
        S.OPEN,
        S.BID_COLLECTION,
        S.CLOSED,
        S.EVALUATION,
        S.AWARDED,
        S.CONTRACTED,
        S.EXECUTING,
        S.VERIFYING,
        S.SETTLED,
    ]
    types = [e.type for e in result.events]
    for expected in (
        EventType.TASK_CREATED,
        EventType.AGENTS_DISCOVERED,
        EventType.BID_SUBMITTED,
        EventType.AUCTION_CLOSED,
        EventType.WINNER_SELECTED,
        EventType.CONTRACT_CREATED,
        EventType.TASK_STARTED,
        EventType.TASK_COMPLETED,
        EventType.VERIFICATION_PASSED,
        EventType.SETTLEMENT_COMPLETED,
        EventType.REPUTATION_UPDATED,
        EventType.AUCTION_SETTLED,
    ):
        assert expected in types
    trace = "\n".join(result.trace())
    assert "3 eligible" in trace
    assert "winner selected: C" in trace
    explanation = result.explain()
    assert "Winner: C" in explanation
    assert "price" in explanation
    profile = market.reputation.profile("C", "analysis")  # type: ignore[attr-defined]
    assert profile.completed == 1


def test_second_price_settlement(market_factory: MarketFactory) -> None:
    market, _ = spec_market(market_factory, mechanism=SecondPriceReverseAuction())
    result = market.submit_task(task(budget=0.10))  # type: ignore[attr-defined]
    assert result.winner == "C"
    assert result.buyer_cost == pytest.approx(0.05)
    contract = result.contracts[0].contract
    assert contract.agreed_price == 0.03
    assert contract.payment_price == 0.05


def test_discovery_filters_ineligible_agents(market_factory: MarketFactory) -> None:
    market = market_factory()
    market.register(ScriptedAgent("ok", 1.0))
    market.register(ScriptedAgent("wrong", 1.0, capabilities=("research",)))
    off = ScriptedAgent("off", 1.0)
    off.available = False
    market.register(off)
    result = market.submit_task(task())
    assert result.auction.participants == ["ok"]
    assert set(result.auction.excluded) == {"off"}
    assert result.discovery.not_capable == 1
    assert "unavailable" in result.auction.excluded["off"]
    assert "1 without the capability" in "\n".join(result.trace())


def test_capacity_blocks_busy_agents(market_factory: MarketFactory) -> None:
    clock = market_factory().clock  # fresh ManualClock
    market = market_factory(clock=clock)
    market.register(ScriptedAgent("slow", 1.0, latency=10.0))
    market.register(ScriptedAgent("pricey", 2.0, latency=1.0))
    first = market.submit_task(task("t1"))
    assert first.winner == "slow"
    second = market.submit_task(task("t2"))
    assert second.winner == "pricey"
    assert "at capacity" in second.auction.excluded["slow"][0]
    clock.set(20.0)  # type: ignore[attr-defined]
    third = market.submit_task(task("t3"))
    assert third.winner == "slow"


def test_invalid_bids_are_rejected_with_reasons(market_factory: MarketFactory) -> None:
    market = market_factory()
    market.register(ScriptedAgent("good", 0.05))
    market.register(ScriptedAgent("over", 0.50))
    market.register(ScriptedAgent("negative", -1.0))
    market.register(ScriptedAgent("nan", math.nan))
    market.register(ScriptedAgent("slow", 0.01, latency=999))
    market.register(ScriptedAgent("weak", 0.01, quality=0.2))
    market.register(ScriptedAgent("garbage", 0.0, proposal="not a proposal"))
    market.register(ScriptedAgent("crash", 0.0, bid_error=RuntimeError("boom")))
    market.register(ScriptedAgent("silent", None))
    result = market.submit_task(task(budget=0.10, deadline=60, min_quality=0.8))
    assert result.winner == "good"
    codes = {r.agent_id: {x.code for x in r.reasons} for r in result.auction.rejected}
    assert codes["over"] == {RejectionCode.OVER_BUDGET}
    assert codes["negative"] == {RejectionCode.INVALID_PRICE}
    assert codes["nan"] == {RejectionCode.INVALID_PRICE}
    assert codes["slow"] == {RejectionCode.DEADLINE_INFEASIBLE}
    assert codes["weak"] == {RejectionCode.BELOW_MIN_QUALITY}
    assert codes["garbage"] == {RejectionCode.MALFORMED}
    assert codes["crash"] == {RejectionCode.AGENT_ERROR}
    assert "silent" not in codes
    rejected_events = [e for e in result.events if e.type == EventType.BID_REJECTED]
    assert len(rejected_events) == 7


def test_no_bids(market_factory: MarketFactory) -> None:
    market = market_factory()
    market.register(ScriptedAgent("a", None))
    result = market.submit_task(task())
    assert result.status == S.NO_BIDS
    assert not result.succeeded
    assert result.winner is None
    assert "no valid bids" in result.explain()


@pytest.mark.integration
def test_verification_failure_penalises_and_updates_reputation(
    market_factory: MarketFactory,
) -> None:
    market = market_factory(
        verifier=MetricThresholdVerifier("quality", 0.95), settlement=PayOnPass(penalty_rate=0.5)
    )
    market.register(ScriptedAgent("a", 1.0, quality=0.5))
    result = market.submit_task(task())
    assert result.status == S.FAILED
    outcome = result.contracts[0]
    assert not outcome.passed
    assert outcome.settlement.penalty == pytest.approx(0.5)
    assert outcome.contract.status.value == "breached"
    profile = market.reputation.profile("a")
    assert profile is not None
    assert profile.failed == 1
    assert profile.violations == pytest.approx(1)


def test_min_quality_gate_applies_after_verification(market_factory: MarketFactory) -> None:
    market = market_factory(verifier=MetricThresholdVerifier("quality", 0.0, as_quality=True))
    market.register(ScriptedAgent("a", 1.0, quality=0.95, output={"quality": 0.6}))
    result = market.submit_task(task(min_quality=0.9))
    assert not result.succeeded
    checks = {c.name: c.passed for c in result.contracts[0].verification.checks}
    assert checks == {"quality": True, "min_quality": False}
    # Quality claim error is recorded for calibration.
    profile = market.reputation.profile("a")
    assert profile.quality_estimate_bias == pytest.approx(0.35)  # type: ignore[union-attr]


def test_execution_errors_become_failures(market_factory: MarketFactory) -> None:
    class Crashing(ScriptedAgent):
        def execute(self, task, contract):  # type: ignore[no-untyped-def]
            raise RuntimeError("kaboom")

    class BadLatency(ScriptedAgent):
        def execute(self, task, contract):  # type: ignore[no-untyped-def]
            from auctionsi.core import ExecutionResult

            return ExecutionResult(success=True, output={}, latency=-5)

    market = market_factory()
    market.register(Crashing("a", 1.0))
    result = market.submit_task(task("t1"))
    assert "kaboom" in (result.contracts[0].execution.error or "")
    market.unregister("a")
    market.register(BadLatency("b", 1.0))
    result = market.submit_task(task("t2"))
    assert "invalid latency" in (result.contracts[0].execution.error or "")


def test_oversized_output_is_rejected(market_factory: MarketFactory) -> None:
    from auctionsi.security import Limits

    market = market_factory(limits=Limits(max_output_bytes=100))
    market.register(ScriptedAgent("a", 1.0, output={"blob": "x" * 500}))
    result = market.submit_task(task())
    assert "exceeds 100 bytes" in (result.contracts[0].execution.error or "")


@pytest.mark.integration
def test_recovery_retry_same(market_factory: MarketFactory) -> None:
    market = market_factory(recovery=RecoveryPolicy(retry_same=2))
    agent = ScriptedAgent("a", 1.0, fail=1)
    market.register(agent)
    result = market.submit_task(task())
    assert result.succeeded
    assert [c.contract.attempt for c in result.contracts] == [1, 2]
    assert agent.executions == 2
    assert any(e.type == EventType.RECOVERY_STARTED for e in result.events)


@pytest.mark.integration
def test_recovery_next_best(market_factory: MarketFactory) -> None:
    market = market_factory(recovery=RecoveryPolicy(next_best=1))
    market.register(ScriptedAgent("cheap", 0.01, fail=True))
    market.register(ScriptedAgent("backup", 0.02))
    market.register(ScriptedAgent("third", 0.03))
    result = market.submit_task(task())
    assert result.succeeded
    assert result.winners == ["backup"]
    assert result.contracts[1].contract.payment_price == 0.02
    assert result.buyer_cost == pytest.approx(0.02)


@pytest.mark.integration
def test_recovery_reopen_excludes_failed_agent(market_factory: MarketFactory) -> None:
    market = market_factory(recovery=RecoveryPolicy(reopen=1))
    market.register(ScriptedAgent("cheap", 0.01, fail=True))
    market.register(ScriptedAgent("other", 0.05))
    result = market.submit_task(task())
    assert result.status == S.FAILED
    assert result.child is not None
    assert result.child.auction.parent_auction_id == result.auction_id
    assert result.final.status == S.SETTLED
    assert result.succeeded
    assert result.winner == "other"
    assert "cheap" in result.child.auction.excluded
    assert "Re-opened as" in result.explain()


def test_no_recovery_means_failure_is_final(market_factory: MarketFactory) -> None:
    market = market_factory()
    market.register(ScriptedAgent("cheap", 0.01, fail=True))
    market.register(ScriptedAgent("other", 0.05))
    result = market.submit_task(task())
    assert not result.succeeded
    assert len(result.contracts) == 1


@pytest.mark.integration
def test_multi_winner_runs_one_contract_per_winner(market_factory: MarketFactory) -> None:
    market = market_factory(mechanism=MultiWinnerReverseAuction(winners=2))
    for name, price in [("a", 0.01), ("b", 0.02), ("c", 0.03)]:
        market.register(ScriptedAgent(name, price))
    result = market.submit_task(task())
    assert result.succeeded
    assert sorted(result.winners) == ["a", "b"]
    assert result.buyer_cost == pytest.approx(0.03)


@pytest.mark.integration
def test_open_auction_records_revisions(market_factory: MarketFactory) -> None:
    market = market_factory(mechanism=OpenReverseAuction(max_rounds=20))
    market.register(ScriptedAgent("a", 0.10, floor=0.06))
    market.register(ScriptedAgent("b", 0.09, floor=0.07))
    result = market.submit_task(task())
    assert result.winner == "a"
    revisions = [e for e in result.events if e.type == EventType.BID_REVISED]
    assert revisions
    final_price = result.auction.bids["a"].price
    assert final_price == pytest.approx(0.06)
    assert result.auction.bids["a"].revision > 0
    assert len(result.auction.bid_log) == 2 + len(revisions)


def test_staged_api_external_bids_and_cancel(market_factory: MarketFactory) -> None:
    market = market_factory()
    market.register(ScriptedAgent("human", None))
    market.register(ScriptedAgent("bot", 0.08))
    auction = market.open_auction(task("t1"), solicit=False)
    assert auction.status == S.BID_COLLECTION
    assert market.submit_bid(auction.auction_id, "human", BidProposal(price=0.04)) is not None
    dup = market.submit_bid(auction.auction_id, "human", BidProposal(price=0.03))
    assert dup is None
    assert auction.rejected[-1].reasons[0].code == RejectionCode.DUPLICATE_BID
    assert market.submit_bid(auction.auction_id, "stranger", BidProposal(price=0.01)) is None
    result = market.close_auction(auction.auction_id)
    assert result.winner == "human"
    with pytest.raises(InvalidTransitionError):
        market.submit_bid(auction.auction_id, "bot", BidProposal(price=0.01))

    other = market.open_auction(task("t2"))
    market.cancel_auction(other.auction_id, "buyer changed mind")
    assert other.status == S.CANCELLED
    with pytest.raises(InvalidTransitionError):
        market.close_auction(other.auction_id)
    with pytest.raises(NotFoundError):
        market.close_auction("auction-nope")


def test_agents_are_notified_and_clearing_price_disclosed(market_factory: MarketFactory) -> None:
    market, agents = spec_market(market_factory, disclose_clearing_price=True)
    market.submit_task(task(budget=0.10))  # type: ignore[attr-defined]
    by_id = {a.agent_id: a for a in agents}
    assert by_id["C"].notices[0].won
    assert not by_id["A"].notices[0].won
    assert by_id["A"].notices[0].clearing_price == 0.03
    hidden, hidden_agents = spec_market(market_factory)
    hidden.submit_task(task(budget=0.10))  # type: ignore[attr-defined]
    assert hidden_agents[0].notices[0].clearing_price is None


def test_registration_rules(market_factory: MarketFactory) -> None:
    market = market_factory()
    market.register(ScriptedAgent("a", 1.0))
    with pytest.raises(ValidationError):
        market.register(ScriptedAgent("a", 1.0))
    with pytest.raises(NotFoundError):
        market.get_agent("zzz")
    market.submit_task(task("t1"))
    with pytest.raises(ValidationError):
        market.submit_task(task("t1"))


def test_long_running_markets_can_drop_finished_auctions(market_factory: MarketFactory) -> None:
    market = market_factory(retain_results=False, keep_events=False)
    market.register(ScriptedAgent("a", 1.0))
    result = market.submit_task(task())
    assert result.succeeded
    assert result.events == []
    assert market.results == {}
    assert market.auctions == {}


def test_exact_verifier_end_to_end(market_factory: MarketFactory) -> None:
    market = market_factory(verifier=ExactMatchVerifier(42, key="answer"))
    market.register(ScriptedAgent("right", 0.02, output={"answer": 42}))
    assert market.submit_task(task()).succeeded


def test_identical_markets_produce_identical_event_streams(market_factory: MarketFactory) -> None:
    def run() -> list[dict[str, object]]:
        market, _ = spec_market(market_factory)
        market.submit_task(task(budget=0.10))  # type: ignore[attr-defined]
        return [e.to_dict() for e in market.log.events]  # type: ignore[attr-defined]

    assert run() == run()
