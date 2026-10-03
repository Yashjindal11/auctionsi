from __future__ import annotations

from pathlib import Path

import pytest

from auctionsi.errors import ConfigurationError
from auctionsi.security import Limits
from auctionsi.security.loading import load_config_file, load_config_text, safe_path


def test_safe_yaml_rejects_python_objects_and_aliases() -> None:
    with pytest.raises(ConfigurationError):
        load_config_text("x: !!python/object/apply:os.system ['echo hi']")
    bomb = "a: &a [1, 2]\nb: [*a, *a]\n"
    with pytest.raises(ConfigurationError, match="aliases"):
        load_config_text(bomb)
    assert load_config_text("market: {name: m}") == {"market": {"name": "m"}}


def test_size_limits(tmp_path: Path) -> None:
    big = tmp_path / "big.yaml"
    big.write_text("x: " + "a" * 2000)
    with pytest.raises(ConfigurationError):
        load_config_file(big, limits=Limits(max_config_bytes=100))
    with pytest.raises(ConfigurationError):
        load_config_text("x" * 200, limits=Limits(max_config_bytes=100))
    with pytest.raises(ConfigurationError):
        load_config_file(tmp_path / "missing.yaml")


def test_json_and_invalid_files(tmp_path: Path) -> None:
    good = tmp_path / "c.json"
    good.write_text('{"a": 1}')
    assert load_config_file(good) == {"a": 1}
    bad = tmp_path / "bad.json"
    bad.write_text("{")
    with pytest.raises(ConfigurationError):
        load_config_file(bad)
    broken = tmp_path / "bad.yaml"
    broken.write_text("a: [")
    with pytest.raises(ConfigurationError):
        load_config_file(broken)


def test_safe_path(tmp_path: Path) -> None:
    assert safe_path(tmp_path, "sub/file.txt") == (tmp_path / "sub/file.txt").resolve()
    for evil in ("../escape", "/etc/passwd", "a/../../b"):
        with pytest.raises(ConfigurationError):
            safe_path(tmp_path, evil)
