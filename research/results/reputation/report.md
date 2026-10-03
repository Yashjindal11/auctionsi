# Experiment report: reputation

Risk-adjusted selection whose failure estimates come from different reputation systems: none (bid confidence only), full-history per task type, exponentially decaying, and a single global profile per agent.


## Hypothesis

Any learned reputation improves completion over no reputation when agents differ in reliability; the variants differ little from each other in a stationary market.


## Experimental setup

- Replications: 30 per arm (common random numbers across arms)
- Seed: 13
- AuctionSI 0.1.1, Python 3.12.15, git commit 0162c05e54894a8575355e5fb4d3f5d47dd18a08+dirty
- Baseline arm: `none`
- Confidence level: 95%; alpha: 0.05

### Parameters

- Agents: {'count': 30, 'capabilities': ['research', 'data_analysis', 'sql', 'optimization'], 'capability_distribution': 'mixed', 'capabilities_per_agent': (1, 3), 'cost_distribution': 'lognormal', 'variable_cost_ratio': 0.01, 'quality_distribution': 'beta', 'quality_spread': 0.05, 'latency_distribution': 'lognormal', 'reliability_distribution': {'name': 'uniform', 'low': 0.4, 'high': 1.0}, 'capacity_distribution': 1, 'strategy': 'cost_plus', 'quality_report_bias': 0.0}
- Tasks: {'count': 500, 'task_types': ['research', 'data_analysis', 'sql', 'optimization'], 'arrival_rate': 1.0, 'budget_distribution': 'lognormal', 'deadline_distribution': 'uniform', 'complexity_distribution': 'lognormal', 'min_quality': None, 'value_multiplier': 1.5}
- Defaults: mechanism=first_price_reverse, policy={'name': 'risk_adjusted_cost', 'newcomer_failure_probability': 0.2, 'min_observations': 3}, reputation=multi_dimensional, settlement=pay_on_pass

### Arms

- `none`: {'reputation': 'none'}
- `full_history`: {'reputation': {'name': 'multi_dimensional'}}
- `decaying`: {'reputation': {'name': 'multi_dimensional', 'decay': {'name': 'exponential', 'half_life': 10}}}
- `global`: {'reputation': {'name': 'multi_dimensional', 'task_specific': False}}

## Results

### completion_rate

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| none | 30 | 0.6994 | [0.6844, 0.7144] | 0.04027 | 0.691 |
| full_history | 30 | 0.7666 | [0.7516, 0.7816] | 0.04017 | 0.764 |
| decaying | 30 | 0.7652 | [0.7503, 0.7801] | 0.03984 | 0.767 |
| global | 30 | 0.7833 | [0.7691, 0.7976] | 0.03821 | 0.781 |

### average_cost

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| none | 30 | 0.02924 | [0.02779, 0.03069] | 0.003878 | 0.02923 |
| full_history | 30 | 0.03412 | [0.03243, 0.03581] | 0.004531 | 0.0351 |
| decaying | 30 | 0.03432 | [0.03262, 0.03603] | 0.004572 | 0.03524 |
| global | 30 | 0.03497 | [0.03329, 0.03664] | 0.004491 | 0.03558 |

### buyer_utility

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| none | 30 | 55.61 | [53.97, 57.26] | 4.418 | 54.77 |
| full_history | 30 | 59.47 | [57.76, 61.18] | 4.578 | 59.46 |
| decaying | 30 | 59.15 | [57.48, 60.81] | 4.456 | 59.98 |
| global | 30 | 60.48 | [58.8, 62.16] | 4.49 | 60.88 |

### hhi

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| none | 30 | 0.07875 | [0.07326, 0.08424] | 0.0147 | 0.075 |
| full_history | 30 | 0.07225 | [0.06756, 0.07694] | 0.01257 | 0.06788 |
| decaying | 30 | 0.07082 | [0.06611, 0.07553] | 0.01262 | 0.06697 |
| global | 30 | 0.07525 | [0.0698, 0.0807] | 0.0146 | 0.07109 |

### opportunity_rate

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| none | 30 | 0.7467 | [0.717, 0.7764] | 0.07956 | 0.7667 |
| full_history | 30 | 0.8889 | [0.8655, 0.9123] | 0.06272 | 0.9 |
| decaying | 30 | 0.9022 | [0.8803, 0.9241] | 0.05868 | 0.9 |
| global | 30 | 0.9011 | [0.8788, 0.9234] | 0.05968 | 0.9167 |

## Statistical tests

Paired t-tests on per-replication differences (treatment - baseline). Effect size is Cohen's d_z.

| metric | treatment | mean diff | CI | relative | d_z | p | p (Holm) |
|---|---|---|---|---|---|---|---|
| completion_rate | full_history | 0.0672 | [0.05794, 0.07646] | +9.6% | 2.71 | 4.47e-15 | 4.92e-14 |
| average_cost | full_history | 0.004879 | [0.004383, 0.005376] | +16.7% | 3.67 | 1.43e-18 | 1.86e-17 |
| buyer_utility | full_history | 3.856 | [3.051, 4.661] | +6.9% | 1.79 | 1.04e-10 | 7.3e-10 |
| hhi | full_history | -0.006497 | [-0.01053, -0.002468] | -8.3% | -0.602 | 0.00258 | 0.00516 |
| opportunity_rate | full_history | 0.1422 | [0.1123, 0.1722] | +19.0% | 1.77 | 1.27e-10 | 7.57e-10 |
| completion_rate | decaying | 0.0658 | [0.05623, 0.07537] | +9.4% | 2.57 | 1.78e-14 | 1.6e-13 |
| average_cost | decaying | 0.005084 | [0.004579, 0.00559] | +17.4% | 3.75 | 7.69e-19 | 1.08e-17 |
| buyer_utility | decaying | 3.533 | [2.686, 4.379] | +6.4% | 1.56 | 2.1e-09 | 8.38e-09 |
| hhi | decaying | -0.007927 | [-0.01176, -0.004092] | -10.1% | -0.772 | 0.000215 | 0.000645 |
| opportunity_rate | decaying | 0.1556 | [0.1228, 0.1883] | +20.8% | 1.77 | 1.26e-10 | 7.57e-10 |
| completion_rate | global | 0.08393 | [0.07513, 0.09274] | +12.0% | 3.56 | 3.27e-18 | 3.93e-17 |
| average_cost | global | 0.00573 | [0.005191, 0.006268] | +19.6% | 3.98 | 1.62e-19 | 2.43e-18 |
| buyer_utility | global | 4.865 | [4.169, 5.561] | +8.7% | 2.61 | 1.16e-14 | 1.16e-13 |
| hhi | global | -0.003493 | [-0.007547, 0.0005611] | -4.4% | -0.322 | 0.0886 | 0.0886 |
| opportunity_rate | global | 0.1544 | [0.1239, 0.185] | +20.7% | 1.89 | 3.13e-11 | 2.5e-10 |

## Limitations

- Agent reliability is constant within a run, so the advantage decay is designed for (adapting to agents that change) is not exercised.
- Results come from a synthetic market; agent costs, quality and reliability are drawn from the configured distributions, not measured from real agents.
- Agents follow fixed (or simple adaptive) bidding strategies; real strategic agents may respond to the mechanism differently.
- A non-significant difference is not evidence of equivalence.
- P-values are Holm-adjusted across the comparisons in this report only.

## Conclusion

- In this simulated environment, `full_history` produced higher `completion_rate` than `none` (mean difference 0.0672, 95% CI [0.05794, 0.07646]).
- In this simulated environment, `full_history` produced higher `average_cost` than `none` (mean difference 0.004879, 95% CI [0.004383, 0.005376]).
- In this simulated environment, `full_history` produced higher `buyer_utility` than `none` (mean difference 3.856, 95% CI [3.051, 4.661]).
- In this simulated environment, `full_history` produced lower `hhi` than `none` (mean difference -0.006497, 95% CI [-0.01053, -0.002468]).
- In this simulated environment, `full_history` produced higher `opportunity_rate` than `none` (mean difference 0.1422, 95% CI [0.1123, 0.1722]).
- In this simulated environment, `decaying` produced higher `completion_rate` than `none` (mean difference 0.0658, 95% CI [0.05623, 0.07537]).
- In this simulated environment, `decaying` produced higher `average_cost` than `none` (mean difference 0.005084, 95% CI [0.004579, 0.00559]).
- In this simulated environment, `decaying` produced higher `buyer_utility` than `none` (mean difference 3.533, 95% CI [2.686, 4.379]).
- In this simulated environment, `decaying` produced lower `hhi` than `none` (mean difference -0.007927, 95% CI [-0.01176, -0.004092]).
- In this simulated environment, `decaying` produced higher `opportunity_rate` than `none` (mean difference 0.1556, 95% CI [0.1228, 0.1883]).
- In this simulated environment, `global` produced higher `completion_rate` than `none` (mean difference 0.08393, 95% CI [0.07513, 0.09274]).
- In this simulated environment, `global` produced higher `average_cost` than `none` (mean difference 0.00573, 95% CI [0.005191, 0.006268]).
- In this simulated environment, `global` produced higher `buyer_utility` than `none` (mean difference 4.865, 95% CI [4.169, 5.561]).
- No difference in `hhi` between `global` and `none` was detected at alpha=0.05 after Holm adjustment (95% CI [-0.007547, 0.0005611]).
- In this simulated environment, `global` produced higher `opportunity_rate` than `none` (mean difference 0.1544, 95% CI [0.1239, 0.185]).
