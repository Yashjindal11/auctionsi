"""Run every experiment in research/experiments and write reports to research/results.

    python research/run_all.py               # all experiments
    python research/run_all.py mechanisms    # one experiment
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from auctionsi.experiments import ExperimentConfig, run_experiment
from auctionsi.security.loading import load_config_file

ROOT = Path(__file__).resolve().parent


def main(argv: list[str]) -> int:
    configs = sorted((ROOT / "experiments").glob("*.yaml"))
    if argv:
        configs = [c for c in configs if c.stem in argv]
    for path in configs:
        config = ExperimentConfig.from_mapping(load_config_file(path))
        start = time.perf_counter()
        result = run_experiment(config)
        out = result.save(ROOT / "results" / config.name)
        print(f"{config.name}: {len(result.runs)} runs in {time.perf_counter() - start:.1f}s -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
