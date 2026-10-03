# Experiment report: strategies

Every agent in the market uses the same bidding strategy; arms change which one.


## Hypothesis

Aggressive (below-cost) bidding lowers buyer cost but produces negative agent utility; conservative and greedy bidding transfer surplus from buyer to agents; adaptive (profit-seeking) bidders settle between the two.


## Experimental setup

- Replications: 30 per arm (common random numbers across arms)
- Seed: 17
- AuctionSI 0.1.1, Python 3.12.15, git commit 0162c05e54894a8575355e5fb4d3f5d47dd18a08+dirty
- Baseline arm: `cost_plus`
- Confidence level: 95%; alpha: 0.05

### Parameters

- Agents: {'count': 30, 'capabilities': ['research', 'data_analysis', 'sql', 'optimization'], 'capability_distribution': 'mixed', 'capabilities_per_agent': (1, 3), 'cost_distribution': 'lognormal', 'variable_cost_ratio': 0.01, 'quality_distribution': 'beta', 'quality_spread': 0.05, 'latency_distribution': 'lognormal', 'reliability_distribution': 'beta', 'capacity_distribution': 1, 'strategy': 'cost_plus', 'quality_report_bias': 0.0}
- Tasks: {'count': 400, 'task_types': ['research', 'data_analysis', 'sql', 'optimization'], 'arrival_rate': 1.0, 'budget_distribution': 'lognormal', 'deadline_distribution': 'uniform', 'complexity_distribution': 'lognormal', 'min_quality': None, 'value_multiplier': 1.5}
- Defaults: mechanism=first_price_reverse, policy=lowest_price, reputation=multi_dimensional, settlement=pay_on_pass

### Arms

- `cost_plus`: {'environment': {'agents': {'strategy': 'cost_plus'}}}
- `aggressive`: {'environment': {'agents': {'strategy': 'aggressive'}}}
- `conservative`: {'environment': {'agents': {'strategy': 'conservative'}}}
- `greedy`: {'environment': {'agents': {'strategy': 'greedy'}}}
- `adaptive`: {'environment': {'agents': {'strategy': 'profit_maximizing'}}}

## Results

### average_cost

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| cost_plus | 30 | 0.02935 | [0.02836, 0.03035] | 0.002671 | 0.02949 |
| aggressive | 30 | 0.02324 | [0.02245, 0.02403] | 0.002114 | 0.02335 |
| conservative | 30 | 0.03901 | [0.03771, 0.0403] | 0.003468 | 0.03929 |
| greedy | 30 | 0.1196 | [0.119, 0.1203] | 0.00173 | 0.1196 |
| adaptive | 30 | 0.02825 | [0.0274, 0.0291] | 0.002285 | 0.02865 |

### buyer_utility

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| cost_plus | 30 | 57.24 | [56.28, 58.19] | 2.553 | 56.86 |
| aggressive | 30 | 59.43 | [58.49, 60.37] | 2.52 | 59.22 |
| conservative | 30 | 53.72 | [52.72, 54.71] | 2.667 | 53.07 |
| greedy | 30 | 24.9 | [24.63, 25.17] | 0.7304 | 24.91 |
| adaptive | 30 | 57.82 | [56.94, 58.7] | 2.35 | 57.55 |

### agent_utility

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| cost_plus | 30 | 0.764 | [0.6378, 0.8903] | 0.3382 | 0.6937 |
| aggressive | 30 | -1.428 | [-1.546, -1.31] | 0.3165 | -1.42 |
| conservative | 30 | 4.237 | [4.037, 4.437] | 0.536 | 4.237 |
| greedy | 30 | 27.69 | [26.8, 28.58] | 2.393 | 27.93 |
| adaptive | 30 | 0.273 | [0.1035, 0.4426] | 0.454 | 0.2354 |

### total_surplus

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| cost_plus | 30 | 58 | [56.96, 59.04] | 2.786 | 57.93 |
| aggressive | 30 | 58 | [56.96, 59.04] | 2.79 | 57.93 |
| conservative | 30 | 57.95 | [56.9, 59.01] | 2.819 | 57.88 |
| greedy | 30 | 52.59 | [51.49, 53.69] | 2.947 | 52.93 |
| adaptive | 30 | 58.09 | [57.11, 59.07] | 2.625 | 58.07 |

### completion_rate

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| cost_plus | 30 | 0.8968 | [0.8854, 0.9083] | 0.03061 | 0.8938 |
| aggressive | 30 | 0.8969 | [0.8854, 0.9084] | 0.03078 | 0.8938 |
| conservative | 30 | 0.894 | [0.8824, 0.9056] | 0.03102 | 0.8925 |
| greedy | 30 | 0.8989 | [0.8895, 0.9083] | 0.02516 | 0.8987 |
| adaptive | 30 | 0.8973 | [0.8864, 0.9083] | 0.02931 | 0.8975 |

## Statistical tests

Paired t-tests on per-replication differences (treatment - baseline). Effect size is Cohen's d_z.

| metric | treatment | mean diff | CI | relative | d_z | p | p (Holm) |
|---|---|---|---|---|---|---|---|
| average_cost | aggressive | -0.006115 | [-0.006323, -0.005907] | -20.8% | -11 | 5.21e-32 | 7.3e-31 |
| buyer_utility | aggressive | 2.195 | [2.121, 2.27] | +3.8% | 11 | 5.24e-32 | 7.3e-31 |
| agent_utility | aggressive | -2.192 | [-2.266, -2.119] | -286.9% | -11.1 | 3.7e-32 | 5.55e-31 |
| total_surplus | aggressive | 0.002772 | [-0.002897, 0.00844] | +0.0% | 0.183 | 0.326 | 1 |
| completion_rate | aggressive | 8.333e-05 | [-8.71e-05, 0.0002538] | +0.0% | 0.183 | 0.326 | 1 |
| average_cost | conservative | 0.009652 | [0.009349, 0.009954] | +32.9% | 11.9 | 5.3e-33 | 9.02e-32 |
| buyer_utility | conservative | -3.521 | [-3.646, -3.395] | -6.2% | -10.5 | 2.11e-31 | 2.53e-30 |
| agent_utility | conservative | 3.473 | [3.362, 3.584] | +454.6% | 11.7 | 8.66e-33 | 1.38e-31 |
| total_surplus | conservative | -0.04767 | [-0.08141, -0.01392] | -0.1% | -0.527 | 0.00724 | 0.0434 |
| completion_rate | conservative | -0.002833 | [-0.003922, -0.001744] | -0.3% | -0.971 | 1.04e-05 | 8.31e-05 |
| average_cost | greedy | 0.09026 | [0.08906, 0.09146] | +307.5% | 28.2 | 7.82e-44 | 1.56e-42 |
| buyer_utility | greedy | -32.34 | [-33.14, -31.53] | -56.5% | -15 | 7.07e-36 | 1.34e-34 |
| agent_utility | greedy | 26.93 | [26.1, 27.75] | +3524.1% | 12.2 | 2.36e-33 | 4.24e-32 |
| total_surplus | greedy | -5.412 | [-6.318, -4.507] | -9.3% | -2.23 | 5.74e-13 | 6.32e-12 |
| completion_rate | greedy | 0.002083 | [-0.007313, 0.01148] | +0.2% | 0.0828 | 0.654 | 1 |
| average_cost | adaptive | -0.001104 | [-0.001514, -0.000694] | -3.8% | -1.01 | 6.21e-06 | 5.59e-05 |
| buyer_utility | adaptive | 0.5817 | [0.3555, 0.8078] | +1.0% | 0.96 | 1.23e-05 | 8.62e-05 |
| agent_utility | adaptive | -0.491 | [-0.6229, -0.3591] | -64.3% | -1.39 | 2.17e-08 | 2.17e-07 |
| total_surplus | adaptive | 0.09068 | [-0.1184, 0.2997] | +0.2% | 0.162 | 0.382 | 1 |
| completion_rate | adaptive | 0.0005 | [-0.001498, 0.002498] | +0.1% | 0.0935 | 0.613 | 1 |

## Limitations

- Results come from a synthetic market; agent costs, quality and reliability are drawn from the configured distributions, not measured from real agents.
- Agents follow fixed (or simple adaptive) bidding strategies; real strategic agents may respond to the mechanism differently.
- A non-significant difference is not evidence of equivalence.
- P-values are Holm-adjusted across the comparisons in this report only.

## Conclusion

- In this simulated environment, `aggressive` produced lower `average_cost` than `cost_plus` (mean difference -0.006115, 95% CI [-0.006323, -0.005907]).
- In this simulated environment, `aggressive` produced higher `buyer_utility` than `cost_plus` (mean difference 2.195, 95% CI [2.121, 2.27]).
- In this simulated environment, `aggressive` produced lower `agent_utility` than `cost_plus` (mean difference -2.192, 95% CI [-2.266, -2.119]).
- No difference in `total_surplus` between `aggressive` and `cost_plus` was detected at alpha=0.05 after Holm adjustment (95% CI [-0.002897, 0.00844]).
- No difference in `completion_rate` between `aggressive` and `cost_plus` was detected at alpha=0.05 after Holm adjustment (95% CI [-8.71e-05, 0.0002538]).
- In this simulated environment, `conservative` produced higher `average_cost` than `cost_plus` (mean difference 0.009652, 95% CI [0.009349, 0.009954]).
- In this simulated environment, `conservative` produced lower `buyer_utility` than `cost_plus` (mean difference -3.521, 95% CI [-3.646, -3.395]).
- In this simulated environment, `conservative` produced higher `agent_utility` than `cost_plus` (mean difference 3.473, 95% CI [3.362, 3.584]).
- In this simulated environment, `conservative` produced lower `total_surplus` than `cost_plus` (mean difference -0.04767, 95% CI [-0.08141, -0.01392]).
- In this simulated environment, `conservative` produced lower `completion_rate` than `cost_plus` (mean difference -0.002833, 95% CI [-0.003922, -0.001744]).
- In this simulated environment, `greedy` produced higher `average_cost` than `cost_plus` (mean difference 0.09026, 95% CI [0.08906, 0.09146]).
- In this simulated environment, `greedy` produced lower `buyer_utility` than `cost_plus` (mean difference -32.34, 95% CI [-33.14, -31.53]).
- In this simulated environment, `greedy` produced higher `agent_utility` than `cost_plus` (mean difference 26.93, 95% CI [26.1, 27.75]).
- In this simulated environment, `greedy` produced lower `total_surplus` than `cost_plus` (mean difference -5.412, 95% CI [-6.318, -4.507]).
- No difference in `completion_rate` between `greedy` and `cost_plus` was detected at alpha=0.05 after Holm adjustment (95% CI [-0.007313, 0.01148]).
- In this simulated environment, `adaptive` produced lower `average_cost` than `cost_plus` (mean difference -0.001104, 95% CI [-0.001514, -0.000694]).
- In this simulated environment, `adaptive` produced higher `buyer_utility` than `cost_plus` (mean difference 0.5817, 95% CI [0.3555, 0.8078]).
- In this simulated environment, `adaptive` produced lower `agent_utility` than `cost_plus` (mean difference -0.491, 95% CI [-0.6229, -0.3591]).
- No difference in `total_surplus` between `adaptive` and `cost_plus` was detected at alpha=0.05 after Holm adjustment (95% CI [-0.1184, 0.2997]).
- No difference in `completion_rate` between `adaptive` and `cost_plus` was detected at alpha=0.05 after Holm adjustment (95% CI [-0.001498, 0.002498]).
