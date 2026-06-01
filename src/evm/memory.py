from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass

from evm.detection import DetectionRecord


@dataclass(slots=True)
class ObjectMemory:
    label: str
    first_seen_frame: int
    first_seen_timestamp: float
    last_seen_frame: int
    last_seen_timestamp: float
    seen_count: int
    best_confidence: float
    best_frame: int
    last_rgb_path: str
    average_center_xy: list[float]
    average_area: float

    def to_json(self) -> dict:
        return asdict(self)


def summarize_detections(detections: list[DetectionRecord]) -> list[ObjectMemory]:
    by_label: dict[str, list[DetectionRecord]] = defaultdict(list)
    for detection in detections:
        by_label[detection.label].append(detection)

    memories: list[ObjectMemory] = []
    for label, label_detections in sorted(by_label.items()):
        ordered = sorted(label_detections, key=lambda item: (item.timestamp, item.frame_id))
        best = max(ordered, key=lambda item: item.confidence)
        last = ordered[-1]
        avg_x = sum(item.center_xy[0] for item in ordered) / len(ordered)
        avg_y = sum(item.center_xy[1] for item in ordered) / len(ordered)
        avg_area = sum(item.area for item in ordered) / len(ordered)
        memories.append(
            ObjectMemory(
                label=label,
                first_seen_frame=ordered[0].frame_id,
                first_seen_timestamp=ordered[0].timestamp,
                last_seen_frame=last.frame_id,
                last_seen_timestamp=last.timestamp,
                seen_count=len(ordered),
                best_confidence=best.confidence,
                best_frame=best.frame_id,
                last_rgb_path=last.rgb_path,
                average_center_xy=[avg_x, avg_y],
                average_area=avg_area,
            )
        )

    return sorted(memories, key=lambda item: (-item.seen_count, item.label))
