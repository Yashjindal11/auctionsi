"""Run every example and fail loudly if any of them errors."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

EXAMPLES = sorted((Path(__file__).resolve().parent.parent / "examples").glob("*.py"))


def main() -> int:
    failures = 0
    for path in EXAMPLES:
        print(f"=== {path.name}")
        try:
            runpy.run_path(str(path), run_name="__main__")
        except Exception as exc:
            failures += 1
            print(f"FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
    print(f"\n{len(EXAMPLES) - failures}/{len(EXAMPLES)} examples ran")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
