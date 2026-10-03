# Experiment report: mechanisms

Four market designs on the same synthetic market: pay-as-bid and second-price reverse auctions with lowest-price selection, and pay-as-bid with quality-weighted and risk-adjusted selection.


## Hypothesis

With bidders whose strategy does not react to the mechanism (cost-plus 20%), second-price payments raise buyer cost relative to first-price without changing allocation, while risk-adjusted selection raises completion rate at some cost.


## Experimental setup

- Replications: 30 per arm (common random numbers across arms)
- Seed: 2026
- AuctionSI 0.1.0, Python 3.12.15, git commit 4cdec6d83de3d2823b91590873730666f37fb1dd
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
| quality_weighted | 30 | 9.993 | [9.597, 10.39] | 1.06 | 9.943 |
| risk_adjusted | 30 | 9.479 | [9.087, 9.871] | 1.05 | 9.235 |

### average_cost

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| first_price | 30 | 0.02672 | [0.02568, 0.02775] | 0.002779 | 0.02681 |
| second_price | 30 | 0.03193 | [0.03069, 0.03317] | 0.003312 | 0.0321 |
| quality_weighted | 30 | 0.0306 | [0.02942, 0.03177] | 0.00315 | 0.03068 |
| risk_adjusted | 30 | 0.02918 | [0.02804, 0.03033] | 0.003064 | 0.02904 |

### average_quality

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| first_price | 30 | 0.8268 | [0.8188, 0.8347] | 0.02127 | 0.8258 |
| second_price | 30 | 0.8268 | [0.8188, 0.8347] | 0.02127 | 0.8258 |
| quality_weighted | 30 | 0.8511 | [0.8438, 0.8584] | 0.01961 | 0.851 |
| risk_adjusted | 30 | 0.8296 | [0.8223, 0.8369] | 0.01949 | 0.8291 |

### completion_rate

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| first_price | 30 | 0.7742 | [0.7578, 0.7907] | 0.04405 | 0.7737 |
| second_price | 30 | 0.7742 | [0.7578, 0.7907] | 0.04405 | 0.7737 |
| quality_weighted | 30 | 0.8172 | [0.8032, 0.8311] | 0.03727 | 0.8125 |
| risk_adjusted | 30 | 0.8126 | [0.7977, 0.8275] | 0.03991 | 0.8037 |

### cost_efficiency

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| first_price | 30 | 0.9327 | [0.9031, 0.9622] | 0.07919 | 0.9567 |
| second_price | 30 | 0.9327 | [0.9031, 0.9622] | 0.07919 | 0.9567 |
| quality_weighted | 30 | 0.7782 | [0.7494, 0.807] | 0.07704 | 0.7849 |
| risk_adjusted | 30 | 0.8098 | [0.7807, 0.8389] | 0.07787 | 0.825 |

### buyer_utility

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| first_price | 30 | 49.98 | [48.8, 51.16] | 3.153 | 50.02 |
| second_price | 30 | 48.37 | [47.19, 49.54] | 3.155 | 48.42 |
| quality_weighted | 30 | 51.65 | [50.56, 52.73] | 2.9 | 51.53 |
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
| total_cost | quality_weighted | 1.724 | [1.492, 1.957] | +20.9% | 2.77 | 2.4e-15 | 2.87e-14 |
| average_cost | quality_weighted | 0.003882 | [0.003376, 0.004387] | +14.5% | 2.87 | 1.04e-15 | 1.35e-14 |
| average_quality | quality_weighted | 0.02432 | [0.01904, 0.02959] | +2.9% | 1.72 | 2.45e-10 | 1.96e-09 |
| completion_rate | quality_weighted | 0.04292 | [0.03284, 0.05299] | +5.5% | 1.59 | 1.37e-09 | 9.57e-09 |
| cost_efficiency | quality_weighted | -0.1545 | [-0.1721, -0.1369] | -16.6% | -3.27 | 3.08e-17 | 4.63e-16 |
| buyer_utility | quality_weighted | 1.667 | [1.017, 2.317] | +3.3% | 0.958 | 1.27e-05 | 6.37e-05 |
| total_cost | risk_adjusted | 1.211 | [1.034, 1.388] | +14.6% | 2.56 | 1.93e-14 | 1.93e-13 |
| average_cost | risk_adjusted | 0.002469 | [0.00211, 0.002827] | +9.2% | 2.57 | 1.71e-14 | 1.88e-13 |
| average_quality | risk_adjusted | 0.002811 | [-0.002134, 0.007756] | +0.3% | 0.212 | 0.254 | 1 |
| completion_rate | risk_adjusted | 0.03833 | [0.03028, 0.04639] | +5.0% | 1.78 | 1.22e-10 | 1.1e-09 |
| cost_efficiency | risk_adjusted | -0.1228 | [-0.1375, -0.1082] | -13.2% | -3.12 | 1.1e-16 | 1.54e-15 |
| buyer_utility | risk_adjusted | 1.76 | [1.248, 2.273] | +3.5% | 1.28 | 9.96e-08 | 5.98e-07 |

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
- In this simulated environment, `quality_weighted` produced higher `total_cost` than `first_price` (mean difference 1.724, 95% CI [1.492, 1.957]).
- In this simulated environment, `quality_weighted` produced higher `average_cost` than `first_price` (mean difference 0.003882, 95% CI [0.003376, 0.004387]).
- In this simulated environment, `quality_weighted` produced higher `average_quality` than `first_price` (mean difference 0.02432, 95% CI [0.01904, 0.02959]).
- In this simulated environment, `quality_weighted` produced higher `completion_rate` than `first_price` (mean difference 0.04292, 95% CI [0.03284, 0.05299]).
- In this simulated environment, `quality_weighted` produced lower `cost_efficiency` than `first_price` (mean difference -0.1545, 95% CI [-0.1721, -0.1369]).
- In this simulated environment, `quality_weighted` produced higher `buyer_utility` than `first_price` (mean difference 1.667, 95% CI [1.017, 2.317]).
- In this simulated environment, `risk_adjusted` produced higher `total_cost` than `first_price` (mean difference 1.211, 95% CI [1.034, 1.388]).
- In this simulated environment, `risk_adjusted` produced higher `average_cost` than `first_price` (mean difference 0.002469, 95% CI [0.00211, 0.002827]).
- No difference in `average_quality` between `risk_adjusted` and `first_price` was detected at alpha=0.05 after Holm adjustment (95% CI [-0.002134, 0.007756]).
- In this simulated environment, `risk_adjusted` produced higher `completion_rate` than `first_price` (mean difference 0.03833, 95% CI [0.03028, 0.04639]).
- In this simulated environment, `risk_adjusted` produced lower `cost_efficiency` than `first_price` (mean difference -0.1228, 95% CI [-0.1375, -0.1082]).
- In this simulated environment, `risk_adjusted` produced higher `buyer_utility` than `first_price` (mean difference 1.76, 95% CI [1.248, 2.273]).
