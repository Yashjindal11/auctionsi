"""AuctionSI: a marketplace and auction framework for autonomous agents."""

from auctionsi._version import __version__
from auctionsi.adapters.function import PythonFunctionAgent
from auctionsi.core import (
    Agent,
    AuctionNotice,
    Bid,
    BidContext,
    BidProposal,
    Capability,
    Contract,
    CostModel,
    ExecutionResult,
    OpenAuctionView,
    Task,
)
from auctionsi.core.auction import Auction, AuctionStatus
from auctionsi.market import (
    AuctionResult,
    BidValidationConfig,
    EventType,
    ManualClock,
    Marketplace,
    RecoveryPolicy,
)
from auctionsi.mechanisms import (
    FirstPriceReverseAuction,
    MultiWinnerReverseAuction,
    OpenReverseAuction,
    SecondPriceReverseAuction,
)
from auctionsi.reputation import MultiDimensionalReputation
from auctionsi.selection import (
    HighestQuality,
    LowestLatency,
    LowestPrice,
    ReputationAdjustedCost,
    RiskAdjustedCost,
    WeightedScore,
)
from auctionsi.settlement import PayOnPass

__all__ = [
    "Agent",
    "Auction",
    "AuctionNotice",
    "AuctionResult",
    "AuctionStatus",
    "Bid",
    "BidContext",
    "BidProposal",
    "BidValidationConfig",
    "Capability",
    "Contract",
    "CostModel",
    "EventType",
    "ExecutionResult",
    "FirstPriceReverseAuction",
    "HighestQuality",
    "LowestLatency",
    "LowestPrice",
    "ManualClock",
    "Marketplace",
    "MultiDimensionalReputation",
    "MultiWinnerReverseAuction",
    "OpenAuctionView",
    "OpenReverseAuction",
    "PayOnPass",
    "PythonFunctionAgent",
    "RecoveryPolicy",
    "ReputationAdjustedCost",
    "RiskAdjustedCost",
    "SecondPriceReverseAuction",
    "Task",
    "WeightedScore",
    "__version__",
]
