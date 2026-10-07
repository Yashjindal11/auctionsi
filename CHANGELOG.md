# Changelog

## [Unreleased]

- Agents can be removed: `Marketplace.unregister` also deletes the stored profile,
  `DELETE /api/agents/{id}`, `auctionsi agent remove`, and a dashboard button.
  Past bids, contracts and reputation observations are kept.
- Breaking (API): the WebSocket no longer accepts `?key=`; send `X-API-Key` on the
  upgrade or a first `{"type": "auth", "key": ...}` message.
- Fix: a WebSocket client that fell 10,000 events behind made every broadcast
  raise `QueueFull`; it now loses its oldest events instead.
- Fix: a non-ASCII `X-API-Key` header caused a 500 instead of a 401.
- Fix: PostgreSQL `status()` could include the password for `key=value` DSNs or
  passwords given as URL parameters; it now reports `host:port/dbname` only.
- `MarketConfig.restore(store)` rebuilds a marketplace (agents and reputation)
  from a store; the CLI and API share it. `open_store` accept
- Documentation site on Material for MkDocs with search, per-page descriptions,
  canonical URLs, sitemap, Open Graph and JSON-LD metadata; the changelog, security
  policy, contributing guide, benchmarks and every research report are published
  with working links. New pages: getting started, storage, development, roadmap.
  CI builds the site in strict mode.
- Tests for Markdown reports, bid validation, replay edge cases and CLI paths;
  coverage gate raised to 93%.s `check_same_thread`.
- Dashboard: live view reconnects with backoff, skips malformed frames, reports a
  rejected key; clickable table rows work from the keyboard; labelled inputs;
  invalid JSON and out-of-range task counts are reported before calling the API.
- Dashboard test suite (Vitest + Testing Library), run in CI.

## [0.2.0] - 2026-10-04

Mechanisms and bidding
- Forward auctions (first or second price) with `Task.reserve_price`;
  direction-aware contracts and settlements.
- Bundle (combinatorial) reverse auction with exact winner determination.
- Capacity (multi-unit) procurement auction, pay-as-bid or uniform; `Award.quantity`.
- Learning bidder `BanditMarkup` (`bandit`: UCB1 or epsilon-greedy).
- `ExplorationBonus` selection policy.

Marketplace
- Concurrent bid solicitation with a deadline (`bid_timeout`), `execution_timeout`.
- HMAC-signed bids bound to agent, auction and task (`bid_keys`, `require_signatures`).
- New rejection codes `TIMEOUT`, `BAD_SIGNATURE`, `BELOW_RESERVE`.
- Capability index for discovery; `retain_results=False` for long runs.

Research
- Experiment configs: `environment.adversaries`, mid-run `environment.changes`,
  factorial `factors`.
- Metrics: `average_winning_markup`, `total_verification_cost`, `bid_cv`,
  `relative_distance`; buyer utility subtracts verification cost.
- Calibration reports (`auctionsi calibration`).
- Four new experiments (learning bidders, reputation decay, collusion screens,
  factorial); all results regenerated.

Interfaces and storage
- Optional REST/WebSocket API with API-key auth (`auctionsi[api]`, `auctionsi serve`).
- Web dashboard bundled in the wheel.
- PostgreSQL store (`auctionsi[postgres]`, `--db postgresql://...`) on a shared SQL
  base; SQLite schema v2 (indexes, `tasks.saved_at`).
- HTTP agents can be registered declaratively (`kind: http`).

Fixes
- Reputation quality and claim calibration use delivered work only, so failed
  executions no longer count as quality 0.
- Sybil copies of colluders keep an independent copy of the strategy.
- Factor levels that share a plugin name get distinct arm labels.

CI: PostgreSQL service, coverage gate (88%), dashboard build, docs site.

## [0.1.1] - 2026-10-03

- Fix: agent capacity is only held on simulated clocks. With a real clock a
  synchronous execution has already finished, and coarse OS timers (Windows) made
  agents look permanently busy.
- Text files are always read and written as UTF-8.
- First PyPI release (`pip install auctionsi`), published with trusted publishing.

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
