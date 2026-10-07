from __future__ import annotations

import json
from pathlib import Path

import pytest

from auctionsi.cli.main import main
from auctionsi.config import DEFAULT_CONFIG_YAML, MarketConfig
from auctionsi.errors import ConfigurationError
from auctionsi.mechanisms import FirstPriceReverseAuction
from auctionsi.reputation import NoReputation
from auctionsi.selection import RiskAdjustedCost
from auctionsi.storage import SQLiteStore


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    code = main(list(argv))
    out, err = capsys.readouterr()
    return code, out, err


def test_default_config_builds_the_documented_market(tmp_path: Path) -> None:
    path = tmp_path / "auctionsi.yaml"
    path.write_text(DEFAULT_CONFIG_YAML)
    cfg = MarketConfig.load(path)
    market = cfg.build()
    assert isinstance(market.mechanism, FirstPriceReverseAuction)
    assert isinstance(market.policy, RiskAdjustedCost)
    assert market.policy.failure_cost == 0.2
    assert market.recovery.next_best == 1
    assert cfg.reputation.spec()["decay"] == {"name": "exponential", "half_life": 50}
    disabled = MarketConfig.model_validate({"reputation": {"enabled": False}})
    assert isinstance(disabled.build().reputation, NoReputation)


@pytest.mark.parametrize(
    "data",
    [
        {"auction": {"mechanism": "nope"}},
        {"selection": {"strategy": "weighted_score", "price_weight": -1}},
        {"validation": {"bogus": True}},
    ],
)
def test_bad_market_configs(data: dict[str, object]) -> None:
    from auctionsi.errors import AuctionSIError

    with pytest.raises(AuctionSIError):
        MarketConfig.model_validate(data).build()


def test_unknown_config_section(tmp_path: Path) -> None:
    path = tmp_path / "c.yaml"
    path.write_text("colour: red\n")
    with pytest.raises(ConfigurationError):
        MarketConfig.load(path)


@pytest.mark.integration
def test_cli_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    code, out, _ = run(capsys, "init", "proj")
    assert code == 0
    assert "wrote" in out
    monkeypatch.chdir(tmp_path / "proj")

    code, out, _ = run(capsys, "agent", "register", "agents.yaml")
    assert code == 0
    assert out.count("registered") == 5
    code, out, _ = run(capsys, "agents", "list")
    assert "agent-00000" in out

    code, out, _ = run(capsys, "task", "submit", "task.yaml")
    assert code in (0, 1)
    assert "Auction auction-" in out
    code, out, err = run(capsys, "task", "submit", "task.yaml")
    assert code == 2
    assert "already exists" in err
    code, out, _ = run(capsys, "auction", "run", "--type", "sql", "--budget", "0.2")
    assert code in (0, 1)

    code, out, _ = run(capsys, "auctions", "list", "--json")
    auctions = json.loads(out)
    assert len(auctions) >= 2
    auction_id = auctions[-1]["auction_id"]
    code, out, _ = run(capsys, "auction", "show", auction_id)
    assert code == 0
    assert "Trace:" in out
    code, out, _ = run(capsys, "replay", auction_id)
    assert code == 0
    assert "reproduced exactly" in out or "nothing to re-derive" in out

    code, out, _ = run(capsys, "tasks", "list")
    assert "task-example-001" in out
    winners = SQLiteStore("auctionsi.db").list_auctions()
    assert winners
    code, out, _ = run(capsys, "market", "status", "--json")
    status = json.loads(out)
    assert status["counts"]["agents"] == 5
    assert status["counts"]["auctions"] >= 2

    observed = SQLiteStore("auctionsi.db").observations()
    if observed:
        code, out, _ = run(capsys, "agent", "show", observed[0].agent_id)
        assert "Tasks:" in out
        code, out, _ = run(capsys, "agent", "show", observed[0].agent_id, "--json")
        assert "spec" not in json.loads(out)["agent"]

    code, out, _ = run(capsys, "agent", "remove", "agent-00000")
    assert code == 0
    assert "removed agent-00000" in out
    code, out, _ = run(capsys, "agents", "list", "--json")
    assert "agent-00000" not in [a["agent_id"] for a in json.loads(out)]
    code, _, err = run(capsys, "agent", "remove", "agent-00000")
    assert code == 2
    assert "not registered" in err


def test_cli_simulate_experiment_and_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    code, out, _ = run(capsys, "market", "simulate", "--agents", "5", "--tasks", "20", "--json")
    assert code == 0
    assert json.loads(out)["metrics"]["total_tasks"] == 20

    run(capsys, "init", ".")
    code, out, _ = run(
        capsys,
        "experiment",
        "run",
        "experiment.yaml",
        "--replications",
        "2",
        "--out",
        "res",
        "--quiet",
        "--save-db",
    )
    assert code == 0
    assert (tmp_path / "res" / "report.md").exists()
    assert "second_price" in out
    code, out, _ = run(capsys, "report", "res")
    assert "## Conclusion" in out
    code, out, _ = run(
        capsys,
        "experiment",
        "compare",
        "--mechanisms",
        "first_price_reverse,second_price_reverse",
        "--agents",
        "5",
        "--tasks",
        "20",
        "--replications",
        "2",
        "--metrics",
        "total_cost",
    )
    assert code == 0
    assert "total_cost" in out


def test_cli_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    code, _, err = run(capsys, "--config", "missing.yaml", "market", "status")
    assert code == 2
    assert "does not exist" in err
    (tmp_path / "bad.yaml").write_text("agents:\n  - {agent_id: x}\n")
    code, _, err = run(capsys, "agent", "register", "bad.yaml")
    assert code == 2
    code, _, err = run(capsys, "auction", "show", "auction-nope")
    assert code == 2
    code, _, err = run(capsys, "replay", "auction-nope")
    assert code == 2
    code, _, err = run(capsys, "task", "submit", "--type", "sql")
    assert code == 2
    assert "no agents registered" in err
    code, _, err = run(capsys, "experiment", "compare", "--mechanisms", "first_price_reverse")
    assert code == 2
    with pytest.raises(SystemExit):
        main(["--version"])
