"""Example 1: a data-analysis marketplace.

Three agents compete to summarise a dataset. The cheapest one is sloppy; the
verifier recomputes the statistics deterministically, rejects its work, and the
recovery policy fails over to the next-best bid.

Run: python examples/data_analysis_market.py
"""

from __future__ import annotations

import statistics

from auctionsi import (
    Marketplace,
    PythonFunctionAgent,
    RecoveryPolicy,
    Task,
)
from auctionsi.verification import CompositeVerifier, SchemaVerifier, UnitTestVerifier

DATASET = [12.0, 15.5, 9.25, 22.0, 18.75, 11.0, 16.5, 14.0]
SCHEMA = {
    "type": "object",
    "required": ["count", "mean", "median", "stdev"],
    "properties": {
        "count": {"type": "integer", "minimum": 0},
        "mean": {"type": "number"},
        "median": {"type": "number"},
        "stdev": {"type": "number", "minimum": 0},
    },
}


def careful(task: Task, contract: object) -> dict[str, float]:
    return {
        "count": len(DATASET),
        "mean": statistics.fmean(DATASET),
        "median": statistics.median(DATASET),
        "stdev": statistics.stdev(DATASET),
    }


def sloppy(task: Task, contract: object) -> dict[str, float]:
    # Off-by-one: drops the last row.
    rows = DATASET[:-1]
    return {
        "count": len(rows),
        "mean": statistics.fmean(rows),
        "median": statistics.median(rows),
        "stdev": statistics.stdev(rows),
    }


def close(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-9 * max(1.0, abs(b))


def main() -> None:
    truth = careful(None, None)  # type: ignore[arg-type]
    verifier = CompositeVerifier(
        [
            SchemaVerifier(SCHEMA),
            UnitTestVerifier(
                {
                    "count": lambda o: o["count"] == truth["count"],
                    "mean": lambda o: close(o["mean"], truth["mean"]),
                    "median": lambda o: close(o["median"], truth["median"]),
                    "stdev": lambda o: close(o["stdev"], truth["stdev"]),
                }
            ),
        ]
    )
    market = Marketplace(
        "data-analysis",
        verifier=verifier,
        recovery=RecoveryPolicy(next_best=1),
    )
    market.register(
        PythonFunctionAgent("agent-a", careful, capabilities=["data_analysis"], price=0.04)
    )
    market.register(
        PythonFunctionAgent("agent-b", sloppy, capabilities=["data_analysis"], price=0.02)
    )
    market.register(
        PythonFunctionAgent("agent-c", careful, capabilities=["data_analysis"], price=0.06)
    )

    task = Task(
        task_id="analyse-001",
        task_type="data_analysis",
        description="Summarise the provided dataset",
        requirements={"input_format": "parquet", "output_format": "json"},
        budget=0.10,
        input_reference="memory://DATASET",
        expected_output_schema=SCHEMA,
    )
    result = market.submit_task(task)
    print(result.explain())
    print()
    print("\n".join(result.trace()))
    print(f"\nDelivered by {result.winner}; buyer paid {result.buyer_cost:.2f} credits")


if __name__ == "__main__":
    main()
