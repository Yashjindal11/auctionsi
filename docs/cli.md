---
description: >-
  The auctionsi command line: register agents, submit tasks, inspect and replay
  auctions, simulate markets, run experiments, serve the API, and configure the
  marketplace in YAML.
---

# CLI

```bash
auctionsi init my-market && cd my-market   # config, agents, task, experiment, db
auctionsi agent register agents.yaml        # simulated agent specs
auctionsi agent generate --count 20 --seed 1
auctionsi agents list | agent show ID [--private]
auctionsi agent remove ID                   # out of future auctions; history is kept
auctionsi task submit task.yaml [--new-id]  # also: auction run --type sql --budget 0.1
auctionsi tasks list
auctionsi auctions list [--status settled]
auctionsi auction show ID                   # bids, rejections, scores, contracts, trace
auctionsi replay ID                         # re-derive the decision; exit 1 on mismatch
auctionsi market status
auctionsi market simulate --agents 100 --tasks 1000 --seed 42 [--mechanism ..] [--policy ..]
auctionsi experiment run experiment.yaml [--out DIR] [--replications N] [--save-db]
auctionsi experiment compare --mechanisms first_price_reverse,second_price_reverse
auctionsi report DIR                        # regenerate report.md
auctionsi calibration [--agent ID]          # claimed vs delivered quality and latency
auctionsi serve [--host 127.0.0.1] [--port 8000]   # API + dashboard (needs auctionsi[api])
```

Global options: `--db PATH_OR_URL` (default `./auctionsi.db`; a `postgresql://` URL
uses PostgreSQL and needs `auctionsi[postgres]`), `--config PATH` (default
`./auctionsi.yaml` if present). Most listing commands accept `--json`. Exit codes:
0 success, 1 the auction failed or replay mismatched, 2 usage/config error.

The CLI marketplace runs agents from the registry: simulated agents, or HTTP agents
given as `{kind: http, agent_id: .., base_url: .., capabilities: [..], token_env: ..}`.
Python-function agents are wired up in Python.

## Market configuration (`auctionsi.yaml`)

```yaml
market: {name: research_market, disclose_clearing_price: false}
auction: {mechanism: first_price_reverse, bidding_window: 10}
selection: {strategy: risk_adjusted_cost, failure_cost: 0.2}   # other keys = policy params
reputation: {enabled: true, decay: exponential, half_life: 50}
verification: {required: true, verifier: simulated_quality}
settlement: {currency: credits, policy: pay_on_pass, penalty_rate: 0.1}
recovery: {retry_same: 0, next_best: 1, reopen: 0}
validation: {max_bids_per_operator: 1}
```

Configuration is parsed with a safe YAML loader that refuses aliases and Python
tags, enforces a size limit, and rejects unknown keys.
