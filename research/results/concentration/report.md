# Experiment report: concentration

Does weighting reputation in winner selection concentrate work on a few agents? Agents can each run up to three tasks at once, so capacity does not force spreading.


## Hypothesis

Giving reputation weight in selection raises concentration (HHI, top-agent share, revenue Gini) relative to price-only selection.


## Experimental setup

- Replications: 30 per arm (common random numbers across arms)
- Seed: 19
- AuctionSI 0.1.0, Python 3.12.15, git commit 4cdec6d83de3d2823b91590873730666f37fb1dd
- Baseline arm: `price_only`
- Confidence level: 95%; alpha: 0.05

### Parameters

- Agents: {'count': 30, 'capabilities': ['research', 'data_analysis', 'sql', 'optimization'], 'capability_distribution': 'mixed', 'capabilities_per_agent': (1, 3), 'cost_distribution': 'lognormal', 'variable_cost_ratio': 0.01, 'quality_distribution': 'beta', 'quality_spread': 0.05, 'latency_distribution': 'lognormal', 'reliability_distribution': 'beta', 'capacity_distribution': 3, 'strategy': 'cost_plus', 'quality_report_bias': 0.0}
- Tasks: {'count': 400, 'task_types': ['research', 'data_analysis', 'sql', 'optimization'], 'arrival_rate': 1.0, 'budget_distribution': 'lognormal', 'deadline_distribution': 'uniform', 'complexity_distribution': 'lognormal', 'min_quality': None, 'value_multiplier': 1.5}
- Defaults: mechanism=first_price_reverse, policy=lowest_price, reputation=multi_dimensional, settlement=pay_on_pass

### Arms

- `price_only`: {'policy': 'lowest_price'}
- `reputation_weighted`: {'policy': {'name': 'weighted_score', 'price_weight': 0.5, 'quality_weight': 0.0, 'latency_weight': 0.0, 'reputation_weight': 0.5}}
- `reputation_adjusted`: {'policy': 'reputation_adjusted_cost'}

## Results

### hhi

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| price_only | 30 | 0.2056 | [0.1891, 0.2222] | 0.04433 | 0.2086 |
| reputation_weighted | 30 | 0.1975 | [0.1808, 0.2142] | 0.0447 | 0.1962 |
| reputation_adjusted | 30 | 0.2015 | [0.1851, 0.2178] | 0.04382 | 0.198 |

### top_agent_share

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| price_only | 30 | 0.2973 | [0.2702, 0.3245] | 0.07273 | 0.3029 |
| reputation_weighted | 30 | 0.3001 | [0.273, 0.3273] | 0.07274 | 0.2934 |
| reputation_adjusted | 30 | 0.3007 | [0.2728, 0.3285] | 0.07453 | 0.2869 |

### revenue_gini

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| price_only | 30 | 0.8325 | [0.8201, 0.8449] | 0.03317 | 0.8325 |
| reputation_weighted | 30 | 0.8277 | [0.814, 0.8415] | 0.03685 | 0.8297 |
| reputation_adjusted | 30 | 0.8294 | [0.8169, 0.8419] | 0.03341 | 0.8239 |

### opportunity_rate

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| price_only | 30 | 0.2989 | [0.2791, 0.3186] | 0.05287 | 0.3 |
| reputation_weighted | 30 | 0.2922 | [0.2733, 0.3112] | 0.0508 | 0.3 |
| reputation_adjusted | 30 | 0.2989 | [0.2778, 0.3199] | 0.05638 | 0.3 |

### average_cost

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| price_only | 30 | 0.0222 | [0.02122, 0.02318] | 0.002624 | 0.02201 |
| reputation_weighted | 30 | 0.02296 | [0.02197, 0.02395] | 0.002658 | 0.0228 |
| reputation_adjusted | 30 | 0.02263 | [0.02159, 0.02367] | 0.002784 | 0.02236 |

### completion_rate

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| price_only | 30 | 0.8978 | [0.8819, 0.9137] | 0.04261 | 0.9012 |
| reputation_weighted | 30 | 0.9113 | [0.8989, 0.9236] | 0.03309 | 0.9138 |
| reputation_adjusted | 30 | 0.9055 | [0.8918, 0.9192] | 0.03661 | 0.905 |

## Statistical tests

Paired t-tests on per-replication differences (treatment - baseline). Effect size is Cohen's d_z.

| metric | treatment | mean diff | CI | relative | d_z | p | p (Holm) |
|---|---|---|---|---|---|---|---|
| hhi | reputation_weighted | -0.008149 | [-0.01573, -0.0005686] | -4.0% | -0.401 | 0.036 | 0.288 |
| top_agent_share | reputation_weighted | 0.002798 | [-0.01179, 0.01739] | +0.9% | 0.0716 | 0.698 | 1 |
| revenue_gini | reputation_weighted | -0.004774 | [-0.01054, 0.0009907] | -0.6% | -0.309 | 0.101 | 0.707 |
| opportunity_rate | reputation_weighted | -0.006667 | [-0.02281, 0.00948] | -2.2% | -0.154 | 0.405 | 1 |
| average_cost | reputation_weighted | 0.0007612 | [0.0005451, 0.0009773] | +3.4% | 1.32 | 6.22e-08 | 7.47e-07 |
| completion_rate | reputation_weighted | 0.01342 | [0.007036, 0.0198] | +1.5% | 0.785 | 0.000176 | 0.00176 |
| hhi | reputation_adjusted | -0.004128 | [-0.01091, 0.002656] | -2.0% | -0.227 | 0.223 | 1 |
| top_agent_share | reputation_adjusted | 0.003343 | [-0.008582, 0.01527] | +1.1% | 0.105 | 0.571 | 1 |
| revenue_gini | reputation_adjusted | -0.003119 | [-0.008621, 0.002383] | -0.4% | -0.212 | 0.256 | 1 |
| opportunity_rate | reputation_adjusted | 9.252e-19 | [-0.01462, 0.01462] | +0.0% | 2.36e-17 | 1 | 1 |
| average_cost | reputation_adjusted | 0.0004278 | [0.0002565, 0.0005991] | +1.9% | 0.933 | 1.88e-05 | 0.000207 |
| completion_rate | reputation_adjusted | 0.007667 | [0.002733, 0.0126] | +0.9% | 0.58 | 0.00351 | 0.0316 |

## Limitations

- Results come from a synthetic market; agent costs, quality and reliability are drawn from the configured distributions, not measured from real agents.
- Agents follow fixed (or simple adaptive) bidding strategies; real strategic agents may respond to the mechanism differently.
- A non-significant difference is not evidence of equivalence.
- P-values are Holm-adjusted across the comparisons in this report only.

## Conclusion

- No difference in `hhi` between `reputation_weighted` and `price_only` was detected at alpha=0.05 after Holm adjustment (95% CI [-0.01573, -0.0005686]).
- No difference in `top_agent_share` between `reputation_weighted` and `price_only` was detected at alpha=0.05 after Holm adjustment (95% CI [-0.01179, 0.01739]).
- No difference in `revenue_gini` between `reputation_weighted` and `price_only` was detected at alpha=0.05 after Holm adjustment (95% CI [-0.01054, 0.0009907]).
- No difference in `opportunity_rate` between `reputation_weighted` and `price_only` was detected at alpha=0.05 after Holm adjustment (95% CI [-0.02281, 0.00948]).
- In this simulated environment, `reputation_weighted` produced higher `average_cost` than `price_only` (mean difference 0.0007612, 95% CI [0.0005451, 0.0009773]).
- In this simulated environment, `reputation_weighted` produced higher `completion_rate` than `price_only` (mean difference 0.01342, 95% CI [0.007036, 0.0198]).
- No difference in `hhi` between `reputation_adjusted` and `price_only` was detected at alpha=0.05 after Holm adjustment (95% CI [-0.01091, 0.002656]).
- No difference in `top_agent_share` between `reputation_adjusted` and `price_only` was detected at alpha=0.05 after Holm adjustment (95% CI [-0.008582, 0.01527]).
- No difference in `revenue_gini` between `reputation_adjusted` and `price_only` was detected at alpha=0.05 after Holm adjustment (95% CI [-0.008621, 0.002383]).
- No difference in `opportunity_rate` between `reputation_adjusted` and `price_only` was detected at alpha=0.05 after Holm adjustment (95% CI [-0.01462, 0.01462]).
- In this simulated environment, `reputation_adjusted` produced higher `average_cost` than `price_only` (mean difference 0.0004278, 95% CI [0.0002565, 0.0005991]).
- In this simulated environment, `reputation_adjusted` produced higher `completion_rate` than `price_only` (mean difference 0.007667, 95% CI [0.002733, 0.0126]).
