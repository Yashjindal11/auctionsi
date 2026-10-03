"""Structured capability declarations and the rules for matching them to tasks."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeGuard

from auctionsi.errors import ValidationError
from auctionsi.security import check_identifier, check_mapping, check_text

if TYPE_CHECKING:
    from auctionsi.core.task import Task


@dataclass(frozen=True, slots=True)
class Capability:
    """A type of work an agent *claims* it can perform.

    Claims are not trusted: discovery uses them only to decide who may bid, and
    reputation tracks how well the agent actually delivers on them.

    ``constraints`` use a small, explicit convention so that matching stays
    transparent: a key ``max_<name>`` rejects tasks whose ``requirements[<name>]``
    is larger, and ``min_<name>`` rejects tasks whose requirement is smaller.
    Other keys are informational.
    """

    name: str
    version: str = "1.0"
    input_formats: tuple[str, ...] = ()
    output_formats: tuple[str, ...] = ()
    constraints: Mapping[str, Any] = field(default_factory=dict)
    performance_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        check_identifier(self.name, "capability name")
        check_text(self.version, "capability version")
        object.__setattr__(self, "input_formats", _formats(self.input_formats, "input_formats"))
        object.__setattr__(self, "output_formats", _formats(self.output_formats, "output_formats"))
        object.__setattr__(
            self, "constraints", check_mapping(self.constraints, "capability constraints")
        )
        object.__setattr__(
            self,
            "performance_metadata",
            check_mapping(self.performance_metadata, "capability performance_metadata"),
        )

    def incompatibilities(self, task: Task) -> list[str]:
        """Reasons this capability cannot serve ``task``; empty when compatible."""
        reasons: list[str] = []
        if self.name != task.task_type:
            reasons.append(f"capability {self.name!r} does not match task type {task.task_type!r}")
            return reasons
        wanted_in = task.requirements.get("input_format")
        if self.input_formats and wanted_in is not None and wanted_in not in self.input_formats:
            reasons.append(f"input format {wanted_in!r} not in {list(self.input_formats)}")
        wanted_out = task.requirements.get("output_format")
        if self.output_formats and wanted_out is not None and wanted_out not in self.output_formats:
            reasons.append(f"output format {wanted_out!r} not in {list(self.output_formats)}")
        for key, limit in self.constraints.items():
            if not isinstance(limit, int | float) or isinstance(limit, bool):
                continue
            if key.startswith("max_"):
                needed = task.requirements.get(key[4:])
                if _is_number(needed) and needed > limit:
                    reasons.append(f"requirement {key[4:]}={needed} exceeds {key}={limit}")
            elif key.startswith("min_"):
                needed = task.requirements.get(key[4:])
                if _is_number(needed) and needed < limit:
                    reasons.append(f"requirement {key[4:]}={needed} below {key}={limit}")
        return reasons

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "input_formats": list(self.input_formats),
            "output_formats": list(self.output_formats),
            "constraints": dict(self.constraints),
            "performance_metadata": dict(self.performance_metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Capability:
        return cls(
            name=data["name"],
            version=data.get("version", "1.0"),
            input_formats=tuple(data.get("input_formats", ())),
            output_formats=tuple(data.get("output_formats", ())),
            constraints=data.get("constraints", {}),
            performance_metadata=data.get("performance_metadata", {}),
        )


def as_capability(value: Capability | str | Mapping[str, Any]) -> Capability:
    if isinstance(value, Capability):
        return value
    if isinstance(value, str):
        return Capability(name=value)
    if isinstance(value, Mapping):
        return Capability.from_dict(value)
    raise ValidationError(f"cannot interpret {value!r} as a capability")


def _formats(values: Iterable[str], field_name: str) -> tuple[str, ...]:
    if isinstance(values, str):
        raise ValidationError(f"{field_name} must be a list of strings, not a string")
    result = tuple(values)
    for value in result:
        check_identifier(value, field_name)
    return result


def _is_number(value: object) -> TypeGuard[float]:
    return isinstance(value, int | float) and not isinstance(value, bool)
