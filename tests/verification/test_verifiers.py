from __future__ import annotations

import pytest

from auctionsi.core import Contract, Task
from auctionsi.errors import ValidationError
from auctionsi.verification import (
    AcceptVerifier,
    CallableVerifier,
    CheckResult,
    CompositeVerifier,
    ExactMatchVerifier,
    HumanApprovalVerifier,
    MetricThresholdVerifier,
    SchemaVerifier,
    ToleranceVerifier,
    UnitTestVerifier,
    VerificationResult,
)
from auctionsi.verification.schema import validate

TASK = Task(
    task_id="t",
    task_type="analysis",
    expected_output_schema={
        "type": "object",
        "required": ["mean", "rows"],
        "properties": {"mean": {"type": "number"}, "rows": {"type": "integer", "minimum": 1}},
        "additionalProperties": False,
    },
)
CONTRACT = Contract(
    contract_id="c",
    auction_id="x",
    task_id="t",
    agent_id="a",
    bid_id="b",
    agreed_price=1,
    payment_price=1,
    unit="credits",
    created_at=0,
)


def test_schema_subset() -> None:
    schema = {
        "type": "object",
        "required": ["items"],
        "properties": {
            "items": {"type": "array", "items": {"type": "string", "enum": ["a", "b"]}},
            "n": {"type": ["integer", "null"], "maximum": 3},
            "name": {"type": "string", "minLength": 2},
        },
    }
    assert validate({"items": ["a", "b"], "n": None}, schema) == []
    errors = validate({"items": ["a", "z"], "n": 5, "name": "x"}, schema)
    assert len(errors) == 3
    assert validate(True, {"type": "integer"})  # bools are not integers
    assert "unsupported" in validate({}, {"pattern": "x"})[0]


def test_schema_verifier_uses_task_schema() -> None:
    verifier = SchemaVerifier()
    good = verifier.verify({"mean": 1.5, "rows": 10}, CONTRACT, TASK)
    assert good.passed
    assert good.quality_score == 1.0
    bad = verifier.verify({"mean": "x", "rows": 0, "extra": 1}, CONTRACT, TASK)
    assert not bad.passed
    assert "unexpected property" in bad.checks[0].detail
    no_schema = SchemaVerifier().verify({}, CONTRACT, Task(task_id="t", task_type="x"))
    assert not no_schema.passed


def test_exact_tolerance_and_metric_verifiers() -> None:
    assert ExactMatchVerifier(42, key="answer").verify({"answer": 42}, CONTRACT, TASK).passed
    assert not ExactMatchVerifier(42).verify(41, CONTRACT, TASK).passed
    assert ToleranceVerifier(1.0, rel_tol=0.01).verify(1.005, CONTRACT, TASK).passed
    assert not ToleranceVerifier(1.0).verify("1.0", CONTRACT, TASK).passed
    metric = MetricThresholdVerifier("scores.f1", 0.8, as_quality=True)
    result = metric.verify({"scores": {"f1": 0.9}}, CONTRACT, TASK)
    assert result.passed
    assert result.quality_score == pytest.approx(0.9)
    assert not metric.verify({"scores": {}}, CONTRACT, TASK).passed
    lower = MetricThresholdVerifier("loss", 0.1, higher_is_better=False)
    assert lower.verify({"loss": 0.05}, CONTRACT, TASK).passed


def test_unit_tests_quality_is_fraction_passed() -> None:
    def explode(output: object) -> bool:
        raise RuntimeError("bad")

    verifier = UnitTestVerifier(
        {"is_list": lambda o: isinstance(o, list), "len3": lambda o: len(o) == 3, "x": explode}
    )
    result = verifier.verify([1, 2], CONTRACT, TASK)
    assert result.quality_score == pytest.approx(1 / 3)
    assert not result.passed
    assert "RuntimeError" in result.checks[2].detail
    with pytest.raises(ValidationError):
        UnitTestVerifier({})


def test_composite_and_human_and_callable() -> None:
    composite = CompositeVerifier(
        [(SchemaVerifier(), 3.0), (MetricThresholdVerifier("mean", 2.0), 1.0)]
    )
    result = composite.verify({"mean": 1.5, "rows": 1}, CONTRACT, TASK)
    assert not result.passed
    assert result.quality_score == pytest.approx(0.75)
    assert {c.name for c in result.checks} == {"schema.schema", "metric_threshold.mean"}
    lenient = CompositeVerifier([SchemaVerifier(), ExactMatchVerifier(0)], require_all=False)
    assert lenient.verify({"mean": 1.5, "rows": 1}, CONTRACT, TASK).passed

    human = HumanApprovalVerifier(ask=lambda prompt: "yes 0.7")
    approved = human.verify("text", CONTRACT, TASK)
    assert approved.passed
    assert approved.quality_score == pytest.approx(0.7)
    assert not HumanApprovalVerifier(ask=lambda prompt: "no").verify("t", CONTRACT, TASK).passed

    custom = CallableVerifier(
        lambda o, c, t: VerificationResult.from_checks([CheckResult("x", True, 0.5)], "mine")
    )
    assert custom.verify(None, CONTRACT, TASK).quality_score == 0.5
    assert AcceptVerifier().verify(None, CONTRACT, TASK).checks[0].name == "accepted_unchecked"


def test_from_checks_rules() -> None:
    checks = [CheckResult("a", True, 1.0), CheckResult("b", False, 0.0, required=False)]
    result = VerificationResult.from_checks(checks, "v", weights=[3, 1])
    assert result.passed
    assert result.quality_score == pytest.approx(0.75)
    gated = result.with_check(CheckResult("min_quality", False, 0.0))
    assert not gated.passed
    assert gated.quality_score == result.quality_score
    assert not VerificationResult.from_checks([], "v").passed
