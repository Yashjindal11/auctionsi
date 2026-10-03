# Experiment report: reputation_decay

The follow-up to the reputation experiment. Ten agents start reliable (reliability 0.98) and drop to 0.3 when task 200 of 600 arrives. Risk-adjusted selection uses full-history or decaying reputation.


## Hypothesis

Decaying reputation notices the drop sooner, so it raises completion rate over full history once agents change.


## Experimental setup

- Replications: 30 per arm (common random numbers across arms)
- Seed: 29
- AuctionSI 0.1.1, Python 3.12.15, git commit 0162c05e54894a8575355e5fb4d3f5d47dd18a08+dirty
- Baseline arm: `full_history`
- Confidence level: 95%; alpha: 0.05

### Parameters

- Agents: {'count': 30, 'capabilities': ['research', 'data_analysis', 'sql', 'optimization'], 'capability_distribution': 'mixed', 'capabilities_per_agent': (1, 3), 'cost_distribution': 'lognormal', 'variable_cost_ratio': 0.01, 'quality_distribution': 'beta', 'quality_spread': 0.05, 'latency_distribution': 'lognormal', 'reliability_distribution': {'name': 'uniform', 'low': 0.85, 'high': 1.0}, 'capacity_distribution': 1, 'strategy': 'cost_plus', 'quality_report_bias': 0.0}
- Tasks: {'count': 600, 'task_types': ['research', 'data_analysis', 'sql', 'optimization'], 'arrival_rate': 1.0, 'budget_distribution': 'lognormal', 'deadline_distribution': 'uniform', 'complexity_distribution': 'lognormal', 'min_quality': None, 'value_multiplier': 1.5}
- Defaults: mechanism=first_price_reverse, policy={'name': 'risk_adjusted_cost', 'newcomer_failure_probability': 0.2, 'min_observations': 3}, reputation=multi_dimensional, settlement=pay_on_pass

### Arms

- `full_history`: {'reputation': {'name': 'multi_dimensional'}}
- `decay_half_life_20`: {'reputation': {'name': 'multi_dimensional', 'decay': {'name': 'exponential', 'half_life': 20}}}
- `decay_half_life_5`: {'reputation': {'name': 'multi_dimensional', 'decay': {'name': 'exponential', 'half_life': 5}}}

## Results

### completion_rate

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| full_history | 30 | 0.8411 | [0.8285, 0.8536] | 0.03361 | 0.8475 |
| decay_half_life_20 | 30 | 0.8486 | [0.8368, 0.8603] | 0.0314 | 0.8542 |
| decay_half_life_5 | 30 | 0.8629 | [0.853, 0.8729] | 0.02667 | 0.8642 |

### average_cost

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| full_history | 30 | 0.03208 | [0.03085, 0.03331] | 0.003284 | 0.03161 |
| decay_half_life_20 | 30 | 0.03228 | [0.03107, 0.03349] | 0.003245 | 0.03159 |
| decay_half_life_5 | 30 | 0.03294 | [0.03177, 0.03411] | 0.003131 | 0.03222 |

### buyer_utility

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| full_history | 30 | 79.52 | [77.93, 81.11] | 4.257 | 79.77 |
| decay_half_life_20 | 30 | 80.13 | [78.61, 81.64] | 4.046 | 80.01 |
| decay_half_life_5 | 30 | 81.16 | [79.86, 82.46] | 3.48 | 81.67 |

### hhi

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| full_history | 30 | 0.07041 | [0.06649, 0.07433] | 0.01049 | 0.07089 |
| decay_half_life_20 | 30 | 0.06958 | [0.06589, 0.07327] | 0.009893 | 0.06962 |
| decay_half_life_5 | 30 | 0.06711 | [0.06351, 0.0707] | 0.009628 | 0.06731 |

## Statistical tests

Paired t-tests on per-replication differences (treatment - baseline). Effect size is Cohen's d_z.

| metric | treatment | mean diff | CI | relative | d_z | p | p (Holm) |
|---|---|---|---|---|---|---|---|
| completion_rate | decay_half_life_20 | 0.0075 | [0.005527, 0.009473] | +0.9% | 1.42 | 1.42e-08 | 8.54e-08 |
| average_cost | decay_half_life_20 | 0.0001994 | [9.284e-05, 0.0003059] | +0.6% | 0.699 | 0.000637 | 0.00127 |
| buyer_utility | decay_half_life_20 | 0.6019 | [0.3572, 0.8467] | +0.8% | 0.918 | 2.34e-05 | 7.01e-05 |
| hhi | decay_half_life_20 | -0.0008284 | [-0.001407, -0.0002502] | -1.2% | -0.535 | 0.00654 | 0.00654 |
| completion_rate | decay_half_life_5 | 0.02189 | [0.01722, 0.02656] | +2.6% | 1.75 | 1.69e-10 | 1.35e-09 |
| average_cost | decay_half_life_5 | 0.0008577 | [0.0006716, 0.001044] | +2.7% | 1.72 | 2.49e-10 | 1.75e-09 |
| buyer_utility | decay_half_life_5 | 1.633 | [1.114, 2.152] | +2.1% | 1.17 | 4.88e-07 | 2.44e-06 |
| hhi | decay_half_life_5 | -0.003301 | [-0.004452, -0.00215] | -4.7% | -1.07 | 2.31e-06 | 9.25e-06 |

## Limitations

- One abrupt change at a fixed time; gradual drift is not tested.
- Results come from a synthetic market; agent costs, quality and reliability are drawn from the configured distributions, not measured from real agents.
- Agents follow fixed (or simple adaptive) bidding strategies; real strategic agents may respond to the mechanism differently.
- A non-significant difference is not evidence of equivalence.
- P-values are Holm-adjusted across the comparisons in this report only.

## Conclusion

- In this simulated environment, `decay_half_life_20` produced higher `completion_rate` than `full_history` (mean difference 0.0075, 95% CI [0.005527, 0.009473]).
- In this simulated environment, `decay_half_life_20` produced higher `average_cost` than `full_history` (mean difference 0.0001994, 95% CI [9.284e-05, 0.0003059]).
- In this simulated environment, `decay_half_life_20` produced higher `buyer_utility` than `full_history` (mean difference 0.6019, 95% CI [0.3572, 0.8467]).
- In this simulated environment, `decay_half_life_20` produced lower `hhi` than `full_history` (mean difference -0.0008284, 95% CI [-0.001407, -0.0002502]).
- In this simulated environment, `decay_half_life_5` produced higher `completion_rate` than `full_history` (mean difference 0.02189, 95% CI [0.01722, 0.02656]).
- In this simulated environment, `decay_half_life_5` produced higher `average_cost` than `full_history` (mean difference 0.0008577, 95% CI [0.0006716, 0.001044]).
- In this simulated environment, `decay_half_life_5` produced higher `buyer_utility` than `full_history` (mean difference 1.633, 95% CI [1.114, 2.152]).
- In this simulated environment, `decay_half_life_5` produced lower `hhi` than `full_history` (mean difference -0.003301, 95% CI [-0.004452, -0.00215]).
