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
    def __init__(self, *, window: int = 5, min_velocity: float = 20.0,
                 max_observation_age_s: float = .20):
        self.window = max(3, int(window))
        self.min_velocity = float(min_velocity)
        self.max_observation_age_s = float(max_observation_age_s)

    def estimate(self, observations, target_y: float, capture_ts: float,
                 *, now: float | None = None) -> TimingEstimate:
        raw_points = list(observations)[-self.window:]
        # Ignore malformed/dropout placeholders when selecting the reference
        # observation.  A missing current-frame sample must not move hit_at to
        # capture time, but an actually old last observation must be rejected.
        points = [point for point in raw_points
                  if len(point) >= 2 and math.isfinite(point[0]) and math.isfinite(point[1])]
        if len(points) < 3:
            return TimingEstimate(None, None, None, None, "insufficient_observations")
        last_observation_ts = points[-1][0]
        reference_ts = capture_ts if now is None else now
        if (not math.isfinite(last_observation_ts) or
                reference_ts - last_observation_ts > self.max_observation_age_s):
            return TimingEstimate(None, None, None, 0.0, "stale_observation")
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
        eta_from_observation = (target_y - y_now) / velocity
        if not math.isfinite(eta_from_observation) or eta_from_observation <= 0:
            return TimingEstimate(None, None, velocity, 0.0, "invalid_eta")
        # The absolute hit timestamp is anchored to the observation that
        # produced the fit.  ETA is exposed relative to this frame's capture
        # timestamp, so a dropped frame naturally shortens ETA and can become
        # an explicit expired prediction.
        hit_at = last_observation_ts + eta_from_observation
        eta = hit_at - capture_ts
        if not math.isfinite(eta) or eta <= 0:
            return TimingEstimate(None, hit_at, velocity, 0.0, "expired_prediction")
        spread = max(velocities) - min(velocities)
        quality = max(0.0, min(1.0, 1.0 - spread / max(velocity, self.min_velocity)))
        return TimingEstimate(eta, hit_at, velocity, quality, "ok")
