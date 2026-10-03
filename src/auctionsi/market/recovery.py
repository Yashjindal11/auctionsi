"""What to do when a winning agent fails to deliver."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from auctionsi.errors import ValidationError


@dataclass(frozen=True, slots=True)
class RecoveryPolicy:
    """Recovery steps, tried in this order for each awarded slot:

    1. ``retry_same``: re-contract the same agent up to this many extra times;
    2. ``next_best``: fail over to the next-ranked backup bid, up to this many times
       (backups are paid their own bid price);
    3. ``reopen``: run a fresh auction for the task, excluding agents that already
       failed it, up to this many times (single-winner auctions only).

    The default does nothing: a failure is final.
    """

    retry_same: int = 0
    next_best: int = 0
    reopen: int = 0

    def __post_init__(self) -> None:
        for name in ("retry_same", "next_best", "reopen"):
            if getattr(self, name) < 0:
                raise ValidationError(f"{name} must be >= 0")

    def to_spec(self) -> dict[str, Any]:
        return {"name": "recovery", **asdict(self)}
