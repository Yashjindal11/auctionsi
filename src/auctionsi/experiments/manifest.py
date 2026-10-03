"""Run manifests: everything needed to reproduce (and audit) an experiment."""

from __future__ import annotations

import datetime as dt
import platform
import shutil
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

from auctionsi._version import __version__


def git_commit(cwd: str | Path | None = None) -> str | None:
    """Commit hash of the git repository at ``cwd`` (``None`` if unavailable). A ``+dirty``
    suffix marks uncommitted changes to tracked files."""
    git = shutil.which("git")
    if git is None:
        return None
    try:
        head = subprocess.run(  # noqa: S603 - fixed argv, no shell, resolved executable
            [git, "rev-parse", "HEAD"], cwd=cwd, capture_output=True, text=True, timeout=5
        )
        if head.returncode != 0:
            return None
        dirty = subprocess.run(  # noqa: S603
            [git, "status", "--porcelain", "--untracked-files=no"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    commit = head.stdout.strip()
    return commit + ("+dirty" if dirty.stdout.strip() else "")


def _version(dist: str) -> str | None:
    try:
        return metadata.version(dist)
    except metadata.PackageNotFoundError:
        return None


def build_manifest(config: dict[str, Any], *, cwd: str | Path | None = None) -> dict[str, Any]:
    return {
        "auctionsi_version": __version__,
        "python_version": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "git_commit": git_commit(cwd),
        "created_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "seed": config.get("seed"),
        "replications": config.get("replications"),
        "agent_generation": config.get("environment", {}).get("agents"),
        "task_generation": config.get("environment", {}).get("tasks"),
        "dependencies": {name: _version(name) for name in ("pydantic", "pyyaml", "scipy")},
        "config": config,
    }
