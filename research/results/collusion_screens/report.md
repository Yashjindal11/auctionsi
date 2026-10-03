# Experiment report: collusion_screens

A bid-rotation cartel of five agents (designated winner bids cost x1.6, others cover at x2.2) against an otherwise competitive market. Measures buyer cost and two simple screens from the procurement literature: the coefficient of variation of bids per auction and the relative distance between the two lowest bids.


## Hypothesis

The cartel raises average buyer cost; the screens move (higher relative distance between the two lowest bids) when it is present.


## Experimental setup

- Replications: 30 per arm (common random numbers across arms)
- Seed: 31
- AuctionSI 0.1.1, Python 3.12.15, git commit 0162c05e54894a8575355e5fb4d3f5d47dd18a08
- Baseline arm: `competitive`
- Confidence level: 95%; alpha: 0.05

### Parameters

- Agents: {'count': 12, 'capabilities': ['general'], 'capability_distribution': 'mixed', 'capabilities_per_agent': (1, 1), 'cost_distribution': 'lognormal', 'variable_cost_ratio': 0.01, 'quality_distribution': 'beta', 'quality_spread': 0.05, 'latency_distribution': 'lognormal', 'reliability_distribution': 'beta', 'capacity_distribution': 1, 'strategy': 'cost_plus', 'quality_report_bias': 0.0}
- Tasks: {'count': 400, 'task_types': ['general'], 'arrival_rate': 1.0, 'budget_distribution': 'lognormal', 'deadline_distribution': 'uniform', 'complexity_distribution': 'lognormal', 'min_quality': None, 'value_multiplier': 1.5}
- Defaults: mechanism=first_price_reverse, policy=lowest_price, reputation=multi_dimensional, settlement=pay_on_pass

### Arms

- `competitive`: experiment defaults
- `cartel`: {'environment': {'adversaries': {'colluders': 5, 'winner_markup': 0.6, 'cover_markup': 1.2}}}

## Results

### average_cost

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| competitive | 30 | 0.04053 | [0.03845, 0.04261] | 0.005575 | 0.04114 |
| cartel | 30 | 0.04844 | [0.04595, 0.05092] | 0.006649 | 0.04848 |

### bid_cv

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| competitive | 30 | 0.3123 | [0.2836, 0.341] | 0.07686 | 0.3129 |
| cartel | 30 | 0.3181 | [0.2932, 0.343] | 0.06677 | 0.3198 |

### relative_distance

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| competitive | 30 | 1.777 | [1.323, 2.232] | 1.218 | 1.371 |
| cartel | 30 | 4.295 | [-0.07746, 8.668] | 11.71 | 1.744 |

### buyer_utility

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| competitive | 30 | 47.57 | [45.91, 49.22] | 4.431 | 47.24 |
| cartel | 30 | 44.4 | [42.72, 46.08] | 4.503 | 44.16 |

### hhi

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| competitive | 30 | 0.1051 | [0.1007, 0.1096] | 0.01187 | 0.1032 |
| cartel | 30 | 0.1066 | [0.103, 0.1103] | 0.009868 | 0.1061 |

## Statistical tests

Paired t-tests on per-replication differences (treatment - baseline). Effect size is Cohen's d_z.

| metric | treatment | mean diff | CI | relative | d_z | p | p (Holm) |
|---|---|---|---|---|---|---|---|
| average_cost | cartel | 0.007905 | [0.006986, 0.008824] | +19.5% | 3.21 | 5.14e-17 | 2.57e-16 |
| bid_cv | cartel | 0.005813 | [-0.01908, 0.0307] | +1.9% | 0.0872 | 0.636 | 0.743 |
| relative_distance | cartel | 2.518 | [-1.847, 6.882] | +141.6% | 0.215 | 0.248 | 0.743 |
| buyer_utility | cartel | -3.167 | [-3.817, -2.518] | -6.7% | -1.82 | 7.03e-11 | 2.81e-10 |
| hhi | cartel | 0.001494 | [-0.001861, 0.004848] | +1.4% | 0.166 | 0.37 | 0.743 |

## Limitations

- The cartel strategy is a simple rotation; real cartels adapt to screens.
- Screens are reported as market averages, not as a per-auction detector.
- Results come from a synthetic market; agent costs, quality and reliability are drawn from the configured distributions, not measured from real agents.
- Agents follow fixed (or simple adaptive) bidding strategies; real strategic agents may respond to the mechanism differently.
- A non-significant difference is not evidence of equivalence.
- P-values are Holm-adjusted across the comparisons in this report only.

## Conclusion

- In this simulated environment, `cartel` produced higher `average_cost` than `competitive` (mean difference 0.007905, 95% CI [0.006986, 0.008824]).
- No difference in `bid_cv` between `cartel` and `competitive` was detected at alpha=0.05 after Holm adjustment (95% CI [-0.01908, 0.0307]).
- No difference in `relative_distance` between `cartel` and `competitive` was detected at alpha=0.05 after Holm adjustment (95% CI [-1.847, 6.882]).
- In this simulated environment, `cartel` produced lower `buyer_utility` than `competitive` (mean difference -3.167, 95% CI [-3.817, -2.518]).
- No difference in `hhi` between `cartel` and `competitive` was detected at alpha=0.05 after Holm adjustment (95% CI [-0.001861, 0.004848]).
