from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from evm.tracking import TrackSummary


@dataclass(slots=True)
class MemoryQueryResult:
    query: str
    matched: bool
    track: TrackSummary | None
    score: float
    supporting_frame_path: Path | None
    answer: str


ALIASES = {
    "cellphone": "cell phone",
    "mobile": "cell phone",
    "phone": "cell phone",
    "tv": "tv",
    "television": "tv",
    "couch": "sofa",
    "bike": "bicycle",
}


def normalize_label(text: str) -> str:
    normalized = " ".join(text.lower().strip().replace("_", " ").split())
    return ALIASES.get(normalized, normalized)


def label_similarity(query: str, label: str) -> float:
    query_norm = normalize_label(query)
    label_norm = normalize_label(label)
    if query_norm == label_norm:
        return 1.0
    if query_norm in label_norm or label_norm in query_norm:
        return 0.85
    return SequenceMatcher(None, query_norm, label_norm).ratio()


def find_best_track(
    run_dir: Path,
    query: str,
    summaries: list[TrackSummary],
    min_score: float = 0.55,
) -> MemoryQueryResult:
    if not summaries:
        return MemoryQueryResult(
            query=query,
            matched=False,
            track=None,
            score=0.0,
            supporting_frame_path=None,
            answer="I do not have any tracked visual memories for this run yet. Run detect and track first.",
        )

    scored = [(label_similarity(query, summary.label), summary) for summary in summaries]
    score, best = max(scored, key=lambda item: (item[0], item[1].last_seen_timestamp))
    if score < min_score:
        known = ", ".join(sorted({summary.label for summary in summaries}))
        return MemoryQueryResult(
            query=query,
            matched=False,
            track=None,
            score=score,
            supporting_frame_path=None,
            answer=f"I could not find '{query}' in this run. Objects I remember: {known}.",
        )

    frame_path = run_dir / best.last_rgb_path
    answer = (
        f"I last saw {best.label} as {best.track_id} at "
        f"{best.last_seen_timestamp:.2f}s in frame {best.last_seen_frame}. "
        f"It appeared in {best.detection_count} detections. "
        f"Supporting frame: {frame_path}"
    )
    return MemoryQueryResult(
        query=query,
        matched=True,
        track=best,
        score=score,
        supporting_frame_path=frame_path,
        answer=answer,
    )
