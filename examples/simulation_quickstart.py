"""Example 6: simulated markets, strategies and a collusion experiment.

No real agents, no API keys: 40 synthetic agents and 400 tasks, first with
honest-ish cost-plus bidders, then with a quarter of them colluding.

Run: python examples/simulation_quickstart.py
"""

from __future__ import annotations

from auctionsi.simulation import derive_seed, generate_agents, generate_tasks, simulate_market
from auctionsi.simulation.adversarial import form_ring, price_inflation


def main() -> None:
    seed = 42
    agent_opts = {"capability_distribution": "generalist", "capabilities": ["analysis"]}
    task_opts = {"task_types": ["analysis"]}

    def population():  # type: ignore[no-untyped-def]
        agents = generate_agents(40, seed=derive_seed(seed, "agents"), **agent_opts)  # type: ignore[arg-type]
        tasks = generate_tasks(400, seed=derive_seed(seed, "tasks"), **task_opts)  # type: ignore[arg-type]
        return agents, tasks

    agents, tasks = population()
    baseline = simulate_market(agents, tasks, seed=seed)

    agents, tasks = population()
    form_ring(agents[:10])
    colluding = simulate_market(agents, tasks, seed=seed)

    for label, run in (("baseline", baseline), ("10 colluders", colluding)):
        m = run.metrics
        print(
            f"{label:<13} completion {m.completion_rate:.1%}  avg cost {m.average_cost:.4f}  "
            f"HHI {m.hhi:.3f}  buyer utility {m.buyer_utility:.2f}"
        )
    inflation = price_inflation(baseline.metrics, colluding.metrics)
    print(f"price inflation from collusion: {inflation:+.1%}")


if __name__ == "__main__":
    main()
