"""Clocks and identifier generation.

Simulations use :class:`ManualClock` and a counter-based :class:`IdGenerator` so a
seeded run produces identical ids and timestamps every time.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Protocol


class Clock(Protocol):
    def now(self) -> float: ...


class WallClock:
    """Seconds since the Unix epoch."""

    def now(self) -> float:
        return time.time()


class ManualClock:
    """A clock that only moves when told to. Time never goes backwards."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = float(start)

    def now(self) -> float:
        return self._now

    def set(self, value: float) -> None:
        if value < self._now:
            raise ValueError(f"clock cannot move backwards ({value} < {self._now})")
        self._now = float(value)

    def advance(self, seconds: float) -> None:
        self.set(self._now + seconds)


class IdGenerator:
    """Deterministic ``<prefix>-<namespace>-<counter>`` ids."""

    def __init__(self, namespace: str = "") -> None:
        self.namespace = namespace
        self._counters: defaultdict[str, int] = defaultdict(int)

    def next(self, prefix: str) -> str:
        self._counters[prefix] += 1
        middle = f"{self.namespace}-" if self.namespace else ""
        return f"{prefix}-{middle}{self._counters[prefix]:06d}"
