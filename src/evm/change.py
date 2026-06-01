from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from evm.tracking import TrackSummary


@dataclass(slots=True)
class ChangeItem:
    label: str
    before_track_id: str | None = None
    after_track_id: str | None = None
    before_frame: int | None = None
    after_frame: int | None = None
    before_timestamp: float | None = None
    after_timestamp: float | None = None
    center_shift: float | None = None
    before_evidence: str | None = None
    after_evidence: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ChangeReport:
    before_run: str
    after_run: str
    appeared: list[ChangeItem]
    disappeared: list[ChangeItem]
    persisted: list[ChangeItem]
    moved: list[ChangeItem]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def center_distance(a: list[float], b: list[float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return (dx * dx + dy * dy) ** 0.5


def filter_tracks(
    tracks: list[TrackSummary],
    min_detections: int = 1,
    min_confidence: float = 0.35,
) -> list[TrackSummary]:
    return [
        track
        for track in tracks
        if track.detection_count >= min_detections and track.best_confidence >= min_confidence
    ]


def strongest_track_by_label(tracks: list[TrackSummary]) -> dict[str, TrackSummary]:
    grouped: dict[str, list[TrackSummary]] = defaultdict(list)
    for track in tracks:
        grouped[track.label].append(track)

    return {
        label: max(
            items,
            key=lambda item: (
                item.detection_count,
                item.best_confidence,
                item.last_seen_timestamp,
            ),
        )
        for label, items in grouped.items()
    }


def compare_track_summaries(
    before_run: Path,
    after_run: Path,
    before_tracks: list[TrackSummary],
    after_tracks: list[TrackSummary],
    min_detections: int = 1,
    min_confidence: float = 0.35,
    moved_distance_threshold: float = 160.0,
) -> ChangeReport:
    before = strongest_track_by_label(filter_tracks(before_tracks, min_detections, min_confidence))
    after = strongest_track_by_label(filter_tracks(after_tracks, min_detections, min_confidence))

    before_labels = set(before)
    after_labels = set(after)

    appeared: list[ChangeItem] = []
    disappeared: list[ChangeItem] = []
    persisted: list[ChangeItem] = []
    moved: list[ChangeItem] = []

    for label in sorted(after_labels - before_labels):
        track = after[label]
        appeared.append(
            ChangeItem(
                label=label,
                after_track_id=track.track_id,
                after_frame=track.last_seen_frame,
                after_timestamp=track.last_seen_timestamp,
                after_evidence=str(after_run / track.last_rgb_path),
            )
        )

    for label in sorted(before_labels - after_labels):
        track = before[label]
        disappeared.append(
            ChangeItem(
                label=label,
                before_track_id=track.track_id,
                before_frame=track.last_seen_frame,
                before_timestamp=track.last_seen_timestamp,
                before_evidence=str(before_run / track.last_rgb_path),
            )
        )

    for label in sorted(before_labels & after_labels):
        before_track = before[label]
        after_track = after[label]
        shift = center_distance(before_track.last_center_xy, after_track.last_center_xy)
        item = ChangeItem(
            label=label,
            before_track_id=before_track.track_id,
            after_track_id=after_track.track_id,
            before_frame=before_track.last_seen_frame,
            after_frame=after_track.last_seen_frame,
            before_timestamp=before_track.last_seen_timestamp,
            after_timestamp=after_track.last_seen_timestamp,
            center_shift=shift,
            before_evidence=str(before_run / before_track.last_rgb_path),
            after_evidence=str(after_run / after_track.last_rgb_path),
        )
        persisted.append(item)
        if shift >= moved_distance_threshold:
            moved.append(item)

    return ChangeReport(
        before_run=str(before_run),
        after_run=str(after_run),
        appeared=appeared,
        disappeared=disappeared,
        persisted=persisted,
        moved=moved,
        metadata={
            "min_detections": min_detections,
            "min_confidence": min_confidence,
            "moved_distance_threshold": moved_distance_threshold,
            "before_labels": sorted(before_labels),
            "after_labels": sorted(after_labels),
        },
    )
