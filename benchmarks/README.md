# Benchmarks

`run_benchmarks.py` measures the in-process marketplace on synthetic markets
(first-price reverse auction, lowest-price selection, cost-plus bidders,
simulated verification, events published but not retained).

| scenario | agents | tasks |
|---|---|---|
| A | 10 | 100 |
| B | 100 | 1,000 |
| C | 1,000 | 10,000 |

```bash
python benchmarks/run_benchmarks.py          # A and B
python benchmarks/run_benchmarks.py --all    # A, B and C (about 2-3 minutes)
```

Each run writes a JSON file to `results/`. Numbers depend on the machine; do not
compare runs from different hardware.

## Latest recorded run

The 0.2.0 code just before the version bump (the JSON records 0.1.1), Python 3.12.15, macOS 26.6.2 on Apple silicon (arm64),
recorded 2026-10-04 (`results/arm64-2026-10-04.json`).

| scenario | auctions/s | bids/s | events/s | mean bids/auction | peak traced memory (MB) |
|---|---|---|---|---|---|
| A | 4,789 | 11,734 | 72,992 | 2.5 | 0 |
| B | 2,413 | 19,310 | 54,542 | 8.0 | 2 |
| C | 470 | 22,681 | 33,123 | 48.3 | 17 |

- SQLite-persisted scenario A (one transaction per run): 1,647 auctions/s.
- Reputation updates (exponential decay, 1,000 agents): about 260,000 per second.

The 0.2 capability index (agents indexed by capability, rebuilt when an agent's
capabilities change) did not measurably change these numbers: discovery was not
the bottleneck; soliciting and validating bids is.

Throughput per auction falls as markets grow because every eligible agent is
asked to bid: cost scales with bids per auction, which is why bids/s stays
roughly flat. Peak memory is measured with `tracemalloc` in a separate run and
covers Python allocations only. Large simulations should use
`Marketplace(keep_events=False, retain_results=False)` (what `simulate_market`
does by default); before that option existed, scenario C peaked at about
2.5 GB because every finished auction was kept in memory.
