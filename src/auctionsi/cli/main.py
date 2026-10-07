"""``auctionsi`` command-line interface."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

from auctionsi._version import __version__
from auctionsi.adapters.specs import agent_spec, build_agent
from auctionsi.config import DEFAULT_CONFIG_YAML, MarketConfig
from auctionsi.core.task import Task
from auctionsi.errors import AuctionSIError, ConfigurationError, NotFoundError, ValidationError
from auctionsi.market.clock import IdGenerator
from auctionsi.market.marketplace import Marketplace
from auctionsi.market.replay import replay_auction
from auctionsi.market.trace import format_trace
from auctionsi.reputation.base import MultiDimensionalReputation
from auctionsi.security.loading import load_config_file
from auctionsi.simulation.generators import generate_agents
from auctionsi.storage import SQLStore, open_store
from auctionsi.storage.sqlite import SQLiteStore

EXAMPLE_TASK = {
    "task_id": "task-example-001",
    "task_type": "data_analysis",
    "description": "Analyse the provided dataset",
    "requirements": {"complexity": 1.0},
    "budget": 0.10,
    "deadline": 60,
    "min_quality": 0.6,
}

EXAMPLE_EXPERIMENT = """\
name: first-vs-second-price
hypothesis: >
  Paying the runner-up price (second-price) raises the buyer's total cost
  relative to pay-as-bid (first-price) when bidders do not change strategy.
seed: 42
replications: 20
environment:
  agents: {count: 30}
  tasks: {count: 300}
arms:
  - {name: first_price, mechanism: first_price_reverse}
  - {name: second_price, mechanism: second_price_reverse}
metrics: [total_cost, average_cost, completion_rate, average_quality, hhi]
"""


def _print_table(rows: Sequence[dict[str, Any]], columns: Sequence[str]) -> None:
    if not rows:
        print("(none)")
        return
    cells = [[_cell(r.get(c)) for c in columns] for r in rows]
    widths = [max(len(c), *(len(row[i]) for row in cells)) for i, c in enumerate(columns)]
    print("  ".join(c.ljust(w) for c, w in zip(columns, widths, strict=True)))
    print("  ".join("-" * w for w in widths))
    for row in cells:
        print("  ".join(v.ljust(w) for v, w in zip(row, widths, strict=True)))


def _cell(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.4g}"
    if isinstance(value, list):
        return ",".join(str(v) for v in value)
    return str(value)


def _dump(data: Any) -> None:
    print(json.dumps(data, indent=2, default=str))


class Context:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.db_path = args.db
        config_path = Path(args.config) if args.config else Path("auctionsi.yaml")
        self.config = MarketConfig.load(config_path if config_path.exists() else None)
        if args.config and not config_path.exists():
            raise ConfigurationError(f"config file {config_path} does not exist")
        self._store: SQLStore | None = None

    @property
    def store(self) -> SQLStore:
        if self._store is None:
            self._store = open_store(self.db_path, run_id=uuid.uuid4().hex[:8])
        return self._store

    def market(self) -> Marketplace:
        """A marketplace with every registered agent and reputation rebuilt from history.
        The store is attached after agents are loaded so re-loading them is not logged."""
        market = self.config.build(ids=IdGenerator(uuid.uuid4().hex[:6]))
        for observation in self.store.observations():
            market.reputation.record(observation)
        for profile in self.store.list_agents():
            spec = profile.get("spec")
            if spec:
                market.register(build_agent(spec))
        market.attach_store(self.store)
        return market

    def close(self) -> None:
        if self._store is not None:
            self._store.close()


# ---------------------------------------------------------------------- commands


def cmd_init(ctx: Context) -> int:
    target = Path(ctx.args.directory)
    target.mkdir(parents=True, exist_ok=True)
    files = {
        "auctionsi.yaml": DEFAULT_CONFIG_YAML,
        "task.yaml": yaml.safe_dump(EXAMPLE_TASK, sort_keys=False),
        "experiment.yaml": EXAMPLE_EXPERIMENT,
        "agents.yaml": yaml.safe_dump(
            {"agents": [a.spec() for a in generate_agents(5, seed=7, prefix="agent")]},
            sort_keys=False,
        ),
    }
    for name, content in files.items():
        path = target / name
        if path.exists() and not ctx.args.force:
            print(f"skip {path} (exists; use --force to overwrite)")
            continue
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path}")
    SQLiteStore(target / "auctionsi.db").close()
    print(f"created {target / 'auctionsi.db'}")
    print(
        "\nNext:\n  cd",
        target,
        "\n  auctionsi agent register agents.yaml\n  auctionsi task submit task.yaml",
    )
    return 0


def cmd_agent_register(ctx: Context) -> int:
    data = load_config_file(ctx.args.file)
    specs = data.get("agents") if isinstance(data, dict) else data
    if not isinstance(specs, list):
        raise ConfigurationError("agent file must be a list or {agents: [...]}")
    for spec in specs:
        agent = build_agent(spec)
        ctx.store.save_agent(agent.describe(), agent_spec(agent))
        print(f"registered {agent.agent_id}")
    return 0


def cmd_agent_remove(ctx: Context) -> int:
    if not ctx.store.delete_agent(ctx.args.agent_id):
        raise NotFoundError(f"agent {ctx.args.agent_id} is not registered")
    print(f"removed {ctx.args.agent_id} (its history stays in the database)")
    return 0


def cmd_agent_generate(ctx: Context) -> int:
    agents = generate_agents(
        ctx.args.count, seed=ctx.args.seed, strategy=ctx.args.strategy, prefix=ctx.args.prefix
    )
    for agent in agents:
        ctx.store.save_agent(agent.describe(), agent_spec(agent))
    print(f"registered {len(agents)} simulated agents")
    return 0


def cmd_agent_list(ctx: Context) -> int:
    agents = ctx.store.list_agents()
    if ctx.args.json:
        _dump(agents)
        return 0
    rows = [
        {
            "agent_id": a["agent_id"],
            "kind": a.get("kind"),
            "capabilities": [c["name"] for c in a.get("capabilities", [])],
            "capacity": a.get("max_concurrent_tasks"),
        }
        for a in agents
    ]
    _print_table(rows, ["agent_id", "kind", "capabilities", "capacity"])
    return 0


def cmd_agent_show(ctx: Context) -> int:
    agent = ctx.store.get_agent(ctx.args.agent_id)
    if agent is None:
        raise NotFoundError(f"agent {ctx.args.agent_id} is not registered")
    rep = MultiDimensionalReputation()
    for obs in ctx.store.observations(ctx.args.agent_id):
        rep.record(obs)
    profiles = {"overall": rep.profile(ctx.args.agent_id)}
    for task_type in rep.task_types(ctx.args.agent_id):
        profiles[task_type] = rep.profile(ctx.args.agent_id, task_type)
    public = {k: v for k, v in agent.items() if k != "spec" or ctx.args.private}
    data = {
        "agent": public,
        "reputation": {k: (p.to_dict() if p else None) for k, p in profiles.items()},
    }
    if ctx.args.json:
        _dump(data)
        return 0
    print(f"Agent {agent['agent_id']} ({agent.get('kind')})")
    print("Capabilities:", ", ".join(c["name"] for c in agent.get("capabilities", [])))
    overall = profiles["overall"]
    if overall is None:
        print("No completed work yet.")
        return 0
    print(f"Tasks: {overall.observations} (completed {overall.completed}, failed {overall.failed})")
    print(f"Success rate: {_cell(overall.success_rate)}  On-time: {_cell(overall.on_time_rate)}")
    print(f"Average quality: {_cell(overall.avg_quality)}")
    print(
        f"Quality estimate bias: {_cell(overall.quality_estimate_bias)}  "
        f"Latency estimate error: {_cell(overall.latency_estimate_error)}"
    )
    for task_type, p in profiles.items():
        if task_type != "overall" and p is not None:
            print(f"  {task_type}: success {_cell(p.success_rate)}, quality {_cell(p.avg_quality)}")
    return 0


def _task_from_args(ctx: Context) -> Task:
    args = ctx.args
    if args.file:
        data = load_config_file(args.file)
        if not isinstance(data, dict):
            raise ConfigurationError("task file must be a mapping")
        data.setdefault("unit", ctx.config.settlement.currency)
        if args.new_id or "task_id" not in data:
            data["task_id"] = f"task-{uuid.uuid4().hex[:10]}"
        return Task.from_dict(data)
    if not args.type:
        raise ConfigurationError("give a task file or --type")
    return Task(
        task_id=f"task-{uuid.uuid4().hex[:10]}",
        task_type=args.type,
        budget=args.budget,
        deadline=args.deadline,
        min_quality=args.min_quality,
        requirements={"complexity": args.complexity},
        unit=ctx.config.settlement.currency,
    )


def cmd_task_submit(ctx: Context) -> int:
    task = _task_from_args(ctx)
    if ctx.store.has_task(task.task_id):
        raise ValidationError(f"task {task.task_id} already exists (use --new-id)")
    market = ctx.market()
    if not market.agents:
        raise ConfigurationError("no agents registered; run `auctionsi agent register` first")
    result = market.submit_task(task)
    if ctx.args.json:
        _dump(result.to_dict())
    else:
        print(result.explain())
        print()
        print("\n".join(result.trace()))
    return 0 if result.succeeded else 1


def cmd_task_list(ctx: Context) -> int:
    tasks = ctx.store.list_tasks()
    if ctx.args.json:
        _dump(tasks)
        return 0
    _print_table(tasks, ["task_id", "task_type", "budget", "deadline", "min_quality"])
    return 0


def cmd_auction_list(ctx: Context) -> int:
    auctions = ctx.store.list_auctions(status=ctx.args.status)
    if ctx.args.json:
        _dump(auctions)
        return 0
    _print_table(auctions, ["auction_id", "task_id", "status", "mechanism", "parent_auction_id"])
    return 0


def cmd_auction_show(ctx: Context) -> int:
    record = ctx.store.get_auction(ctx.args.auction_id)
    if record is None:
        raise NotFoundError(f"auction {ctx.args.auction_id} not found")
    if ctx.args.json:
        _dump(record)
        return 0
    task = record["task"]
    print(f"Auction {record['auction_id']}  [{record['status']}]  mechanism={record['mechanism']}")
    print(
        f"Task {task['task_id']} ({task['task_type']}) budget={task['budget']} deadline={task['deadline']}"
    )
    print(f"Participants: {', '.join(record['participants']) or 'none'}")
    for agent_id, reasons in record["excluded"].items():
        print(f"  excluded {agent_id}: {'; '.join(reasons)}")
    print("\nBids:")
    _print_table(
        record["bids"],
        ["agent_id", "price", "estimated_latency", "estimated_quality", "confidence", "revision"],
    )
    for rejected in record["rejected"]:
        codes = ", ".join(r["code"] for r in rejected["reasons"])
        print(f"  rejected {rejected['agent_id']}: {codes}")
    outcome = record.get("outcome")
    if outcome:
        print("\nSelection (score contributions):")
        for i, s in enumerate(outcome["ranking"], start=1):
            parts = ", ".join(f"{k}={v:+.4g}" for k, v in s["contributions"].items())
            print(f"  {i}. {s['agent_id']} score={s['score']:.6g} ({parts})")
        for a in outcome["awards"]:
            print(f"  award: {a['agent_id']} paid {a['payment']:.6g} - {a['payment_rule']}")
    for c in record["contracts"]:
        v, s = c["verification"], c["settlement"]
        print(
            f"\nContract {c['contract']['contract_id']} ({c['contract']['agent_id']}): "
            f"verification {'passed' if v['passed'] else 'failed'} quality={v['quality_score']:.3f}; "
            f"settlement payment={s['payment']:.6g} penalty={s['penalty']:.6g} ({s['reason']})"
        )
    events = ctx.store.events(record["auction_id"])
    if events:
        print("\nTrace:")
        print("\n".join(format_trace(events)))
    return 0


def cmd_market_status(ctx: Context) -> int:
    status = ctx.store.status()
    if ctx.args.json:
        _dump(status)
        return 0
    print(f"Database: {status['path']} (schema v{status['schema_version']})")
    for table, n in status["counts"].items():
        print(f"  {table:<13} {n}")
    print("Auctions by status:", status["auctions_by_status"] or "-")
    print(f"Total buyer cost: {status['total_buyer_cost']:.6g} {ctx.config.settlement.currency}")
    return 0


def cmd_market_simulate(ctx: Context) -> int:
    from auctionsi.plugins import default_registry
    from auctionsi.simulation.market import simulate_market

    reg = default_registry()
    cfg = ctx.config
    result = simulate_market(
        ctx.args.agents,
        ctx.args.tasks,
        seed=ctx.args.seed,
        mechanism=reg.mechanisms.create(ctx.args.mechanism or cfg.auction.mechanism),
        policy=reg.policies.create(
            {"name": ctx.args.policy} if ctx.args.policy else cfg.selection.spec()
        ),
        reputation=cfg.build_reputation(reg),
        settlement=reg.settlements.create(cfg.settlement.spec()),
    )
    scalars = result.metrics.scalars()
    if ctx.args.json:
        _dump({"metrics": scalars, "performance": result.performance()})
        return 0
    print(f"Simulated {ctx.args.agents} agents, {ctx.args.tasks} tasks (seed {ctx.args.seed})")
    for name, value in scalars.items():
        print(f"  {name:<22} {_cell(value)}")
    perf = result.performance()
    print(f"  ({perf['auctions_per_second']:.0f} auctions/s wall clock)")
    return 0


def cmd_experiment_run(ctx: Context) -> int:
    from auctionsi.experiments import ExperimentConfig, run_experiment

    config = ExperimentConfig.from_mapping(load_config_file(ctx.args.config_file))
    if ctx.args.replications:
        config = config.model_copy(update={"replications": ctx.args.replications})

    def progress(arm: str, done: int, total: int) -> None:
        if not ctx.args.quiet:
            print(f"\r  {done}/{total} runs", end="", file=sys.stderr, flush=True)

    result = run_experiment(config, progress=progress)
    if not ctx.args.quiet:
        print(file=sys.stderr)
    out = Path(ctx.args.out or Path("auctionsi-results") / config.name)
    result.save(out)
    if ctx.args.save_db:
        ctx.store.save_experiment(
            f"{config.name}-{uuid.uuid4().hex[:6]}", config.name, result.manifest, result.to_dict()
        )
    _print_experiment(result)
    print(f"\nreport: {out / 'report.md'}")
    return 0


def cmd_experiment_compare(ctx: Context) -> int:
    from auctionsi.experiments import run_experiment

    names = [n.strip() for n in ctx.args.mechanisms.split(",") if n.strip()]
    if len(names) < 2:
        raise ConfigurationError("--mechanisms needs at least two comma-separated names")
    data: dict[str, Any] = {
        "name": "compare-" + "-vs-".join(names),
        "seed": ctx.args.seed,
        "replications": ctx.args.replications,
        "environment": {"agents": {"count": ctx.args.agents}, "tasks": {"count": ctx.args.tasks}},
        "policy": ctx.args.policy or ctx.config.selection.spec(),
        "arms": [{"name": n, "mechanism": n} for n in names],
    }
    if ctx.args.metrics:
        data["metrics"] = [m.strip() for m in ctx.args.metrics.split(",")]
    result = run_experiment(data)
    if ctx.args.out:
        result.save(ctx.args.out)
    _print_experiment(result)
    return 0


def cmd_calibration(ctx: Context) -> int:
    from auctionsi.reports import calibration_report, calibration_table, reliability_bins

    observations = ctx.store.observations(ctx.args.agent)
    if ctx.args.json:
        _dump({"agents": calibration_table(observations), "bins": reliability_bins(observations)})
    else:
        print(calibration_report(observations))
    return 0


def cmd_serve(ctx: Context) -> int:
    try:
        import uvicorn
    except ImportError as exc:
        raise ConfigurationError(
            'serving needs the API extra: pip install "auctionsi[api]"'
        ) from exc
    from auctionsi.api import create_app

    ctx.close()
    app = create_app(ctx.db_path, config=ctx.config)
    if ctx.args.host not in ("127.0.0.1", "localhost", "::1") and not os.environ.get(
        "AUCTIONSI_API_KEY"
    ):
        print("warning: serving beyond localhost without AUCTIONSI_API_KEY set", file=sys.stderr)
    uvicorn.run(app, host=ctx.args.host, port=ctx.args.port, log_level="info")
    return 0


def _print_experiment(result: Any) -> None:
    summary = result.summary()
    rows = []
    for arm, metrics in summary.items():
        for metric, s in metrics.items():
            rows.append(
                {
                    "arm": arm,
                    "metric": metric,
                    "mean": s.mean,
                    "ci_low": s.ci_low,
                    "ci_high": s.ci_high,
                    "n": s.n,
                }
            )
    _print_table(rows, ["arm", "metric", "mean", "ci_low", "ci_high", "n"])
    comparisons = result.comparisons()
    if comparisons:
        print()
        _print_table(
            [c.to_dict() for c in comparisons],
            ["metric", "treatment", "mean_diff", "ci_low", "ci_high", "effect_size", "p_adjusted"],
        )


def cmd_replay(ctx: Context) -> int:
    events = ctx.store.events(ctx.args.auction_id)
    if not events:
        raise NotFoundError(f"no events recorded for auction {ctx.args.auction_id}")
    report = replay_auction(events)
    print(report.to_text())
    return 0 if report.matches else 1


def cmd_report(ctx: Context) -> int:
    from auctionsi.experiments import ExperimentResult
    from auctionsi.reports import experiment_report

    result = ExperimentResult.load(ctx.args.results_dir)
    text = experiment_report(result)
    (Path(ctx.args.results_dir) / "report.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


# ------------------------------------------------------------------------ parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="auctionsi", description="Marketplace and auction framework for autonomous agents."
    )
    parser.add_argument("--version", action="version", version=f"auctionsi {__version__}")
    parser.add_argument(
        "--db",
        default="auctionsi.db",
        help="SQLite path or postgresql:// URL (default: ./auctionsi.db)",
    )
    parser.add_argument("--config", help="market config (default: ./auctionsi.yaml if present)")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(subparsers: Any, name: str, func: Any, help: str, **kw: Any) -> argparse.ArgumentParser:
        p: argparse.ArgumentParser = subparsers.add_parser(name, help=help, **kw)
        p.set_defaults(func=func)
        return p

    def json_flag(p: argparse.ArgumentParser) -> None:
        p.add_argument("--json", action="store_true", help="machine-readable output")

    p = add(sub, "init", cmd_init, "create a starter config, agents, task and experiment")
    p.add_argument("directory", nargs="?", default=".")
    p.add_argument("--force", action="store_true")

    for group_name in ("agent", "agents"):
        group = sub.add_parser(group_name, help="manage registered agents").add_subparsers(
            dest="sub", required=True
        )
        p = add(group, "register", cmd_agent_register, "register agents from a YAML/JSON file")
        p.add_argument("file")
        p = add(group, "generate", cmd_agent_generate, "register synthetic agents")
        p.add_argument("--count", type=int, default=10)
        p.add_argument("--seed", type=int, default=0)
        p.add_argument("--strategy", default="cost_plus")
        p.add_argument("--prefix", default="agent")
        json_flag(add(group, "list", cmd_agent_list, "list agents"))
        p = add(group, "show", cmd_agent_show, "agent profile and reputation")
        p.add_argument("agent_id")
        p.add_argument("--private", action="store_true", help="include the private agent spec")
        json_flag(p)
        p = add(group, "remove", cmd_agent_remove, "remove an agent from future auctions")
        p.add_argument("agent_id")

    def task_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("file", nargs="?", help="task YAML/JSON file")
        p.add_argument("--type", help="task type (when no file is given)")
        p.add_argument("--budget", type=float)
        p.add_argument("--deadline", type=float)
        p.add_argument("--min-quality", type=float)
        p.add_argument("--complexity", type=float, default=1.0)
        p.add_argument("--new-id", action="store_true", help="give the task a fresh id")
        json_flag(p)

    for group_name in ("task", "tasks"):
        group = sub.add_parser(group_name, help="submit and list tasks").add_subparsers(
            dest="sub", required=True
        )
        task_args(add(group, "submit", cmd_task_submit, "auction a task to registered agents"))
        json_flag(add(group, "list", cmd_task_list, "list tasks"))

    for group_name in ("auction", "auctions"):
        group = sub.add_parser(group_name, help="run and inspect auctions").add_subparsers(
            dest="sub", required=True
        )
        task_args(add(group, "run", cmd_task_submit, "run an auction for a task"))
        p = add(group, "list", cmd_auction_list, "list auctions")
        p.add_argument("--status")
        json_flag(p)
        for name in ("show", "inspect"):
            p = add(group, name, cmd_auction_show, "full detail of one auction")
            p.add_argument("auction_id")
            json_flag(p)

    group = sub.add_parser("market", help="marketplace status and simulation").add_subparsers(
        dest="sub", required=True
    )
    json_flag(add(group, "status", cmd_market_status, "database and market summary"))
    p = add(group, "simulate", cmd_market_simulate, "simulate a synthetic market")
    p.add_argument("--agents", type=int, default=50)
    p.add_argument("--tasks", type=int, default=500)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--mechanism")
    p.add_argument("--policy")
    json_flag(p)

    group = sub.add_parser("experiment", help="reproducible experiments").add_subparsers(
        dest="sub", required=True
    )
    p = add(group, "run", cmd_experiment_run, "run an experiment config")
    p.add_argument("config_file")
    p.add_argument("--out")
    p.add_argument("--replications", type=int)
    p.add_argument("--save-db", action="store_true")
    p.add_argument("--quiet", action="store_true")
    p = add(group, "compare", cmd_experiment_compare, "compare mechanisms quickly")
    p.add_argument("--mechanisms", required=True, help="comma-separated mechanism names")
    p.add_argument("--agents", type=int, default=20)
    p.add_argument("--tasks", type=int, default=200)
    p.add_argument("--replications", type=int, default=10)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--policy")
    p.add_argument("--metrics")
    p.add_argument("--out")

    p = add(sub, "replay", cmd_replay, "rebuild an auction from its events and verify it")
    p.add_argument("auction_id")
    p = add(sub, "report", cmd_report, "regenerate an experiment report")
    p.add_argument("results_dir")
    p = add(sub, "calibration", cmd_calibration, "claimed vs delivered quality and latency")
    p.add_argument("--agent")
    json_flag(p)
    p = add(sub, "serve", cmd_serve, "run the REST/WebSocket API and dashboard")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    ctx: Context | None = None
    try:
        ctx = Context(args)
        code: int = args.func(ctx)
        return code
    except AuctionSIError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        if ctx is not None:
            ctx.close()


if __name__ == "__main__":
    raise SystemExit(main())
