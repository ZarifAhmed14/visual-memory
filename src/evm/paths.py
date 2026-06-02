from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = Path(os.environ.get("EVM_DATA_DIR", str(PROJECT_ROOT / "data"))).resolve()
RUNS_DIR = DATA_ROOT / "runs"
VIDEOS_DIR = DATA_ROOT / "videos"
UPLOADS_DIR = VIDEOS_DIR / "uploads"


def ensure_data_dirs() -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
