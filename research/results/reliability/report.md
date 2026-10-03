# Experiment report: reliability

Agents' reliability is drawn uniformly from [0.4, 1.0]. Three selection policies decide between cheap-but-flaky and pricier-but-reliable bidders.


## Hypothesis

Lowest-price selection awards many tasks to unreliable agents; risk-adjusted and reputation-adjusted selection raise completion rate and buyer utility.


## Experimental setup

- Replications: 30 per arm (common random numbers across arms)
- Seed: 11
- AuctionSI 0.1.1, Python 3.12.15, git commit 0162c05e54894a8575355e5fb4d3f5d47dd18a08+dirty
- Baseline arm: `lowest_price`
- Confidence level: 95%; alpha: 0.05

### Parameters

- Agents: {'count': 30, 'capabilities': ['research', 'data_analysis', 'sql', 'optimization'], 'capability_distribution': 'mixed', 'capabilities_per_agent': (1, 3), 'cost_distribution': 'lognormal', 'variable_cost_ratio': 0.01, 'quality_distribution': 'beta', 'quality_spread': 0.05, 'latency_distribution': 'lognormal', 'reliability_distribution': {'name': 'uniform', 'low': 0.4, 'high': 1.0}, 'capacity_distribution': 1, 'strategy': 'cost_plus', 'quality_report_bias': 0.0}
- Tasks: {'count': 400, 'task_types': ['research', 'data_analysis', 'sql', 'optimization'], 'arrival_rate': 1.0, 'budget_distribution': 'lognormal', 'deadline_distribution': 'uniform', 'complexity_distribution': 'lognormal', 'min_quality': None, 'value_multiplier': 1.5}
- Defaults: mechanism=first_price_reverse, policy=lowest_price, reputation=multi_dimensional, settlement={'name': 'pay_on_pass', 'penalty_rate': 0.0}

### Arms

- `lowest_price`: {'policy': 'lowest_price'}
- `risk_adjusted`: {'policy': {'name': 'risk_adjusted_cost'}}
- `reputation_adjusted`: {'policy': {'name': 'reputation_adjusted_cost'}}

## Results

### completion_rate

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| lowest_price | 30 | 0.6811 | [0.6611, 0.701] | 0.0534 | 0.6887 |
| risk_adjusted | 30 | 0.7293 | [0.7081, 0.7504] | 0.05652 | 0.7325 |
| reputation_adjusted | 30 | 0.7156 | [0.6946, 0.7366] | 0.05626 | 0.715 |

### total_cost

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| lowest_price | 30 | 8.257 | [7.838, 8.675] | 1.121 | 8.334 |
| risk_adjusted | 30 | 9.866 | [9.413, 10.32] | 1.214 | 9.928 |
| reputation_adjusted | 30 | 9.299 | [8.834, 9.765] | 1.246 | 9.328 |

### average_cost

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| lowest_price | 30 | 0.03034 | [0.02901, 0.03166] | 0.003552 | 0.03026 |
| risk_adjusted | 30 | 0.03386 | [0.03254, 0.03518] | 0.003526 | 0.03391 |
| reputation_adjusted | 30 | 0.03251 | [0.03114, 0.03389] | 0.003681 | 0.03247 |

### buyer_utility

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| lowest_price | 30 | 42.81 | [41.39, 44.23] | 3.796 | 42.89 |
| risk_adjusted | 30 | 45.29 | [43.7, 46.87] | 4.241 | 45.23 |
| reputation_adjusted | 30 | 44.72 | [43.15, 46.29] | 4.211 | 45.32 |

### total_surplus

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| lowest_price | 30 | 40.95 | [39.3, 42.61] | 4.426 | 41.19 |
| risk_adjusted | 30 | 43.94 | [42.08, 45.79] | 4.977 | 43.98 |
| reputation_adjusted | 30 | 43.25 | [41.41, 45.09] | 4.925 | 43.89 |

### hhi

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| lowest_price | 30 | 0.07524 | [0.07151, 0.07897] | 0.009985 | 0.07256 |
| risk_adjusted | 30 | 0.07515 | [0.07129, 0.07901] | 0.01034 | 0.07445 |
| reputation_adjusted | 30 | 0.07497 | [0.07091, 0.07902] | 0.01087 | 0.07509 |

## Statistical tests

Paired t-tests on per-replication differences (treatment - baseline). Effect size is Cohen's d_z.

| metric | treatment | mean diff | CI | relative | d_z | p | p (Holm) |
|---|---|---|---|---|---|---|---|
| completion_rate | risk_adjusted | 0.04817 | [0.04041, 0.05593] | +7.1% | 2.32 | 2.28e-13 | 1.82e-12 |
| total_cost | risk_adjusted | 1.61 | [1.467, 1.753] | +19.5% | 4.2 | 3.5e-20 | 4.2e-19 |
| average_cost | risk_adjusted | 0.003523 | [0.003146, 0.003899] | +11.6% | 3.49 | 5.42e-18 | 5.97e-17 |
| buyer_utility | risk_adjusted | 2.475 | [1.957, 2.994] | +5.8% | 1.78 | 1.14e-10 | 7.28e-10 |
| total_surplus | risk_adjusted | 2.982 | [2.36, 3.604] | +7.3% | 1.79 | 1.04e-10 | 7.28e-10 |
| hhi | risk_adjusted | -8.883e-05 | [-0.002108, 0.00193] | -0.1% | -0.0164 | 0.929 | 1 |
| completion_rate | reputation_adjusted | 0.0345 | [0.02668, 0.04232] | +5.1% | 1.65 | 6.37e-10 | 3.18e-09 |
| total_cost | reputation_adjusted | 1.043 | [0.8942, 1.191] | +12.6% | 2.62 | 1.03e-14 | 1.03e-13 |
| average_cost | reputation_adjusted | 0.002176 | [0.001833, 0.002518] | +7.2% | 2.37 | 1.3e-13 | 1.17e-12 |
| buyer_utility | reputation_adjusted | 1.909 | [1.331, 2.486] | +4.5% | 1.23 | 2.02e-07 | 6.05e-07 |
| total_surplus | reputation_adjusted | 2.299 | [1.631, 2.967] | +5.6% | 1.28 | 9.7e-08 | 3.88e-07 |
| hhi | reputation_adjusted | -0.0002741 | [-0.00172, 0.001171] | -0.4% | -0.0708 | 0.701 | 1 |

## Limitations

- Results come from a synthetic market; agent costs, quality and reliability are drawn from the configured distributions, not measured from real agents.
- Agents follow fixed (or simple adaptive) bidding strategies; real strategic agents may respond to the mechanism differently.
- A non-significant difference is not evidence of equivalence.
- P-values are Holm-adjusted across the comparisons in this report only.

## Conclusion

- In this simulated environment, `risk_adjusted` produced higher `completion_rate` than `lowest_price` (mean difference 0.04817, 95% CI [0.04041, 0.05593]).
- In this simulated environment, `risk_adjusted` produced higher `total_cost` than `lowest_price` (mean difference 1.61, 95% CI [1.467, 1.753]).
- In this simulated environment, `risk_adjusted` produced higher `average_cost` than `lowest_price` (mean difference 0.003523, 95% CI [0.003146, 0.003899]).
- In this simulated environment, `risk_adjusted` produced higher `buyer_utility` than `lowest_price` (mean difference 2.475, 95% CI [1.957, 2.994]).
- In this simulated environment, `risk_adjusted` produced higher `total_surplus` than `lowest_price` (mean difference 2.982, 95% CI [2.36, 3.604]).
- No difference in `hhi` between `risk_adjusted` and `lowest_price` was detected at alpha=0.05 after Holm adjustment (95% CI [-0.002108, 0.00193]).
- In this simulated environment, `reputation_adjusted` produced higher `completion_rate` than `lowest_price` (mean difference 0.0345, 95% CI [0.02668, 0.04232]).
- In this simulated environment, `reputation_adjusted` produced higher `total_cost` than `lowest_price` (mean difference 1.043, 95% CI [0.8942, 1.191]).
- In this simulated environment, `reputation_adjusted` produced higher `average_cost` than `lowest_price` (mean difference 0.002176, 95% CI [0.001833, 0.002518]).
- In this simulated environment, `reputation_adjusted` produced higher `buyer_utility` than `lowest_price` (mean difference 1.909, 95% CI [1.331, 2.486]).
- In this simulated environment, `reputation_adjusted` produced higher `total_surplus` than `lowest_price` (mean difference 2.299, 95% CI [1.631, 2.967]).
- No difference in `hhi` between `reputation_adjusted` and `lowest_price` was detected at alpha=0.05 after Holm adjustment (95% CI [-0.00172, 0.001171]).
