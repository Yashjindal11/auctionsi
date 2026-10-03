"""The agent abstraction: anything that can bid for and perform work."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

from auctionsi.core.capability import Capability, as_capability
from auctionsi.errors import ValidationError
from auctionsi.security import check_identifier, check_mapping, check_text, require_number

if TYPE_CHECKING:
    from auctionsi.core.bid import Bid, BidProposal
    from auctionsi.core.contract import Contract
    from auctionsi.core.execution import ExecutionResult
    from auctionsi.core.task import Task


@dataclass(frozen=True, slots=True)
class CostModel:
    """An agent's own cost of doing work, in abstract units.

    ``cost = fixed_cost + variable_cost_per_second * latency + sum(per_unit[k] * usage[k])``
    where ``usage`` can carry tokens, compute units, rows, and so on.
    """

    fixed_cost: float = 0.0
    variable_cost_per_second: float = 0.0
    per_unit_costs: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_number(self.fixed_cost, "fixed_cost", minimum=0)
        require_number(self.variable_cost_per_second, "variable_cost_per_second", minimum=0)
        for key, value in self.per_unit_costs.items():
            require_number(value, f"per_unit_costs[{key}]", minimum=0)

    def cost(self, latency: float, usage: Mapping[str, float] | None = None) -> float:
        total = self.fixed_cost + self.variable_cost_per_second * max(latency, 0.0)
        for key, amount in (usage or {}).items():
            total += self.per_unit_costs.get(key, 0.0) * amount
        return total

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixed_cost": self.fixed_cost,
            "variable_cost_per_second": self.variable_cost_per_second,
            "per_unit_costs": dict(self.per_unit_costs),
        }


@dataclass(frozen=True, slots=True)
class BidContext:
    """What a bidder is told when asked for a bid. Sealed auctions reveal no rival bids."""

    auction_id: str
    mechanism: str
    now: float
    sealed: bool
    unit: str
    round: int = 0


@dataclass(frozen=True, slots=True)
class OpenAuctionView:
    """Public state of an open auction shown to bidders between rounds."""

    auction_id: str
    round: int
    best_price: float | None
    bid_count: int
    own_bid: Bid | None
    now: float


@dataclass(frozen=True, slots=True)
class AuctionNotice:
    """Sent to every bidder after an auction is decided, so strategies can learn.

    ``clearing_price`` is only filled in when the marketplace is configured to
    disclose it (``Marketplace(disclose_clearing_price=True)``).
    """

    auction_id: str
    task: Task
    own_bid: Bid | None
    won: bool
    payment: float | None
    clearing_price: float | None


class Agent(ABC):
    """Base class for marketplace participants.

    Subclass it and implement :meth:`bid` and :meth:`execute`. Agents may be LLMs,
    plain Python functions, solvers, HTTP services, humans or simulations; the
    marketplace only sees this interface.

    The marketplace treats agents as untrusted: proposals are validated, ids are
    stamped by the market, and exceptions raised by agents are recorded as
    failures instead of propagating.
    """

    #: Bumped whenever any agent's capabilities change, so marketplaces can re-index.
    capability_epoch: ClassVar[int] = 0

    def __init__(
        self,
        agent_id: str,
        *,
        capabilities: Iterable[Capability | str | Mapping[str, Any]],
        name: str | None = None,
        version: str = "1.0",
        cost_model: CostModel | None = None,
        max_concurrent_tasks: int = 1,
        available: bool = True,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self.agent_id = check_identifier(agent_id, "agent_id")
        self.name = check_text(name if name is not None else agent_id, "agent name")
        self.version = check_text(version, "agent version")
        caps = tuple(as_capability(c) for c in capabilities)
        if not caps:
            raise ValidationError(f"agent {agent_id} must declare at least one capability")
        self._capabilities = caps
        self._capability_index = {c.name: c for c in caps}
        self.cost_model = cost_model or CostModel()
        if isinstance(max_concurrent_tasks, bool) or not isinstance(max_concurrent_tasks, int):
            raise ValidationError("max_concurrent_tasks must be an integer")
        if max_concurrent_tasks < 1:
            raise ValidationError("max_concurrent_tasks must be >= 1")
        self.max_concurrent_tasks = max_concurrent_tasks
        self.available = available
        self.metadata = check_mapping(metadata or {}, "agent metadata")

    @property
    def capabilities(self) -> tuple[Capability, ...]:
        return self._capabilities

    def set_capabilities(
        self, capabilities: Iterable[Capability | str | Mapping[str, Any]]
    ) -> None:
        caps = tuple(as_capability(c) for c in capabilities)
        if not caps:
            raise ValidationError("an agent must keep at least one capability")
        self._capabilities = caps
        self._capability_index = {c.name: c for c in caps}
        Agent.capability_epoch += 1

    def capability(self, name: str) -> Capability | None:
        return self._capability_index.get(name)

    @abstractmethod
    def bid(self, task: Task, context: BidContext) -> BidProposal | None:
        """Return a proposal, or ``None`` to abstain."""

    @abstractmethod
    def execute(self, task: Task, contract: Contract) -> ExecutionResult:
        """Perform the contracted work."""

    def revise_bid(self, task: Task, view: OpenAuctionView) -> BidProposal | None:
        """Open auctions only: return an improved proposal or ``None`` to stand pat."""
        return None

    def observe(self, notice: AuctionNotice) -> None:
        """Hook for learning bidders; called once per auction the agent bid in."""
        return None

    def describe(self) -> dict[str, Any]:
        """Public, serialisable profile. Does not include private strategy or cost data."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "version": self.version,
            "kind": type(self).__name__,
            "capabilities": [c.to_dict() for c in self._capabilities],
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "available": self.available,
            "metadata": dict(self.metadata),
        }
