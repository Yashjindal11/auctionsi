---
title: Auction and marketplace framework for AI agents
description: >-
  AuctionSI is an open-source Python framework where autonomous agents bid for tasks
  in auctions: reverse, Vickrey, forward, combinatorial and capacity auctions with
  verification, settlement, reputation, simulation and reproducible experiments.
---

# AuctionSI

**An open-source marketplace and auction framework for autonomous agents.**

Instead of a central orchestrator deciding which agent does a task, AuctionSI
announces the task to a market. Capable agents bid, an auction mechanism picks the
winner, and the work is contracted, executed, verified, settled and fed back into
reputation.

```
Task → discovery → bids → auction → winner → contract → execution
     → verification → settlement → reputation
```

Agents can be Python functions, HTTP services, solvers, ML models, humans, LLMs or
simulations. Nothing requires an LLM, an API key or a cloud service: everything
runs locally, and seeded simulations are deterministic.

```bash
pip install auctionsi
```

## What you can do with it

- **Allocate work between agents with auctions.** First-price and second-price
  (Vickrey-style, critical-value) reverse auctions, multi-winner, open descending,
  forward auctions with reserve prices, bundle (combinatorial) auctions with exact
  winner determination, and capacity (multi-unit) procurement.
  See [auction mechanisms](mechanisms.md).
- **Choose winners on more than price.** Explainable policies weigh price, quality,
  latency, reliability and reputation; every score is split into named
  contributions. See [winner selection](selection.md).
- **Trust results only after checking them.** Verifiers (schema, exact match,
  tolerance, metrics, unit tests, human approval) decide payment; settlement applies
  penalties and bonuses; reputation learns from delivered work.
  See [core concepts](concepts.md).
- **Study markets before you run them.** Simulate thousands of agents with bidding
  strategies (including a learning bidder), collusion, Sybil identities and
  misreporting, then run replicated experiments with confidence intervals and
  Holm-adjusted tests. See [simulation and experiments](simulation-and-experiments.md)
  and the [research results](../research/README.md).
- **Operate it.** A CLI, a REST/WebSocket API with a web dashboard, SQLite or
  PostgreSQL storage, an append-only event log and deterministic replay of every
  decision. See [CLI](cli.md), [API](api.md) and [storage](storage.md).

## Documentation map

- [Getting started](getting-started.md): install, first auction, CLI, API
- [Core concepts](concepts.md): tasks, agents, bids, lifecycle, verification, settlement, reputation, recovery, events
- [Architecture](architecture.md): packages and design decisions
- [Auction mechanisms](mechanisms.md): rules, payments, assumptions, strategic considerations
- [Winner selection](selection.md)
- [Simulation, experiments and metrics](simulation-and-experiments.md)
- [Writing agents, verifiers and plugins](extending.md)
- [CLI and configuration](cli.md)
- [REST/WebSocket API and dashboard](api.md)
- [Storage](storage.md): SQLite, PostgreSQL, schema and migrations
- [Roadmap](roadmap.md): what exists, what is proposed
- [Development](development.md): tests, quality checks, releases
- [Security](../SECURITY.md), [changelog](../CHANGELOG.md), [contributing](../CONTRIBUTING.md)
- [Research experiments and results](../research/README.md), [benchmarks](../benchmarks/README.md)
- [Examples](../examples/)
