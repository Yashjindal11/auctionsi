---
description: >-
  The AuctionSI roadmap: what is implemented in each release, what is proposed
  next, and known limitations, with no promised dates.
---

# Roadmap

No dates are promised. "Proposed" means not started; anything not listed under a
release does not exist yet.

## Released

**0.1** - the core marketplace: tasks, agents, validated bids, auction and contract
state machines; first-price, second-price, multi-winner and open descending reverse
auctions; explainable selection policies; deterministic verifiers; settlement;
multi-dimensional reputation with decay; recovery (retry, fail-over, re-open);
events, traces and deterministic replay; SQLite; simulation, metrics and replicated
experiments; Python, HTTP, OpenAI-compatible and human agents; the CLI.

**0.2** - forward, bundle (combinatorial) and capacity auctions; a learning (bandit)
bidder; exploration-bonus selection; adversaries, mid-run changes and factorial
sweeps in experiment configs; calibration reports; HMAC-signed bids and bid and
execution timeouts; PostgreSQL; the REST/WebSocket API and dashboard.

**Unreleased** - agent removal across API, CLI and dashboard; WebSocket
authentication without URLs; dashboard reconnects and tests; see the
[changelog](../CHANGELOG.md).

## Proposed

Mechanisms and selection
- Scoring auctions (announced scoring rules over price and quality) and
  reserve-price variants for reverse auctions.
- Larger bundle auctions. The exact dynamic program is exponential in the number of
  items, so `BundleReverseAuction` caps it (`max_items`, default 12); larger
  instances need a solver or heuristics.
- Double auctions, where several buyers and sellers trade at once.

Market integrity
- Per-auction and per-group collusion screens. The
  [collusion experiment](../research/README.md) found that the market-wide averages
  of the current screens did not detect a simple bid-rotation cartel.
- Identity verification behind `metadata["operator"]`, which the Sybil cap relies on.

Operations
- Distributed execution: agents and auctions across processes or machines (today
  one process runs the market, with concurrent bid solicitation in a thread pool).
- Multi-tenant API with per-user keys and permissions (today one shared key).
- Sandboxing for in-process Python agents.

Interoperability
- Adapters for standard agent-to-agent protocols, so agents built for other
  frameworks can bid without custom code.

Stability
- **1.0**: a stable public API with a deprecation policy.

## Known limitations

- Incentive properties (for example truthful bidding under second price) hold only
  under the assumptions stated in [auction mechanisms](mechanisms.md); learning
  bidders in the research results do not bid truthfully.
- Research results come from synthetic markets, not measurements of real agents.
- The SQLite store expects one writing process.

Suggestions and contributions are welcome: see [contributing](../CONTRIBUTING.md).
