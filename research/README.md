# Research experiments

Each file in `experiments/` is a complete, seeded experiment config. Running

```bash
python research/run_all.py            # everything (about 6 minutes on a laptop)
python research/run_all.py mechanisms # one experiment
```

writes `results/<name>/manifest.json` (seed, config, versions, git commit),
`results.json` (every replication) and `report.md` (hypothesis, setup,
confidence intervals, Holm-adjusted paired tests, limitations, conclusion).
The committed results were produced by the AuctionSI version and git commit
recorded in each manifest.

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
successful task. Quality-weighted selection raised completion by 1.5 points and
verified quality by 0.038 (since 0.2, quality is learned only from delivered work).

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

**[learning bidders](results/learning_bidders/report.md).** With every agent
learning its markup by UCB1, the learned winning markup was 6.8 points lower under
second price (CI 6.0 to 7.7) than under first price, as theory suggests: the bid
no longer sets the price. Buyer cost was still 37% *higher* under second price,
because the critical-value payment more than offset the lower bids, so the
hypothesis that cost would be similar or lower was **not supported**. Completion
did not change detectably.

**[reputation decay](results/reputation_decay/report.md).** When ten of thirty
agents drop from 0.98 to 0.3 reliability a third of the way through, decaying
reputation adapted faster: completion rose by 0.75 points (half-life 20) and 2.2
points (half-life 5) over full history, with buyer utility up 0.8% and 2.1%. The
effects are real but small, because risk-adjusted selection with full history
also reacts once failures accumulate.

**[collusion screens](results/collusion_screens/report.md).** A five-agent
bid-rotation cartel in a twelve-agent market raised average buyer cost by 19.5%
(CI 17% to 22%). The two screens averaged over the market (bid coefficient of
variation, relative distance between the two lowest bids) did **not** move
detectably after Holm adjustment. Averaged screens are too blunt here; per-auction
or per-group screens would be needed to detect this cartel.

**[factorial](results/factorial/report.md).** A 2 x 2 x 2 sweep of payment rule,
selection policy and reliability spread. Wide reliability spread (0.4 to 1.0)
cost about 27 completion points under lowest-price selection and about 23 under
risk-adjusted selection, so risk adjustment recovered only part of the loss.
When agents were all reliable, risk adjustment changed nothing but cost.
Second price raised cost in every cell and did not change completion.

## Adding an experiment

Copy a YAML file, change the hypothesis, environment and arms, and run it. Any
registered plugin name works in `mechanism`, `policy`, `reputation` and
`settlement`; `environment` overrides inside an arm are deep-merged into the base
environment. `environment.adversaries` adds colluders, Sybils and overstaters,
`environment.changes` changes agents mid-run, and `factors` crosses every level
of each factor into arms. Keep conclusions to what the report supports.
