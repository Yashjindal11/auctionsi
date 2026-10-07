"""The MkDocs hook that publishes repository files and keeps their links working."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

pytest.importorskip("mkdocs")
from mkdocs.config import load_config
from mkdocs.structure.files import File, Files

ROOT = Path(__file__).resolve().parents[2]


def _load_hooks() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "mkdocs_hooks", ROOT / "scripts" / "mkdocs_hooks.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["mkdocs_hooks"] = module
    spec.loader.exec_module(module)
    return module


hooks = _load_hooks()


def _files() -> Files:
    config = load_config(str(ROOT / "mkdocs.yml"))
    # Set by MkDocs while a hook runs during a build; File.generated records it.
    config.plugins._current_plugin = "hooks"
    docs = [File(p, config.docs_dir, config.site_dir, True) for p in ("index.md", "storage.md")]
    return hooks.on_files(Files(docs), config)


def _page(src_uri: str, meta: dict[str, str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(file=SimpleNamespace(src_uri=src_uri), meta=meta or {})


def test_external_files_are_added_with_their_site_paths() -> None:
    uris = {f.src_uri for f in _files()}
    assert {"changelog.md", "security.md", "benchmarks.md", "research/index.md"} <= uris
    assert "research/results/mechanisms/report.md" in uris


def test_links_resolve_to_site_pages_or_github() -> None:
    files = _files()
    md = (
        "[sec](../SECURITY.md) [res](../research/README.md#top) [ex](../examples/) "
        "[src](../src/auctionsi/config.py) [web](https://example.com) [anchor](#here)"
    )
    out = hooks.on_page_markdown(md, _page("index.md"), {}, files)
    assert "[sec](security.md)" in out
    assert "[res](research/index.md#top)" in out
    assert "[ex](https://github.com/Yashjindal11/auctionsi/tree/main/examples)" in out
    assert (
        "[src](https://github.com/Yashjindal11/auctionsi/blob/main/src/auctionsi/config.py)" in out
    )
    assert "[web](https://example.com)" in out
    assert "[anchor](#here)" in out


def test_links_inside_published_repository_files() -> None:
    files = _files()
    out = hooks.on_page_markdown(
        "[r](results/mechanisms/report.md) [d](../docs/storage.md)",
        _page("research/index.md"),
        {},
        files,
    )
    assert "[r](results/mechanisms/report.md)" in out
    assert "[d](../storage.md)" in out


def test_descriptions() -> None:
    files = _files()
    page = _page("changelog.md")
    hooks.on_page_markdown("# Changelog\n\n## [1.0]\n\n- x", page, {}, files)
    assert page.meta["description"].startswith("Release history of AuctionSI")

    page = _page("research/results/mechanisms/report.md")
    hooks.on_page_markdown("# Report\n\nFour market designs compared.\n", page, {}, files)
    assert page.meta["description"] == "Four market designs compared."

    page = _page("storage.md", {"description": "kept"})
    hooks.on_page_markdown("# S\n\nOther text.", page, {}, files)
    assert page.meta["description"] == "kept"


def test_summary_skips_headings_lists_tables_and_code() -> None:
    text = "# T\n\n```bash\nnot this\n```\n\n- item\n\n| a |\n\nThe `reserve_price` is *used* [here](x.md)."
    assert hooks.summary(text) == "The reserve_price is used here."
    long = "word " * 100
    out = hooks.summary(long)
    assert len(out) <= hooks.MAX_DESCRIPTION
    assert out.endswith("…")
    assert hooks.summary("# Only a heading") == ""
