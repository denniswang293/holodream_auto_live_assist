"""Timestamp-preserving video encoding for Geometry Scene outputs (PyAV)."""
from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import numpy as np

try:
    import av
except ImportError as exc:  # pragma: no cover - exercised when optional dependency absent
    av = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


class VFRVideoWriter:
    """Encode frames at explicit source-index timestamps on a fresh video stream."""

    def __init__(self, path: Path, width: int, height: int, final_frame_duration: float,
                 *, codec: str = "libx264", crf: int = 20):
        if av is None:
            raise RuntimeError("VFR output requires the optional `av` package; install holodream[geometry-video].") from _IMPORT_ERROR
        if width <= 0 or height <= 0 or final_frame_duration <= 0:
            raise ValueError("positive dimensions and final_frame_duration are required")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.width, self.height = width, height
        self.time_base = Fraction(1, 90_000)
        self.final_frame_duration = final_frame_duration
        rate = Fraction(1, 1) / Fraction(final_frame_duration).limit_denominator(100_000)
        self.container = av.open(str(self.path), mode="w", format="mp4")
        self.stream = self.container.add_stream(codec, rate=rate)
        self.stream.width, self.stream.height = width, height
        self.stream.pix_fmt = "yuv420p"
        self.stream.time_base = self.time_base
        self.stream.codec_context.time_base = self.time_base
        self.stream.codec_context.max_b_frames = 0
        self.stream.options = {"crf": str(crf), "preset": "medium", "x264-params": "force-cfr=0"}
        self._last_pts: int | None = None
        self.frame_count = 0

    def write(self, frame_bgr: np.ndarray, timestamp_seconds: float) -> int:
        if frame_bgr.shape != (self.height, self.width, 3) or frame_bgr.dtype != np.uint8:
            raise ValueError(f"frame must be uint8 BGR {(self.height, self.width, 3)}")
        pts = round(timestamp_seconds * self.time_base.denominator)
        if self._last_pts is not None and pts <= self._last_pts:
            raise ValueError("timestamps must be strictly increasing after 90 kHz quantization")
        frame = av.VideoFrame.from_ndarray(frame_bgr, format="bgr24")
        frame.pts = pts
        frame.time_base = self.time_base
        for packet in self.stream.encode(frame):
            self.container.mux(packet)
        self._last_pts = pts
        self.frame_count += 1
        return pts

    def close(self) -> None:
        if self.container is None:
            return
        for packet in self.stream.encode():
            self.container.mux(packet)
        self.container.close()
        self.container = None

    def __enter__(self) -> "VFRVideoWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
