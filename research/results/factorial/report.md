# Experiment report: factorial

A 2 x 2 x 2 factorial sweep: payment rule x selection policy x agent reliability spread. Every combination is one arm.


## Hypothesis

Risk-adjusted selection matters only when reliability varies; the payment rule shifts cost but not completion.


## Experimental setup

- Replications: 20 per arm (common random numbers across arms)
- Seed: 37
- AuctionSI 0.1.1, Python 3.12.15, git commit 0162c05e54894a8575355e5fb4d3f5d47dd18a08+dirty
- Baseline arm: `mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0)`
- Confidence level: 95%; alpha: 0.05

### Parameters

- Agents: {'count': 25, 'capabilities': ['research', 'data_analysis', 'sql', 'optimization'], 'capability_distribution': 'mixed', 'capabilities_per_agent': (1, 3), 'cost_distribution': 'lognormal', 'variable_cost_ratio': 0.01, 'quality_distribution': 'beta', 'quality_spread': 0.05, 'latency_distribution': 'lognormal', 'reliability_distribution': 'beta', 'capacity_distribution': 1, 'strategy': 'cost_plus', 'quality_report_bias': 0.0}
- Tasks: {'count': 300, 'task_types': ['research', 'data_analysis', 'sql', 'optimization'], 'arrival_rate': 1.0, 'budget_distribution': 'lognormal', 'deadline_distribution': 'uniform', 'complexity_distribution': 'lognormal', 'min_quality': None, 'value_multiplier': 1.5}
- Defaults: mechanism=first_price_reverse, policy=lowest_price, reputation=multi_dimensional, settlement=pay_on_pass

### Arms

- `mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0)`: {'mechanism': 'first_price_reverse', 'policy': 'lowest_price', 'environment': {'agents': {'reliability_distribution': {'name': 'uniform', 'low': 0.95, 'high': 1.0}}}}
- `mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.4,high=1.0)`: {'mechanism': 'first_price_reverse', 'policy': 'lowest_price', 'environment': {'agents': {'reliability_distribution': {'name': 'uniform', 'low': 0.4, 'high': 1.0}}}}
- `mechanism=first_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.95,high=1.0)`: {'mechanism': 'first_price_reverse', 'policy': 'risk_adjusted_cost', 'environment': {'agents': {'reliability_distribution': {'name': 'uniform', 'low': 0.95, 'high': 1.0}}}}
- `mechanism=first_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.4,high=1.0)`: {'mechanism': 'first_price_reverse', 'policy': 'risk_adjusted_cost', 'environment': {'agents': {'reliability_distribution': {'name': 'uniform', 'low': 0.4, 'high': 1.0}}}}
- `mechanism=second_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0)`: {'mechanism': 'second_price_reverse', 'policy': 'lowest_price', 'environment': {'agents': {'reliability_distribution': {'name': 'uniform', 'low': 0.95, 'high': 1.0}}}}
- `mechanism=second_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.4,high=1.0)`: {'mechanism': 'second_price_reverse', 'policy': 'lowest_price', 'environment': {'agents': {'reliability_distribution': {'name': 'uniform', 'low': 0.4, 'high': 1.0}}}}
- `mechanism=second_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.95,high=1.0)`: {'mechanism': 'second_price_reverse', 'policy': 'risk_adjusted_cost', 'environment': {'agents': {'reliability_distribution': {'name': 'uniform', 'low': 0.95, 'high': 1.0}}}}
- `mechanism=second_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.4,high=1.0)`: {'mechanism': 'second_price_reverse', 'policy': 'risk_adjusted_cost', 'environment': {'agents': {'reliability_distribution': {'name': 'uniform', 'low': 0.4, 'high': 1.0}}}}

## Results

### completion_rate

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0) | 20 | 0.9688 | [0.9633, 0.9744] | 0.01181 | 0.9683 |
| mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.4,high=1.0) | 20 | 0.6968 | [0.6796, 0.7141] | 0.03687 | 0.6883 |
| mechanism=first_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.95,high=1.0) | 20 | 0.969 | [0.9638, 0.9742] | 0.01103 | 0.9683 |
| mechanism=first_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.4,high=1.0) | 20 | 0.7382 | [0.7181, 0.7583] | 0.04298 | 0.7367 |
| mechanism=second_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0) | 20 | 0.9688 | [0.9633, 0.9744] | 0.01181 | 0.9683 |
| mechanism=second_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.4,high=1.0) | 20 | 0.6968 | [0.6796, 0.7141] | 0.03687 | 0.6883 |
| mechanism=second_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.95,high=1.0) | 20 | 0.969 | [0.9638, 0.9742] | 0.01103 | 0.9683 |
| mechanism=second_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.4,high=1.0) | 20 | 0.7382 | [0.7181, 0.7583] | 0.04298 | 0.7367 |

### average_cost

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0) | 20 | 0.03165 | [0.02998, 0.03333] | 0.003583 | 0.03096 |
| mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.4,high=1.0) | 20 | 0.03173 | [0.02999, 0.03347] | 0.003722 | 0.03121 |
| mechanism=first_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.95,high=1.0) | 20 | 0.03205 | [0.03038, 0.03372] | 0.003572 | 0.03118 |
| mechanism=first_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.4,high=1.0) | 20 | 0.0347 | [0.03307, 0.03632] | 0.003472 | 0.03495 |
| mechanism=second_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0) | 20 | 0.04105 | [0.03875, 0.04335] | 0.004911 | 0.04075 |
| mechanism=second_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.4,high=1.0) | 20 | 0.0409 | [0.03864, 0.04317] | 0.004841 | 0.03974 |
| mechanism=second_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.95,high=1.0) | 20 | 0.04977 | [0.04742, 0.05211] | 0.005002 | 0.04939 |
| mechanism=second_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.4,high=1.0) | 20 | 0.05411 | [0.05193, 0.05629] | 0.00465 | 0.05477 |

### buyer_utility

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0) | 20 | 45.5 | [44.76, 46.24] | 1.58 | 45.1 |
| mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.4,high=1.0) | 20 | 32.58 | [31.72, 33.44] | 1.838 | 32.43 |
| mechanism=first_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.95,high=1.0) | 20 | 45.4 | [44.69, 46.1] | 1.508 | 44.96 |
| mechanism=first_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.4,high=1.0) | 20 | 34.14 | [33.13, 35.16] | 2.17 | 34.15 |
| mechanism=second_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0) | 20 | 42.77 | [41.87, 43.67] | 1.93 | 42.71 |
| mechanism=second_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.4,high=1.0) | 20 | 30.65 | [29.86, 31.44] | 1.691 | 30.71 |
| mechanism=second_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.95,high=1.0) | 20 | 40.25 | [39.4, 41.1] | 1.816 | 39.98 |
| mechanism=second_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.4,high=1.0) | 20 | 29.83 | [28.97, 30.69] | 1.836 | 29.99 |

## Statistical tests

Paired t-tests on per-replication differences (treatment - baseline). Effect size is Cohen's d_z.

| metric | treatment | mean diff | CI | relative | d_z | p | p (Holm) |
|---|---|---|---|---|---|---|---|
| completion_rate | mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.4,high=1.0) | -0.272 | [-0.2921, -0.2519] | -28.1% | -6.32 | 5.44e-17 | 8.71e-16 |
| average_cost | mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.4,high=1.0) | 7.464e-05 | [-0.0003665, 0.0005158] | +0.2% | 0.0792 | 0.727 | 1 |
| buyer_utility | mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.4,high=1.0) | -12.92 | [-14.01, -11.83] | -28.4% | -5.55 | 6.17e-16 | 8.63e-15 |
| completion_rate | mechanism=first_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.95,high=1.0) | 0.0001667 | [-0.002009, 0.002342] | +0.0% | 0.0359 | 0.874 | 1 |
| average_cost | mechanism=first_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.95,high=1.0) | 0.0003978 | [0.0001832, 0.0006124] | +1.3% | 0.867 | 0.00101 | 0.00606 |
| buyer_utility | mechanism=first_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.95,high=1.0) | -0.1019 | [-0.247, 0.04327] | -0.2% | -0.328 | 0.158 | 0.791 |
| completion_rate | mechanism=first_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.4,high=1.0) | -0.2307 | [-0.2528, -0.2085] | -23.8% | -4.87 | 6.74e-15 | 8.77e-14 |
| average_cost | mechanism=first_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.4,high=1.0) | 0.003046 | [0.002486, 0.003607] | +9.6% | 2.54 | 6.38e-10 | 4.47e-09 |
| buyer_utility | mechanism=first_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.4,high=1.0) | -11.36 | [-12.53, -10.18] | -25.0% | -4.52 | 2.57e-14 | 2.06e-13 |
| completion_rate | mechanism=second_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0) | 0 | [0, 0] | +0.0% | n/a | 1 | 1 |
| average_cost | mechanism=second_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0) | 0.009397 | [0.008453, 0.01034] | +29.7% | 4.66 | 1.51e-14 | 1.36e-13 |
| buyer_utility | mechanism=second_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0) | -2.729 | [-2.999, -2.46] | -6.0% | -4.74 | 1.11e-14 | 1.11e-13 |
| completion_rate | mechanism=second_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.4,high=1.0) | -0.272 | [-0.2921, -0.2519] | -28.1% | -6.32 | 5.44e-17 | 8.71e-16 |
| average_cost | mechanism=second_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.4,high=1.0) | 0.00925 | [0.008355, 0.01014] | +29.2% | 4.84 | 7.56e-15 | 8.77e-14 |
| buyer_utility | mechanism=second_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.4,high=1.0) | -14.85 | [-15.8, -13.89] | -32.6% | -7.28 | 3.9e-18 | 6.63e-17 |
| completion_rate | mechanism=second_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.95,high=1.0) | 0.0001667 | [-0.002009, 0.002342] | +0.0% | 0.0359 | 0.874 | 1 |
| average_cost | mechanism=second_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.95,high=1.0) | 0.01811 | [0.01716, 0.01906] | +57.2% | 8.93 | 8.58e-20 | 1.72e-18 |
| buyer_utility | mechanism=second_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.95,high=1.0) | -5.25 | [-5.516, -4.984] | -11.5% | -9.25 | 4.45e-20 | 9.35e-19 |
| completion_rate | mechanism=second_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.4,high=1.0) | -0.2307 | [-0.2528, -0.2085] | -23.8% | -4.87 | 6.74e-15 | 8.77e-14 |
| average_cost | mechanism=second_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.4,high=1.0) | 0.02246 | [0.02115, 0.02376] | +70.9% | 8.06 | 5.83e-19 | 1.11e-17 |
| buyer_utility | mechanism=second_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.4,high=1.0) | -15.67 | [-16.6, -14.74] | -34.4% | -7.9 | 8.49e-19 | 1.53e-17 |

## Limitations

- Main effects are read from arm means; interactions are not modelled formally.
- Results come from a synthetic market; agent costs, quality and reliability are drawn from the configured distributions, not measured from real agents.
- Agents follow fixed (or simple adaptive) bidding strategies; real strategic agents may respond to the mechanism differently.
- A non-significant difference is not evidence of equivalence.
- P-values are Holm-adjusted across the comparisons in this report only.

## Conclusion

- In this simulated environment, `mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.4,high=1.0)` produced lower `completion_rate` than `mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0)` (mean difference -0.272, 95% CI [-0.2921, -0.2519]).
- No difference in `average_cost` between `mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.4,high=1.0)` and `mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0)` was detected at alpha=0.05 after Holm adjustment (95% CI [-0.0003665, 0.0005158]).
- In this simulated environment, `mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.4,high=1.0)` produced lower `buyer_utility` than `mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0)` (mean difference -12.92, 95% CI [-14.01, -11.83]).
- No difference in `completion_rate` between `mechanism=first_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.95,high=1.0)` and `mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0)` was detected at alpha=0.05 after Holm adjustment (95% CI [-0.002009, 0.002342]).
- In this simulated environment, `mechanism=first_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.95,high=1.0)` produced higher `average_cost` than `mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0)` (mean difference 0.0003978, 95% CI [0.0001832, 0.0006124]).
- No difference in `buyer_utility` between `mechanism=first_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.95,high=1.0)` and `mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0)` was detected at alpha=0.05 after Holm adjustment (95% CI [-0.247, 0.04327]).
- In this simulated environment, `mechanism=first_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.4,high=1.0)` produced lower `completion_rate` than `mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0)` (mean difference -0.2307, 95% CI [-0.2528, -0.2085]).
- In this simulated environment, `mechanism=first_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.4,high=1.0)` produced higher `average_cost` than `mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0)` (mean difference 0.003046, 95% CI [0.002486, 0.003607]).
- In this simulated environment, `mechanism=first_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.4,high=1.0)` produced lower `buyer_utility` than `mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0)` (mean difference -11.36, 95% CI [-12.53, -10.18]).
- No difference in `completion_rate` between `mechanism=second_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0)` and `mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0)` was detected at alpha=0.05 after Holm adjustment (95% CI [0, 0]).
- In this simulated environment, `mechanism=second_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0)` produced higher `average_cost` than `mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0)` (mean difference 0.009397, 95% CI [0.008453, 0.01034]).
- In this simulated environment, `mechanism=second_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0)` produced lower `buyer_utility` than `mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0)` (mean difference -2.729, 95% CI [-2.999, -2.46]).
- In this simulated environment, `mechanism=second_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.4,high=1.0)` produced lower `completion_rate` than `mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0)` (mean difference -0.272, 95% CI [-0.2921, -0.2519]).
- In this simulated environment, `mechanism=second_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.4,high=1.0)` produced higher `average_cost` than `mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0)` (mean difference 0.00925, 95% CI [0.008355, 0.01014]).
- In this simulated environment, `mechanism=second_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.4,high=1.0)` produced lower `buyer_utility` than `mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0)` (mean difference -14.85, 95% CI [-15.8, -13.89]).
- No difference in `completion_rate` between `mechanism=second_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.95,high=1.0)` and `mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0)` was detected at alpha=0.05 after Holm adjustment (95% CI [-0.002009, 0.002342]).
- In this simulated environment, `mechanism=second_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.95,high=1.0)` produced higher `average_cost` than `mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0)` (mean difference 0.01811, 95% CI [0.01716, 0.01906]).
- In this simulated environment, `mechanism=second_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.95,high=1.0)` produced lower `buyer_utility` than `mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0)` (mean difference -5.25, 95% CI [-5.516, -4.984]).
- In this simulated environment, `mechanism=second_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.4,high=1.0)` produced lower `completion_rate` than `mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0)` (mean difference -0.2307, 95% CI [-0.2528, -0.2085]).
- In this simulated environment, `mechanism=second_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.4,high=1.0)` produced higher `average_cost` than `mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0)` (mean difference 0.02246, 95% CI [0.02115, 0.02376]).
- In this simulated environment, `mechanism=second_price_reverse,policy=risk_adjusted_cost,agents.reliability_distribution=uniform(low=0.4,high=1.0)` produced lower `buyer_utility` than `mechanism=first_price_reverse,policy=lowest_price,agents.reliability_distribution=uniform(low=0.95,high=1.0)` (mean difference -15.67, 95% CI [-16.6, -14.74]).
