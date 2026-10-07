---
description: >-
  Simulate agent markets and run reproducible experiments in AuctionSI: synthetic
  agents and tasks, bidding strategies, learning bidders, collusion and Sybil
  attacks, market metrics, factorial sweeps and statistical reports.
---

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

## Learning bidders

`BanditMarkup` (strategy name `bandit`) learns a markup over cost from a fixed grid
with UCB1 (`algorithm: ucb1`) or epsilon-greedy (`algorithm: epsilon_greedy`). The
reward for a won task is realised profit relative to cost; a loss is reward 0. It
does not observe rivals' bids.

## Adversarial participants

`auctionsi.simulation.adversarial`: `form_ring` (bid-rotation collusion with cover
bids), `make_sybils` (extra identities with one operator), `overstate_quality`,
`add_fake_capability`, `exit_scam` (reputation built then abandoned),
`operator_hhi`, `price_inflation`. Defence example:
`BidValidationConfig(max_bids_per_operator=1)`.

In experiment configs the same tools are declarative:

```yaml
environment:
  adversaries: {colluders: 5, winner_markup: 0.6, cover_markup: 1.2, sybil_copies: 2, overstaters: 3}
  changes:
    - {at_task: 200, agents: 10, set: {reliability: 0.3}}   # or at: <sim seconds>
    - {at: 500, agents: [agent-0003], leave: true}
```

Changeable attributes: `reliability`, `available`, `quality`, `latency_mean`,
`quality_report_bias`, `latency_report_bias`.

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
- `average_winning_markup` = mean of (awarded bid price / true expected cost − 1).
- `total_verification_cost`; `buyer_utility` subtracts it.
- `bid_cv` = mean coefficient of variation of valid bids per auction; `relative_distance`
  = mean (second-lowest − lowest) / SD of the losing bids. Both use auctions with at
  least 3 bids; they are collusion screens from the procurement literature, hints
  rather than proof.

## Calibration

`auctionsi calibration [--agent ID] [--json]` (and `/api/calibration`) compares each
agent's claimed quality and latency with what it delivered, plus reliability bins
(claimed confidence vs observed success). Only delivered work counts towards
quality and latency calibration.

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

`factors` crosses every level of each factor into arms (and with explicit arms, if
any). Keys are `mechanism`, `policy`, `reputation`, `settlement` or
`environment.<path>`:

```yaml
factors:
  mechanism: [first_price_reverse, second_price_reverse]
  policy: [lowest_price, risk_adjusted_cost]
  environment.agents.count: [20, 100]
```
