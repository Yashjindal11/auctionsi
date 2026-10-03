from __future__ import annotations

import math

import pytest

from auctionsi.core import (
    Agent,
    Bid,
    BidContext,
    BidProposal,
    Capability,
    Contract,
    ContractStatus,
    CostModel,
    ExecutionResult,
    Task,
)
from auctionsi.errors import InvalidTransitionError, ValidationError


class EchoAgent(Agent):
    def bid(self, task: Task, context: BidContext) -> BidProposal | None:
        return BidProposal(price=1.0)

    def execute(self, task: Task, contract: Contract) -> ExecutionResult:
        return ExecutionResult(success=True, output={"ok": True})


def test_task_reads_spec_style_constraints() -> None:
    task = Task(
        task_id="task-001",
        task_type="data_analysis",
        requirements={"input_format": "parquet"},
        constraints={"max_cost": 0.10, "max_latency": 30, "min_quality": 0.9},
    )
    assert task.budget == 0.10
    assert task.deadline == 30
    assert task.min_quality == 0.9


def test_task_explicit_fields_win_over_constraints() -> None:
    task = Task(task_id="t", task_type="x", budget=1.0, constraints={"max_cost": 5})
    assert task.budget == 1.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"task_id": "../etc/passwd"},
        {"task_id": ""},
        {"task_type": "has space"},
        {"budget": -1},
        {"budget": math.nan},
        {"deadline": math.inf},
        {"min_quality": 1.5},
        {"priority": 1.5},
        {"requirements": {"x": object()}},
        {"requirements": {1: "a"}},
        {"description": "x" * 20_000},
        {"requirements": {"blob": "x" * 70_000}},
    ],
)
def test_task_rejects_bad_input(kwargs: dict[str, object]) -> None:
    base: dict[str, object] = {"task_id": "t-1", "task_type": "research"}
    base.update(kwargs)
    with pytest.raises(ValidationError):
        Task(**base)  # type: ignore[arg-type]


def test_task_round_trips_and_rejects_unknown_fields() -> None:
    task = Task(task_id="t-1", task_type="sql", budget=2.0, metadata={"a": 1})
    assert Task.from_dict(task.to_dict()) == task
    with pytest.raises(ValidationError):
        Task.from_dict({"task_id": "t", "task_type": "x", "evil": True})


def test_capability_matching_rules() -> None:
    cap = Capability(
        name="sql_analysis",
        input_formats=("parquet", "csv"),
        output_formats=("json",),
        constraints={"max_rows": 1000, "min_rows": 10, "note": "informational"},
    )
    ok = Task(task_id="a", task_type="sql_analysis", requirements={"rows": 500})
    assert cap.incompatibilities(ok) == []
    wrong_type = Task(task_id="b", task_type="research")
    assert "does not match" in cap.incompatibilities(wrong_type)[0]
    too_big = Task(task_id="c", task_type="sql_analysis", requirements={"rows": 5000})
    assert "exceeds max_rows" in cap.incompatibilities(too_big)[0]
    too_small = Task(task_id="d", task_type="sql_analysis", requirements={"rows": 1})
    assert "below min_rows" in cap.incompatibilities(too_small)[0]
    bad_format = Task(
        task_id="e",
        task_type="sql_analysis",
        requirements={"input_format": "xlsx", "output_format": "xml"},
    )
    assert len(cap.incompatibilities(bad_format)) == 2


def test_capability_round_trip() -> None:
    cap = Capability(name="x", version="1.2", input_formats=("a",), constraints={"max_n": 3})
    assert Capability.from_dict(cap.to_dict()) == cap


def test_agent_accepts_strings_and_mappings_as_capabilities() -> None:
    agent = EchoAgent("a-1", capabilities=["research", {"name": "sql", "version": "2"}])
    assert [c.name for c in agent.capabilities] == ["research", "sql"]
    assert agent.capability("sql") is not None
    assert agent.capability("sql").version == "2"  # type: ignore[union-attr]
    assert agent.describe()["kind"] == "EchoAgent"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"capabilities": []},
        {"max_concurrent_tasks": 0},
        {"max_concurrent_tasks": True},
        {"metadata": {"x": object()}},
    ],
)
def test_agent_rejects_bad_metadata(kwargs: dict[str, object]) -> None:
    base: dict[str, object] = {"capabilities": ["research"]}
    base.update(kwargs)
    with pytest.raises(ValidationError):
        EchoAgent("a-1", **base)  # type: ignore[arg-type]


def test_cost_model() -> None:
    model = CostModel(fixed_cost=0.01, variable_cost_per_second=0.002, per_unit_costs={"tok": 1e-5})
    assert model.cost(10, {"tok": 1000}) == pytest.approx(0.01 + 0.02 + 0.01)
    with pytest.raises(ValidationError):
        CostModel(fixed_cost=-1)


def test_bid_validates_numbers() -> None:
    bid = Bid(bid_id="b", task_id="t", agent_id="a", auction_id="x", price=0.5)
    assert Bid.from_dict(bid.to_dict()) == bid
    with pytest.raises(ValidationError):
        Bid(bid_id="b", task_id="t", agent_id="a", auction_id="x", price=math.nan)
    with pytest.raises(ValidationError):
        Bid(bid_id="b", task_id="t", agent_id="a", auction_id="x", price="1")  # type: ignore[arg-type]


def _contract() -> Contract:
    return Contract(
        contract_id="c",
        auction_id="x",
        task_id="t",
        agent_id="a",
        bid_id="b",
        agreed_price=1.0,
        payment_price=1.0,
        unit="credits",
        created_at=0.0,
        deadline=10.0,
    )


def test_contract_happy_path_and_due_time() -> None:
    contract = _contract()
    assert contract.due_at == 10.0
    contract.start(1.0)
    contract.transition(ContractStatus.DELIVERED, 2.0)
    contract.transition(ContractStatus.FULFILLED, 3.0)
    assert [h[0] for h in contract.history] == ["executing", "delivered", "fulfilled"]


def test_contract_cannot_execute_after_cancellation() -> None:
    contract = _contract()
    contract.cancel(0.0)
    with pytest.raises(InvalidTransitionError):
        contract.start(1.0)


def test_contract_cannot_skip_execution() -> None:
    with pytest.raises(InvalidTransitionError):
        _contract().transition(ContractStatus.FULFILLED, 0.0)
