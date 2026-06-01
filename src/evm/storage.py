from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np

from evm.observation import ObservationRecord


class RunWriter:
    def __init__(self, run_dir: Path, source: str) -> None:
        self.run_dir = run_dir
        self.frames_dir = run_dir / "frames"
        self.observations_path = run_dir / "observations.jsonl"
        self.source = source
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.records_written = 0

    def __enter__(self) -> "RunWriter":
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self._obs_file = self.observations_path.open("w", encoding="utf-8")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._obs_file.close()
        self.write_manifest()

    def write_frame(
        self,
        frame_id: int,
        timestamp: float,
        frame_bgr: np.ndarray,
        metadata: dict | None = None,
    ) -> ObservationRecord:
        filename = f"{frame_id:06d}.jpg"
        frame_path = self.frames_dir / filename
        ok = cv2.imwrite(str(frame_path), frame_bgr)
        if not ok:
            raise RuntimeError(f"Could not write frame: {frame_path}")

        record = ObservationRecord(
            frame_id=frame_id,
            timestamp=timestamp,
            rgb_path=str(Path("frames") / filename),
            source=self.source,
            metadata=metadata or {},
        )
        self._obs_file.write(json.dumps(record.to_json()) + "\n")
        self.records_written += 1
        return record

    def write_manifest(self) -> None:
        manifest = {
            "source": self.source,
            "started_at": self.started_at,
            "frame_count": self.records_written,
            "observations": "observations.jsonl",
            "frames": "frames",
        }
        (self.run_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )


def read_observations(run_dir: Path) -> Iterable[ObservationRecord]:
    observations_path = run_dir / "observations.jsonl"
    if not observations_path.exists():
        raise FileNotFoundError(f"Missing observations file: {observations_path}")

    with observations_path.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            payload = json.loads(line)
            yield ObservationRecord(**payload)

