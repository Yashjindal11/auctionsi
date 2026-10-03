"""Settlement policies: turn a verified (or failed) contract into payments."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any

from auctionsi.core.contract import Contract
from auctionsi.core.settlement import Settlement
from auctionsi.errors import ValidationError
from auctionsi.verification.verifiers import VerificationResult


class SettlementPolicy(ABC):
    name: str = "settlement"

    @abstractmethod
    def settle(
        self, contract: Contract, verification: VerificationResult, on_time: bool
    ) -> Settlement: ...

    def to_spec(self) -> dict[str, Any]:
        params: dict[str, Any] = asdict(self) if is_dataclass(self) else {}
        return {"name": self.name, **params}

    def _record(
        self,
        contract: Contract,
        verification: VerificationResult,
        on_time: bool,
        *,
        payment: float,
        penalty: float = 0.0,
        bonus: float = 0.0,
        reason: str,
    ) -> Settlement:
        return Settlement(
            contract_id=contract.contract_id,
            agent_id=contract.agent_id,
            task_id=contract.task_id,
            unit=contract.unit,
            payment=payment,
            penalty=penalty,
            bonus=bonus,
            refund=max(0.0, contract.payment_price - payment),
            quality_score=verification.quality_score,
            passed=verification.passed,
            on_time=on_time,
            reason=reason,
            policy=self.name,
        )


def _rate(value: float, name: str) -> None:
    if not 0 <= value <= 1:
        raise ValidationError(f"{name} must be in [0, 1]")


@dataclass(frozen=True)
class PayOnPass(SettlementPolicy):
    """Pay the mechanism's ``payment_price`` if verification passed, nothing otherwise.

    On failure the agent owes ``penalty_rate * payment_price``. A passing but late
    delivery is paid ``(1 - late_penalty_rate) * payment_price``. A passing delivery
    with quality >= ``bonus_threshold`` earns ``bonus_rate * payment_price`` extra.
    """

    penalty_rate: float = 0.0
    late_penalty_rate: float = 0.0
    bonus_rate: float = 0.0
    bonus_threshold: float = 1.0
    name = "pay_on_pass"

    def __post_init__(self) -> None:
        for field_name in ("penalty_rate", "late_penalty_rate", "bonus_rate", "bonus_threshold"):
            _rate(getattr(self, field_name), field_name)

    def settle(
        self, contract: Contract, verification: VerificationResult, on_time: bool
    ) -> Settlement:
        price = contract.payment_price
        if not verification.passed:
            return self._record(
                contract,
                verification,
                on_time,
                payment=0.0,
                penalty=self.penalty_rate * price,
                reason="verification failed",
            )
        payment = price if on_time else (1 - self.late_penalty_rate) * price
        bonus = (
            self.bonus_rate * price
            if self.bonus_rate and verification.quality_score >= self.bonus_threshold
            else 0.0
        )
        reason = "verification passed" + ("" if on_time else ", delivered late")
        return self._record(
            contract, verification, on_time, payment=payment, bonus=bonus, reason=reason
        )


@dataclass(frozen=True)
class QualityProportionalPayment(SettlementPolicy):
    """Passing work is paid ``payment_price * quality_score``; failed work is paid 0
    and penalised ``penalty_rate * payment_price``."""

    penalty_rate: float = 0.0
    name = "quality_proportional"

    def __post_init__(self) -> None:
        _rate(self.penalty_rate, "penalty_rate")

    def settle(
        self, contract: Contract, verification: VerificationResult, on_time: bool
    ) -> Settlement:
        price = contract.payment_price
        if not verification.passed:
            return self._record(
                contract,
                verification,
                on_time,
                payment=0.0,
                penalty=self.penalty_rate * price,
                reason="verification failed",
            )
        return self._record(
            contract,
            verification,
            on_time,
            payment=price * verification.quality_score,
            reason=f"paid {verification.quality_score:.3f} of price for quality",
        )


@dataclass(frozen=True)
class PartialPaymentOnFailure(SettlementPolicy):
    """Full payment on pass; ``failure_fraction * payment_price`` when verification
    fails but the agent did deliver something (e.g. to cover partial work)."""

    failure_fraction: float = 0.25
    name = "partial_on_failure"

    def __post_init__(self) -> None:
        _rate(self.failure_fraction, "failure_fraction")

    def settle(
        self, contract: Contract, verification: VerificationResult, on_time: bool
    ) -> Settlement:
        price = contract.payment_price
        if verification.passed:
            return self._record(
                contract, verification, on_time, payment=price, reason="verification passed"
            )
        return self._record(
            contract,
            verification,
            on_time,
            payment=self.failure_fraction * price,
            reason="verification failed, partial payment",
        )
