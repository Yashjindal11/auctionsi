---
description: >-
  Core concepts of AuctionSI: tasks, agents, capabilities, bids, the auction and
  contract lifecycles, discovery, bid validation, verification, settlement,
  reputation, recovery, events and replay.
---

# Core concepts

| concept | object | notes |
|---|---|---|
| Market | `Marketplace` | agents + plugins + event bus |
| Task | `Task` | type, requirements, constraints, budget, deadline (seconds), `min_quality`, `value`, abstract `unit` |
| Agent | `Agent` subclass | declares capabilities; implements `bid` and `execute` |
| Capability | `Capability` | name, version, accepted input/output formats, `max_*`/`min_*` constraints |
| Bid | `BidProposal` → `Bid` | the agent proposes; the market validates and stamps |
| Auction | `Auction` | mutable record with a state machine |
| Contract | `Contract` | agreed price vs payment price, deadline, quality requirement |
| Execution | `ExecutionResult` | the agent's output; *not* acceptance |
| Verification | `VerificationResult` | named checks → passed + quality score |
| Settlement | `Settlement` | payment, penalty, bonus, refund |
| Reputation | `ReputationProfile` | many dimensions, overall and per task type |

## Lifecycle

```
CREATED → ANNOUNCED → OPEN → BID_COLLECTION → CLOSED → EVALUATION → AWARDED
        → CONTRACTED → EXECUTING → VERIFYING → SETTLED
failures: NO_BIDS, FAILED, CANCELLED, EXPIRED
recovery loops: VERIFYING → EXECUTING (retry / next contract), VERIFYING → AWARDED (backup)
```

Invalid transitions raise `InvalidTransitionError`. Contracts have their own state
machine (`created → executing → delivered → fulfilled|breached`, or `cancelled`
before execution; a cancelled contract cannot execute).

## Discovery

`find_agents(task)` returns candidates — agents that have the capability, are
available, accept the formats, satisfy constraints and have spare capacity. It
never picks a winner. Agents that claim the capability but fail a check are listed
with reasons; agents without it are counted.

## Bid validation

Rejections are structured (`RejectionCode` + message): unknown task, ineligible
agent, capability mismatch, malformed proposal, invalid/negative price, over budget,
invalid latency, deadline infeasible, estimates outside [0, 1], below the required
quality, expired, duplicate, non-improving revision, too many bids, agent error.
`BidValidationConfig` toggles the policy rules and adds an optional per-operator
bid cap (a Sybil defence).

## Verification and quality

Quality is always computed from checks: `VerificationResult.from_checks` uses the
weighted mean of check scores; `passed` means every *required* check passed. After
the verifier runs, the marketplace adds a `min_quality` gate check if the task sets
one. Built-ins: `SchemaVerifier`, `ExactMatchVerifier`, `ToleranceVerifier`,
`MetricThresholdVerifier`, `UnitTestVerifier` (callables written by the task owner),
`CompositeVerifier`, `HumanApprovalVerifier`, `CallableVerifier`. None calls a model.

## Settlement

`PayOnPass` (default), `QualityProportionalPayment`, `PartialPaymentOnFailure`.
`buyer_cost = payment + bonus - penalty`. Units are abstract (`credits`, `points`,
`compute_credits`...).

## Reputation

`MultiDimensionalReputation` tracks raw counts and decay-weighted rates: success,
average quality, on-time rate, quality-estimate error and bias (over-promising),
latency-estimate error and violations. `success_estimate` is a Beta-posterior mean,
so newcomers start at the prior (0.5 by default). Decay: `NoDecay` (plain average),
`ExponentialDecay(half_life)` in observations, `RollingWindow(size)`. Decay makes
reputation track agents that change but forgets good history faster and is noisier.
`NoReputation` and `StaticReputation` are research baselines.

## Recovery

`RecoveryPolicy(retry_same, next_best, reopen)`: retry the same agent (new contract,
`attempt+1`), fail over to the next-ranked backup (paid its own bid), or reopen a new
auction excluding failed agents (single-winner only). Default: none.

## Events and replay

Every step is an immutable `Event` (`seq`, type, timestamp, ids, JSON data).
`AuctionResult.trace()` renders them; `replay_auction(events)` rebuilds the mechanism
and policy from their recorded specs and re-derives winners and payments from the
recorded bids and reputation snapshot.
