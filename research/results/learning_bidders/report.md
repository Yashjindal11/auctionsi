# Experiment report: learning_bidders

Every agent learns its markup with a UCB1 bandit (reward = realised profit relative to cost). Arms change the payment rule.


## Hypothesis

Under second-price (critical value) payment the bid does not set the price, so learned winning markups are lower than under first price, while buyer cost stays similar or lower.


## Experimental setup

- Replications: 30 per arm (common random numbers across arms)
- Seed: 23
- AuctionSI 0.1.1, Python 3.12.15, git commit 0162c05e54894a8575355e5fb4d3f5d47dd18a08+dirty
- Baseline arm: `first_price`
- Confidence level: 95%; alpha: 0.05

### Parameters

- Agents: {'count': 20, 'capabilities': ['research', 'data_analysis', 'sql', 'optimization'], 'capability_distribution': 'mixed', 'capabilities_per_agent': (1, 3), 'cost_distribution': 'lognormal', 'variable_cost_ratio': 0.01, 'quality_distribution': 'beta', 'quality_spread': 0.05, 'latency_distribution': 'lognormal', 'reliability_distribution': 'beta', 'capacity_distribution': 1, 'strategy': {'name': 'bandit', 'algorithm': 'ucb1'}, 'quality_report_bias': 0.0}
- Tasks: {'count': 600, 'task_types': ['research', 'data_analysis', 'sql', 'optimization'], 'arrival_rate': 1.0, 'budget_distribution': 'lognormal', 'deadline_distribution': 'uniform', 'complexity_distribution': 'lognormal', 'min_quality': None, 'value_multiplier': 1.5}
- Defaults: mechanism=first_price_reverse, policy=lowest_price, reputation=multi_dimensional, settlement=pay_on_pass

### Arms

- `first_price`: {'mechanism': 'first_price_reverse'}
- `second_price`: {'mechanism': 'second_price_reverse'}

## Results

### average_winning_markup

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| first_price | 30 | 0.227 | [0.2164, 0.2375] | 0.02819 | 0.2286 |
| second_price | 30 | 0.1586 | [0.1489, 0.1684] | 0.02616 | 0.1571 |

### average_cost

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| first_price | 30 | 0.03524 | [0.03352, 0.03695] | 0.004598 | 0.03497 |
| second_price | 30 | 0.04816 | [0.04557, 0.05074] | 0.006922 | 0.04849 |

### agent_utility

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| first_price | 30 | 1.54 | [1.37, 1.71] | 0.4555 | 1.575 |
| second_price | 30 | 8.434 | [7.725, 9.142] | 1.898 | 8.566 |

### buyer_utility

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| first_price | 30 | 81.15 | [79.79, 82.52] | 3.656 | 81.16 |
| second_price | 30 | 74.51 | [72.66, 76.37] | 4.96 | 74.03 |

### completion_rate

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| first_price | 30 | 0.8806 | [0.8713, 0.8898] | 0.02477 | 0.88 |
| second_price | 30 | 0.8823 | [0.8732, 0.8913] | 0.02424 | 0.8817 |

## Statistical tests

Paired t-tests on per-replication differences (treatment - baseline). Effect size is Cohen's d_z.

| metric | treatment | mean diff | CI | relative | d_z | p | p (Holm) |
|---|---|---|---|---|---|---|---|
| average_winning_markup | second_price | -0.06833 | [-0.07648, -0.06018] | -30.1% | -3.13 | 1.02e-16 | 2.03e-16 |
| average_cost | second_price | 0.01292 | [0.01171, 0.01414] | +36.7% | 3.97 | 1.65e-19 | 6.59e-19 |
| agent_utility | second_price | 6.894 | [6.297, 7.491] | +447.7% | 4.31 | 1.73e-20 | 8.63e-20 |
| buyer_utility | second_price | -6.639 | [-7.32, -5.959] | -8.2% | -3.64 | 1.74e-18 | 5.22e-18 |
| completion_rate | second_price | 0.001722 | [-0.000688, 0.004132] | +0.2% | 0.267 | 0.155 | 0.155 |

## Limitations

- Markups are learned from a fixed grid of seven values; agents do not observe rivals' bids.
- Synthetic market; one learner population per run.
- Results come from a synthetic market; agent costs, quality and reliability are drawn from the configured distributions, not measured from real agents.
- Agents follow fixed (or simple adaptive) bidding strategies; real strategic agents may respond to the mechanism differently.
- A non-significant difference is not evidence of equivalence.
- P-values are Holm-adjusted across the comparisons in this report only.

## Conclusion

- In this simulated environment, `second_price` produced lower `average_winning_markup` than `first_price` (mean difference -0.06833, 95% CI [-0.07648, -0.06018]).
- In this simulated environment, `second_price` produced higher `average_cost` than `first_price` (mean difference 0.01292, 95% CI [0.01171, 0.01414]).
- In this simulated environment, `second_price` produced higher `agent_utility` than `first_price` (mean difference 6.894, 95% CI [6.297, 7.491]).
- In this simulated environment, `second_price` produced lower `buyer_utility` than `first_price` (mean difference -6.639, 95% CI [-7.32, -5.959]).
- No difference in `completion_rate` between `second_price` and `first_price` was detected at alpha=0.05 after Holm adjustment (95% CI [-0.000688, 0.004132]).
