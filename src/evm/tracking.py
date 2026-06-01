from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any

from evm.detection import DetectionRecord


@dataclass(slots=True)
class TrackRecord:
    track_id: str
    label: str
    frame_id: int
    timestamp: float
    confidence: float
    bbox_xyxy: list[float]
    center_xy: list[float]
    area: float
    rgb_path: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TrackSummary:
    track_id: str
    label: str
    first_seen_frame: int
    first_seen_timestamp: float
    last_seen_frame: int
    last_seen_timestamp: float
    detection_count: int
    average_confidence: float
    best_confidence: float
    last_bbox_xyxy: list[float]
    last_center_xy: list[float]
    last_rgb_path: str

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def bbox_iou(a: list[float], b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    intersection = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - intersection
    if union <= 0:
        return 0.0
    return intersection / union


def center_distance(a: list[float], b: list[float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return (dx * dx + dy * dy) ** 0.5


def track_detections(
    detections: list[DetectionRecord],
    iou_threshold: float = 0.25,
    max_center_distance: float = 180.0,
    max_frame_gap: int = 10,
) -> list[TrackRecord]:
    ordered = sorted(detections, key=lambda item: (item.frame_id, -item.confidence))
    active_tracks: dict[str, TrackRecord] = {}
    label_counts: dict[str, int] = defaultdict(int)
    output: list[TrackRecord] = []

    for detection in ordered:
        best_track_id = None
        best_score = -1.0

        for track_id, previous in active_tracks.items():
            if previous.label != detection.label:
                continue
            frame_gap = detection.frame_id - previous.frame_id
            if frame_gap <= 0 or frame_gap > max_frame_gap:
                continue

            iou = bbox_iou(previous.bbox_xyxy, detection.bbox_xyxy)
            distance = center_distance(previous.center_xy, detection.center_xy)
            if iou < iou_threshold and distance > max_center_distance:
                continue

            distance_score = max(0.0, 1.0 - distance / max_center_distance)
            score = iou + 0.25 * distance_score
            if score > best_score:
                best_score = score
                best_track_id = track_id

        if best_track_id is None:
            label_counts[detection.label] += 1
            best_track_id = f"{detection.label}_{label_counts[detection.label]:03d}"

        track_record = TrackRecord(
            track_id=best_track_id,
            label=detection.label,
            frame_id=detection.frame_id,
            timestamp=detection.timestamp,
            confidence=detection.confidence,
            bbox_xyxy=detection.bbox_xyxy,
            center_xy=detection.center_xy,
            area=detection.area,
            rgb_path=detection.rgb_path,
            metadata={
                "association_score": best_score if best_score >= 0 else None,
                "iou_threshold": iou_threshold,
                "max_center_distance": max_center_distance,
                "max_frame_gap": max_frame_gap,
            },
        )
        active_tracks[best_track_id] = track_record
        output.append(track_record)

    return output


def summarize_tracks(records: list[TrackRecord]) -> list[TrackSummary]:
    by_track: dict[str, list[TrackRecord]] = defaultdict(list)
    for record in records:
        by_track[record.track_id].append(record)

    summaries: list[TrackSummary] = []
    for track_id, items in sorted(by_track.items()):
        ordered = sorted(items, key=lambda item: (item.frame_id, item.timestamp))
        last = ordered[-1]
        summaries.append(
            TrackSummary(
                track_id=track_id,
                label=last.label,
                first_seen_frame=ordered[0].frame_id,
                first_seen_timestamp=ordered[0].timestamp,
                last_seen_frame=last.frame_id,
                last_seen_timestamp=last.timestamp,
                detection_count=len(ordered),
                average_confidence=sum(item.confidence for item in ordered) / len(ordered),
                best_confidence=max(item.confidence for item in ordered),
                last_bbox_xyxy=last.bbox_xyxy,
                last_center_xy=last.center_xy,
                last_rgb_path=last.rgb_path,
            )
        )

    return sorted(summaries, key=lambda item: (-item.detection_count, item.track_id))
