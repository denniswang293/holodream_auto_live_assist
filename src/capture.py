"""Unnormalized, bounded screen acquisition for the new runtime."""
from __future__ import annotations

from dataclasses import dataclass
import importlib
import math
import os
import threading
import time

import numpy as np

from .model import Frame


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
        return self.left, self.top, self.left + self.width, self.top + self.height


class _MSS:
    name = "mss"
    def __init__(self, region):
        self.camera = importlib.import_module("mss").mss()
        self.region = dict(left=region.left, top=region.top, width=region.width, height=region.height)
    def grab(self):
        return np.asarray(self.camera.grab(self.region))[:, :, :3].copy()
    def close(self): self.camera.close()


class _DX:
    name = "dxcam"
    def __init__(self, region):
        from .windows import primary_monitor_bounds
        bounds = primary_monitor_bounds()
        if not (0 <= region.left < region.left+region.width <= bounds[0] and
                0 <= region.top < region.top+region.height <= bounds[1]):
            raise ValueError("Use MSS for a region outside the primary DXcam output")
        self.camera = importlib.import_module("dxcam").create(output_idx=0, output_color="BGR")
        self.region = region.bounds
    def grab(self):
        image = self.camera.grab(region=self.region)
        return None if image is None else image.copy()
    def close(self): self.camera.release()


class _Auto:
    name = "auto"
    def __init__(self, region, requested):
        self.region, self.requested, self.fallback_reason = region, requested, ""
        try:
            self.backend = _MSS(region) if requested == "mss" else _DX(region)
        except Exception as exc:
            if requested != "auto": raise RuntimeError(f"{requested} capture unavailable: {exc}") from exc
            self.fallback_reason = str(exc)
            self.backend = _MSS(region)
        self.name = self.backend.name
    def grab(self):
        try: return self.backend.grab()
        except Exception as exc:
            if self.requested != "auto" or self.backend.name != "dxcam": raise
            self.backend.close()
            self.fallback_reason = str(exc)
            self.backend = _MSS(self.region); self.name = self.backend.name
            return self.backend.grab()
    def close(self): self.backend.close()


class CaptureWorker:
    """Capture on the resource-owning thread and publish only the latest frame."""
    def __init__(self, region: Region, backend="auto", fps=120, *, factory=None,
                 clock=time.perf_counter, sleeper=time.sleep):
        if backend not in ("auto", "mss", "dxcam"):
            raise ValueError("backend must be auto, mss, or dxcam")
        if not math.isfinite(fps) or fps <= 0: raise ValueError("Capture FPS must be positive")
        self.region, self.backend, self.fps = region, backend, fps
        self.factory = factory or (lambda: _Auto(region, backend))
        self.clock, self.sleeper = clock, sleeper
        self._condition = threading.Condition()
        self._frame = None
        self._closed = False
        self._stop = threading.Event()
        self.thread = None
        self.error = None
        self.captured = self.dropped = 0
        self.resolved_backend = None
        self.fallback_reason = ""

    def _publish_resource_status(self, resource):
        # Read only metadata exposed by the backend. Resource creation, grabs,
        # and closes remain on the capture owner thread.
        self.resolved_backend = getattr(resource, "name", self.backend)
        self.fallback_reason = getattr(resource, "fallback_reason", "") or ""

    def start(self):
        if self.thread is not None: raise RuntimeError("CaptureWorker already started")
        self.thread = threading.Thread(target=self._run, name="rebuild-capture", daemon=False)
        self.thread.start()
        return self

    def _run(self):
        resource = None
        try:
            resource = self.factory()
            self._publish_resource_status(resource)
            while not self._stop.is_set():
                begin = self.clock()
                image = resource.grab()
                end = self.clock()
                self._publish_resource_status(resource)
                if image is not None:
                    self.captured += 1
                    frame = Frame(self.captured-1, image, begin, end)
                    with self._condition:
                        if self._frame is not None: self.dropped += 1
                        self._frame = frame
                        self._condition.notify_all()
                deadline = begin + 1/self.fps
                while not self._stop.is_set():
                    remaining = deadline - self.clock()
                    if remaining <= 0: break
                    self.sleeper(min(remaining, .01))
        except Exception as exc:
            self.error = exc
        finally:
            try:
                if resource is not None: resource.close()
            except Exception as exc: self.error = self.error or exc
            with self._condition:
                self._closed = True
                self._condition.notify_all()

    def take(self, timeout=None):
        with self._condition:
            self._condition.wait_for(lambda: self._frame is not None or self._closed, timeout)
            frame, self._frame = self._frame, None
            return frame

    def close(self):
        self._stop.set()
        with self._condition: self._condition.notify_all()
        if self.thread:
            self.thread.join(3)
            if self.thread.is_alive(): raise RuntimeError("Capture backend did not stop within 3 seconds")

