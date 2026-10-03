"""Example 4: a research marketplace with deterministic structure checks.

Research agents return structured reports. Without calling any model, the
verifier checks required sections, that every claim cites at least one source,
and that every cited source exists. (To use a real LLM, swap one agent for
``auctionsi.adapters.OpenAICompatibleAgent`` pointed at a local server; the
verifier stays the same.)

Run: python examples/research_market.py
"""

from __future__ import annotations

from typing import Any

from auctionsi import Marketplace, PythonFunctionAgent, RiskAdjustedCost, Task
from auctionsi.core import Contract
from auctionsi.verification import UnitTestVerifier

REQUIRED_SECTIONS = ("summary", "findings", "limitations")


def thorough(task: Task, contract: Contract) -> dict[str, Any]:
    return {
        "sections": {s: f"{s} text" for s in REQUIRED_SECTIONS},
        "claims": [
            {"text": "Second-price auctions pay the runner-up price.", "evidence": ["s1"]},
            {"text": "Collusion raises procurement prices.", "evidence": ["s2", "s3"]},
        ],
        "sources": {"s1": "Vickrey (1961)", "s2": "Survey A", "s3": "Survey B"},
    }


def hasty(task: Task, contract: Contract) -> dict[str, Any]:
    return {
        "sections": {"summary": "short"},
        "claims": [{"text": "Auctions are always efficient.", "evidence": []}],
        "sources": {},
    }


def has_sections(report: dict[str, Any]) -> bool:
    return all(report["sections"].get(s) for s in REQUIRED_SECTIONS)


def claims_cited(report: dict[str, Any]) -> bool:
    return bool(report["claims"]) and all(c["evidence"] for c in report["claims"])


def citations_resolve(report: dict[str, Any]) -> bool:
    return all(e in report["sources"] for c in report["claims"] for e in c["evidence"])


def main() -> None:
    market = Marketplace(
        "research",
        verifier=UnitTestVerifier(
            {
                "required_sections": has_sections,
                "every_claim_cited": claims_cited,
                "citations_resolve": citations_resolve,
            }
        ),
        policy=RiskAdjustedCost(failure_cost=0.3),
    )
    market.register(
        PythonFunctionAgent(
            "thorough", thorough, capabilities=["research"], price=0.06, confidence=0.95
        )
    )
    market.register(
        PythonFunctionAgent("hasty", hasty, capabilities=["research"], price=0.03, confidence=0.6)
    )
    for i in range(3):
        result = market.submit_task(
            Task(
                task_id=f"research-{i}",
                task_type="research",
                description="Auction design brief",
                budget=0.1,
            )
        )
        verdict = "passed" if result.succeeded else "failed"
        winner = result.contracts[0].contract.agent_id
        print(
            f"research-{i}: awarded to {winner:<8} -> {verdict}, quality {result.contracts[0].verification.quality_score:.2f}"
        )
    print()
    print(result.explain())


if __name__ == "__main__":
    main()
