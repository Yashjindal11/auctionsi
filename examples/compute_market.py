"""Example 5: a compute marketplace.

Providers advertise capacity limits as capability constraints (``max_cpu``,
``max_memory_gb``); discovery excludes providers that cannot fit a request.
A job that needs two replicas uses a multi-winner auction with uniform pricing.

Run: python examples/compute_market.py
"""

from __future__ import annotations

from typing import Any

from auctionsi import (
    Capability,
    Marketplace,
    MultiWinnerReverseAuction,
    PythonFunctionAgent,
    Task,
)
from auctionsi.core import Contract
from auctionsi.verification import UnitTestVerifier

PROVIDERS = [
    # id, max cpu, max memory, price per cpu-hour
    ("small-box", 4, 16, 0.020),
    ("big-box", 64, 256, 0.025),
    ("spot-pool", 32, 128, 0.012),
    ("gpu-node", 16, 512, 0.050),
]


def provider(agent_id: str, max_cpu: int, max_mem: int, rate: float) -> PythonFunctionAgent:
    def run(task: Task, contract: Contract) -> dict[str, Any]:
        req = task.requirements
        return {"cpu": req["cpu"], "memory_gb": req["memory_gb"], "hours": req["hours"]}

    def price(task: Task) -> float:
        req = task.requirements
        return round(rate * req["cpu"] * req["hours"], 6)

    return PythonFunctionAgent(
        agent_id,
        run,
        capabilities=[
            Capability("compute", constraints={"max_cpu": max_cpu, "max_memory_gb": max_mem})
        ],
        price=price,
    )


def main() -> None:
    requested = {"cpu": 16, "memory_gb": 64, "hours": 2}
    verifier = UnitTestVerifier(
        {name: (lambda o, n=name: o[n] >= requested[n]) for name in requested}
    )
    market = Marketplace(
        "compute",
        mechanism=MultiWinnerReverseAuction(winners=2, pricing="uniform"),
        verifier=verifier,
    )
    for agent_id, cpu, mem, rate in PROVIDERS:
        market.register(provider(agent_id, cpu, mem, rate))
    task = Task(
        task_id="job-001",
        task_type="compute",
        description="Two replicas of a 16-CPU batch job",
        requirements=requested,
        budget=2.0,
        unit="compute_credits",
    )
    result = market.submit_task(task)
    print("Excluded:", {k: v[0] for k, v in result.auction.excluded.items()})
    print(result.explain())


if __name__ == "__main__":
    main()
