from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class ObservationRecord:
    frame_id: int
    timestamp: float
    rgb_path: str
    depth_path: str | None = None
    camera_pose: list[list[float]] | None = None
    camera_intrinsics: dict[str, Any] | None = None
    source: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

