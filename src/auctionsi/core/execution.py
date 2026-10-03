"""Results returned by agents after executing a contract."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """What came back from an agent.

    ``success`` is the agent's (or adapter's) own report that it produced an
    output. It is *not* acceptance: acceptance is decided by verification.
    """

    success: bool
    output: Any = None
    latency: float = 0.0
    actual_cost: float | None = None
    error: str | None = None
    artifacts: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "latency": self.latency,
            "actual_cost": self.actual_cost,
            "error": self.error,
            "artifacts": list(self.artifacts),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def failure(cls, error: str, latency: float = 0.0) -> ExecutionResult:
        return cls(success=False, error=error, latency=latency)
