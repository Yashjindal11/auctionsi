from __future__ import annotations

import json
from pathlib import Path

import pytest

from auctionsi.cli.main import main
from auctionsi.core import Bid
from auctionsi.market.replay import replay_auction
from auctionsi.reports import calibration_report, calibration_table, reliability_bins
from auctionsi.reputation import AgentFeatures, Observation
from auctionsi.selection import ExplorationBonus, LowestPrice
from auctionsi.storage import InMemoryStore
from conftest import MarketFactory, ScriptedAgent, task


def obs(agent: str, claimed: float, delivered: float, success: bool = True) -> Observation:
    return Observation(
        agent_id=agent,
        task_type="x",
        success=success,
        quality=delivered,
        on_time=True,
        latency=10.0,
        price=1.0,
        estimated_quality=claimed,
        estimated_latency=12.0,
    )


def test_calibration_table_and_bins() -> None:
    data = [obs("liar", 0.95, 0.6), obs("liar", 0.95, 0.7), obs("honest", 0.8, 0.8)]
    rows = {r["agent_id"]: r for r in calibration_table(data)}
    assert rows["liar"]["quality_bias"] == pytest.approx(0.3)
    assert rows["honest"]["quality_mae"] == pytest.approx(0.0)
    assert rows["honest"]["latency_relative_error"] == pytest.approx(0.2)
    bins = {b["claimed_from"]: b for b in reliability_bins(data)}
    assert bins[0.9]["count"] == 2
    assert bins[0.9]["mean_delivered"] == pytest.approx(0.65)
    assert "| liar | 2 |" in calibration_report(data)


def test_calibration_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init", "."])
    main(["agent", "register", "agents.yaml"])
    main(["task", "submit", "task.yaml"])
    capsys.readouterr()
    assert main(["calibration", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert {"agents", "bins"} == set(data)
    assert main(["calibration"]) == 0
    assert "# Calibration report" in capsys.readouterr().out


def bid(agent: str, price: float) -> Bid:
    return Bid(bid_id=f"b-{agent}", task_id="t", agent_id=agent, auction_id="x", price=price)


def test_exploration_bonus_lets_newcomers_win_close_calls() -> None:
    bids = [bid("veteran", 1.00), bid("newcomer", 1.005)]
    features = {
        "veteran": AgentFeatures("veteran", observations=99),
        "newcomer": AgentFeatures("newcomer", observations=0),
    }
    policy = ExplorationBonus(LowestPrice(), weight=0.02)
    ranked = policy.rank(bids, task(), features)
    assert ranked[0].agent_id == "newcomer"
    assert ranked[0].contributions["exploration"] == pytest.approx(0.02)
    assert sum(ranked[0].contributions.values()) == pytest.approx(ranked[0].score)
    assert LowestPrice().rank(bids, task(), features)[0].agent_id == "veteran"


def test_exploration_bonus_is_replayable(market_factory: MarketFactory) -> None:
    store = InMemoryStore()
    market = market_factory(store=store, policy=ExplorationBonus(LowestPrice(), 0.5))
    market.register(ScriptedAgent("a", 1.0))
    market.register(ScriptedAgent("b", 1.2))
    result = market.submit_task(task())
    report = replay_auction(store.events(result.auction_id))
    assert report.matches, report.differences
