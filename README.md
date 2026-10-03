# AuctionSI

**Let agents compete to solve the work.**

AuctionSI is an open-source marketplace and auction framework for autonomous agents.
Instead of a central orchestrator choosing which agent does a task, the task is
announced to a market, capable agents bid, an auction mechanism picks the winner,
and the work is contracted, executed, verified, settled and fed back into reputation.

```
Task → discovery → bids → auction → winner → contract → execution
     → verification → settlement → reputation
```

Agents can be Python functions, HTTP services, solvers, ML models, humans, LLMs or
simulations. **Nothing requires an LLM, an API key or a cloud service.** Everything
runs locally, and simulations are deterministic when seeded.

The auction mechanism, the winner-selection policy, the bidding strategy, the
verifier, the settlement policy, the reputation system and the experiment are all
plugins.

## Install

```bash
pip install -e ".[dev]"        # from a clone; Python 3.11+
pip install -e ".[plotly]"     # optional figures
```

## Quick start

```python
from auctionsi import Marketplace, PythonFunctionAgent, RecoveryPolicy, Task
from auctionsi.verification import ExactMatchVerifier

def right(task, contract):
    return {"answer": 42}

def wrong(task, contract):
    return {"answer": 41}

market = Marketplace(
    verifier=ExactMatchVerifier(42, key="answer"),
    recovery=RecoveryPolicy(next_best=1),
)
market.register(PythonFunctionAgent("agent-a", right, capabilities=["qa"], price=0.05))
market.register(PythonFunctionAgent("agent-b", wrong, capabilities=["qa"], price=0.07))
market.register(PythonFunctionAgent("agent-c", wrong, capabilities=["qa"], price=0.03))

result = market.submit_task(Task(task_id="task-001", task_type="qa", budget=0.10))
print(result.explain())                 # ranking with per-term score contributions
print("\n".join(result.trace()))        # every lifecycle event
assert result.winner == "agent-a"       # C was cheapest, failed verification, A took over
```

## What is in v0.1

| area | contents |
|---|---|
| Mechanisms | first-price (pay-as-bid), second-price (critical value), multi-winner (pay-as-bid or uniform), open descending with bid revisions |
| Selection | lowest price, highest quality, lowest latency, weighted score, risk-adjusted cost, reputation-adjusted cost; every score is broken into named contributions |
| Bids | multi-dimensional (price, latency, quality, cost, confidence, capacity, validity); validated with structured rejection reasons |
| Verification | schema, exact match, tolerance, metric threshold, unit tests, composite, human approval; quality score always derived from checks |
| Settlement | pay on pass (penalties, late penalties, bonuses), quality-proportional, partial payment |
| Reputation | per agent and per task type: success, quality, timeliness, estimate calibration, violations; no/exponential/rolling decay |
| Recovery | retry, fail over to backup bids, re-open the auction |
| Observability | immutable events, traces, JSON logs, counters, SQLite persistence, deterministic replay |
| Simulation | synthetic agents/tasks, 12 bid strategies, market dynamics, collusion/Sybil/misreporting tools, market metrics (HHI, Gini, surplus, efficiency...) |
| Experiments | YAML configs, common random numbers, CIs, paired tests with Holm adjustment, run manifests, Markdown reports |
| Adapters | Python function, HTTP, OpenAI-compatible (optional), human-in-the-loop |
| CLI | `auctionsi init / agent / task / auction / market / experiment / replay / report` |

Not in v0.1 (see the roadmap): REST/WebSocket API, web dashboard, distributed
execution, combinatorial and forward auctions, learning bidders.

## Simulate and experiment

```python
from auctionsi.experiments import compare_mechanisms
from auctionsi.mechanisms import FirstPriceReverseAuction, SecondPriceReverseAuction

result = compare_mechanisms(
    [FirstPriceReverseAuction(), SecondPriceReverseAuction()],
    environment={"agents": {"count": 20}, "tasks": {"count": 100}},
    replications=5,
    seed=42,
    metrics=["total_cost", "completion_rate"],
)
for c in result.comparisons():
    print(c.metric, c.treatment, round(c.mean_diff, 4), (round(c.ci_low, 4), round(c.ci_high, 4)))
```

```bash
auctionsi market simulate --agents 100 --tasks 1000 --seed 42
auctionsi experiment run research/experiments/mechanisms.yaml
```

Six reproducible experiments (mechanisms, market size, reliability, reputation,
strategies, concentration) with their reports are in [research/](research/README.md).
All results there come from synthetic markets and say so.

## Examples

[`examples/`](examples/): data-analysis (fail-over after deterministic checks), SQL
(queries executed against a read-only test database), scheduling optimisation
(constraint and objective checks), research reports (structure and citation checks),
compute capacity (constraints and multi-winner uniform pricing), and a simulated
collusion experiment. `python scripts/run_examples.py` runs them all.

## Benchmarks

Measured on an Apple-silicon laptop, Python 3.12 (details and method in
[benchmarks/](benchmarks/README.md)):

| scenario | agents | tasks | auctions/s | bids/s | peak MB |
|---|---|---|---|---|---|
| A | 10 | 100 | 4,715 | 11,551 | 0 |
| B | 100 | 1,000 | 2,449 | 19,600 | 2 |
| C | 1,000 | 10,000 | 456 | 22,032 | 17 |

## Documentation

[docs/](docs/README.md): concepts, architecture, mechanisms (with assumptions and
limitations), selection, simulation and metrics, extending, CLI, and
[security](SECURITY.md).

## Roadmap

- **v0.1** core marketplace (this release)
- **v0.2** more mechanisms (scoring auctions, reserve-price variants)
- **v0.3** richer simulation and experiment designs (factorial sweeps)
- **v0.4** reputation research and stronger adversarial models and defences
- **v0.5** persistence backends (PostgreSQL) and distributed execution
- **v0.6** REST/WebSocket API and web dashboard
- **v0.7** agent protocol interoperability
- **v0.8** advanced mechanism research (combinatorial, forward, capacity auctions, learning bidders)
- **v1.0** stable public API

No dates are promised.

## Contributing and licence

See [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
MIT licensed ([LICENSE](LICENSE), [NOTICE](NOTICE)).
