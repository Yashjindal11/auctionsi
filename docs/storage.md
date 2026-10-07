---
description: >-
  How AuctionSI persists agents, tasks, auctions, bids, contracts, settlements,
  events and reputation observations in SQLite or PostgreSQL, with versioned
  migrations and deterministic replay.
---

# Storage

A marketplace runs fully in memory unless a store is attached. With a store, every
event and every finished auction is written as it happens.

| store | use | install |
|---|---|---|
| `InMemoryStore` | tests and notebooks | core |
| `SQLiteStore(path)` | default for the CLI and API (`./auctionsi.db`) | core |
| `PostgresStore(dsn)` | shared or larger deployments | `pip install "auctionsi[postgres]"` |

```python
from auctionsi import Marketplace, PythonFunctionAgent, Task
from auctionsi.storage import open_store

store = open_store("market.db")  # or "postgresql://user@host/dbname"
market = Marketplace(store=store)
market.register(PythonFunctionAgent("a", lambda t, c: {}, capabilities=["qa"], price=1.0))
result = market.submit_task(Task(task_id="t-1", task_type="qa"))
assert store.get_auction(result.auction_id)["status"] == "settled"
store.close()
```

`open_store(url)` picks PostgreSQL for `postgresql://` or `postgres://` URLs and
SQLite for anything else. The CLI's `--db` and `create_app(db_path)` accept the
same values.

## What is stored

Both backends share one schema (`SQLStore` holds all SQL, written with `?`
placeholders and `ON CONFLICT` upserts; PostgreSQL translates the placeholders).
Structured values are JSON text columns; nothing is pickled.

| table | key | contents |
|---|---|---|
| `agents` | `agent_id` | public profile (`describe()`), private spec used to rebuild the agent, registration time |
| `tasks` | `task_id` | task type, full task, save time |
| `auctions` | `auction_id` | status, mechanism, parent auction (re-opened auctions), full result record |
| `bids` | `bid_id` | auction, agent, price, full bid |
| `contracts` | `contract_id` | auction, agent, status, full contract with execution and verification |
| `settlements` | `contract_id` | agent, buyer cost, full settlement |
| `events` | auto id | run id, sequence number, type, timestamp, related ids, event data |
| `observations` | auto id | per-agent, per-task-type reputation observations |
| `experiments` | `experiment_id` | name, manifest and results (`experiment run --save-db`) |
| `schema_version` | | applied migration versions |

Indexes cover auctions by task, bids by auction and agent, contracts by agent,
events by auction and observations by agent.

Removing an agent (`Marketplace.unregister`, `DELETE /api/agents/{id}`,
`auctionsi agent remove`) deletes its `agents` row only. Its bids, contracts,
settlements, events and observations stay, so past auctions remain replayable.

## Reading it back

`list_agents()`, `get_agent(id)`, `list_tasks()`, `list_auctions(status=)`,
`get_auction(id)`, `agent_bids(id)`, `fulfilled_contracts(id)`, `events(auction_id)`,
`observations(agent_id)`, `list_experiments()` and `status()` (row counts, auctions
by status, total buyer cost, schema version and a location string). For
PostgreSQL the location is `host:port/dbname`; user names, passwords and options
are never included.

`MarketConfig.restore(store)` builds a marketplace with every stored agent that
has a spec and with reputation rebuilt from the stored observations. The CLI and the
API both start this way, so a restarted service keeps its agents and their
reputation.

## Migrations

Migrations are numbered SQL scripts applied in order when a store opens
(`migrate()` is idempotent). A released migration is never edited; schema changes
add a new version.

| version | change |
|---|---|
| 1 | initial schema |
| 2 | `tasks.saved_at`, indexes on `bids.agent_id` and `contracts.agent_id` (PostgreSQL has these in version 1; its version 2 is a no-op so both report the same version) |

## Performance

Each write commits immediately by default. For simulations, group writes:

```python
from auctionsi import Marketplace
from auctionsi.simulation import generate_agents, generate_tasks
from auctionsi.storage import SQLiteStore

store = SQLiteStore("sim.db")
market = Marketplace(store=store)
for agent in generate_agents(5, seed=1):
    market.register(agent)
with store.batch():  # one transaction
    for t in generate_tasks(20, seed=1):
        market.submit_task(t)
store.close()
```

The [benchmarks](../benchmarks/README.md) include a SQLite-persisted scenario.

## Threads

A `SQLiteStore` is used from the thread that created it unless opened with
`check_same_thread=False`; the API does that and serialises all access under one
lock. Stores are not designed for several processes writing at once; use
PostgreSQL if more than one process needs the data.
