---
description: >-
  Install AuctionSI, run a first agent auction in Python, use the CLI to register
  agents and submit tasks, and start the REST API and dashboard.
---

# Getting started

## Install

```bash
pip install auctionsi                # Python 3.11+, core only
pip install "auctionsi[api]"         # + REST/WebSocket API and dashboard
pip install "auctionsi[postgres]"    # + PostgreSQL store
pip install "auctionsi[plotly]"      # + Plotly figures
```

The core depends on pydantic, PyYAML and SciPy only.

## A first auction in Python

Three agents can answer a question. One of them answers correctly; the cheapest
one does not. Verification catches the wrong answer and recovery hands the task to
the next-best bid.

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
assert result.winner == "agent-a"
print(result.explain())   # ranking, with each score split into named contributions
print(result.buyer_cost)  # total paid across attempts (the failed one was not paid)
```

What happened, in order: discovery found three agents with the `qa` capability;
each bid; the default first-price mechanism and lowest-price policy picked
`agent-c`; its answer failed verification, so it was not paid; recovery contracted
the next-best bid, `agent-a`, whose answer passed and was paid. Every step is an
event in `result.trace()`.

## Bids from outside the process

`open_auction` starts an auction without running it to completion, so bids can
arrive from anywhere (the REST API uses the same calls). Only registered agents may
bid.

```python
from auctionsi import BidProposal, Marketplace, PythonFunctionAgent, Task

market = Marketplace()
market.register(PythonFunctionAgent("remote-1", lambda t, c: {"ok": True}, capabilities=["sql"], price=1.0))

auction = market.open_auction(Task(task_id="t-1", task_type="sql", budget=1.0), solicit=False)
market.submit_bid(auction.auction_id, "remote-1", BidProposal(price=0.4, estimated_latency=2.0))
result = market.close_auction(auction.auction_id)
assert result.winner == "remote-1"
```

## The command line

```bash
auctionsi init my-market && cd my-market    # config, five example agents, a task, an experiment
auctionsi agent register agents.yaml
auctionsi task submit task.yaml              # runs the auction and prints the explanation
auctionsi auctions list
auctionsi auction show AUCTION_ID            # bids, rejections, scores, contracts, trace
auctionsi replay AUCTION_ID                  # re-derive the decision from the event log
auctionsi market simulate --agents 100 --tasks 1000 --seed 42
auctionsi experiment run experiment.yaml
```

Everything is stored in `./auctionsi.db` (SQLite) unless `--db` points elsewhere,
including a `postgresql://` URL. See [CLI and configuration](cli.md).

## The API and dashboard

```bash
pip install "auctionsi[api]"
auctionsi serve                     # http://127.0.0.1:8000
```

The dashboard shows the market, agents and their reputation, every auction with
its bids and trace, live events, simulations, calibration and saved experiments.
See [REST API and dashboard](api.md).

## Simulate before you deploy

```python
from auctionsi.experiments import compare_mechanisms
from auctionsi.mechanisms import FirstPriceReverseAuction, SecondPriceReverseAuction

result = compare_mechanisms(
    [FirstPriceReverseAuction(), SecondPriceReverseAuction()],
    environment={"agents": {"count": 10}, "tasks": {"count": 50}},
    replications=3,
    seed=7,
    metrics=["total_cost", "completion_rate"],
)
for c in result.comparisons():
    print(c.metric, c.treatment, round(c.mean_diff, 4))
```

See [simulation and experiments](simulation-and-experiments.md) for environments,
adversaries, factorial sweeps and the metrics.

## Next

- [Core concepts](concepts.md) explains the lifecycle and every object.
- [Writing agents and plugins](extending.md) shows how to plug in your own agents,
  verifiers, mechanisms and policies.
