from __future__ import annotations

import time
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(slots=True)
class FramePacket:
    frame_id: int
    timestamp: float
    frame_bgr: np.ndarray
    metadata: dict


class WebcamSource:
    def __init__(
        self,
        camera_index: int = 0,
        width: int | None = 1280,
        height: int | None = 720,
    ) -> None:
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.capture: cv2.VideoCapture | None = None
        self.frame_id = 0
        self.started_at = 0.0

    def open(self) -> None:
        self.capture = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        if self.width:
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        if self.height:
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        if not self.capture.isOpened():
            raise RuntimeError(
                f"Could not open webcam index {self.camera_index}. "
                "Check camera permissions or try --camera-index 1."
            )
        self.started_at = time.perf_counter()

    def next(self) -> FramePacket | None:
        if self.capture is None:
            raise RuntimeError("WebcamSource.open() must be called before next().")

        ok, frame = self.capture.read()
        if not ok:
            return None

        self.frame_id += 1
        timestamp = time.perf_counter() - self.started_at
        return FramePacket(
            frame_id=self.frame_id,
            timestamp=timestamp,
            frame_bgr=frame,
            metadata={
                "camera_index": self.camera_index,
                "height": int(frame.shape[0]),
                "width": int(frame.shape[1]),
            },
        )

    def close(self) -> None:
        if self.capture is not None:
            self.capture.release()
            self.capture = None

