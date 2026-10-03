"""Example 3: an optimisation marketplace.

Solvers bid to schedule jobs on identical machines (minimise makespan). The
verifier checks the constraints (every job assigned exactly once, valid machine
ids) and scores quality as ``lower_bound / makespan`` (1.0 = provably optimal).

Run: python examples/optimization_market.py
"""

from __future__ import annotations

import itertools
import random
from typing import Any

from auctionsi import Marketplace, PythonFunctionAgent, Task, WeightedScore
from auctionsi.core import Contract
from auctionsi.verification import CheckResult, VerificationResult, Verifier

JOBS = [7, 5, 4, 4, 3, 3, 2, 2, 1]
MACHINES = 3


def makespan(assignment: list[int]) -> int:
    loads = [0] * MACHINES
    for job, machine in enumerate(assignment):
        loads[machine] += JOBS[job]
    return max(loads)


def lpt(task: Task, contract: Contract) -> dict[str, Any]:
    """Longest processing time first: fast, usually near-optimal."""
    loads = [0] * MACHINES
    assignment = [0] * len(JOBS)
    for job in sorted(range(len(JOBS)), key=lambda j: -JOBS[j]):
        machine = loads.index(min(loads))
        assignment[job] = machine
        loads[machine] += JOBS[job]
    return {"assignment": assignment}


def random_solver(task: Task, contract: Contract) -> dict[str, Any]:
    rng = random.Random(1)
    return {"assignment": [rng.randrange(MACHINES) for _ in JOBS]}


def exhaustive(task: Task, contract: Contract) -> dict[str, Any]:
    best = min(
        itertools.product(range(MACHINES), repeat=len(JOBS)), key=lambda a: makespan(list(a))
    )
    return {"assignment": list(best)}


class ScheduleVerifier(Verifier):
    name = "schedule"

    def verify(self, output: Any, contract: Contract, task: Task) -> VerificationResult:
        assignment = output.get("assignment") if isinstance(output, dict) else None
        valid = (
            isinstance(assignment, list)
            and len(assignment) == len(JOBS)
            and all(isinstance(m, int) and 0 <= m < MACHINES for m in assignment)
        )
        if not valid:
            return VerificationResult.from_checks(
                [CheckResult("feasible", False, 0.0, "invalid assignment")], self.name
            )
        assert isinstance(assignment, list)
        lower_bound = max(max(JOBS), -(-sum(JOBS) // MACHINES))
        quality = lower_bound / makespan(assignment)
        return VerificationResult.from_checks(
            [
                CheckResult("feasible", True, 1.0, "every job assigned once"),
                CheckResult(
                    "objective",
                    True,
                    quality,
                    f"makespan {makespan(assignment)}, bound {lower_bound}",
                ),
            ],
            self.name,
            weights=[0.0, 1.0],
        )


def main() -> None:
    market = Marketplace(
        "optimisation",
        verifier=ScheduleVerifier(),
        policy=WeightedScore(price_weight=0.3, quality_weight=0.6, latency_weight=0.1),
    )
    for agent_id, fn, price, latency, quality in [
        ("lpt", lpt, 0.03, 0.1, 0.95),
        ("random", random_solver, 0.01, 0.05, 0.6),
        ("exact", exhaustive, 0.09, 5.0, 1.0),
    ]:
        market.register(
            PythonFunctionAgent(
                agent_id,
                fn,
                capabilities=["optimization"],
                price=price,
                estimated_latency=latency,
                estimated_quality=quality,
            )
        )
    task = Task(
        task_id="schedule-001",
        task_type="optimization",
        description=f"Schedule {len(JOBS)} jobs on {MACHINES} machines",
        budget=0.10,
        min_quality=0.9,
    )
    result = market.submit_task(task)
    print(result.explain())


if __name__ == "__main__":
    main()
