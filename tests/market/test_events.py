from __future__ import annotations

import pytest

from auctionsi.market.clock import IdGenerator, ManualClock
from auctionsi.market.events import Event, EventBus, EventLog, EventType


def test_bus_orders_filters_and_unsubscribes() -> None:
    bus = EventBus(strict=True)
    everything = EventLog()
    bids: list[Event] = []
    bus.subscribe(everything)
    unsubscribe = bus.subscribe(bids.append, [EventType.BID_SUBMITTED])
    bus.publish(EventType.TASK_CREATED, 1.0, task_id="t")
    bus.publish(EventType.BID_SUBMITTED, 2.0, task_id="t", agent_id="a", data={"price": 1})
    unsubscribe()
    bus.publish(EventType.BID_SUBMITTED, 3.0)
    assert [e.seq for e in everything.events] == [1, 2, 3]
    assert len(bids) == 1
    assert bids[0].data["price"] == 1


def test_events_are_immutable_and_round_trip() -> None:
    bus = EventBus()
    event = bus.publish(EventType.WINNER_SELECTED, 5.0, auction_id="a", data={"score": 0.5})
    with pytest.raises(AttributeError):
        event.seq = 9  # type: ignore[misc]
    assert Event.from_dict(event.to_dict()) == event


def test_failing_handler_is_isolated_unless_strict() -> None:
    def boom(event: Event) -> None:
        raise RuntimeError("subscriber bug")

    bus = EventBus()
    bus.subscribe(boom)
    bus.publish(EventType.TASK_CREATED, 0.0)
    assert bus.handler_errors == 1
    strict = EventBus(strict=True)
    strict.subscribe(boom)
    with pytest.raises(RuntimeError):
        strict.publish(EventType.TASK_CREATED, 0.0)


def test_bounded_log() -> None:
    log = EventLog(max_events=2)
    bus = EventBus()
    bus.subscribe(log)
    for _ in range(5):
        bus.publish(EventType.TASK_CREATED, 0.0)
    assert [e.seq for e in log.events] == [4, 5]


def test_manual_clock_and_ids() -> None:
    clock = ManualClock()
    clock.advance(2)
    assert clock.now() == 2
    with pytest.raises(ValueError):
        clock.set(1)
    ids = IdGenerator("run1")
    assert ids.next("bid") == "bid-run1-000001"
    assert ids.next("bid") == "bid-run1-000002"
    assert IdGenerator().next("auction") == "auction-000001"
