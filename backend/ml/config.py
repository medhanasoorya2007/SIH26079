"""Central configuration and path handling for BustGuard.

All pipeline stages read their settings from YAML files in ``backend/configs``.
Paths are resolved relative to the repository so the code runs the same from
``make``, pytest, the API server or Docker.
"""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path
from typing import Any

import yaml

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent
CONFIG_DIR = BACKEND_DIR / "configs"


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    if not value:
        return default
    p = Path(value)
    return p if p.is_absolute() else (BACKEND_DIR / p).resolve()


DATA_DIR = _env_path("BUSTGUARD_DATA_DIR", REPO_DIR / "data")
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
ARTIFACTS_DIR = _env_path("BUSTGUARD_ARTIFACTS", DATA_DIR / "artifacts")
SAMPLE_DIR = DATA_DIR / "sample"


@cache
def load_config(name: str) -> dict[str, Any]:
    """Load ``configs/<name>.yaml`` (cached)."""
    path = CONFIG_DIR / f"{name}.yaml"
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def ensure_dirs() -> None:
    """Create the data directory tree if missing."""
    for d in (RAW_DIR, PROCESSED_DIR, ARTIFACTS_DIR, SAMPLE_DIR):
        d.mkdir(parents=True, exist_ok=True)
