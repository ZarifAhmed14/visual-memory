from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2

from evm.change import ChangeItem, compare_track_summaries
from evm.detection import YoloObjectDetector, draw_detections, frame_path_for
from evm.memory import summarize_detections
from evm.query import find_best_track
from evm.report import build_run_report
from evm.detection import DetectionRecord
from evm.sources import VideoFileSource, WebcamSource
from evm.storage import RunWriter, read_observations
from evm.tracking import TrackRecord, summarize_tracks, track_detections


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNS_DIR = PROJECT_ROOT / "data" / "runs"


def capture_webcam(args: argparse.Namespace) -> None:
    run_dir = DEFAULT_RUNS_DIR / args.run_name
    if run_dir.exists() and any(run_dir.iterdir()):
        raise SystemExit(f"Run already exists and is not empty: {run_dir}")

    source = WebcamSource(
        camera_index=args.camera_index,
        width=args.width,
        height=args.height,
    )
    source.open()
    deadline = time.perf_counter() + args.seconds if args.seconds else None

    print(f"Capturing webcam to {run_dir}")
    print("Press q in the camera window to stop.")

    try:
        with RunWriter(run_dir=run_dir, source="webcam") as writer:
            while True:
                packet = source.next()
                if packet is None:
                    break

                writer.write_frame(
                    frame_id=packet.frame_id,
                    timestamp=packet.timestamp,
                    frame_bgr=packet.frame_bgr,
                    metadata=packet.metadata,
                )

                preview = packet.frame_bgr.copy()
                cv2.putText(
                    preview,
                    f"frame={packet.frame_id} time={packet.timestamp:.2f}s",
                    (16, 32),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2,
                )
                cv2.imshow("Embodied Visual Memory - Capture", preview)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                if deadline and time.perf_counter() >= deadline:
                    break
    finally:
        source.close()
        cv2.destroyAllWindows()

    print(f"Saved run: {run_dir}")


def ingest_video(args: argparse.Namespace) -> None:
    run_dir = DEFAULT_RUNS_DIR / args.run_name
    if run_dir.exists() and any(run_dir.iterdir()):
        raise SystemExit(f"Run already exists and is not empty: {run_dir}")

    source = VideoFileSource(
        video_path=args.video_path,
        frame_stride=args.video_frame_stride,
        resize_width=args.resize_width,
    )
    source.open()

    print(f"Ingesting video to {run_dir}")
    try:
        with RunWriter(run_dir=run_dir, source="video") as writer:
            while True:
                packet = source.next()
                if packet is None:
                    break
                writer.write_frame(
                    frame_id=packet.frame_id,
                    timestamp=packet.timestamp,
                    frame_bgr=packet.frame_bgr,
                    metadata=packet.metadata,
                )
    finally:
        source.close()

    print(f"Saved run: {run_dir}")


def run_detection_for_dir(
    run_dir: Path,
    model: str,
    confidence: float,
    frame_stride: int,
    annotate: bool,
) -> tuple[int, int]:
    observations = list(read_observations(run_dir))
    if not observations:
        raise SystemExit(f"No observations found in {run_dir}")

    detector = YoloObjectDetector(model_name=model, confidence=confidence)
    detections_path = run_dir / "detections.jsonl"
    annotated_dir = run_dir / "annotated_frames"
    if annotate:
        annotated_dir.mkdir(exist_ok=True)

    all_detections = []
    processed = 0
    with detections_path.open("w", encoding="utf-8") as file:
        for observation in observations:
            if frame_stride > 1 and (observation.frame_id - 1) % frame_stride != 0:
                continue

            frame_path = frame_path_for(run_dir, observation)
            frame = cv2.imread(str(frame_path))
            if frame is None:
                raise SystemExit(f"Could not read frame: {frame_path}")

            detections = detector.detect(frame, observation)
            for detection in detections:
                file.write(json.dumps(detection.to_json()) + "\n")
            all_detections.extend(detections)
            processed += 1

            if annotate:
                annotated = draw_detections(frame, detections)
                cv2.imwrite(str(annotated_dir / f"{observation.frame_id:06d}.jpg"), annotated)

    memories = summarize_detections(all_detections)
    (run_dir / "memory_summary.json").write_text(
        json.dumps([memory.to_json() for memory in memories], indent=2),
        encoding="utf-8",
    )
    return processed, len(all_detections)


def run_tracking_for_dir(
    run_dir: Path,
    iou_threshold: float,
    max_center_distance: float,
    max_frame_gap: int,
) -> tuple[int, int]:
    detections = load_detections(run_dir)
    if not detections:
        return 0, 0

    track_records = track_detections(
        detections,
        iou_threshold=iou_threshold,
        max_center_distance=max_center_distance,
        max_frame_gap=max_frame_gap,
    )
    summaries = summarize_tracks(track_records)

    with (run_dir / "tracks.jsonl").open("w", encoding="utf-8") as file:
        for record in track_records:
            file.write(json.dumps(record.to_json()) + "\n")

    (run_dir / "track_summary.json").write_text(
        json.dumps([summary.to_json() for summary in summaries], indent=2),
        encoding="utf-8",
    )
    return len(track_records), len(summaries)


def replay(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir).resolve()
    records = list(read_observations(run_dir))
    if not records:
        raise SystemExit(f"No observations found in {run_dir}")

    print(f"Replaying {len(records)} frames from {run_dir}")
    print("Controls: space=pause/play, n=next while paused, q=quit")

    paused = False
    index = 0
    while index < len(records):
        record = records[index]
        frame_path = run_dir / record.rgb_path
        frame = cv2.imread(str(frame_path))
        if frame is None:
            raise SystemExit(f"Could not read frame: {frame_path}")

        cv2.putText(
            frame,
            f"frame={record.frame_id} time={record.timestamp:.2f}s",
            (16, 32),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2,
        )
        cv2.imshow("Embodied Visual Memory - Replay", frame)
        key = cv2.waitKey(0 if paused else args.delay_ms) & 0xFF

        if key == ord("q"):
            break
        if key == ord(" "):
            paused = not paused
            continue
        if paused and key != ord("n"):
            continue

        index += 1

    cv2.destroyAllWindows()


def load_detections(run_dir: Path) -> list[DetectionRecord]:
    detections_path = run_dir / "detections.jsonl"
    if not detections_path.exists():
        raise FileNotFoundError(f"Missing detections file: {detections_path}")

    detections: list[DetectionRecord] = []
    with detections_path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                detections.append(DetectionRecord(**json.loads(line)))
    return detections


def detect(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir).resolve()
    processed, detection_count = run_detection_for_dir(
        run_dir=run_dir,
        model=args.model,
        confidence=args.confidence,
        frame_stride=args.frame_stride,
        annotate=args.annotate,
    )

    print(f"Processed {processed} frames from {run_dir}")
    print(f"Saved {detection_count} detections: {run_dir / 'detections.jsonl'}")
    print(f"Saved memory summary: {run_dir / 'memory_summary.json'}")
    if args.annotate:
        print(f"Saved annotated frames: {run_dir / 'annotated_frames'}")


def summarize(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir).resolve()
    detections = load_detections(run_dir)
    memories = summarize_detections(detections)
    if not memories:
        print("No objects detected.")
        return

    print("Objects seen:")
    for memory in memories:
        print(
            "- "
            f"{memory.label}: seen in {memory.seen_count} detections, "
            f"first at {memory.first_seen_timestamp:.2f}s, "
            f"last at {memory.last_seen_timestamp:.2f}s, "
            f"best confidence {memory.best_confidence:.2f}"
        )


def load_tracks(run_dir: Path) -> list[TrackRecord]:
    tracks_path = run_dir / "tracks.jsonl"
    if not tracks_path.exists():
        raise FileNotFoundError(f"Missing tracks file: {tracks_path}")

    records: list[TrackRecord] = []
    with tracks_path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                records.append(TrackRecord(**json.loads(line)))
    return records


def track(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir).resolve()
    track_count, summary_count = run_tracking_for_dir(
        run_dir=run_dir,
        iou_threshold=args.iou_threshold,
        max_center_distance=args.max_center_distance,
        max_frame_gap=args.max_frame_gap,
    )
    if track_count == 0:
        raise SystemExit("No detections available. Run detect first.")

    print(f"Created {summary_count} object tracks from {track_count} detections")
    print(f"Saved tracks: {run_dir / 'tracks.jsonl'}")
    print(f"Saved track summary: {run_dir / 'track_summary.json'}")


def scan_webcam(args: argparse.Namespace) -> None:
    capture_webcam(args)
    run_dir = DEFAULT_RUNS_DIR / args.run_name
    processed, detection_count = run_detection_for_dir(
        run_dir=run_dir,
        model=args.model,
        confidence=args.confidence,
        frame_stride=args.frame_stride,
        annotate=args.annotate,
    )
    track_count, summary_count = run_tracking_for_dir(
        run_dir=run_dir,
        iou_threshold=args.iou_threshold,
        max_center_distance=args.max_center_distance,
        max_frame_gap=args.max_frame_gap,
    )
    print("Pipeline complete")
    print(f"Run: {run_dir}")
    print(f"Frames processed for detection: {processed}")
    print(f"Detections: {detection_count}")
    print(f"Tracked detection records: {track_count}")
    print(f"Object tracks: {summary_count}")
    print("Next:")
    print(f"  python -m evm.cli list-memory data\\runs\\{args.run_name}")


def scan_video(args: argparse.Namespace) -> None:
    ingest_video(args)
    run_dir = DEFAULT_RUNS_DIR / args.run_name
    processed, detection_count = run_detection_for_dir(
        run_dir=run_dir,
        model=args.model,
        confidence=args.confidence,
        frame_stride=args.detection_frame_stride,
        annotate=args.annotate,
    )
    track_count, summary_count = run_tracking_for_dir(
        run_dir=run_dir,
        iou_threshold=args.iou_threshold,
        max_center_distance=args.max_center_distance,
        max_frame_gap=args.max_frame_gap,
    )
    print("Video pipeline complete")
    print(f"Run: {run_dir}")
    print(f"Frames processed for detection: {processed}")
    print(f"Detections: {detection_count}")
    print(f"Tracked detection records: {track_count}")
    print(f"Object tracks: {summary_count}")
    print("Next:")
    print(f"  python -m evm.cli list-memory data\\runs\\{args.run_name}")


def summarize_tracks_command(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir).resolve()
    summaries = summarize_tracks(load_tracks(run_dir))
    if not summaries:
        print("No tracks found.")
        return

    print("Object tracks:")
    for summary in summaries:
        print(
            "- "
            f"{summary.track_id}: {summary.detection_count} detections, "
            f"{summary.first_seen_timestamp:.2f}s -> {summary.last_seen_timestamp:.2f}s, "
            f"avg confidence {summary.average_confidence:.2f}"
        )


def list_memory(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir).resolve()
    summaries = summarize_tracks(load_tracks(run_dir))
    if not summaries:
        print("No visual memories found.")
        return

    print("Visual memory:")
    for summary in summaries:
        print(
            "- "
            f"{summary.track_id} ({summary.label}): "
            f"last seen at {summary.last_seen_timestamp:.2f}s, "
            f"frame {summary.last_seen_frame}, "
            f"evidence {run_dir / summary.last_rgb_path}"
        )


def query_memory(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir).resolve()
    summaries = summarize_tracks(load_tracks(run_dir))
    result = find_best_track(run_dir, args.object, summaries, min_score=args.min_score)
    print(result.answer)


def ensure_tracks_for_run(run_dir: Path, args: argparse.Namespace) -> list[TrackRecord]:
    tracks_path = run_dir / "tracks.jsonl"
    if tracks_path.exists():
        return load_tracks(run_dir)
    if not args.auto_track:
        raise FileNotFoundError(
            f"Missing tracks file: {tracks_path}. Run track first or pass --auto-track."
        )

    detections = load_detections(run_dir)
    records = track_detections(
        detections,
        iou_threshold=args.iou_threshold,
        max_center_distance=args.max_center_distance,
        max_frame_gap=args.max_frame_gap,
    )
    with tracks_path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record.to_json()) + "\n")
    (run_dir / "track_summary.json").write_text(
        json.dumps([summary.to_json() for summary in summarize_tracks(records)], indent=2),
        encoding="utf-8",
    )
    return records


def format_change_items(title: str, items: list[ChangeItem]) -> list[str]:
    lines = [f"{title}:"]
    if not items:
        lines.append("- none")
        return lines
    for item in items:
        if item.center_shift is None:
            lines.append(f"- {item.label}")
        else:
            lines.append(f"- {item.label} (center shift {item.center_shift:.1f}px)")
    return lines


def compare_runs(args: argparse.Namespace) -> None:
    before_run = Path(args.before_run).resolve()
    after_run = Path(args.after_run).resolve()

    before_track_records = ensure_tracks_for_run(before_run, args)
    after_track_records = ensure_tracks_for_run(after_run, args)
    report = compare_track_summaries(
        before_run=before_run,
        after_run=after_run,
        before_tracks=summarize_tracks(before_track_records),
        after_tracks=summarize_tracks(after_track_records),
        min_detections=args.min_detections,
        min_confidence=args.min_confidence,
        moved_distance_threshold=args.moved_distance_threshold,
    )

    output_path = Path(args.output).resolve() if args.output else after_run / "change_report.json"
    output_path.write_text(json.dumps(report.to_json(), indent=2), encoding="utf-8")

    print("Change report")
    for line in format_change_items("Appeared", report.appeared):
        print(line)
    for line in format_change_items("Disappeared", report.disappeared):
        print(line)
    for line in format_change_items("Still present", report.persisted):
        print(line)
    for line in format_change_items("Moved", report.moved):
        print(line)
    print(f"Saved report: {output_path}")


def report(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir).resolve()
    tracks = summarize_tracks(load_tracks(run_dir))
    output_path = Path(args.output).resolve() if args.output else run_dir / "report.html"
    build_run_report(run_dir, tracks, output_path)
    print(f"Saved HTML report: {output_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Embodied visual memory tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture_parser = subparsers.add_parser("capture-webcam")
    capture_parser.add_argument("--run-name", default="webcam_test")
    capture_parser.add_argument("--camera-index", type=int, default=0)
    capture_parser.add_argument("--seconds", type=float, default=10)
    capture_parser.add_argument("--width", type=int, default=1280)
    capture_parser.add_argument("--height", type=int, default=720)
    capture_parser.set_defaults(func=capture_webcam)

    scan_parser = subparsers.add_parser("scan-webcam")
    scan_parser.add_argument("--run-name", default="webcam_scan")
    scan_parser.add_argument("--camera-index", type=int, default=0)
    scan_parser.add_argument("--seconds", type=float, default=10)
    scan_parser.add_argument("--width", type=int, default=1280)
    scan_parser.add_argument("--height", type=int, default=720)
    scan_parser.add_argument("--model", default="yolov8n.pt")
    scan_parser.add_argument("--confidence", type=float, default=0.35)
    scan_parser.add_argument("--frame-stride", type=int, default=5)
    scan_parser.add_argument("--annotate", action=argparse.BooleanOptionalAction, default=True)
    scan_parser.add_argument("--iou-threshold", type=float, default=0.25)
    scan_parser.add_argument("--max-center-distance", type=float, default=180.0)
    scan_parser.add_argument("--max-frame-gap", type=int, default=10)
    scan_parser.set_defaults(func=scan_webcam)

    ingest_video_parser = subparsers.add_parser("ingest-video")
    ingest_video_parser.add_argument("video_path")
    ingest_video_parser.add_argument("--run-name", default="video_scan")
    ingest_video_parser.add_argument("--video-frame-stride", type=int, default=5)
    ingest_video_parser.add_argument("--resize-width", type=int, default=1280)
    ingest_video_parser.set_defaults(func=ingest_video)

    scan_video_parser = subparsers.add_parser("scan-video")
    scan_video_parser.add_argument("video_path")
    scan_video_parser.add_argument("--run-name", default="video_scan")
    scan_video_parser.add_argument("--video-frame-stride", type=int, default=5)
    scan_video_parser.add_argument("--resize-width", type=int, default=1280)
    scan_video_parser.add_argument("--model", default="yolov8n.pt")
    scan_video_parser.add_argument("--confidence", type=float, default=0.35)
    scan_video_parser.add_argument("--detection-frame-stride", type=int, default=1)
    scan_video_parser.add_argument("--annotate", action=argparse.BooleanOptionalAction, default=True)
    scan_video_parser.add_argument("--iou-threshold", type=float, default=0.25)
    scan_video_parser.add_argument("--max-center-distance", type=float, default=180.0)
    scan_video_parser.add_argument("--max-frame-gap", type=int, default=10)
    scan_video_parser.set_defaults(func=scan_video)

    replay_parser = subparsers.add_parser("replay")
    replay_parser.add_argument("run_dir")
    replay_parser.add_argument("--delay-ms", type=int, default=33)
    replay_parser.set_defaults(func=replay)

    detect_parser = subparsers.add_parser("detect")
    detect_parser.add_argument("run_dir")
    detect_parser.add_argument("--model", default="yolov8n.pt")
    detect_parser.add_argument("--confidence", type=float, default=0.35)
    detect_parser.add_argument("--frame-stride", type=int, default=1)
    detect_parser.add_argument("--annotate", action=argparse.BooleanOptionalAction, default=True)
    detect_parser.set_defaults(func=detect)

    summarize_parser = subparsers.add_parser("summarize")
    summarize_parser.add_argument("run_dir")
    summarize_parser.set_defaults(func=summarize)

    track_parser = subparsers.add_parser("track")
    track_parser.add_argument("run_dir")
    track_parser.add_argument("--iou-threshold", type=float, default=0.25)
    track_parser.add_argument("--max-center-distance", type=float, default=180.0)
    track_parser.add_argument("--max-frame-gap", type=int, default=10)
    track_parser.set_defaults(func=track)

    summarize_tracks_parser = subparsers.add_parser("summarize-tracks")
    summarize_tracks_parser.add_argument("run_dir")
    summarize_tracks_parser.set_defaults(func=summarize_tracks_command)

    list_memory_parser = subparsers.add_parser("list-memory")
    list_memory_parser.add_argument("run_dir")
    list_memory_parser.set_defaults(func=list_memory)

    query_memory_parser = subparsers.add_parser("query-memory")
    query_memory_parser.add_argument("run_dir")
    query_memory_parser.add_argument("object")
    query_memory_parser.add_argument("--min-score", type=float, default=0.55)
    query_memory_parser.set_defaults(func=query_memory)

    compare_parser = subparsers.add_parser("compare-runs")
    compare_parser.add_argument("before_run")
    compare_parser.add_argument("after_run")
    compare_parser.add_argument("--min-detections", type=int, default=1)
    compare_parser.add_argument("--min-confidence", type=float, default=0.35)
    compare_parser.add_argument("--moved-distance-threshold", type=float, default=160.0)
    compare_parser.add_argument("--auto-track", action=argparse.BooleanOptionalAction, default=True)
    compare_parser.add_argument("--iou-threshold", type=float, default=0.25)
    compare_parser.add_argument("--max-center-distance", type=float, default=180.0)
    compare_parser.add_argument("--max-frame-gap", type=int, default=10)
    compare_parser.add_argument("--output", default=None)
    compare_parser.set_defaults(func=compare_runs)

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("run_dir")
    report_parser.add_argument("--output", default=None)
    report_parser.set_defaults(func=report)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
