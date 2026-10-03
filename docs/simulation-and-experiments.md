# Simulation, experiments and metrics

## Simulating a market

```python
from auctionsi.simulation import simulate_market
from auctionsi.mechanisms import SecondPriceReverseAuction

result = simulate_market(agents=100, tasks=1000, seed=42, mechanism=SecondPriceReverseAuction())
print(result.metrics.scalars())
```

Integers generate agents and tasks with `generate_agents` / `generate_tasks` using
seeds derived from `seed` (SHA-256 based, independent of `PYTHONHASHSEED`). The same
seed, inputs and AuctionSI version give the same records; only wall-clock
`performance()` numbers vary.

`SimulatedAgent` has hidden ground truth: per-capability quality, reliability,
latency (log-normal around `latency_mean * complexity`) and a `CostModel`. It prices
with a `BidStrategy` and can misreport quality/latency via report biases. Tasks
arrive as a Poisson process; agents are busy for their realised latency and have
limited capacity. `MarketChange` events (`agent_joins`, `agent_leaves`,
`agent_changes`) model entry, exit and changing agents.

Generator options include `capability_distribution` (`mixed`, `specialist`,
`generalist`), `cost_distribution`, `quality_distribution`, `latency_distribution`,
`reliability_distribution`, `capacity_distribution` (preset names, numbers, or
`{name: lognormal, median: .., sigma: ..}` style specs) and `strategy`.

## Adversarial participants

`auctionsi.simulation.adversarial`: `form_ring` (bid-rotation collusion with cover
bids), `make_sybils` (extra identities with one operator), `overstate_quality`,
`add_fake_capability`, `exit_scam` (reputation built then abandoned),
`operator_hhi`, `price_inflation`. Defence example:
`BidValidationConfig(max_bids_per_operator=1)`.

## Metrics (per run)

- `completion_rate` = successful tasks / tasks.
- `total_cost` = sum of buyer cost (payments + bonuses − penalties), failed attempts included.
- `average_cost`, `median_cost` = buyer cost per successful task.
- `average_quality` = mean verified quality of successful tasks.
- `average_latency` = mean total execution time over awarded tasks.
- `hhi` = Σ share² of successful wins (0-1 scale); `top_agent_share`.
- `revenue_gini` = Gini of revenue across *all* agents, zeros included.
- `buyer_utility` = Σ value of successful tasks − total_cost.
- `agent_utility` = Σ agent revenue − Σ agent execution cost.
- `total_surplus` = buyer_utility + agent_utility.
- `cost_efficiency` = mean of (cheapest true expected cost among eligible agents) /
  (awarded agent's true expected cost). It deliberately ignores quality and
  reliability; it is *one* notion of allocation efficiency, not "the" efficiency.
- `quality_adjusted_cost` = total_cost / Σ quality.
- `participation_rate`, `opportunity_rate` = share of agents that bid / won at least once.

## Experiments

An experiment is a YAML file (see `research/experiments/`). Each replication `r`
derives one seed shared by all arms (common random numbers), so arms with the same
environment see identical agents and tasks. Results: per-arm summaries (mean,
median, SD, variance, quantiles, t-interval), paired t-tests of each arm against the
baseline with Cohen's d_z and Holm adjustment across all comparisons in the
report. `ExperimentResult.save(dir)` writes `manifest.json` (seed, config, AuctionSI
and Python versions, dependency versions, git commit), `results.json` and `report.md`.

```bash
auctionsi experiment run research/experiments/mechanisms.yaml --out results/mechanisms
```
