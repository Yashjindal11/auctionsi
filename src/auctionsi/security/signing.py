"""HMAC signatures on bids, so a bid provably came from the holder of an agent's key.

The signature covers the agent, auction and task ids plus every economic field of
the proposal, which stops a signed bid being replayed into another auction or
altered in transit. Keys are shared secrets held by the marketplace operator.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import replace

from auctionsi.core.bid import BidProposal

SIGNED_FIELDS = (
    "price",
    "estimated_latency",
    "estimated_quality",
    "estimated_cost",
    "confidence",
    "capacity",
    "valid_for",
    "constraints",
    "terms",
)


def canonical_payload(
    proposal: BidProposal, *, agent_id: str, auction_id: str, task_id: str
) -> bytes:
    body = {name: getattr(proposal, name) for name in SIGNED_FIELDS}
    body.update(agent_id=agent_id, auction_id=auction_id, task_id=task_id)
    return json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode()


def sign_proposal(
    proposal: BidProposal, key: bytes, *, agent_id: str, auction_id: str, task_id: str
) -> BidProposal:
    digest = hmac.new(
        key,
        canonical_payload(proposal, agent_id=agent_id, auction_id=auction_id, task_id=task_id),
        hashlib.sha256,
    ).hexdigest()
    return replace(proposal, signature=digest)


def verify_proposal(
    proposal: BidProposal, key: bytes, *, agent_id: str, auction_id: str, task_id: str
) -> bool:
    if not isinstance(proposal.signature, str):
        return False
    expected = sign_proposal(
        replace(proposal, signature=None),
        key,
        agent_id=agent_id,
        auction_id=auction_id,
        task_id=task_id,
    ).signature
    assert expected is not None
    return hmac.compare_digest(expected, proposal.signature)
