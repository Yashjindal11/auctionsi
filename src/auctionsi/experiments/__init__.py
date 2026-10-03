"""Reproducible experiments comparing market designs."""

from auctionsi.experiments.config import (
    AgentsConfig,
    ArmConfig,
    EnvironmentConfig,
    ExperimentConfig,
    TasksConfig,
)
from auctionsi.experiments.manifest import build_manifest, git_commit
from auctionsi.experiments.runner import (
    ArmRun,
    ExperimentResult,
    compare_mechanisms,
    run_experiment,
)

__all__ = [
    "AgentsConfig",
    "ArmConfig",
    "ArmRun",
    "EnvironmentConfig",
    "ExperimentConfig",
    "ExperimentResult",
    "TasksConfig",
    "build_manifest",
    "compare_mechanisms",
    "git_commit",
    "run_experiment",
]
