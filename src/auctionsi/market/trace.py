"""Human-readable auction traces built from the event stream."""

from __future__ import annotations

from collections.abc import Iterable

from auctionsi.market.events import Event, EventType

E = EventType


def describe_event(event: Event) -> str:
    d = event.data
    agent = event.agent_id or ""
    match event.type:
        case E.TASK_CREATED:
            return f"task {event.task_id} created"
        case E.AUCTION_CREATED:
            parent = d.get("parent_auction_id")
            suffix = f" (re-opened from {parent})" if parent else ""
            return f"auction {event.auction_id} created with {d.get('mechanism', {}).get('name')}{suffix}"
        case E.AGENTS_DISCOVERED:
            return (
                f"{d.get('registered', 0)} agents registered, "
                f"{len(d.get('eligible', []))} eligible, {len(d.get('excluded', {}))} excluded"
            )
        case E.TASK_ANNOUNCED:
            return "task announced"
        case E.AUCTION_OPENED:
            return "auction opened (" + ("sealed" if d.get("sealed") else "open") + " bidding)"
        case E.BID_SUBMITTED:
            return f"bid from {agent}: {d['bid']['price']}"
        case E.BID_REVISED:
            return f"revised bid from {agent}: {d['bid']['price']} (round {d.get('round')})"
        case E.BID_REJECTED:
            reasons = ", ".join(r["code"] for r in d.get("reasons", []))
            return f"bid from {agent} rejected: {reasons}"
        case E.AUCTION_CLOSED:
            return (
                f"auction closed: {d.get('valid', 0)} valid bids, {d.get('rejected', 0)} rejected"
            )
        case E.NO_BIDS:
            return "no valid bids"
        case E.WINNER_SELECTED:
            awards = d.get("outcome", {}).get("awards", [])
            names = ", ".join(f"{a['agent_id']} (paid {a['payment']:.6g})" for a in awards)
            return f"winner selected: {names}"
        case E.CONTRACT_CREATED:
            return f"contract {event.contract_id} created with {agent}"
        case E.TASK_STARTED:
            return f"execution started by {agent}"
        case E.TASK_COMPLETED:
            return f"execution completed by {agent} in {d.get('latency', 0):.4g}s"
        case E.TASK_FAILED:
            return f"execution failed for {agent}: {d.get('error')}"
        case E.VERIFICATION_PASSED:
            return f"verification passed (quality {d.get('quality_score', 0):.3f})"
        case E.VERIFICATION_FAILED:
            failed = [c["name"] for c in d.get("checks", []) if not c["passed"]]
            return f"verification failed ({', '.join(failed)})"
        case E.SETTLEMENT_COMPLETED:
            return f"settlement completed: {agent} paid {d.get('buyer_cost', 0):.6g} {d.get('unit', '')}"
        case E.REPUTATION_UPDATED:
            return f"reputation updated for {agent}"
        case E.RECOVERY_STARTED:
            return f"recovery: {d.get('action')} -> {d.get('agent_id', '')}"
        case E.AUCTION_SETTLED:
            return "auction settled"
        case E.AUCTION_FAILED:
            return f"auction failed: {d.get('reason', '')}"
        case E.AUCTION_CANCELLED:
            return f"auction cancelled: {d.get('reason', '')}"
        case _:
            return event.type.value


def format_trace(events: Iterable[Event]) -> list[str]:
    return [f"[{e.seq:>6}] {describe_event(e)}" for e in events]
