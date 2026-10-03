"""A small, dependency-free JSON-Schema subset validator.

Supported keywords: ``type`` (string or list), ``properties``, ``required``,
``additionalProperties`` (bool), ``items``, ``enum``, ``const``, ``minimum``,
``maximum``, ``minLength``, ``maxLength``, ``minItems``, ``maxItems``. Unsupported
keywords are reported as errors rather than silently ignored, so a schema never
appears to validate something it does not check.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

SUPPORTED = frozenset(
    {
        "type",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "enum",
        "const",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
        "title",
        "description",
        "$schema",
    }
)

_TYPES: dict[str, tuple[type, ...]] = {
    "object": (dict,),
    "array": (list, tuple),
    "string": (str,),
    "number": (int, float),
    "integer": (int,),
    "boolean": (bool,),
    "null": (type(None),),
}


def validate(instance: Any, schema: Mapping[str, Any], path: str = "$") -> list[str]:
    """Return a list of human-readable errors (empty when valid)."""
    errors: list[str] = []
    unknown = set(schema) - SUPPORTED
    if unknown:
        return [f"{path}: unsupported schema keywords {sorted(unknown)}"]
    if "type" in schema and not _type_ok(instance, schema["type"]):
        return [f"{path}: expected type {schema['type']}, got {type(instance).__name__}"]
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} not in enum {schema['enum']}")
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: expected constant {schema['const']!r}")
    if _is_number(instance):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: {instance} < minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: {instance} > maximum {schema['maximum']}")
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: shorter than {schema['minLength']}")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(f"{path}: longer than {schema['maxLength']}")
    if isinstance(instance, list | tuple):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{path}: more than {schema['maxItems']} items")
        if isinstance(schema.get("items"), Mapping):
            for i, item in enumerate(instance):
                errors.extend(validate(item, schema["items"], f"{path}[{i}]"))
    if isinstance(instance, dict):
        properties: Mapping[str, Any] = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required property {key!r}")
        for key, value in instance.items():
            if key in properties:
                errors.extend(validate(value, properties[key], f"{path}.{key}"))
            elif schema.get("additionalProperties", True) is False:
                errors.append(f"{path}: unexpected property {key!r}")
    return errors


def _type_ok(instance: Any, expected: str | list[str]) -> bool:
    names = [expected] if isinstance(expected, str) else list(expected)
    for name in names:
        if name not in _TYPES:
            return False
        if isinstance(instance, bool) and name in ("number", "integer"):
            continue
        if isinstance(instance, _TYPES[name]):
            return True
    return False


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)
