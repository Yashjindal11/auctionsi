from __future__ import annotations

import io
import json

from auctionsi import visualization as viz
from auctionsi.experiments import compare_mechanisms
from auctionsi.mechanisms import FirstPriceReverseAuction, SecondPriceReverseAuction
from auctionsi.observability import JsonEventLogger, MarketCounters
from auctionsi.simulation import simulate_market
from auctionsi.verification import MetricThresholdVerifier
from conftest import MarketFactory, ScriptedAgent, task


def test_json_logger_and_counters(market_factory: MarketFactory) -> None:
    stream = io.StringIO()
    market = market_factory(verifier=MetricThresholdVerifier("quality", 0.95))
    JsonEventLogger(stream).attach(market.bus)
    counters = MarketCounters()
    counters.attach(market.bus)
    market.register(ScriptedAgent("good", 0.05, quality=0.99))
    market.register(ScriptedAgent("bad", 0.01, quality=0.5))
    market.register(ScriptedAgent("over", 9.0))
    market.submit_task(task("t1", budget=1.0))
    market.clock.set(10)  # type: ignore[attr-defined]
    market.submit_task(task("t2", budget=1.0))

    rows = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert {"timestamp", "event", "seq"} <= set(rows[0])
    assert all("data" not in r for r in rows)
    bid_rows = [r for r in rows if r["event"] == "BidSubmitted"]
    assert all("price" in r and "agent_id" in r for r in bid_rows)
    snap = counters.snapshot()
    assert snap["auctions_created"] == 2
    assert snap["bids_rejected"] == 2
    assert snap["bids_submitted"] == 4
    assert snap["verification_failure_rate"] == 1.0
    assert snap["average_bid_count"] == 2.0
    detailed = JsonEventLogger(io.StringIO(), include_data=True)
    assert "data" in detailed.record(market.log.events[-1])  # type: ignore[union-attr]


def test_figures_build(market_factory: MarketFactory) -> None:
    market = market_factory()
    for name, price in [("a", 0.1), ("b", 0.2)]:
        market.register(ScriptedAgent(name, price))
    result = market.submit_task(task())
    assert viz.bid_distribution(result).data[0].y == (0.1, 0.2)
    assert viz.auction_timeline(result).data
    assert viz.event_counts(result)["BidSubmitted"] == 2

    sim = simulate_market(8, 60, seed=1)
    for fig in (
        viz.market_share(sim),
        viz.price_distribution(sim),
        viz.quality_vs_price(sim),
        viz.reputation_vs_win_rate(sim),
        viz.concentration_over_time(sim, 20),
    ):
        assert fig.layout.title.text

    exp = compare_mechanisms(
        [FirstPriceReverseAuction(), SecondPriceReverseAuction()],
        environment={"agents": {"count": 5}, "tasks": {"count": 20}},
        replications=2,
        metrics=["total_cost"],
    )
    assert len(viz.mechanism_comparison(exp, "total_cost").data[0].x) == 2
