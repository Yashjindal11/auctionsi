"""The Marketplace: the runtime that drives the full auction lifecycle.

``Task -> discovery -> bids -> auction -> winner -> contract -> execution ->
verification -> settlement -> reputation``, with every step emitted as an event.
Every component is a replaceable plugin passed to the constructor (or per task).
"""

from __future__ import annotations

import json
import math
from collections import deque
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from typing import Any

from auctionsi.core.agent import Agent, AuctionNotice
from auctionsi.core.auction import Auction, AuctionStatus
from auctionsi.core.bid import Bid
from auctionsi.core.contract import Contract, ContractStatus
from auctionsi.core.execution import ExecutionResult
from auctionsi.core.task import Task
from auctionsi.errors import (
    InvalidTransitionError,
    NotFoundError,
    ValidationError,
)
from auctionsi.market.clock import Clock, IdGenerator, WallClock
from auctionsi.market.discovery import DiscoveryResult, find_agents
from auctionsi.market.events import Event, EventBus, EventLog, EventType
from auctionsi.market.intake import BidIntake
from auctionsi.market.recovery import RecoveryPolicy
from auctionsi.market.result import AuctionResult, ContractOutcome
from auctionsi.market.validation import BidValidationConfig
from auctionsi.mechanisms.base import AuctionMechanism, MechanismOutcome
from auctionsi.mechanisms.first_price import FirstPriceReverseAuction
from auctionsi.plugins import PluginRegistry, default_registry
from auctionsi.reputation.base import (
    MultiDimensionalReputation,
    Observation,
    ReputationSystem,
)
from auctionsi.security import DEFAULT_LIMITS, Limits, check_json_size
from auctionsi.selection.policies import LowestPrice, ScoredBid, SelectionPolicy
from auctionsi.settlement.policies import PayOnPass, SettlementPolicy
from auctionsi.storage.base import MarketStore
from auctionsi.verification.verifiers import (
    AcceptVerifier,
    CheckResult,
    SchemaVerifier,
    VerificationResult,
    Verifier,
)

S = AuctionStatus
E = EventType


@dataclass
class _Pending:
    intake: BidIntake
    discovery: DiscoveryResult
    mechanism: AuctionMechanism
    policy: SelectionPolicy
    verifier: Verifier | None
    settlement: SettlementPolicy
    reopens_left: int
    exclude: set[str] = field(default_factory=set)


class Marketplace:
    """Coordinates agents, auctions and everything that follows an award.

    The simplest use is :meth:`submit_task`, which runs an auction to completion.
    For external or human bidders use the staged API: :meth:`open_auction`,
    :meth:`submit_bid`, then :meth:`close_auction` (or :meth:`cancel_auction`).
    """

    def __init__(
        self,
        name: str = "market",
        *,
        mechanism: AuctionMechanism | None = None,
        policy: SelectionPolicy | None = None,
        verifier: Verifier | None = None,
        settlement: SettlementPolicy | None = None,
        reputation: ReputationSystem | None = None,
        recovery: RecoveryPolicy | None = None,
        validation: BidValidationConfig | None = None,
        clock: Clock | None = None,
        ids: IdGenerator | None = None,
        bus: EventBus | None = None,
        limits: Limits = DEFAULT_LIMITS,
        keep_events: bool = True,
        max_events: int | None = None,
        disclose_clearing_price: bool = False,
        bidding_window: float | None = None,
        store: MarketStore | None = None,
        plugins: PluginRegistry | None = None,
        retain_results: bool = True,
        bid_timeout: float | None = None,
        execution_timeout: float | None = None,
        max_workers: int = 16,
        bid_keys: Mapping[str, bytes] | None = None,
        require_signatures: bool = False,
    ) -> None:
        self.name = name
        self.mechanism = mechanism or FirstPriceReverseAuction()
        self.policy = policy or LowestPrice()
        self.verifier = verifier
        self.settlement = settlement or PayOnPass()
        self.reputation = reputation if reputation is not None else MultiDimensionalReputation()
        self.recovery = recovery or RecoveryPolicy()
        self.validation = validation or BidValidationConfig()
        self.clock: Clock = clock or WallClock()
        self.ids = ids or IdGenerator()
        self.bus = bus or EventBus()
        self.limits = limits
        self.disclose_clearing_price = disclose_clearing_price
        self.bidding_window = bidding_window
        self.plugins = plugins or default_registry()
        self.retain_results = retain_results
        self._bid_timeout = bid_timeout
        self.execution_timeout = execution_timeout
        self.max_workers = max_workers
        self._executor: ThreadPoolExecutor | None = None
        # HMAC keys per agent: bids from these agents must be signed (see security.signing).
        self.bid_keys = dict(bid_keys or {})
        self.require_signatures = require_signatures
        self.log: EventLog | None = EventLog(max_events) if keep_events else None
        self._collecting: dict[str, list[Event]] = {}
        if self.log is not None:
            self.bus.subscribe(self.log)
            self.bus.subscribe(self._collect)
        self.store: MarketStore | None = None
        if store is not None:
            self.attach_store(store)
        self._agents: dict[str, Agent] = {}
        self._sorted_agents: list[Agent] | None = None
        self._by_capability: dict[str, list[Agent]] = {}
        self._index_epoch = -1
        self._task_ids: set[str] = set()
        self._busy: dict[str, list[float]] = {}
        self._pending: dict[str, _Pending] = {}
        self.auctions: dict[str, Auction] = {}
        self.results: dict[str, AuctionResult] = {}

    # ------------------------------------------------------------------ plugins

    def attach_store(self, store: MarketStore) -> None:
        """Persist everything from now on (events, tasks, auctions, observations)."""
        if self.store is not None:
            raise ValidationError("a store is already attached")
        self.store = store
        self.bus.subscribe(store.record_event)

    def register_auction_mechanism(
        self, name: str, factory: Callable[..., AuctionMechanism]
    ) -> None:
        self.plugins.mechanisms.register(name, factory)

    def register_selection_policy(self, name: str, factory: Callable[..., SelectionPolicy]) -> None:
        self.plugins.policies.register(name, factory)

    def register_verifier(self, name: str, factory: Callable[..., Verifier]) -> None:
        self.plugins.verifiers.register(name, factory)

    def register_settlement_policy(
        self, name: str, factory: Callable[..., SettlementPolicy]
    ) -> None:
        self.plugins.settlements.register(name, factory)

    # ------------------------------------------------------------------- agents

    def register(self, agent: Agent, *, spec: dict[str, Any] | None = None) -> None:
        if agent.agent_id in self._agents:
            raise ValidationError(f"agent {agent.agent_id} is already registered")
        self._agents[agent.agent_id] = agent
        self._sorted_agents = None
        profile = agent.describe()
        self.bus.publish(
            E.AGENT_REGISTERED, self.clock.now(), agent_id=agent.agent_id, data=profile
        )
        if self.store is not None:
            self.store.save_agent(profile, spec)

    def unregister(self, agent_id: str) -> Agent:
        agent = self.get_agent(agent_id)
        del self._agents[agent_id]
        self._sorted_agents = None
        self.bus.publish(E.AGENT_UNREGISTERED, self.clock.now(), agent_id=agent_id)
        return agent

    def get_agent(self, agent_id: str) -> Agent:
        try:
            return self._agents[agent_id]
        except KeyError:
            raise NotFoundError(f"agent {agent_id} is not registered") from None

    @property
    def agents(self) -> list[Agent]:
        return list(self._agents.values())

    def agent_updated(self, agent_id: str, **changes: Any) -> None:
        """Record that an agent changed (availability, capabilities, costs...)."""
        self.bus.publish(
            E.AGENT_UPDATED, self.clock.now(), agent_id=agent_id, data=_jsonable(changes)
        )

    def active_contracts(self) -> dict[str, int]:
        now = self.clock.now()
        counts = {}
        for agent_id, ends in self._busy.items():
            ends[:] = [t for t in ends if t > now]
            if ends:
                counts[agent_id] = len(ends)
        return counts

    def find_agents(self, task: Task, *, exclude: Iterable[str] = ()) -> DiscoveryResult:
        if self._sorted_agents is None or self._index_epoch != Agent.capability_epoch:
            self._sorted_agents = sorted(self._agents.values(), key=lambda a: a.agent_id)
            self._by_capability = {}
            for agent in self._sorted_agents:
                for cap in agent.capabilities:
                    self._by_capability.setdefault(cap.name, []).append(agent)
            self._index_epoch = Agent.capability_epoch
        capable = self._by_capability.get(task.task_type, [])
        found = find_agents(
            task,
            capable,
            active_contracts=self.active_contracts(),
            exclude=exclude,
            presorted=True,
        )
        return DiscoveryResult(
            found.candidates, found.excluded, len(self._sorted_agents) - len(capable)
        )

    @property
    def bid_timeout(self) -> float | None:
        """Bidding deadline in real seconds; simulated clocks never wait."""
        if self._bid_timeout is not None:
            return self._bid_timeout
        if self.bidding_window is not None and not getattr(self.clock, "simulated", False):
            return self.bidding_window
        return None

    def _pool(self) -> ThreadPoolExecutor:
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=self.max_workers, thread_name_prefix="auctionsi"
            )
        return self._executor

    def close(self) -> None:
        """Release worker threads (only created when timeouts are used)."""
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None

    # ------------------------------------------------------------------- tasks

    def submit_task(
        self,
        task: Task,
        *,
        mechanism: AuctionMechanism | None = None,
        policy: SelectionPolicy | None = None,
        verifier: Verifier | None = None,
        settlement: SettlementPolicy | None = None,
    ) -> AuctionResult:
        """Run a complete auction for ``task`` and return its result."""
        auction = self.open_auction(
            task, mechanism=mechanism, policy=policy, verifier=verifier, settlement=settlement
        )
        return self.close_auction(auction.auction_id)

    def open_auction(
        self,
        task: Task,
        *,
        mechanism: AuctionMechanism | None = None,
        policy: SelectionPolicy | None = None,
        verifier: Verifier | None = None,
        settlement: SettlementPolicy | None = None,
        solicit: bool = True,
    ) -> Auction:
        """Create, announce and open an auction; with ``solicit`` registered eligible
        agents are asked for bids immediately. Leaves the auction in BID_COLLECTION."""
        if not isinstance(task, Task):
            raise ValidationError("task must be a Task")
        if task.task_id in self._task_ids:
            raise ValidationError(f"task {task.task_id} was already submitted")
        self._task_ids.add(task.task_id)
        task_event = self.bus.publish(
            E.TASK_CREATED, self.clock.now(), task_id=task.task_id, data=task.to_dict()
        )
        if self.store is not None:
            self.store.save_task(task.to_dict())
        return self._open(
            task,
            mechanism or self.mechanism,
            policy or self.policy,
            verifier or self.verifier,
            settlement or self.settlement,
            reopens_left=self.recovery.reopen,
            exclude=set(),
            parent=None,
            solicit=solicit,
            task_event=task_event,
        )

    def submit_bid(self, auction_id: str, agent_id: str, proposal: object) -> Bid | None:
        """Submit a proposal from outside the solicitation loop (API, human, script)."""
        pending = self._pending_for(auction_id)
        if pending.intake.auction.status != S.BID_COLLECTION:
            raise InvalidTransitionError(f"auction {auction_id} is not collecting bids")
        return pending.intake.submit(agent_id, proposal)

    def close_auction(self, auction_id: str) -> AuctionResult:
        pending = self._pending_for(auction_id)
        try:
            return self._close(pending)
        finally:
            self._pending.pop(auction_id, None)

    def cancel_auction(self, auction_id: str, reason: str = "cancelled") -> Auction:
        auction = self._auction(auction_id)
        now = self.clock.now()
        auction.transition(S.CANCELLED, now)
        for contract in auction.contracts:
            if contract.status == ContractStatus.CREATED:
                contract.cancel(now)
        self._pending.pop(auction_id, None)
        self.bus.publish(
            E.AUCTION_CANCELLED,
            now,
            auction_id=auction_id,
            task_id=auction.task_id,
            data={"reason": reason},
        )
        return auction

    # --------------------------------------------------------------- internals

    def _collect(self, event: Event) -> None:
        if event.auction_id is not None and event.auction_id in self._collecting:
            self._collecting[event.auction_id].append(event)

    def _auction(self, auction_id: str) -> Auction:
        try:
            return self.auctions[auction_id]
        except KeyError:
            raise NotFoundError(f"auction {auction_id} does not exist") from None

    def _pending_for(self, auction_id: str) -> _Pending:
        self._auction(auction_id)
        try:
            return self._pending[auction_id]
        except KeyError:
            raise InvalidTransitionError(f"auction {auction_id} is no longer open") from None

    def _emit(
        self, type: EventType, auction: Auction, *, at: float | None = None, **kw: Any
    ) -> None:
        self.bus.publish(
            type,
            self.clock.now() if at is None else at,
            auction_id=auction.auction_id,
            task_id=auction.task_id,
            **kw,
        )

    def _open(
        self,
        task: Task,
        mechanism: AuctionMechanism,
        policy: SelectionPolicy,
        verifier: Verifier | None,
        settlement: SettlementPolicy,
        *,
        reopens_left: int,
        exclude: set[str],
        parent: str | None,
        solicit: bool,
        task_event: Event | None = None,
    ) -> Auction:
        now = self.clock.now()
        auction = Auction(
            auction_id=self.ids.next("auction"),
            task=task,
            mechanism=mechanism.name,
            created_at=now,
            bidding_window=self.bidding_window,
            parent_auction_id=parent,
        )
        self.auctions[auction.auction_id] = auction
        if self.log is not None:
            self._collecting[auction.auction_id] = [task_event] if task_event else []
        self._emit(
            E.AUCTION_CREATED,
            auction,
            data={
                "task": task.to_dict(),
                "mechanism": mechanism.to_spec(),
                "policy": policy.to_spec(),
                "parent_auction_id": parent,
            },
        )
        discovery = self.find_agents(task, exclude=exclude)
        auction.participants = discovery.candidate_ids
        auction.excluded = discovery.excluded
        self._emit(
            E.AGENTS_DISCOVERED,
            auction,
            data={
                "registered": len(self._agents),
                "eligible": discovery.candidate_ids,
                "excluded": discovery.excluded,
                "not_capable": discovery.not_capable,
            },
        )
        auction.transition(S.ANNOUNCED, now)
        self._emit(E.TASK_ANNOUNCED, auction)
        auction.transition(S.OPEN, now)
        self._emit(
            E.AUCTION_OPENED,
            auction,
            data={"sealed": mechanism.sealed, "bidding_window": self.bidding_window},
        )
        auction.transition(S.BID_COLLECTION, now)
        intake = BidIntake(
            auction,
            self._agents,
            clock=self.clock,
            ids=self.ids,
            bus=self.bus,
            config=self.validation,
            sealed=mechanism.sealed,
            limits=self.limits,
            timeout=self.bid_timeout,
            executor=self._pool() if self.bid_timeout is not None else None,
            bid_keys=self.bid_keys,
            require_signatures=self.require_signatures,
            direction=mechanism.direction,
        )
        pending = _Pending(
            intake, discovery, mechanism, policy, verifier, settlement, reopens_left, exclude
        )
        self._pending[auction.auction_id] = pending
        if solicit:
            mechanism.collect_bids(auction, discovery.candidates, intake)
        return auction

    def _close(self, pending: _Pending) -> AuctionResult:
        auction = pending.intake.auction
        task = auction.task
        now = self.clock.now()
        pending.intake.expire_stale()
        auction.transition(S.CLOSED, now)
        bids = sorted(auction.valid_bids, key=lambda b: b.agent_id)
        self._emit(
            E.AUCTION_CLOSED,
            auction,
            data={
                "valid": len(bids),
                "rejected": len(auction.rejected),
                "final_bids": [b.to_dict() for b in bids],
            },
        )
        features = {b.agent_id: self.reputation.features(b.agent_id, task.task_type) for b in bids}
        result = AuctionResult(auction, pending.discovery, features)
        if not bids:
            auction.transition(S.NO_BIDS, now)
            self._emit(E.NO_BIDS, auction)
            return self._finish(result, "no valid bids")

        auction.transition(S.EVALUATION, now)
        try:
            outcome = pending.mechanism.determine_winners(bids, task, pending.policy, features)
        except ValidationError as exc:
            auction.transition(S.FAILED, now)
            self._emit(E.AUCTION_FAILED, auction, data={"reason": str(exc)})
            return self._finish(result, f"winner determination failed: {exc}")
        result.outcome = outcome
        if not outcome.awards:
            auction.transition(S.NO_BIDS, now)
            self._emit(E.NO_BIDS, auction)
            return self._finish(result, "mechanism made no awards")

        auction.transition(S.AWARDED, now)
        self._emit(
            E.WINNER_SELECTED,
            auction,
            agent_id=outcome.awards[0].agent_id,
            bid_id=outcome.awards[0].bid.bid_id,
            data={
                "mechanism": pending.mechanism.to_spec(),
                "policy": pending.policy.to_spec(),
                "features": {k: f.to_dict() for k, f in features.items()},
                "outcome": outcome.to_dict(),
            },
        )
        all_passed, failed_agents = self._perform(auction, outcome, pending, result)
        end = self.clock.now()
        if all_passed:
            auction.transition(S.SETTLED, end)
            self._emit(E.AUCTION_SETTLED, auction, data=_summary(result))
            return self._finish(result)

        auction.transition(S.FAILED, end)
        reopen = pending.reopens_left > 0 and len(outcome.awards) == 1
        reason = "winner(s) failed to deliver"
        if reopen:
            reason += "; re-opening"
        self._emit(E.AUCTION_FAILED, auction, data={"reason": reason, **_summary(result)})
        self._finish(result, reason)
        if reopen:
            child_auction = self._open(
                task,
                pending.mechanism,
                pending.policy,
                pending.verifier,
                pending.settlement,
                reopens_left=pending.reopens_left - 1,
                exclude=pending.exclude | failed_agents,
                parent=auction.auction_id,
                solicit=True,
            )
            child_pending = self._pending[child_auction.auction_id]
            try:
                result.child = self._close(child_pending)
            finally:
                self._pending.pop(child_auction.auction_id, None)
        return result

    def _perform(
        self,
        auction: Auction,
        outcome: MechanismOutcome,
        pending: _Pending,
        result: AuctionResult,
    ) -> tuple[bool, set[str]]:
        backups: deque[ScoredBid] = deque(outcome.backups)
        failed: set[str] = set()
        all_passed = True
        for award in outcome.awards:
            bid, payment = award.bid, award.payment
            retries = failovers = 0
            attempt = 1
            while True:
                co = self._run_contract(auction, bid, payment, attempt, pending)
                result.contracts.append(co)
                if co.passed:
                    break
                failed.add(bid.agent_id)
                if retries < self.recovery.retry_same and bid.agent_id in self._agents:
                    retries += 1
                    attempt += 1
                    self._emit(
                        E.RECOVERY_STARTED,
                        auction,
                        agent_id=bid.agent_id,
                        data={"action": "retry_same", "agent_id": bid.agent_id, "attempt": attempt},
                    )
                    continue
                backup = self._next_backup(backups, failed)
                if backup is not None and failovers < self.recovery.next_best:
                    failovers += 1
                    bid, payment, attempt = backup.bid, backup.bid.price, 1
                    auction.transition(S.AWARDED, self.clock.now())
                    self._emit(
                        E.RECOVERY_STARTED,
                        auction,
                        agent_id=bid.agent_id,
                        bid_id=bid.bid_id,
                        data={"action": "next_best", "agent_id": bid.agent_id, "payment": payment},
                    )
                    continue
                all_passed = False
                break
        return all_passed, failed

    def _next_backup(self, backups: deque[ScoredBid], failed: set[str]) -> ScoredBid | None:
        while backups:
            candidate = backups.popleft()
            if candidate.agent_id not in failed and candidate.agent_id in self._agents:
                return candidate
        return None

    def _run_contract(
        self, auction: Auction, bid: Bid, payment: float, attempt: int, pending: _Pending
    ) -> ContractOutcome:
        task = auction.task
        agent = self._agents[bid.agent_id]
        start = self.clock.now()
        contract = Contract(
            contract_id=self.ids.next("contract"),
            auction_id=auction.auction_id,
            task_id=task.task_id,
            agent_id=bid.agent_id,
            bid_id=bid.bid_id,
            agreed_price=bid.price,
            payment_price=payment,
            unit=task.unit,
            created_at=start,
            deadline=task.deadline,
            min_quality=task.min_quality,
            output_requirements=task.expected_output_schema,
            verification_method=self._verifier_for(task, pending).name,
            penalty_policy=pending.settlement.name,
            estimated_quality=bid.estimated_quality,
            estimated_latency=bid.estimated_latency,
            attempt=attempt,
            direction=pending.mechanism.direction,
        )
        auction.contracts.append(contract)
        ids: dict[str, Any] = {"agent_id": bid.agent_id, "contract_id": contract.contract_id}
        self._emit(E.CONTRACT_CREATED, auction, **ids, data=contract.to_dict())
        if auction.status == S.AWARDED:
            auction.transition(S.CONTRACTED, start)
        auction.transition(S.EXECUTING, start)
        contract.start(start)
        self._emit(E.TASK_STARTED, auction, **ids)

        execution = self._execute(agent, task, contract)
        done = start + execution.latency
        # With a real clock the synchronous call has already finished, so only simulated time holds capacity.
        if getattr(self.clock, "simulated", False):
            self._busy.setdefault(agent.agent_id, []).append(done)
        if execution.success:
            contract.transition(ContractStatus.DELIVERED, done)
            self._emit(
                E.TASK_COMPLETED,
                auction,
                at=done,
                **ids,
                data={"latency": execution.latency, "actual_cost": execution.actual_cost},
            )
        else:
            contract.transition(ContractStatus.BREACHED, done)
            self._emit(
                E.TASK_FAILED,
                auction,
                at=done,
                **ids,
                data={"latency": execution.latency, "error": execution.error},
            )

        auction.transition(S.VERIFYING, done)
        verification = self._verify(execution, contract, task, pending)
        on_time = execution.success and (
            contract.deadline is None or execution.latency <= contract.deadline
        )
        if execution.success:
            contract.transition(
                ContractStatus.FULFILLED if verification.passed else ContractStatus.BREACHED, done
            )
        self._emit(
            E.VERIFICATION_PASSED if verification.passed else E.VERIFICATION_FAILED,
            auction,
            at=done,
            **ids,
            data=verification.to_dict(),
        )
        settlement = pending.settlement.settle(contract, verification, on_time)
        self._emit(E.SETTLEMENT_COMPLETED, auction, at=done, **ids, data=settlement.to_dict())

        observation = Observation(
            agent_id=agent.agent_id,
            task_type=task.task_type,
            success=verification.passed,
            quality=verification.quality_score,
            on_time=on_time,
            latency=execution.latency,
            price=payment,
            estimated_quality=bid.estimated_quality,
            estimated_latency=bid.estimated_latency,
            violation=not verification.passed,
            timestamp=done,
            delivered=execution.success,
        )
        self.reputation.record(observation)
        profile = self.reputation.profile(agent.agent_id, task.task_type)
        self._emit(
            E.REPUTATION_UPDATED,
            auction,
            at=done,
            **ids,
            data={
                "observation": observation.to_dict(),
                "profile": profile.to_dict() if profile else None,
            },
        )
        if self.store is not None:
            self.store.save_observation(observation)
        return ContractOutcome(contract, execution, verification, settlement, observation)

    def _execute(self, agent: Agent, task: Task, contract: Contract) -> ExecutionResult:
        try:
            if self.execution_timeout is None:
                result = agent.execute(task, contract)
            else:
                future = self._pool().submit(agent.execute, task, contract)
                try:
                    result = future.result(timeout=self.execution_timeout)
                except FutureTimeout:
                    # Python cannot kill the thread; the late result is simply discarded.
                    future.cancel()
                    return ExecutionResult.failure(
                        f"execution timed out after {self.execution_timeout}s",
                        latency=self.execution_timeout,
                    )
        except Exception as exc:
            return ExecutionResult.failure(f"{type(exc).__name__}: {exc}"[:300])
        if not isinstance(result, ExecutionResult):
            return ExecutionResult.failure("agent returned something other than ExecutionResult")
        if (
            isinstance(result.latency, bool)
            or not isinstance(result.latency, int | float)
            or not math.isfinite(result.latency)
            or result.latency < 0
        ):
            return ExecutionResult.failure(f"invalid latency {result.latency!r}")
        if result.success and result.output is not None:
            try:
                encoded = json.dumps(result.output, allow_nan=False)
            except (TypeError, ValueError):
                encoded = ""  # non-JSON outputs (Python objects) are allowed in-process
            if len(encoded.encode()) > self.limits.max_output_bytes:
                return ExecutionResult.failure(
                    f"output exceeds {self.limits.max_output_bytes} bytes", latency=result.latency
                )
        return result

    def _verifier_for(self, task: Task, pending: _Pending) -> Verifier:
        if pending.verifier is not None:
            return pending.verifier
        if task.expected_output_schema:
            return SchemaVerifier()
        return AcceptVerifier()

    def _verify(
        self, execution: ExecutionResult, contract: Contract, task: Task, pending: _Pending
    ) -> VerificationResult:
        if not execution.success:
            check = CheckResult("execution", False, 0.0, execution.error or "execution failed")
            return VerificationResult.from_checks([check], "execution")
        verifier = self._verifier_for(task, pending)
        try:
            result = verifier.verify(execution.output, contract, task)
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}"[:300]
            check = CheckResult("verifier_error", False, 0.0, detail)
            return VerificationResult.from_checks([check], verifier.name)
        if contract.min_quality is not None:
            ok = result.quality_score >= contract.min_quality
            result = result.with_check(
                CheckResult(
                    "min_quality",
                    ok,
                    result.quality_score,
                    f"{result.quality_score:.4f} >= {contract.min_quality}: {ok}",
                )
            )
        return result

    def _finish(self, result: AuctionResult, reason: str = "") -> AuctionResult:
        auction = result.auction
        result.reason = reason
        result.events = self._collecting.pop(auction.auction_id, [])
        if self.retain_results:
            self.results[auction.auction_id] = result
        else:
            self.auctions.pop(auction.auction_id, None)
        self._notify(result)
        if self.store is not None:
            self.store.save_auction(result.to_dict())
        return result

    def _notify(self, result: AuctionResult) -> None:
        outcome = result.outcome
        awards = {a.agent_id: a for a in outcome.awards} if outcome else {}
        clearing = None
        if self.disclose_clearing_price and outcome and outcome.awards:
            clearing = outcome.awards[0].payment
        for agent_id, bid in result.auction.bids.items():
            agent = self._agents.get(agent_id)
            if agent is None:
                continue
            award = awards.get(agent_id)
            notice = AuctionNotice(
                auction_id=result.auction_id,
                task=result.task,
                own_bid=bid,
                won=award is not None,
                payment=award.payment if award else None,
                clearing_price=clearing,
            )
            try:
                agent.observe(notice)
            except Exception:  # noqa: S112 - agents are untrusted; a bad hook must not break the market
                continue


def _summary(result: AuctionResult) -> dict[str, Any]:
    return {
        "winners": [c.contract.agent_id for c in result.contracts if c.passed],
        "buyer_cost": sum(c.settlement.buyer_cost for c in result.contracts),
        "attempts": len(result.contracts),
    }


def _jsonable(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in data.items():
        try:
            check_json_size(value, key, 64 * 1024)
            out[key] = value
        except ValidationError:
            out[key] = repr(value)[:200]
    return out
