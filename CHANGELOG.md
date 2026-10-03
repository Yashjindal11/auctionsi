# Changelog

## [0.1.0] - 2026-10-03

First release.

- Core models: tasks, capabilities, agents, bid proposals and stamped bids, contracts,
  execution results, settlements; auction and contract state machines.
- Marketplace running the full lifecycle (discovery, validated bid intake, award,
  contract, execution, verification, settlement, reputation), with a staged API for
  external bids, cancellation, capacity tracking and recovery (retry, fail-over, re-open).
- Mechanisms: first-price, second-price (critical value), multi-winner, open descending.
- Explainable selection policies: lowest price, highest quality, lowest latency,
  weighted score, risk-adjusted cost, reputation-adjusted cost.
- Deterministic verifiers, settlement policies, multi-dimensional reputation with decay.
- Event bus, traces, JSON logging, counters, SQLite persistence, deterministic replay.
- Simulation (synthetic agents/tasks, bid strategies, dynamics, adversaries), market
  metrics, experiment runner with manifests, statistics and Markdown reports.
- Adapters: Python function, HTTP, OpenAI-compatible (optional), human.
- CLI, YAML configuration, Plotly figures (optional), examples, benchmarks, research configs.
