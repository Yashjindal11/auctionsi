from __future__ import annotations

import math

import pytest

from auctionsi.core import BidProposal
from auctionsi.market.validation import BidValidationConfig, validate_proposal
from auctionsi.reports import auction_report
from auctionsi.reports.markdown import conclusions
from auctionsi.statistics.summary import Comparison
from auctionsi.verification import ExactMatchVerifier
from conftest import MarketFactory, ScriptedAgent, task


def _comparison(**kwargs: object) -> Comparison:
    values: dict[str, object] = {
        "metric": "total_cost",
        "baseline": "a",
        "treatment": "b",
        "design": "paired",
        "n": 10,
        "mean_diff": 1.0,
        "ci_low": 0.5,
        "ci_high": 1.5,
        "statistic": 3.0,
        "p_value": 0.01,
        "effect_size": 0.9,
    }
    values.update(kwargs)
    return Comparison(**values)  # type: ignore[arg-type]


def test_conclusions_wording() -> None:
    assert conclusions([], 0.05, 0.95) == ["No comparison was run, so no conclusion is drawn."]
    higher, lower, null = conclusions(
        [
            _comparison(),
            _comparison(mean_diff=-1.0, ci_low=-1.5, ci_high=-0.5),
            _comparison(p_value=0.2, p_adjusted=0.4),
        ],
        0.05,
        0.95,
    )
    assert "produced higher `total_cost` than `a`" in higher
    assert "produced lower" in lower
    assert "No difference in `total_cost`" in null
    assert "95% CI [0.5, 1.5]" in higher


def test_auction_report_covers_every_section(market_factory: MarketFactory) -> None:
    market = market_factory(verifier=ExactMatchVerifier(42, key="answer"))
    market.register(ScriptedAgent("good", 0.05, output={"answer": 42}))
    market.register(ScriptedAgent("pricey", 5.0))
    market.register(ScriptedAgent("other", 0.01, available=False))
    result = market.submit_task(task(budget=0.1, deadline=10))
    report = auction_report(result)
    assert report.startswith(f"# Auction {result.auction_id}")
    assert "budget=0.1 deadline=10" in report
    assert "Final status: settled" in report
    assert "## Excluded at discovery" in report
    assert "- other:" in report
    assert "| good | 0.05 |" in report
    assert "## Rejected bids" in report
    assert "pricey: over_budget" in report
    assert "## Selection" in report
    assert "Agent good, attempt 1, agreed 0.05" in report
    assert ": pass (" in report
    assert "Settlement (pay_on_pass): payment 0.05" in report
    assert "## Trace" in report


def test_auction_report_without_bids(market_factory: MarketFactory) -> None:
    market = market_factory()
    result = market.submit_task(task())
    report = auction_report(result)
    assert "Participants: none" in report
    assert "## Selection" not in report
    assert "## Contract" not in report


# ------------------------------------------------------------------- validation

AGENT = ScriptedAgent("a", 1.0)
CFG = BidValidationConfig()


def _codes(proposal: object, **kwargs: object) -> list[str]:
    t = kwargs.pop("task", task(budget=1.0, deadline=10, min_quality=0.5, reserve_price=0.2))
    reasons = validate_proposal(
        proposal,
        t,  # type: ignore[arg-type]
        kwargs.pop("agent", AGENT),  # type: ignore[arg-type]
        eligible=bool(kwargs.pop("eligible", True)),
        now=0.0,
        config=kwargs.pop("config", CFG),  # type: ignore[arg-type]
        direction=str(kwargs.pop("direction", "reverse")),
    )
    return [r.code.value for r in reasons]


def test_valid_proposal_has_no_reasons() -> None:
    assert _codes(BidProposal(price=0.5, estimated_latency=1, estimated_quality=0.9)) == []


@pytest.mark.parametrize(
    ("kwargs", "code"),
    [
        ({"task": None}, "unknown_task"),
        ({"agent": None}, "agent_not_eligible"),
        ({"eligible": False}, "agent_not_eligible"),
        ({"agent": ScriptedAgent("s", 1.0, capabilities=("sql",))}, "capability_mismatch"),
    ],
)
def test_gatekeeping_reasons(kwargs: dict[str, object], code: str) -> None:
    assert _codes(BidProposal(price=0.5), **kwargs) == [code]


def test_malformed_proposal() -> None:
    assert _codes({"price": 1}) == ["malformed"]


@pytest.mark.parametrize(
    ("proposal", "code"),
    [
        (BidProposal(price=math.nan), "invalid_price"),
        (BidProposal(price=True), "invalid_price"),  # type: ignore[arg-type]
        (BidProposal(price=-0.1), "invalid_price"),
        (BidProposal(price=2.0), "over_budget"),
        (BidProposal(price=0.5, estimated_latency=-1), "invalid_latency"),
        (BidProposal(price=0.5, estimated_latency=math.inf), "invalid_latency"),
        (BidProposal(price=0.5, estimated_latency=11), "deadline_infeasible"),
        (BidProposal(price=0.5, estimated_quality=1.2), "invalid_estimate"),
        (BidProposal(price=0.5, confidence=-0.1), "invalid_estimate"),
        (BidProposal(price=0.5, estimated_cost=math.nan), "invalid_estimate"),
        (BidProposal(price=0.5, capacity=-1), "malformed"),
        (BidProposal(price=0.5, capacity=True), "malformed"),  # type: ignore[arg-type]
        (BidProposal(price=0.5, capacity=1.5), "malformed"),  # type: ignore[arg-type]
        (BidProposal(price=0.5, estimated_quality=0.4), "below_min_quality"),
        (BidProposal(price=0.5, valid_for=0), "expired"),
        (BidProposal(price=0.5, valid_for=math.nan), "expired"),
    ],
)
def test_field_reasons(proposal: BidProposal, code: str) -> None:
    assert _codes(proposal) == [code]


def test_every_reason_is_reported_at_once() -> None:
    codes = _codes(BidProposal(price=2.0, estimated_latency=-1, confidence=2, valid_for=-1))
    assert codes == ["over_budget", "invalid_latency", "invalid_estimate", "expired"]


def test_config_switches() -> None:
    lenient = BidValidationConfig(
        enforce_budget=False,
        enforce_deadline=False,
        enforce_min_quality=False,
        allow_negative_prices=True,
    )
    assert (
        _codes(BidProposal(price=-2.0, estimated_latency=99, estimated_quality=0.1), config=lenient)
        == []
    )
    strict = BidValidationConfig(require_latency_estimate=True)
    assert _codes(BidProposal(price=0.5), config=strict) == ["invalid_latency"]


def test_forward_direction_checks_reserve_not_budget() -> None:
    assert _codes(BidProposal(price=0.1), direction="forward") == ["below_reserve"]
    assert _codes(BidProposal(price=50.0), direction="forward") == []
