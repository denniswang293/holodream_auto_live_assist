"""Lightweight linear ETA estimator used for shadow comparison only."""
from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import median


@dataclass(frozen=True)
class TimingEstimate:
    eta: float | None
    hit_at: float | None
    velocity: float | None
    quality: float | None
    reason: str


class LinearTimingEstimator:
    def __init__(self, *, window: int = 5, min_velocity: float = 20.0):
        self.window = max(3, int(window))
        self.min_velocity = float(min_velocity)

    def estimate(self, observations, target_y: float, capture_ts: float) -> TimingEstimate:
        points = list(observations)[-self.window:]
        if len(points) < 3:
            return TimingEstimate(None, None, None, None, "insufficient_observations")
        velocities = []
        for (t0, y0, _), (t1, y1, _) in zip(points, points[1:]):
            dt = t1 - t0
            dy = y1 - y0
            if dt <= 0 or not math.isfinite(dt) or not math.isfinite(dy) or dy <= 0:
                continue
            velocities.append(dy / dt)
        if not velocities:
            return TimingEstimate(None, None, None, None, "invalid_or_reverse_motion")
        velocity = median(velocities)
        if not math.isfinite(velocity) or velocity < self.min_velocity:
            return TimingEstimate(None, None, velocity, 0.0, "velocity_too_low")
        y_now = points[-1][1]
        if not math.isfinite(y_now) or target_y <= y_now:
            return TimingEstimate(None, None, velocity, 0.0, "target_not_future")
        eta = (target_y - y_now) / velocity
        if not math.isfinite(eta) or eta <= 0:
            return TimingEstimate(None, None, velocity, 0.0, "invalid_eta")
        spread = max(velocities) - min(velocities)
        quality = max(0.0, min(1.0, 1.0 - spread / max(velocity, self.min_velocity)))
        return TimingEstimate(eta, capture_ts + eta, velocity, quality, "ok")
