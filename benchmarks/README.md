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

AuctionSI 0.1.0.dev0, Python 3.12.15, macOS 26.6.2 on Apple silicon (arm64),
recorded 2026-10-03 (`results/arm64-2026-10-03.json`).

| scenario | auctions/s | bids/s | events/s | mean bids/auction | peak traced memory (MB) |
|---|---|---|---|---|---|
| A | 4,715 | 11,551 | 71,855 | 2.5 | 0 |
| B | 2,449 | 19,600 | 55,360 | 8.0 | 2 |
| C | 456 | 22,032 | 32,175 | 48.3 | 17 |

- SQLite-persisted scenario A (one transaction per run): 1,616 auctions/s.
- Reputation updates (exponential decay, 1,000 agents): about 250,000 per second.

Throughput per auction falls as markets grow because every eligible agent is
asked to bid: cost scales with bids per auction, which is why bids/s stays
roughly flat. Peak memory is measured with `tracemalloc` in a separate run and
covers Python allocations only. Large simulations should use
`Marketplace(keep_events=False, retain_results=False)` (what `simulate_market`
does by default); before that option existed, scenario C peaked at about
2.5 GB because every finished auction was kept in memory.
