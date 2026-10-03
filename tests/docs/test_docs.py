"""Every ```python block in the docs and README must run."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FILES = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]
BLOCK = re.compile(r"```python\n(.*?)```", re.DOTALL)
CASES = [
    pytest.param(code, id=f"{path.name}:{i}")
    for path in FILES
    for i, code in enumerate(BLOCK.findall(path.read_text(encoding="utf-8")))
]


@pytest.mark.parametrize("code", CASES)
def test_doc_snippet_runs(code: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    exec(compile(code, "<doc>", "exec"), {"__name__": "__doc_snippet__"})
