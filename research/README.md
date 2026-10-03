# Research experiments

Each file in `experiments/` is a complete, seeded experiment config. Running

```bash
python research/run_all.py            # everything (about 5 minutes on a laptop)
python research/run_all.py mechanisms # one experiment
```

writes `results/<name>/manifest.json` (seed, config, versions, git commit),
`results.json` (every replication) and `report.md` (hypothesis, setup,
confidence intervals, Holm-adjusted paired tests, limitations, conclusion).
The committed results were produced by AuctionSI 0.1.0 on the date in each
manifest.

All of these are **synthetic markets**: agent costs, quality and reliability
come from the distributions in each config. They show what the framework can
measure and how the built-in designs behave in these specific environments, not
how real agent markets behave.

## What the committed runs show

Effects are mean paired differences against the first arm, with 95% confidence
intervals (see each report for the full tables).

**[mechanisms](results/mechanisms/report.md).** With bidders that do not change
strategy, the second-price rule raised total buyer cost by 19.5% (CI 17.5% to
21.5% relative) and left allocation, quality and completion unchanged, as
expected when only the payment rule differs. Risk-adjusted selection raised
completion by 3.8 points and buyer utility by 3.5%, at 9.2% higher cost per
successful task. Quality-weighted selection raised completion by 4.3 points and
quality by 0.024.

**[reliability](results/reliability/report.md).** When reliability ranges from
0.4 to 1.0, risk-adjusted selection completed 4.8 points more tasks than
lowest-price selection and raised total surplus by 7.3%; reputation-adjusted
cost was in between. Concentration (HHI) did not change detectably.

**[reputation](results/reputation/report.md).** Every learned reputation variant
completed 6.6 to 8.4 points more tasks than using bid confidence alone, and
spread work across more agents (opportunity rate +19 to +21%). In this
stationary market the per-task, decaying and global variants were close to each
other; the global profile did slightly best, plausibly because it learns from
more observations per agent.

**[strategies](results/strategies/report.md).** Strategies mostly move surplus
between buyer and agents: aggressive bidding cut average cost by 20.8% and made
agent utility negative; greedy bidding (near the budget) quadrupled average cost.
Total surplus changed little except under greedy bidding (-9.3%): every greedy
agent bids the same fraction of the budget, so ties are broken by agent id
rather than by cost and higher-cost agents win more often.

**[concentration](results/concentration/report.md).** The hypothesis that
weighting reputation concentrates work was **not supported** here: no
concentration measure changed detectably after Holm adjustment, while cost rose
slightly (+1.9% to +3.4%) and completion rose slightly.

**[market size](results/market_size/report.md).** Going from 10 to 50 agents cut
the average price paid by 41% and raised completion by 31 points; further growth
kept lowering price with diminishing returns (-70% at 1,000 agents). Most of the
completion gain comes from having *any* capable, available agent: at 10 agents
many tasks found nobody free.

## Adding an experiment

Copy a YAML file, change the hypothesis, environment and arms, and run it. Any
registered plugin name works in `mechanism`, `policy`, `reputation` and
`settlement`; `environment` overrides inside an arm are deep-merged into the base
environment. Keep conclusions to what the report supports.
