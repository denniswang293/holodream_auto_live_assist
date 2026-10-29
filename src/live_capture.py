"""Bounded Windows acquisition and 720×404 frame normalization."""
from __future__ import annotations

from dataclasses import dataclass
from collections import deque
import importlib
import math
import threading
import time

import cv2
import numpy as np
from .calibration import FrameTransform


@dataclass(frozen=True)
class Region:
    left: int
    top: int
    width: int
    height: int

    def __post_init__(self):
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Capture region must have positive width/height")

    @property
    def bounds(self):
        return self.left, self.top, self.left+self.width, self.top+self.height

    def crop(self, relative):
        x, y, w, h = relative
        if min(x, y) < 0 or min(w, h) <= 0 or x+w > self.width or y+h > self.height:
            raise ValueError("Crop must be entirely inside the window client area")
        return Region(self.left+x, self.top+y, w, h)


def normalization_transform(source_size, native_size=(720, 404)):
    """Accept 16:9 and small manual/legacy rounding; fit without stretching."""
    width, height = source_size
    if width <= 0 or height <= 0:
        raise ValueError("Capture dimensions must be positive")
    ratio = width/height
    if abs(ratio/(16/9)-1) > .015 and abs(width-height*16/9) > 2:
        raise ValueError(f"Captured display {width}x{height} is not close to 16:9; set the game display to a 16:9 resolution")
    return FrameTransform((width, height), tuple(native_size))


def normalize_frame(image, native_size=(720, 404)):
    """Uniform scale plus centered letterboxing into the shared geometry space."""
    if image is None or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Capture backend must return a BGR image")
    height, width = image.shape[:2]
    transform = normalization_transform((width, height), native_size)
    if (width, height) == tuple(native_size):
        return image.copy()
    sx = transform.scale
    ox, oy = transform.offset
    matrix = np.array([[sx, 0, ox], [0, sx, oy]], dtype=float)
    return cv2.warpAffine(image, matrix, tuple(native_size), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))


@dataclass
class CapturedFrame:
    sequence: int
    image: np.ndarray
    captured_at: float
    acquired_at: float
    timestamp_source: str = "host_perf_counter_capture_start"


class LatestFrameBuffer:
    """One frame only. Replaced unread frames are counted, never queued."""
    def __init__(self):
        self.condition = threading.Condition()
        self.frame = None
        self.dropped = 0
        self.closed = False

    def put(self, frame):
        with self.condition:
            if self.closed:
                return
            if self.frame is not None:
                self.dropped += 1
            self.frame = frame
            self.condition.notify_all()

    def take(self, timeout=.1):
        with self.condition:
            self.condition.wait_for(lambda: self.frame is not None or self.closed, timeout)
            frame, self.frame = self.frame, None
            return frame

    def close(self):
        with self.condition:
            self.closed = True
            self.condition.notify_all()


class MSSCapture:
    name = "mss"

    def __init__(self, region):
        mss = importlib.import_module("mss")
        self.camera = mss.mss()
        self.region = dict(left=region.left, top=region.top, width=region.width, height=region.height)

    def grab(self):
        return np.asarray(self.camera.grab(self.region))[:, :, :3].copy()

    def close(self):
        self.camera.close()


class DXCapture:
    name = "dxcam"

    def __init__(self, region):
        # DXcam output 0 coordinates are monitor-local. Do not guess a monitor
        # for negative/secondary-desktop rectangles: auto mode falls back to MSS.
        from .windows_runtime import primary_monitor_bounds
        primary = primary_monitor_bounds()
        if not (0 <= region.left < region.left+region.width <= primary[0] and
                0 <= region.top < region.top+region.height <= primary[1]):
            raise ValueError("Use MSS for a region outside the primary DXcam output")
        self.camera = importlib.import_module("dxcam").create(output_idx=0, output_color="BGR")
        self.region = region.bounds

    def grab(self):
        image = self.camera.grab(region=self.region)
        return None if image is None else image.copy()

    def close(self):
        self.camera.release()


class AutoCapture:
    """Fallback on import, creation, or first DX grab failure (same thread)."""
    def __init__(self, region, backend="auto"):
        self.region, self.requested = region, backend
        self.fallback_reason = ""
        try:
            self.backend = MSSCapture(region) if backend == "mss" else DXCapture(region)
        except Exception as error:
            if backend != "auto":
                raise RuntimeError(f"{backend} capture unavailable: {error}. Install: python -m pip install -r requirements-live.txt") from error
            self.fallback_reason = str(error)
            self.backend = self._mss()

    @property
    def name(self):
        return self.backend.name

    def _mss(self):
        try:
            return MSSCapture(self.region)
        except Exception as error:
            raise RuntimeError(f"No capture backend available: {error}. Install: python -m pip install -r requirements-live.txt") from error

    def grab(self):
        try:
            return self.backend.grab()
        except Exception as error:
            if self.requested != "auto" or self.backend.name != "dxcam":
                raise
            self.backend.close()
            self.fallback_reason = str(error)
            self.backend = self._mss()
            return self.backend.grab()

    def close(self):
        self.backend.close()


class CaptureWorker:
    def __init__(self, factory, fps=120, clock=time.perf_counter, on_capture=None):
        if not math.isfinite(fps) or fps <= 0:
            raise ValueError("Capture FPS must be positive")
        self.factory, self.fps, self.clock = factory, fps, clock
        self.on_capture = on_capture
        self.buffer = LatestFrameBuffer()
        self.stop_event = threading.Event()
        self.thread = None
        self.error = None
        self.captured = 0
        self.backend_name = "initializing"
        self.fallback_reason = ""
        self.capture_times = deque(maxlen=120)

    @property
    def actual_fps(self):
        with self.buffer.condition:
            times = list(self.capture_times)
        return (len(times)-1)/(times[-1]-times[0]) if len(times)>1 and times[-1]>times[0] else 0.0

    def start(self):
        self.thread = threading.Thread(target=self._run, name="holodream-capture", daemon=False)
        self.thread.start()
        return self

    def _run(self):
        backend = None
        try:
            # MSS and DX resources are constructed/released on their owner thread.
            backend = self.factory()
            while not self.stop_event.is_set():
                begin = self.clock()
                image = backend.grab()
                end = self.clock()
                self.backend_name = backend.name
                self.fallback_reason = getattr(backend, "fallback_reason", "")
                if image is not None:
                    self.captured += 1
                    with self.buffer.condition:
                        self.capture_times.append(begin)
                    packet = CapturedFrame(self.captured-1, image, begin, end)
                    self.buffer.put(packet)
                    if self.on_capture:
                        self.on_capture(packet)
                self.stop_event.wait(max(0, 1/self.fps-(end-begin)))
        except Exception as error:
            self.error = error
        finally:
            try:
                if backend is not None:
                    backend.close()
            except Exception as error:
                self.error = self.error or error
            finally:
                self.buffer.close()

    def close(self):
        self.stop_event.set()
        self.buffer.close()
        if self.thread:
            self.thread.join(timeout=3)
            if self.thread.is_alive():
                raise RuntimeError("Capture backend did not stop within 3 seconds")


