# Experiment report: market_size

The same task stream (300 tasks) served by markets of 10, 50, 100, 500 and 1000 synthetic agents. Arms differ in population, so they are paired by replication seed rather than by identical agents.


## Hypothesis

More competitors lower the average price paid and raise completion, with diminishing returns; concentration of wins (HHI) falls as the market grows.


## Experimental setup

- Replications: 20 per arm (common random numbers across arms)
- Seed: 7
- AuctionSI 0.1.1, Python 3.12.15, git commit 0162c05e54894a8575355e5fb4d3f5d47dd18a08+dirty
- Baseline arm: `n10`
- Confidence level: 95%; alpha: 0.05

### Parameters

- Agents: {'count': 10, 'capabilities': ['research', 'data_analysis', 'sql', 'optimization'], 'capability_distribution': 'mixed', 'capabilities_per_agent': (1, 3), 'cost_distribution': 'lognormal', 'variable_cost_ratio': 0.01, 'quality_distribution': 'beta', 'quality_spread': 0.05, 'latency_distribution': 'lognormal', 'reliability_distribution': 'beta', 'capacity_distribution': 1, 'strategy': 'cost_plus', 'quality_report_bias': 0.0}
- Tasks: {'count': 300, 'task_types': ['research', 'data_analysis', 'sql', 'optimization'], 'arrival_rate': 1.0, 'budget_distribution': 'lognormal', 'deadline_distribution': 'uniform', 'complexity_distribution': 'lognormal', 'min_quality': None, 'value_multiplier': 1.5}
- Defaults: mechanism=first_price_reverse, policy=lowest_price, reputation=multi_dimensional, settlement=pay_on_pass

### Arms

- `n10`: {'environment': {'agents': {'count': 10}}}
- `n50`: {'environment': {'agents': {'count': 50}}}
- `n100`: {'environment': {'agents': {'count': 100}}}
- `n500`: {'environment': {'agents': {'count': 500}}}
- `n1000`: {'environment': {'agents': {'count': 1000}}}

## Results

### average_cost

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| n10 | 20 | 0.04356 | [0.04089, 0.04623] | 0.0057 | 0.04429 |
| n50 | 20 | 0.02572 | [0.02429, 0.02715] | 0.003051 | 0.02549 |
| n100 | 20 | 0.0208 | [0.01986, 0.02175] | 0.002022 | 0.02128 |
| n500 | 20 | 0.01484 | [0.01434, 0.01534] | 0.001069 | 0.01468 |
| n1000 | 20 | 0.01312 | [0.01267, 0.01357] | 0.000957 | 0.01317 |

### completion_rate

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| n10 | 20 | 0.5975 | [0.5591, 0.6359] | 0.08198 | 0.5817 |
| n50 | 20 | 0.9057 | [0.8924, 0.919] | 0.02839 | 0.91 |
| n100 | 20 | 0.9058 | [0.8954, 0.9163] | 0.02229 | 0.9067 |
| n500 | 20 | 0.8958 | [0.8866, 0.9051] | 0.01979 | 0.8933 |
| n1000 | 20 | 0.9053 | [0.8945, 0.9161] | 0.02308 | 0.9067 |

### hhi

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| n10 | 20 | 0.1194 | [0.1142, 0.1247] | 0.01117 | 0.1181 |
| n50 | 20 | 0.07059 | [0.06575, 0.07543] | 0.01035 | 0.06898 |
| n100 | 20 | 0.07482 | [0.06903, 0.08061] | 0.01237 | 0.07475 |
| n500 | 20 | 0.08029 | [0.07492, 0.08566] | 0.01147 | 0.07923 |
| n1000 | 20 | 0.08423 | [0.07977, 0.08869] | 0.009532 | 0.08448 |

### average_bid_count

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| n10 | 20 | 1.305 | [1.169, 1.441] | 0.2908 | 1.305 |
| n50 | 20 | 18.54 | [17.76, 19.33] | 1.681 | 18.57 |
| n100 | 20 | 42.57 | [41.44, 43.69] | 2.403 | 43.08 |
| n500 | 20 | 234.3 | [231.6, 237.1] | 5.922 | 234.5 |
| n1000 | 20 | 472.5 | [469.8, 475.2] | 5.75 | 471.8 |

### cost_efficiency

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| n10 | 20 | 0.9978 | [0.9966, 0.999] | 0.002627 | 0.9979 |
| n50 | 20 | 0.999 | [0.9983, 0.9996] | 0.001351 | 0.9995 |
| n100 | 20 | 0.9995 | [0.9993, 0.9998] | 0.0006002 | 0.9999 |
| n500 | 20 | 0.9997 | [0.9993, 1] | 0.0008902 | 1 |
| n1000 | 20 | 0.9998 | [0.9996, 1] | 0.00041 | 1 |

### opportunity_rate

| arm | n | mean | 95% CI | sd | median |
|---|---|---|---|---|---|
| n10 | 20 | 1 | [1, 1] | 0 | 1 |
| n50 | 20 | 0.446 | [0.4296, 0.4624] | 0.035 | 0.44 |
| n100 | 20 | 0.223 | [0.2134, 0.2326] | 0.02055 | 0.22 |
| n500 | 20 | 0.0418 | [0.03996, 0.04364] | 0.003942 | 0.042 |
| n1000 | 20 | 0.0206 | [0.01925, 0.02195] | 0.002891 | 0.0205 |

## Statistical tests

Paired t-tests on per-replication differences (treatment - baseline). Effect size is Cohen's d_z.

| metric | treatment | mean diff | CI | relative | d_z | p | p (Holm) |
|---|---|---|---|---|---|---|---|
| average_cost | n50 | -0.01784 | [-0.02064, -0.01504] | -41.0% | -2.98 | 4.34e-11 | 3.47e-10 |
| completion_rate | n50 | 0.3082 | [0.263, 0.3534] | +51.6% | 3.19 | 1.32e-11 | 1.19e-10 |
| hhi | n50 | -0.04886 | [-0.05506, -0.04265] | -40.9% | -3.69 | 1.04e-12 | 1.45e-11 |
| average_bid_count | n50 | 17.24 | [16.49, 17.98] | +1321.0% | 10.8 | 2.31e-21 | 3.92e-20 |
| cost_efficiency | n50 | 0.001159 | [-0.000201, 0.00252] | +0.1% | 0.399 | 0.0904 | 0.0904 |
| opportunity_rate | n50 | -0.554 | [-0.5704, -0.5376] | -55.4% | -15.8 | 1.75e-24 | 3.14e-23 |
| average_cost | n100 | -0.02276 | [-0.02574, -0.01978] | -52.2% | -3.57 | 1.82e-12 | 2.31e-11 |
| completion_rate | n100 | 0.3083 | [0.268, 0.3487] | +51.6% | 3.58 | 1.78e-12 | 2.31e-11 |
| hhi | n100 | -0.04463 | [-0.05207, -0.03719] | -37.4% | -2.81 | 1.2e-10 | 8.4e-10 |
| average_bid_count | n100 | 41.26 | [40.17, 42.35] | +3161.8% | 17.7 | 2.15e-25 | 4.08e-24 |
| cost_efficiency | n100 | 0.00174 | [0.0006124, 0.002869] | +0.2% | 0.722 | 0.00441 | 0.0132 |
| opportunity_rate | n100 | -0.777 | [-0.7866, -0.7674] | -77.7% | -37.8 | 1.16e-31 | 2.33e-30 |
| average_cost | n500 | -0.02872 | [-0.03136, -0.02609] | -65.9% | -5.11 | 2.8e-15 | 4.2e-14 |
| completion_rate | n500 | 0.2983 | [0.2582, 0.3385] | +49.9% | 3.48 | 2.92e-12 | 2.92e-11 |
| hhi | n500 | -0.03916 | [-0.04632, -0.03199] | -32.8% | -2.56 | 5.8e-10 | 3.48e-09 |
| average_bid_count | n500 | 233 | [230.2, 235.8] | +17855.8% | 39.3 | 5.74e-32 | 1.21e-30 |
| cost_efficiency | n500 | 0.001889 | [0.000583, 0.003195] | +0.2% | 0.677 | 0.00693 | 0.0139 |
| opportunity_rate | n500 | -0.9582 | [-0.96, -0.9564] | -95.8% | -243 | 5.19e-47 | 1.19e-45 |
| average_cost | n1000 | -0.03044 | [-0.03306, -0.02782] | -69.9% | -5.44 | 8.71e-16 | 1.39e-14 |
| completion_rate | n1000 | 0.3078 | [0.2672, 0.3485] | +51.5% | 3.54 | 2.09e-12 | 2.31e-11 |
| hhi | n1000 | -0.03522 | [-0.04204, -0.0284] | -29.5% | -2.42 | 1.48e-09 | 7.4e-09 |
| average_bid_count | n1000 | 471.2 | [468.5, 473.9] | +36108.8% | 81.7 | 5.2e-38 | 1.14e-36 |
| cost_efficiency | n1000 | 0.00201 | [0.000794, 0.003225] | +0.2% | 0.774 | 0.00262 | 0.0105 |
| opportunity_rate | n1000 | -0.9794 | [-0.9808, -0.978] | -97.9% | -339 | 9.48e-50 | 2.28e-48 |

## Limitations

- Results come from a synthetic market; agent costs, quality and reliability are drawn from the configured distributions, not measured from real agents.
- Agents follow fixed (or simple adaptive) bidding strategies; real strategic agents may respond to the mechanism differently.
- A non-significant difference is not evidence of equivalence.
- P-values are Holm-adjusted across the comparisons in this report only.

## Conclusion

- In this simulated environment, `n50` produced lower `average_cost` than `n10` (mean difference -0.01784, 95% CI [-0.02064, -0.01504]).
- In this simulated environment, `n50` produced higher `completion_rate` than `n10` (mean difference 0.3082, 95% CI [0.263, 0.3534]).
- In this simulated environment, `n50` produced lower `hhi` than `n10` (mean difference -0.04886, 95% CI [-0.05506, -0.04265]).
- In this simulated environment, `n50` produced higher `average_bid_count` than `n10` (mean difference 17.24, 95% CI [16.49, 17.98]).
- No difference in `cost_efficiency` between `n50` and `n10` was detected at alpha=0.05 after Holm adjustment (95% CI [-0.000201, 0.00252]).
- In this simulated environment, `n50` produced lower `opportunity_rate` than `n10` (mean difference -0.554, 95% CI [-0.5704, -0.5376]).
- In this simulated environment, `n100` produced lower `average_cost` than `n10` (mean difference -0.02276, 95% CI [-0.02574, -0.01978]).
- In this simulated environment, `n100` produced higher `completion_rate` than `n10` (mean difference 0.3083, 95% CI [0.268, 0.3487]).
- In this simulated environment, `n100` produced lower `hhi` than `n10` (mean difference -0.04463, 95% CI [-0.05207, -0.03719]).
- In this simulated environment, `n100` produced higher `average_bid_count` than `n10` (mean difference 41.26, 95% CI [40.17, 42.35]).
- In this simulated environment, `n100` produced higher `cost_efficiency` than `n10` (mean difference 0.00174, 95% CI [0.0006124, 0.002869]).
- In this simulated environment, `n100` produced lower `opportunity_rate` than `n10` (mean difference -0.777, 95% CI [-0.7866, -0.7674]).
- In this simulated environment, `n500` produced lower `average_cost` than `n10` (mean difference -0.02872, 95% CI [-0.03136, -0.02609]).
- In this simulated environment, `n500` produced higher `completion_rate` than `n10` (mean difference 0.2983, 95% CI [0.2582, 0.3385]).
- In this simulated environment, `n500` produced lower `hhi` than `n10` (mean difference -0.03916, 95% CI [-0.04632, -0.03199]).
- In this simulated environment, `n500` produced higher `average_bid_count` than `n10` (mean difference 233, 95% CI [230.2, 235.8]).
- In this simulated environment, `n500` produced higher `cost_efficiency` than `n10` (mean difference 0.001889, 95% CI [0.000583, 0.003195]).
- In this simulated environment, `n500` produced lower `opportunity_rate` than `n10` (mean difference -0.9582, 95% CI [-0.96, -0.9564]).
- In this simulated environment, `n1000` produced lower `average_cost` than `n10` (mean difference -0.03044, 95% CI [-0.03306, -0.02782]).
- In this simulated environment, `n1000` produced higher `completion_rate` than `n10` (mean difference 0.3078, 95% CI [0.2672, 0.3485]).
- In this simulated environment, `n1000` produced lower `hhi` than `n10` (mean difference -0.03522, 95% CI [-0.04204, -0.0284]).
- In this simulated environment, `n1000` produced higher `average_bid_count` than `n10` (mean difference 471.2, 95% CI [468.5, 473.9]).
- In this simulated environment, `n1000` produced higher `cost_efficiency` than `n10` (mean difference 0.00201, 95% CI [0.000794, 0.003225]).
- In this simulated environment, `n1000` produced lower `opportunity_rate` than `n10` (mean difference -0.9794, 95% CI [-0.9808, -0.978]).
