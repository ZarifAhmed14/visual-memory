from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from ultralytics import YOLO

from evm.observation import ObservationRecord


@dataclass(slots=True)
class DetectionRecord:
    frame_id: int
    timestamp: float
    label: str
    confidence: float
    bbox_xyxy: list[float]
    center_xy: list[float]
    area: float
    rgb_path: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


class YoloObjectDetector:
    def __init__(self, model_name: str = "yolov8n.pt", confidence: float = 0.35) -> None:
        self.model_name = model_name
        self.confidence = confidence
        self.model = YOLO(model_name)

    def detect(self, frame_bgr: np.ndarray, observation: ObservationRecord) -> list[DetectionRecord]:
        results = self.model.predict(frame_bgr, conf=self.confidence, verbose=False)
        if not results:
            return []

        result = results[0]
        detections: list[DetectionRecord] = []
        names = result.names
        boxes = result.boxes
        if boxes is None:
            return detections

        for box in boxes:
            x1, y1, x2, y2 = [float(value) for value in box.xyxy[0].tolist()]
            width = max(0.0, x2 - x1)
            height = max(0.0, y2 - y1)
            class_id = int(box.cls[0].item())
            confidence = float(box.conf[0].item())
            detections.append(
                DetectionRecord(
                    frame_id=observation.frame_id,
                    timestamp=observation.timestamp,
                    label=str(names[class_id]),
                    confidence=confidence,
                    bbox_xyxy=[x1, y1, x2, y2],
                    center_xy=[x1 + width / 2.0, y1 + height / 2.0],
                    area=width * height,
                    rgb_path=observation.rgb_path,
                    metadata={
                        "model": self.model_name,
                        "class_id": class_id,
                    },
                )
            )

        return detections


def draw_detections(frame_bgr: np.ndarray, detections: list[DetectionRecord]) -> np.ndarray:
    annotated = frame_bgr.copy()
    for detection in detections:
        x1, y1, x2, y2 = [int(round(value)) for value in detection.bbox_xyxy]
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (35, 180, 75), 2)
        label = f"{detection.label} {detection.confidence:.2f}"
        (text_w, text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        cv2.rectangle(annotated, (x1, max(0, y1 - text_h - 8)), (x1 + text_w + 8, y1), (35, 180, 75), -1)
        cv2.putText(
            annotated,
            label,
            (x1 + 4, max(text_h + 2, y1 - 5)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            2,
        )
    return annotated


def frame_path_for(run_dir: Path, observation: ObservationRecord) -> Path:
    return run_dir / observation.rgb_path
