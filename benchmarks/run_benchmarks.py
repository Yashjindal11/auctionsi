"""AuctionSI benchmarks. Numbers are measured on the machine that runs this script.

    python benchmarks/run_benchmarks.py            # A and B
    python benchmarks/run_benchmarks.py --all      # A, B and C (slow)
    python benchmarks/run_benchmarks.py --only C

Results are written to benchmarks/results/<host>-<date>.json and printed as a
Markdown table.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import platform
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

from auctionsi import __version__
from auctionsi.market import EventBus, IdGenerator, ManualClock, Marketplace
from auctionsi.observability import MarketCounters
from auctionsi.reputation import ExponentialDecay, MultiDimensionalReputation, Observation
from auctionsi.simulation import SimulatedQualityVerifier, generate_agents, generate_tasks
from auctionsi.storage import SQLiteStore

SCENARIOS = {"A": (10, 100), "B": (100, 1_000), "C": (1_000, 10_000)}


def run_market(
    n_agents: int, n_tasks: int, *, store: SQLiteStore | None = None
) -> dict[str, float]:
    agents = generate_agents(n_agents, seed=1)
    tasks = generate_tasks(n_tasks, seed=2, arrival_rate=max(1.0, n_agents / 10))
    bus = EventBus()
    counters = MarketCounters()
    events = [0]
    bus.subscribe(counters)
    bus.subscribe(lambda e: events.__setitem__(0, events[0] + 1))
    clock = ManualClock()
    market = Marketplace(
        clock=clock,
        ids=IdGenerator(),
        bus=bus,
        keep_events=False,
        retain_results=False,
        verifier=SimulatedQualityVerifier(),
        store=store,
    )
    for agent in agents:
        market.register(agent)
    start = time.perf_counter()
    if store is not None:
        with store.batch():
            for task in tasks:
                clock.set(task.created_at)
                market.submit_task(task)
    else:
        for task in tasks:
            clock.set(task.created_at)
            market.submit_task(task)
    elapsed = time.perf_counter() - start
    snap = counters.snapshot()
    return {
        "agents": n_agents,
        "tasks": n_tasks,
        "seconds": elapsed,
        "auctions_per_second": n_tasks / elapsed,
        "events": events[0],
        "events_per_second": events[0] / elapsed,
        "bids": snap["bids_submitted"],
        "bids_per_second": snap["bids_submitted"] / elapsed,
        "mean_bids_per_auction": snap["average_bid_count"],
    }


def peak_memory_mb(n_agents: int, n_tasks: int) -> float:
    tracemalloc.start()
    run_market(n_agents, n_tasks)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak / 1e6


def reputation_updates(n: int = 200_000) -> dict[str, float]:
    rep = MultiDimensionalReputation(decay=ExponentialDecay(half_life=50))
    observations = [
        Observation(
            agent_id=f"a{i % 1000}",
            task_type=f"t{i % 4}",
            success=i % 7 != 0,
            quality=0.8,
            on_time=True,
            latency=10.0,
            price=0.05,
            estimated_quality=0.85,
            estimated_latency=9.0,
        )
        for i in range(n)
    ]
    start = time.perf_counter()
    for obs in observations:
        rep.record(obs)
    elapsed = time.perf_counter() - start
    return {"updates": n, "seconds": elapsed, "updates_per_second": n / elapsed}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="include scenario C")
    parser.add_argument("--only", choices=sorted(SCENARIOS))
    parser.add_argument("--no-memory", action="store_true")
    args = parser.parse_args()
    names = [args.only] if args.only else (["A", "B", "C"] if args.all else ["A", "B"])

    results: dict[str, object] = {
        "auctionsi_version": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "date": dt.date.today().isoformat(),
        "scenarios": {},
    }
    scenarios: dict[str, dict[str, float]] = {}
    for name in names:
        n_agents, n_tasks = SCENARIOS[name]
        print(
            f"scenario {name}: {n_agents} agents, {n_tasks} tasks ...", file=sys.stderr, flush=True
        )
        row = run_market(n_agents, n_tasks)
        if not args.no_memory:
            row["peak_memory_mb"] = peak_memory_mb(n_agents, n_tasks)
        scenarios[name] = row
    results["scenarios"] = scenarios

    print("sqlite persistence (scenario A) ...", file=sys.stderr, flush=True)
    with tempfile.TemporaryDirectory() as tmp:
        store = SQLiteStore(Path(tmp) / "bench.db")
        results["sqlite_A"] = run_market(*SCENARIOS["A"], store=store)
        store.close()
    print("reputation updates ...", file=sys.stderr, flush=True)
    results["reputation"] = reputation_updates()

    out_dir = Path(__file__).parent / "results"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{platform.machine()}-{results['date']}.json"
    out.write_text(json.dumps(results, indent=2))

    print(f"\nAuctionSI {__version__}, Python {results['python']}, {results['platform']}\n")
    print(
        "| scenario | agents | tasks | auctions/s | bids/s | events/s | mean bids/auction | peak MB |"
    )
    print("|---|---|---|---|---|---|---|---|")
    for name, r in scenarios.items():
        mem = f"{r['peak_memory_mb']:.0f}" if "peak_memory_mb" in r else "-"
        print(
            f"| {name} | {r['agents']:.0f} | {r['tasks']:.0f} | {r['auctions_per_second']:,.0f} | "
            f"{r['bids_per_second']:,.0f} | {r['events_per_second']:,.0f} | "
            f"{r['mean_bids_per_auction']:.1f} | {mem} |"
        )
    sq = results["sqlite_A"]
    rep = results["reputation"]
    assert isinstance(sq, dict) and isinstance(rep, dict)
    print(f"\nSQLite-persisted scenario A: {sq['auctions_per_second']:,.0f} auctions/s")
    print(f"Reputation updates: {rep['updates_per_second']:,.0f}/s")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
