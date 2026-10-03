"""Safe loading of YAML/JSON configuration and safe path handling."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from auctionsi.errors import ConfigurationError
from auctionsi.security.validation import DEFAULT_LIMITS, Limits


class _NoAliasLoader(yaml.SafeLoader):
    """SafeLoader (no arbitrary object construction) that also refuses YAML aliases,
    which closes the "billion laughs" expansion attack."""

    def compose_node(self, parent: Any, index: Any) -> Any:
        if self.check_event(yaml.AliasEvent):
            raise ConfigurationError("YAML aliases are not allowed in AuctionSI config files")
        return super().compose_node(parent, index)


def load_config_text(text: str, *, limits: Limits = DEFAULT_LIMITS, source: str = "<text>") -> Any:
    if len(text.encode()) > limits.max_config_bytes:
        raise ConfigurationError(f"{source} is larger than {limits.max_config_bytes} bytes")
    try:
        return yaml.load(text, Loader=_NoAliasLoader)  # noqa: S506 - _NoAliasLoader is a SafeLoader
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"invalid YAML in {source}: {exc}") from exc


def load_config_file(path: str | Path, *, limits: Limits = DEFAULT_LIMITS) -> Any:
    """Load a ``.yaml``/``.yml``/``.json`` file with size limits and safe parsing."""
    p = Path(path)
    if not p.is_file():
        raise ConfigurationError(f"config file {p} does not exist")
    if p.stat().st_size > limits.max_config_bytes:
        raise ConfigurationError(f"{p} is larger than {limits.max_config_bytes} bytes")
    text = p.read_text(encoding="utf-8")
    if p.suffix == ".json":
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigurationError(f"invalid JSON in {p}: {exc}") from exc
    return load_config_text(text, limits=limits, source=str(p))


def safe_path(base: str | Path, user_path: str | Path) -> Path:
    """Resolve ``user_path`` under ``base`` and refuse anything that escapes it."""
    root = Path(base).resolve()
    candidate = (root / user_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise ConfigurationError(f"path {user_path!s} escapes {root}")
    return candidate
