# Architecture

AuctionSI is the infrastructure; everything that decides an outcome is a plugin.

```
                  ┌──────────────────── Marketplace ─────────────────────┐
 Task ──────────▶ │ discovery ─▶ BidIntake ─▶ AuctionMechanism           │
                  │   (find_agents)  (validate,   (collect_bids,         │
                  │                   stamp)       determine_winners)    │
                  │                                   │ uses             │
                  │                          SelectionPolicy + features  │
                  │                                   ▼                  │
                  │ Contract ─▶ Agent.execute ─▶ Verifier ─▶ Settlement  │
                  │                                   ▼                  │
                  │                 ReputationSystem.record(Observation) │
                  │                 RecoveryPolicy (retry / backup / reopen)
                  └──────────────┬───────────────────────────────────────┘
                                 │ every step
                                 ▼
                     EventBus ─▶ EventLog, MarketStore (SQLite), JsonEventLogger,
                                 MarketCounters, your subscribers
```

## Packages

| package | responsibility |
|---|---|
| `core` | value objects: `Task`, `Capability`, `Agent`, `BidProposal`/`Bid`, `Auction` (state machine), `Contract`, `ExecutionResult`, `Settlement` |
| `market` | `Marketplace`, discovery, bid validation and intake, events, clocks/ids, recovery, results, trace, replay |
| `mechanisms` | `AuctionMechanism` and the built-in reverse auctions |
| `selection` | explainable `SelectionPolicy` implementations |
| `bidding` | `BidStrategy` implementations used by simulated agents |
| `verification` | deterministic verifiers and the JSON-Schema subset |
| `settlement` | settlement policies |
| `reputation` | multi-dimensional reputation and decay |
| `simulation` | synthetic agents/tasks, `simulate_market`, metrics, adversaries |
| `experiments` | configs, the replicated runner, manifests |
| `statistics` | summaries, paired/Welch comparisons, Holm, concentration |
| `storage` | `MarketStore` protocol, SQLite and in-memory stores |
| `adapters` | Python-function, HTTP, OpenAI-compatible and human agents |
| `reports`, `visualization`, `observability`, `cli`, `config`, `plugins` | outputs and wiring |

## Key decisions

- **Agents are untrusted.** They return a `BidProposal`; the marketplace validates it
  and stamps ids and timestamps. Exceptions from agents become recorded failures.
- **Selection is separate from the mechanism.** "Who ranks first" (policy) and "who
  is awarded and what are they paid" (mechanism) are independent plugins, so a
  second-price rule can sit on top of a quality-weighted ranking.
- **Decisions are pure.** Mechanisms and policies are deterministic functions of the
  bids, the task and a reputation-features snapshot. That snapshot is recorded in
  the `WinnerSelected` event, which is what makes replay possible.
- **Events, not callbacks.** Every lifecycle step publishes an immutable, timestamped
  `Event` with a sequence number. Persistence, logging and metrics are subscribers.
  Full event sourcing is not implemented, but events carry enough to add it.
- **Synchronous core.** `submit_task` runs the lifecycle to completion in-process.
  Time comes from a `Clock` (wall clock in production, `ManualClock` in simulations),
  and agent capacity is tracked against it.
- **Local first.** No network calls, API keys or cloud services in the core.
  Persistence is SQLite with versioned migrations and JSON columns (no pickle).

## Not in v0.1

REST/WebSocket API, web dashboard, distributed execution, combinatorial (bundle)
and forward auctions, capacity reservations and learning bidders. The interfaces
(`AuctionMechanism.direction`, the staged `open_auction`/`submit_bid`/`close_auction`
API, `MarketStore`) are designed so these can be added without changing the core.
