"""Example 2: a SQL marketplace with deterministic verification.

Agents bid to write a query. The verifier runs each submitted query against a
throw-away SQLite test database with an authorizer that only permits reads,
and compares the rows to the expected answer. A malicious "agent" that tries to
drop a table is stopped by the authorizer and fails verification.

Run: python examples/sql_market.py
"""

from __future__ import annotations

import sqlite3
from typing import Any

from auctionsi import (
    Marketplace,
    PythonFunctionAgent,
    RecoveryPolicy,
    Task,
    WeightedScore,
)
from auctionsi.core import Contract
from auctionsi.verification import CheckResult, VerificationResult, Verifier

SEED_SQL = """
CREATE TABLE orders (id INTEGER PRIMARY KEY, customer TEXT, amount REAL);
INSERT INTO orders (customer, amount) VALUES
  ('ada', 120.0), ('ada', 80.0), ('bob', 45.5), ('cy', 300.0), ('bob', 10.0);
"""
EXPECTED = [("ada", 200.0), ("bob", 55.5), ("cy", 300.0)]


def test_database() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(SEED_SQL)

    def read_only(action: int, *args: Any) -> int:
        allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}
        return sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY

    conn.set_authorizer(read_only)
    return conn


class SQLResultVerifier(Verifier):
    name = "sql_result"

    def verify(self, output: Any, contract: Contract, task: Task) -> VerificationResult:
        query = output.get("sql") if isinstance(output, dict) else None
        if not isinstance(query, str):
            return VerificationResult.from_checks(
                [CheckResult("sql", False, 0.0, "no sql")], self.name
            )
        conn = test_database()
        try:
            rows = conn.execute(query).fetchall()
        except sqlite3.Error as exc:
            check = CheckResult("executes", False, 0.0, f"{type(exc).__name__}: {exc}")
            return VerificationResult.from_checks([check], self.name)
        finally:
            conn.close()
        ok = sorted(rows) == sorted(EXPECTED)
        checks = [
            CheckResult("executes", True, 1.0),
            CheckResult("rows_match", ok, 1.0 if ok else 0.0, f"{len(rows)} rows"),
        ]
        return VerificationResult.from_checks(checks, self.name)


def writer(sql: str) -> Any:
    return lambda task, contract: {"sql": sql}


def main() -> None:
    market = Marketplace(
        "sql",
        verifier=SQLResultVerifier(),
        policy=WeightedScore(price_weight=0.5, quality_weight=0.5, latency_weight=0.0),
        recovery=RecoveryPolicy(next_best=2),
    )
    agents = [
        ("vandal", "DROP TABLE orders", 0.01, 0.99),
        ("forgetful", "SELECT customer, SUM(amount) FROM orders", 0.02, 0.9),
        (
            "solid",
            "SELECT customer, SUM(amount) FROM orders GROUP BY customer ORDER BY customer",
            0.05,
            0.95,
        ),
    ]
    for agent_id, sql, price, claimed_quality in agents:
        market.register(
            PythonFunctionAgent(
                agent_id,
                writer(sql),
                capabilities=["sql_generation"],
                price=price,
                estimated_quality=claimed_quality,
            )
        )
    task = Task(
        task_id="sql-001",
        task_type="sql_generation",
        description="Total order amount per customer",
        budget=0.10,
    )
    result = market.submit_task(task)
    for outcome in result.contracts:
        failed = [c for c in outcome.verification.checks if not c.passed]
        verdict = "passed" if outcome.passed else f"failed: {failed[0].detail}"
        print(f"{outcome.contract.agent_id:<10} {verdict}")
    print(f"\nWinner: {result.winner}, buyer cost {result.buyer_cost:.2f}")
    profile = market.reputation.profile("vandal")
    assert profile is not None
    print(f"vandal reputation: success rate {profile.success_rate:.0%}")


if __name__ == "__main__":
    main()
