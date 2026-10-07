"""MkDocs hooks: publish selected repository files on the docs site and keep every
relative link working.

Files outside ``docs/`` (changelog, security policy, research reports, ...) are
added to the site. Each page's relative links are resolved against the page's
location in the repository: targets that are on the site are rewritten to their
site path, anything else points to the file on GitHub.
"""

from __future__ import annotations

import posixpath
import re
from pathlib import Path
from typing import Any

from mkdocs.structure.files import File, Files

ROOT = Path(__file__).resolve().parents[1]
GITHUB = "https://github.com/Yashjindal11/auctionsi"

# repository path -> (site source path, meta description)
EXTERNAL = {
    "CHANGELOG.md": (
        "changelog.md",
        "Release history of AuctionSI: features, fixes and breaking changes in every version.",
    ),
    "SECURITY.md": (
        "security.md",
        "AuctionSI security policy and threat model: untrusted agents, input limits, signed bids, API authentication and how to report a vulnerability.",
    ),
    "CONTRIBUTING.md": (
        "contributing.md",
        "How to contribute to AuctionSI: development setup, pull requests, and rules for mechanisms, research and architecture changes.",
    ),
    "benchmarks/README.md": (
        "benchmarks.md",
        "AuctionSI performance benchmarks: auctions and bids per second and memory for markets of 10 to 1,000 agents, with method and hardware.",
    ),
    "research/README.md": (
        "research/index.md",
        "Reproducible AuctionSI experiments on synthetic agent markets: mechanisms, reliability, reputation, bidding strategies, learning bidders, collusion and market size.",
    ),
}

LINK = re.compile(r"(\]\()([^)\s]+)(\))")
MAX_DESCRIPTION = 160


def summary(markdown: str) -> str:
    """The first prose paragraph as plain text, cut at a word boundary, for pages
    without a ``description`` in their front matter."""
    in_code = False
    for block in re.split(r"\n\s*\n", markdown):
        text = block.strip()
        if text.startswith("```"):
            in_code = not in_code if text.count("```") % 2 else in_code
            continue
        if in_code or not text or text[0] in "#|-*>!<" or text[0].isdigit():
            continue
        plain = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
        plain = re.sub(r"[`*]", "", " ".join(plain.split()))
        if len(plain) <= MAX_DESCRIPTION:
            return plain
        return plain[: MAX_DESCRIPTION - 1].rsplit(" ", 1)[0] + "…"
    return ""


def _external_files() -> dict[str, str]:
    mapping = {repo: site for repo, (site, _) in EXTERNAL.items()}
    for report in sorted((ROOT / "research" / "results").glob("*/report.md")):
        rel = report.relative_to(ROOT).as_posix()
        mapping[rel] = rel
    return mapping


def _site_paths(files: Files, mapping: dict[str, str]) -> dict[str, str]:
    """repository path -> site source path for every page on the site."""
    paths = {f"docs/{f.src_uri}": f.src_uri for f in files if f.src_uri.endswith(".md")}
    paths.update(mapping)
    return paths


def on_files(files: Files, config: Any) -> Files:
    for repo_path, site_path in _external_files().items():
        files.append(File.generated(config, site_path, abs_src_path=str(ROOT / repo_path)))
    return files


def on_page_markdown(markdown: str, page: Any, config: Any, files: Files) -> str:
    mapping = _external_files()
    site = _site_paths(files, mapping)
    origin = {v: k for k, v in site.items()}[page.file.src_uri]
    if not page.meta.get("description"):
        description = EXTERNAL[origin][1] if origin in EXTERNAL else summary(markdown)
        if description:
            page.meta["description"] = description
    here = posixpath.dirname(page.file.src_uri)

    def rewrite(match: re.Match[str]) -> str:
        target = match.group(2)
        if re.match(r"^[a-z]+:|^#|^/", target):
            return match.group(0)
        path, _, anchor = target.partition("#")
        repo = posixpath.normpath(posixpath.join(posixpath.dirname(origin), path))
        if repo in site:
            new = posixpath.relpath(site[repo], here or ".")
        elif repo.startswith(".."):
            return match.group(0)
        else:
            kind = "tree" if (ROOT / repo).is_dir() else "blob"
            new = f"{GITHUB}/{kind}/main/{repo}"
        return f"{match.group(1)}{new}{'#' + anchor if anchor else ''}{match.group(3)}"

    return LINK.sub(rewrite, markdown)
