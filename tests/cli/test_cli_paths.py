from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from auctionsi import __version__
from auctionsi.cli.main import main
from auctionsi.experiments import manifest
from auctionsi.storage import SQLiteStore, open_store


@pytest.fixture
def project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> Path:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "."]) == 0
    assert main(["agent", "register", "agents.yaml"]) == 0
    capsys.readouterr()
    return tmp_path


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    code = main(list(argv))
    out, err = capsys.readouterr()
    return code, out, err


def test_init_skips_existing_files_unless_forced(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, _ = run(capsys, "init", ".")
    assert code == 0
    assert "skip" in out
    code, out, _ = run(capsys, "init", ".", "--force")
    assert "wrote" in out


def test_agent_generate_and_text_show(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "agent", "generate", "--count", "2", "--prefix", "gen")
    assert code == 0
    assert "registered 2 simulated agents" in out
    code, out, _ = run(capsys, "agent", "show", "gen-00000")
    assert "No completed work yet." in out
    code, out, _ = run(capsys, "agent", "show", "gen-00000", "--json", "--private")
    assert json.loads(out)["agent"]["spec"]["agent_id"] == "gen-00000"
    code, _, err = run(capsys, "agent", "show", "nobody")
    assert code == 2
    assert "not registered" in err


def test_agent_file_must_be_a_list(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    Path("bad.yaml").write_text("agents: 3\n", encoding="utf-8")
    code, _, err = run(capsys, "agent", "register", "bad.yaml")
    assert code == 2
    assert "must be a list" in err


def test_task_inputs(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    Path("list.yaml").write_text("- 1\n", encoding="utf-8")
    code, _, err = run(capsys, "task", "submit", "list.yaml")
    assert code == 2
    assert "must be a mapping" in err
    code, _, err = run(capsys, "auction", "run")
    assert code == 2
    assert "give a task file or --type" in err
    code, out, _ = run(capsys, "task", "submit", "task.yaml", "--new-id", "--json")
    assert json.loads(out)["task"]["task_id"] != "task-example-001"


def test_task_needs_agents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    code, _, err = run(capsys, "auction", "run", "--type", "sql")
    assert code == 2
    assert "no agents registered" in err


def test_auction_show_text_and_errors(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run(capsys, "auction", "run", "--type", "data_analysis", "--budget", "1", "--deadline", "100")
    auction_id = SQLiteStore("auctionsi.db").list_auctions()[0]["auction_id"]
    code, out, _ = run(capsys, "auction", "show", auction_id)
    assert code == 0
    assert "Selection (score contributions):" in out
    assert "award:" in out
    assert "Contract contract-" in out
    code, out, _ = run(capsys, "auction", "show", auction_id, "--json")
    assert json.loads(out)["auction_id"] == auction_id
    code, _, err = run(capsys, "auction", "show", "auction-missing")
    assert code == 2
    assert "not found" in err
    code, out, _ = run(capsys, "auctions", "list")
    assert auction_id in out
    code, out, _ = run(capsys, "tasks", "list", "--json")
    assert len(json.loads(out)) == 1


def test_market_status_text_and_calibration(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, _ = run(capsys, "market", "status")
    assert code == 0
    assert "Database: auctionsi.db (schema v2)" in out
    assert "Auctions by status: -" in out
    run(capsys, "auction", "run", "--type", "data_analysis", "--budget", "1", "--deadline", "100")
    code, out, _ = run(capsys, "calibration")
    assert code == 0
    assert out.strip()
    code, out, _ = run(capsys, "calibration", "--json")
    assert set(json.loads(out)) == {"agents", "bins"}


def test_market_simulate_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    code, out, _ = run(
        capsys, "market", "simulate", "--agents", "4", "--tasks", "10", "--policy", "lowest_price"
    )
    assert code == 0
    assert "Simulated 4 agents, 10 tasks (seed 0)" in out
    assert "auctions/s wall clock" in out


def test_experiment_compare(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    code, _, err = run(capsys, "experiment", "compare", "--mechanisms", "first_price_reverse")
    assert code == 2
    assert "at least two" in err
    code, out, _ = run(
        capsys,
        "experiment",
        "compare",
        "--mechanisms",
        "first_price_reverse,second_price_reverse",
        "--agents",
        "4",
        "--tasks",
        "10",
        "--replications",
        "2",
        "--metrics",
        "total_cost",
        "--out",
        "cmp",
    )
    assert code == 0
    assert "second_price_reverse" in out
    assert (tmp_path / "cmp" / "report.md").is_file()


def test_missing_config_file_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    code, _, err = run(capsys, "--config", "nope.yaml", "market", "status")
    assert code == 2
    assert "does not exist" in err


def test_serve_warns_without_key_beyond_localhost(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import uvicorn

    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: calls.append(kw))
    monkeypatch.delenv("AUCTIONSI_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    code, _, err = run(capsys, "serve", "--host", "0.0.0.0", "--port", "9001")
    assert code == 0
    assert "without AUCTIONSI_API_KEY" in err
    assert calls == [{"host": "0.0.0.0", "port": 9001, "log_level": "info"}]
    monkeypatch.setenv("AUCTIONSI_API_KEY", "k")
    _, _, err = run(capsys, "serve", "--host", "0.0.0.0")
    assert err == ""


def test_module_entry_point() -> None:
    out = subprocess.run(
        [sys.executable, "-m", "auctionsi", "--version"], capture_output=True, text=True, check=True
    )
    assert __version__ in out.stdout


def test_open_store_routes_postgres_urls(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import auctionsi.storage.postgres as pg

    seen: list[tuple[str, str]] = []

    class FakePostgres:
        def __init__(self, url: str, *, run_id: str) -> None:
            seen.append((url, run_id))

    monkeypatch.setattr(pg, "PostgresStore", FakePostgres)
    assert isinstance(open_store("postgresql://u@h/db", run_id="r"), FakePostgres)
    assert isinstance(open_store("postgres://u@h/db"), FakePostgres)
    assert seen == [("postgresql://u@h/db", "r"), ("postgres://u@h/db", "default")]
    store = open_store(str(tmp_path / "x.db"), check_same_thread=False)
    assert isinstance(store, SQLiteStore)
    store.close()


def test_git_commit_handles_missing_git_and_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(manifest.shutil, "which", lambda name: None)
    assert manifest.git_commit() is None
    monkeypatch.setattr(manifest.shutil, "which", lambda name: "/usr/bin/git")

    def boom(*args: object, **kwargs: object) -> None:
        raise OSError("no git")

    monkeypatch.setattr(manifest.subprocess, "run", boom)
    assert manifest.git_commit() is None


def test_git_commit_outside_a_repository(tmp_path: Path) -> None:
    assert manifest.git_commit(tmp_path) is None


def test_unknown_distribution_version() -> None:
    assert manifest._version("auctionsi-no-such-dist") is None
