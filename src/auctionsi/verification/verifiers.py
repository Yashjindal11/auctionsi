"""Verifiers decide whether delivered work satisfies a contract.

Every verifier returns a :class:`VerificationResult` made of named checks, and
the ``quality_score`` is always computed from those checks by a documented rule,
so a score of 0.97 can be traced back to exactly what passed and failed.
Deterministic verifiers are the default; nothing here calls a model.
"""

from __future__ import annotations

import contextlib
import math
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from auctionsi.core.contract import Contract
from auctionsi.core.task import Task
from auctionsi.errors import ValidationError
from auctionsi.verification import schema as _schema


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    passed: bool
    score: float
    detail: str = ""
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "score": self.score,
            "detail": self.detail,
            "required": self.required,
        }


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """``passed`` = every required check passed; ``quality_score`` in [0, 1]."""

    passed: bool
    quality_score: float
    checks: tuple[CheckResult, ...] = ()
    verifier: str = ""
    cost: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_checks(
        cls,
        checks: Sequence[CheckResult],
        verifier: str,
        *,
        weights: Sequence[float] | None = None,
        cost: float = 0.0,
    ) -> VerificationResult:
        """Quality = weighted mean of check scores; passed = all required checks pass."""
        if not checks:
            return cls(False, 0.0, (), verifier, cost)
        w = list(weights) if weights is not None else [1.0] * len(checks)
        total = sum(w)
        quality = sum(c.score * wi for c, wi in zip(checks, w, strict=True)) / total
        passed = all(c.passed for c in checks if c.required)
        return cls(passed, min(1.0, max(0.0, quality)), tuple(checks), verifier, cost)

    def with_check(self, check: CheckResult) -> VerificationResult:
        """Append a gating check without changing the quality score."""
        passed = self.passed and (check.passed or not check.required)
        return VerificationResult(
            passed, self.quality_score, (*self.checks, check), self.verifier, self.cost
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "quality_score": self.quality_score,
            "checks": [c.to_dict() for c in self.checks],
            "verifier": self.verifier,
            "cost": self.cost,
        }


class Verifier(ABC):
    name: str = "verifier"

    @abstractmethod
    def verify(self, output: Any, contract: Contract, task: Task) -> VerificationResult: ...


class AcceptVerifier(Verifier):
    """Accepts any successful execution with quality 1.0. Used only when nothing else is
    configured; the check detail says so explicitly in every trace."""

    name = "accept"

    def verify(self, output: Any, contract: Contract, task: Task) -> VerificationResult:
        check = CheckResult("accepted_unchecked", True, 1.0, "no verifier configured")
        return VerificationResult.from_checks([check], self.name)


class SchemaVerifier(Verifier):
    """Validates output against a JSON-Schema subset (the task's schema by default)."""

    name = "schema"

    def __init__(self, schema: Mapping[str, Any] | None = None) -> None:
        self.schema = schema

    def verify(self, output: Any, contract: Contract, task: Task) -> VerificationResult:
        schema = self.schema or contract.output_requirements or task.expected_output_schema
        if not schema:
            check = CheckResult("schema", False, 0.0, "no schema available")
            return VerificationResult.from_checks([check], self.name)
        errors = _schema.validate(output, schema)
        detail = "valid" if not errors else "; ".join(errors[:5])
        check = CheckResult("schema", not errors, 0.0 if errors else 1.0, detail)
        return VerificationResult.from_checks([check], self.name)


class ExactMatchVerifier(Verifier):
    """Output (or ``output[key]``) must equal ``expected``."""

    name = "exact_match"

    def __init__(self, expected: Any, key: str | None = None) -> None:
        self.expected = expected
        self.key = key

    def verify(self, output: Any, contract: Contract, task: Task) -> VerificationResult:
        actual = _lookup(output, self.key)
        ok = actual == self.expected
        check = CheckResult("exact_match", ok, 1.0 if ok else 0.0, f"got {actual!r}"[:200])
        return VerificationResult.from_checks([check], self.name)


class ToleranceVerifier(Verifier):
    """Numeric output within ``math.isclose(rel_tol, abs_tol)`` of ``expected``."""

    name = "tolerance"

    def __init__(
        self, expected: float, *, key: str | None = None, rel_tol: float = 0, abs_tol: float = 1e-9
    ) -> None:
        self.expected = expected
        self.key = key
        self.rel_tol = rel_tol
        self.abs_tol = abs_tol

    def verify(self, output: Any, contract: Contract, task: Task) -> VerificationResult:
        actual = _lookup(output, self.key)
        ok = _is_number(actual) and math.isclose(
            actual, self.expected, rel_tol=self.rel_tol, abs_tol=self.abs_tol
        )
        check = CheckResult("tolerance", ok, 1.0 if ok else 0.0, f"got {actual!r}"[:200])
        return VerificationResult.from_checks([check], self.name)


class MetricThresholdVerifier(Verifier):
    """``output[metric]`` must clear ``threshold``.

    Quality is the metric itself (clipped to [0, 1]) when ``as_quality=True``,
    otherwise 1.0 on pass and 0.0 on failure.
    """

    name = "metric_threshold"

    def __init__(
        self,
        metric: str,
        threshold: float,
        *,
        higher_is_better: bool = True,
        as_quality: bool = False,
    ) -> None:
        self.metric = metric
        self.threshold = threshold
        self.higher_is_better = higher_is_better
        self.as_quality = as_quality

    def verify(self, output: Any, contract: Contract, task: Task) -> VerificationResult:
        value = _lookup(output, self.metric)
        if not _is_number(value):
            check = CheckResult(
                self.metric, False, 0.0, f"metric missing or not numeric: {value!r}"
            )
            return VerificationResult.from_checks([check], self.name)
        ok = value >= self.threshold if self.higher_is_better else value <= self.threshold
        if self.as_quality:
            score = min(1.0, max(0.0, float(value)))
        else:
            score = 1.0 if ok else 0.0
        op = ">=" if self.higher_is_better else "<="
        check = CheckResult(self.metric, ok, score, f"{value} {op} {self.threshold}: {ok}")
        return VerificationResult.from_checks([check], self.name)


class UnitTestVerifier(Verifier):
    """Runs named test callables (written by the *task owner*, never by agents)
    against the output. Quality = fraction passed; passed = all passed. A test that
    raises counts as failed."""

    name = "unit_tests"

    def __init__(self, tests: Mapping[str, Callable[[Any], bool]]) -> None:
        if not tests:
            raise ValidationError("UnitTestVerifier needs at least one test")
        self.tests = dict(tests)

    def verify(self, output: Any, contract: Contract, task: Task) -> VerificationResult:
        checks = []
        for name, test in self.tests.items():
            try:
                ok = bool(test(output))
                detail = ""
            except Exception as exc:
                ok, detail = False, f"{type(exc).__name__}: {exc}"[:200]
            checks.append(CheckResult(name, ok, 1.0 if ok else 0.0, detail))
        return VerificationResult.from_checks(checks, self.name)


class CallableVerifier(Verifier):
    """Wrap ``fn(output, contract, task) -> VerificationResult``."""

    def __init__(
        self, fn: Callable[[Any, Contract, Task], VerificationResult], name: str = "custom"
    ) -> None:
        self.fn = fn
        self.name = name

    def verify(self, output: Any, contract: Contract, task: Task) -> VerificationResult:
        return self.fn(output, contract, task)


class HumanApprovalVerifier(Verifier):
    """Asks a person to approve the output. ``ask`` receives a prompt and returns the
    answer; an answer of ``y``/``yes`` approves, optionally followed by a quality
    score (``y 0.8``)."""

    name = "human_approval"

    def __init__(self, ask: Callable[[str], str] = input) -> None:
        self.ask = ask

    def verify(self, output: Any, contract: Contract, task: Task) -> VerificationResult:
        preview = repr(output)[:500]
        answer = self.ask(f"Approve output of {contract.agent_id} for {task.task_id}?\n{preview}\n")
        parts = answer.strip().lower().split()
        ok = bool(parts) and parts[0] in ("y", "yes")
        score = 1.0 if ok else 0.0
        if ok and len(parts) > 1:
            with contextlib.suppress(ValueError):
                score = min(1.0, max(0.0, float(parts[1])))
        check = CheckResult("human_approval", ok, score, answer.strip()[:200])
        return VerificationResult.from_checks([check], self.name)


class CompositeVerifier(Verifier):
    """Runs several verifiers. Quality = weighted mean of their quality scores;
    passed = every verifier passed (or, with ``require_all=False``, at least one)."""

    name = "composite"

    def __init__(
        self,
        verifiers: Sequence[Verifier | tuple[Verifier, float]],
        *,
        require_all: bool = True,
    ) -> None:
        self.parts: list[tuple[Verifier, float]] = [
            v if isinstance(v, tuple) else (v, 1.0) for v in verifiers
        ]
        if not self.parts:
            raise ValidationError("CompositeVerifier needs at least one verifier")
        self.require_all = require_all

    def verify(self, output: Any, contract: Contract, task: Task) -> VerificationResult:
        results = [(v.verify(output, contract, task), w) for v, w in self.parts]
        total = sum(w for _, w in results)
        quality = sum(r.quality_score * w for r, w in results) / total
        flags = [r.passed for r, _ in results]
        passed = all(flags) if self.require_all else any(flags)
        checks = tuple(
            CheckResult(f"{r.verifier}.{c.name}", c.passed, c.score, c.detail, c.required)
            for r, _ in results
            for c in r.checks
        )
        return VerificationResult(
            passed, quality, checks, self.name, sum(r.cost for r, _ in results)
        )


def _lookup(output: Any, key: str | None) -> Any:
    if key is None:
        return output
    current = output
    for part in key.split("."):
        if isinstance(current, Mapping) and part in current:
            current = current[part]
        else:
            return None
    return current


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)
