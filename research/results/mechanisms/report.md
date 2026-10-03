# Experiment report: mechanisms

Four market designs on the same synthetic market: pay-as-bid and second-price reverse auctions with lowest-price selection, and pay-as-bid with quality-weighted and risk-adjusted selection.


## Hypothesis

With bidders whose strategy does not react to the mechanism (cost-plus 20%), second-price payments raise buyer cost relative to first-price without changing allocation, while risk-adjusted selection raises completion rate at some cost.


## Experimental setup

- Replications: 30 per arm (common random numbers across arms)
- Seed: 2026
- AuctionSI 0.1.1, Python 3.12.15, git commit 0162c05e54894a8575355e5fb4d3f5d47dd18a08+dirty
- Baseline arm: `first_price`
- Confidence level: 95%; alpha: 0.05

### Parameters

- Agents: {'count': 40, 'capabilities': ['research', 'data_analysis', 'sql', 'optimization'], 'capability_distribution': 'mixed', 'capabilities_per_agent': (1, 3), 'cost_distribution': 'lognormal', 'variable_cost_ratio': 0.01, 'quality_distribution': 'beta', 'quality_spread': 0.05, 'latency_distribution': 'lognormal', 'reliability_distribution': {'name': 'uniform', 'low': 0.6, 'high': 1.0}, 'capacity_distribution': 1, 'strategy': 'cost_plus', 'quality_report_bias': 0.0}
- Tasks: {'count': 400, 'task_types': ['research', 'data_analysis', 'sql', 'optimization'], 'arrival_rate': 1.0, 'budget_distribution': 'lognormal', 'deadline_distribution': 'uniform', 'complexity_distribution': 'lognormal', 'min_quality': 0.6, 'value_multiplier': 1.5}
- Defaults: mechanism=first_price_reverse, policy=lowest_price, reputation=multi_dimensional, settlement=pay_on_pass

### Arms

- `first_price`: {'mechanism': 'first_price_reverse', 'policy': 'lowest_price'}
- `second_price`: {'mechanism': 'second_price_reverse', 'policy': 'lowest_price'}
- `quality_weighted`: {'mechanism': 'first_price_reverse', 'policy': {'name': 'weighted_score', 'price_weight': 0.5, 'quality_weight': 0.5, 'latency_weight': 0.0}}
- `risk_adjusted`: {'mechanism': 'first_price_reverse', 'policy': {'name': 'risk_adjusted_cost'}}

## Results

### total_cost

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| first_price | 30 | 8.268 | [7.923, 8.613] | 0.9233 | 8.171 |
| second_price | 30 | 9.881 | [9.471, 10.29] | 1.097 | 9.969 |
| quality_weighted | 30 | 8.849 | [8.449, 9.248] | 1.07 | 8.82 |
| risk_adjusted | 30 | 9.479 | [9.087, 9.871] | 1.05 | 9.235 |

### average_cost

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| first_price | 30 | 0.02672 | [0.02568, 0.02775] | 0.002779 | 0.02681 |
| second_price | 30 | 0.03193 | [0.03069, 0.03317] | 0.003312 | 0.0321 |
| quality_weighted | 30 | 0.02803 | [0.02695, 0.02911] | 0.002899 | 0.02824 |
| risk_adjusted | 30 | 0.02918 | [0.02804, 0.03033] | 0.003064 | 0.02904 |

### average_quality

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| first_price | 30 | 0.8268 | [0.8188, 0.8347] | 0.02127 | 0.8258 |
| second_price | 30 | 0.8268 | [0.8188, 0.8347] | 0.02127 | 0.8258 |
| quality_weighted | 30 | 0.8653 | [0.8581, 0.8724] | 0.01913 | 0.8684 |
| risk_adjusted | 30 | 0.8296 | [0.8223, 0.8369] | 0.01949 | 0.8291 |

### completion_rate

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| first_price | 30 | 0.7742 | [0.7578, 0.7907] | 0.04405 | 0.7737 |
| second_price | 30 | 0.7742 | [0.7578, 0.7907] | 0.04405 | 0.7737 |
| quality_weighted | 30 | 0.7888 | [0.7732, 0.8045] | 0.04183 | 0.7875 |
| risk_adjusted | 30 | 0.8126 | [0.7977, 0.8275] | 0.03991 | 0.8037 |

### cost_efficiency

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| first_price | 30 | 0.9327 | [0.9031, 0.9622] | 0.07919 | 0.9567 |
| second_price | 30 | 0.9327 | [0.9031, 0.9622] | 0.07919 | 0.9567 |
| quality_weighted | 30 | 0.8611 | [0.8307, 0.8915] | 0.08144 | 0.8915 |
| risk_adjusted | 30 | 0.8098 | [0.7807, 0.8389] | 0.07787 | 0.825 |

### buyer_utility

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| first_price | 30 | 49.98 | [48.8, 51.16] | 3.153 | 50.02 |
| second_price | 30 | 48.37 | [47.19, 49.54] | 3.155 | 48.42 |
| quality_weighted | 30 | 50.48 | [49.45, 51.51] | 2.763 | 50.31 |
| risk_adjusted | 30 | 51.74 | [50.69, 52.78] | 2.8 | 51.74 |

## Statistical tests

Paired t-tests on per-replication differences (treatment - baseline). Effect size is Cohen's d_z.

| metric | treatment | mean diff | CI | relative | d_z | p | p (Holm) |
|---|---|---|---|---|---|---|---|
| total_cost | second_price | 1.613 | [1.447, 1.778] | +19.5% | 3.64 | 1.84e-18 | 3.13e-17 |
| average_cost | second_price | 0.005214 | [0.004686, 0.005742] | +19.5% | 3.69 | 1.27e-18 | 2.29e-17 |
| average_quality | second_price | 0 | [0, 0] | +0.0% | n/a | 1 | 1 |
| completion_rate | second_price | 0 | [0, 0] | +0.0% | n/a | 1 | 1 |
| cost_efficiency | second_price | 0 | [0, 0] | +0.0% | n/a | 1 | 1 |
| buyer_utility | second_price | -1.613 | [-1.778, -1.447] | -3.2% | -3.64 | 1.84e-18 | 3.13e-17 |
| total_cost | quality_weighted | 0.5808 | [0.4421, 0.7194] | +7.0% | 1.56 | 1.95e-09 | 1.56e-08 |
| average_cost | quality_weighted | 0.001316 | [0.001093, 0.00154] | +4.9% | 2.2 | 8.15e-13 | 8.97e-12 |
| average_quality | quality_weighted | 0.03847 | [0.03311, 0.04382] | +4.7% | 2.68 | 5.64e-15 | 7.89e-14 |
| completion_rate | quality_weighted | 0.01458 | [0.0053, 0.02387] | +1.9% | 0.587 | 0.00321 | 0.0193 |
| cost_efficiency | quality_weighted | -0.0716 | [-0.08418, -0.05902] | -7.7% | -2.13 | 1.89e-12 | 1.89e-11 |
| buyer_utility | quality_weighted | 0.5012 | [-0.1387, 1.141] | +1.0% | 0.292 | 0.12 | 0.6 |
| total_cost | risk_adjusted | 1.211 | [1.034, 1.388] | +14.6% | 2.56 | 1.93e-14 | 2.31e-13 |
| average_cost | risk_adjusted | 0.002469 | [0.00211, 0.002827] | +9.2% | 2.57 | 1.71e-14 | 2.22e-13 |
| average_quality | risk_adjusted | 0.002811 | [-0.002134, 0.007756] | +0.3% | 0.212 | 0.254 | 1 |
| completion_rate | risk_adjusted | 0.03833 | [0.03028, 0.04639] | +5.0% | 1.78 | 1.22e-10 | 1.1e-09 |
| cost_efficiency | risk_adjusted | -0.1228 | [-0.1375, -0.1082] | -13.2% | -3.12 | 1.1e-16 | 1.65e-15 |
| buyer_utility | risk_adjusted | 1.76 | [1.248, 2.273] | +3.5% | 1.28 | 9.96e-08 | 6.98e-07 |

## Limitations

- Bidders use a fixed cost-plus strategy in every arm, so the classic incentive argument for second-price auctions (bidders shading less) is deliberately not modelled here.
- Results come from a synthetic market; agent costs, quality and reliability are drawn from the configured distributions, not measured from real agents.
- Agents follow fixed (or simple adaptive) bidding strategies; real strategic agents may respond to the mechanism differently.
- A non-significant difference is not evidence of equivalence.
- P-values are Holm-adjusted across the comparisons in this report only.

## Conclusion

- In this simulated environment, `second_price` produced higher `total_cost` than `first_price` (mean difference 1.613, 95% CI [1.447, 1.778]).
- In this simulated environment, `second_price` produced higher `average_cost` than `first_price` (mean difference 0.005214, 95% CI [0.004686, 0.005742]).
- No difference in `average_quality` between `second_price` and `first_price` was detected at alpha=0.05 after Holm adjustment (95% CI [0, 0]).
- No difference in `completion_rate` between `second_price` and `first_price` was detected at alpha=0.05 after Holm adjustment (95% CI [0, 0]).
- No difference in `cost_efficiency` between `second_price` and `first_price` was detected at alpha=0.05 after Holm adjustment (95% CI [0, 0]).
- In this simulated environment, `second_price` produced lower `buyer_utility` than `first_price` (mean difference -1.613, 95% CI [-1.778, -1.447]).
- In this simulated environment, `quality_weighted` produced higher `total_cost` than `first_price` (mean difference 0.5808, 95% CI [0.4421, 0.7194]).
- In this simulated environment, `quality_weighted` produced higher `average_cost` than `first_price` (mean difference 0.001316, 95% CI [0.001093, 0.00154]).
- In this simulated environment, `quality_weighted` produced higher `average_quality` than `first_price` (mean difference 0.03847, 95% CI [0.03311, 0.04382]).
- In this simulated environment, `quality_weighted` produced higher `completion_rate` than `first_price` (mean difference 0.01458, 95% CI [0.0053, 0.02387]).
- In this simulated environment, `quality_weighted` produced lower `cost_efficiency` than `first_price` (mean difference -0.0716, 95% CI [-0.08418, -0.05902]).
- No difference in `buyer_utility` between `quality_weighted` and `first_price` was detected at alpha=0.05 after Holm adjustment (95% CI [-0.1387, 1.141]).
- In this simulated environment, `risk_adjusted` produced higher `total_cost` than `first_price` (mean difference 1.211, 95% CI [1.034, 1.388]).
- In this simulated environment, `risk_adjusted` produced higher `average_cost` than `first_price` (mean difference 0.002469, 95% CI [0.00211, 0.002827]).
- No difference in `average_quality` between `risk_adjusted` and `first_price` was detected at alpha=0.05 after Holm adjustment (95% CI [-0.002134, 0.007756]).
- In this simulated environment, `risk_adjusted` produced higher `completion_rate` than `first_price` (mean difference 0.03833, 95% CI [0.03028, 0.04639]).
- In this simulated environment, `risk_adjusted` produced lower `cost_efficiency` than `first_price` (mean difference -0.1228, 95% CI [-0.1375, -0.1082]).
- In this simulated environment, `risk_adjusted` produced higher `buyer_utility` than `first_price` (mean difference 1.76, 95% CI [1.248, 2.273]).
