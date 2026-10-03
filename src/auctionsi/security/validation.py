"""Input validation helpers shared by every model that accepts untrusted data."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from auctionsi.errors import ValidationError

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:\-]{0,127}$")


@dataclass(frozen=True, slots=True)
class Limits:
    """Upper bounds applied to untrusted input. Raise them deliberately, not by accident."""

    max_text_length: int = 10_000
    max_mapping_bytes: int = 64 * 1024
    max_output_bytes: int = 1024 * 1024
    max_bids_per_auction: int = 10_000
    max_revisions_per_agent: int = 100
    max_config_bytes: int = 1024 * 1024


DEFAULT_LIMITS = Limits()


def check_identifier(value: object, field: str) -> str:
    """Identifiers are short, printable and safe to use in logs, URLs and file names."""
    if not isinstance(value, str) or not _IDENTIFIER.match(value):
        raise ValidationError(
            f"{field} must be 1-128 characters of letters, digits, '.', '_', ':' or '-' "
            f"and start with a letter or digit; got {value!r}"
        )
    return value


def check_text(value: object, field: str, limits: Limits = DEFAULT_LIMITS) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a string")
    if len(value) > limits.max_text_length:
        raise ValidationError(f"{field} exceeds {limits.max_text_length} characters")
    return value


def check_number(
    value: object,
    field: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    allow_none: bool = False,
) -> float | None:
    """Accept finite ints/floats (not bools) inside optional bounds."""
    if value is None:
        if allow_none:
            return None
        raise ValidationError(f"{field} is required")
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValidationError(f"{field} must be a number, got {type(value).__name__}")
    number = float(value)
    if not math.isfinite(number):
        raise ValidationError(f"{field} must be finite")
    if minimum is not None and number < minimum:
        raise ValidationError(f"{field} must be >= {minimum}, got {number}")
    if maximum is not None and number > maximum:
        raise ValidationError(f"{field} must be <= {maximum}, got {number}")
    return number


def require_number(
    value: object, field: str, *, minimum: float | None = None, maximum: float | None = None
) -> float:
    number = check_number(value, field, minimum=minimum, maximum=maximum)
    assert number is not None
    return number


def check_mapping(
    value: object, field: str, limits: Limits = DEFAULT_LIMITS, *, max_bytes: int | None = None
) -> dict[str, Any]:
    """A JSON-serialisable mapping with string keys and a bounded encoded size."""
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be a mapping")
    if not all(isinstance(key, str) for key in value):
        raise ValidationError(f"{field} keys must be strings")
    check_json_size(value, field, max_bytes or limits.max_mapping_bytes)
    return dict(value)


def check_json_size(value: object, field: str, max_bytes: int) -> int:
    try:
        encoded = json.dumps(value, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be JSON-serialisable: {exc}") from exc
    size = len(encoded.encode())
    if size > max_bytes:
        raise ValidationError(f"{field} is {size} bytes, above the {max_bytes} byte limit")
    return size
