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


class VideoFileSource:
    def __init__(
        self,
        video_path: str,
        frame_stride: int = 1,
        resize_width: int | None = None,
    ) -> None:
        self.video_path = video_path
        self.frame_stride = max(1, frame_stride)
        self.resize_width = resize_width
        self.capture: cv2.VideoCapture | None = None
        self.frame_id = 0
        self.source_frame_index = 0
        self.fps = 0.0

    def open(self) -> None:
        self.capture = cv2.VideoCapture(self.video_path)
        if not self.capture.isOpened():
            raise RuntimeError(f"Could not open video file: {self.video_path}")
        self.fps = float(self.capture.get(cv2.CAP_PROP_FPS) or 0.0)

    def next(self) -> FramePacket | None:
        if self.capture is None:
            raise RuntimeError("VideoFileSource.open() must be called before next().")

        while True:
            ok, frame = self.capture.read()
            if not ok:
                return None

            source_index = self.source_frame_index
            self.source_frame_index += 1
            if source_index % self.frame_stride != 0:
                continue

            if self.resize_width and frame.shape[1] > self.resize_width:
                scale = self.resize_width / frame.shape[1]
                new_height = int(round(frame.shape[0] * scale))
                frame = cv2.resize(frame, (self.resize_width, new_height), interpolation=cv2.INTER_AREA)

            self.frame_id += 1
            timestamp = source_index / self.fps if self.fps > 0 else float(self.frame_id - 1)
            return FramePacket(
                frame_id=self.frame_id,
                timestamp=timestamp,
                frame_bgr=frame,
                metadata={
                    "video_path": self.video_path,
                    "source_frame_index": source_index,
                    "source_fps": self.fps,
                    "height": int(frame.shape[0]),
                    "width": int(frame.shape[1]),
                },
            )

    def close(self) -> None:
        if self.capture is not None:
            self.capture.release()
            self.capture = None
