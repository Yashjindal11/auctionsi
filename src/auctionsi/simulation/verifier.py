"""Verifier for simulated agents, whose output carries its own realised quality."""

from __future__ import annotations

from typing import Any

from auctionsi.core.contract import Contract
from auctionsi.core.task import Task
from auctionsi.verification.verifiers import CheckResult, VerificationResult, Verifier


class SimulatedQualityVerifier(Verifier):
    """Reads ``output["quality"]`` (the simulator's ground truth) as the quality score.

    The pass/fail gate is the contract's ``min_quality`` (applied by the marketplace);
    on its own this verifier passes any well-formed simulated output.
    """

    name = "simulated_quality"

    def verify(self, output: Any, contract: Contract, task: Task) -> VerificationResult:
        quality = output.get("quality") if isinstance(output, dict) else None
        if not isinstance(quality, int | float) or isinstance(quality, bool):
            check = CheckResult("simulated_quality", False, 0.0, "output has no numeric quality")
            return VerificationResult.from_checks([check], self.name)
        score = min(1.0, max(0.0, float(quality)))
        check = CheckResult("simulated_quality", True, score, f"realised quality {score:.4f}")
        return VerificationResult.from_checks([check], self.name)
