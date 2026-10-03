from __future__ import annotations

import pytest

from auctionsi.core import Contract
from auctionsi.errors import ValidationError
from auctionsi.settlement import PartialPaymentOnFailure, PayOnPass, QualityProportionalPayment
from auctionsi.verification import CheckResult, VerificationResult


def contract(payment_price: float = 0.05) -> Contract:
    return Contract(
        contract_id="c",
        auction_id="x",
        task_id="t",
        agent_id="a",
        bid_id="b",
        agreed_price=payment_price,
        payment_price=payment_price,
        unit="credits",
        created_at=0,
        min_quality=0.9,
    )


def verification(passed: bool, quality: float) -> VerificationResult:
    return VerificationResult.from_checks([CheckResult("q", passed, quality)], "test")


def test_pay_on_pass_full_payment() -> None:
    s = PayOnPass().settle(contract(), verification(True, 0.98), on_time=True)
    assert s.payment == 0.05
    assert s.refund == 0.0
    assert s.buyer_cost == 0.05


def test_pay_on_pass_failure_penalty_and_refund() -> None:
    s = PayOnPass(penalty_rate=0.5).settle(contract(), verification(False, 0.4), on_time=True)
    assert s.payment == 0.0
    assert s.penalty == pytest.approx(0.025)
    assert s.refund == pytest.approx(0.05)
    assert s.buyer_cost == pytest.approx(-0.025)


def test_pay_on_pass_late_and_bonus() -> None:
    policy = PayOnPass(late_penalty_rate=0.2, bonus_rate=0.1, bonus_threshold=0.95)
    late = policy.settle(contract(1.0), verification(True, 0.99), on_time=False)
    assert late.payment == pytest.approx(0.8)
    assert late.bonus == pytest.approx(0.1)
    assert "late" in late.reason
    no_bonus = policy.settle(contract(1.0), verification(True, 0.9), on_time=True)
    assert no_bonus.bonus == 0.0


def test_quality_proportional_and_partial() -> None:
    s = QualityProportionalPayment().settle(contract(1.0), verification(True, 0.9), True)
    assert s.payment == pytest.approx(0.9)
    assert s.refund == pytest.approx(0.1)
    p = PartialPaymentOnFailure(0.25).settle(contract(1.0), verification(False, 0.3), True)
    assert p.payment == pytest.approx(0.25)
    assert PartialPaymentOnFailure().to_spec() == {
        "name": "partial_on_failure",
        "failure_fraction": 0.25,
    }


def test_rates_are_validated() -> None:
    with pytest.raises(ValidationError):
        PayOnPass(penalty_rate=2)
    with pytest.raises(ValidationError):
        QualityProportionalPayment(penalty_rate=-0.1)
