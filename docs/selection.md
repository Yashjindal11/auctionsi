---
description: >-
  Winner selection policies in AuctionSI: lowest price, quality, latency, weighted
  score, risk-adjusted and reputation-adjusted cost, exploration bonus, with
  explainable score contributions.
---

# Winner selection

A `SelectionPolicy` scores every valid bid (higher is better). Each score is the
sum of named `contributions`, shown by `AuctionResult.explain()` and stored in the
`WinnerSelected` event. Ties: lower price, then earlier bid, then agent id.

| policy | score |
|---|---|
| `LowestPrice` | `-price` |
| `HighestQuality(quality_source)` | quality |
| `LowestLatency` | `-estimated_latency` (deadline if missing) |
| `WeightedScore(price_weight, quality_weight, latency_weight, reputation_weight)` | weighted sum of normalised terms |
| `RiskAdjustedCost(failure_cost, verification_cost, latency_penalty, ...)` | `-effective_cost` |
| `ReputationAdjustedCost(floor, include_quality)` | `-price / max(floor, success_estimate)` |
| `CallablePolicy(name, fn)` | your function (not replayable from a spec) |

## Not trusting claimed quality

`quality_source` decides where quality comes from:
- `estimate`: the bid's claim;
- `reputation`: the agent's observed average quality;
- `calibrated` (default): the claim minus the agent's historical over-promise.
Missing history falls back to the claim; the source used is shown in `details`.

## Weighted score

Price and latency are min-max normalised *within the auction* (1 = best). Quality is
absolute. Reputation is `success_estimate` (0.5 when unknown). Because of the
within-auction normalisation, scores are relative: adding a bid can change how two
others compare.

## Risk-adjusted cost

```
effective_cost = price + verification_cost + p_fail * failure_cost + latency_penalty * latency
```

`p_fail` = `1 - success_estimate` from reputation once the agent has
`min_observations` outcomes; before that `newcomer_failure_probability`, else
`1 - confidence` from the bid, else 0. `failure_cost` defaults to the task budget.
Example: A bids 0.02 with 20% failure, B bids 0.04 with 2%; with `failure_cost=0.2`,
A costs 0.06 and B 0.044, so B wins.
