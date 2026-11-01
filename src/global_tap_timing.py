"""Bounded shared ETA model for independently tracked Tap notes.

The estimator shares only motion timing evidence.  Track identity, position,
lane coverage and the existing PF remain per-note and are never merged.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import median


@dataclass(frozen=True)
class GlobalTapModel:
    ready: bool = False
    velocity_px_s: float | None = None
    velocity_mad_px_s: float | None = None
    velocity_sigma_px_s: float | None = None
    quality: float = 0.0
    independent_tracks: int = 0
    sample_count: int = 0
    reason: str = "NOT_READY"
    model_version: int = 0


@dataclass(frozen=True)
class GlobalTapEta:
    track_id: int
    status: str
    reason: str
    eta_s: float | None = None
    hit_at: float | None = None
    uncertainty_s: float | None = None
    quality: float = 0.0
    velocity_px_s: float | None = None
    observed_y: float | None = None
    observed_at: float | None = None
    model_version: int = 0


class GlobalTapTimingEstimator:
    """Estimate one bounded motion model from multiple reliable tracks."""

    def __init__(self, config: dict | None = None):
        cfg = dict(config or {})
        self.enabled = bool(cfg.get("enabled", False))
        self.mode = str(cfg.get("mode", "shadow")).lower()
        self.allow_active = bool(cfg.get("allow_active", False))
        if self.mode not in {"shadow", "active"}:
            raise ValueError("global_tap_timing.mode must be shadow or active")
        self.min_tracks = int(cfg.get("min_tracks", 2))
        self.min_samples = int(cfg.get("min_samples", 3))
        self.history_size = int(cfg.get("history_size", 8))
        self.max_tracks = int(cfg.get("max_tracks", 32))
        self.max_observation_age_s = float(cfg.get("max_observation_age_ms", 180)) / 1000
        self.min_velocity = float(cfg.get("min_velocity", 20))
        self.max_velocity = float(cfg.get("max_velocity", 1800))
        self.max_speed_dispersion = float(cfg.get("max_speed_dispersion", .25))
        self.max_jump_px = float(cfg.get("max_jump_px", 80))
        self.max_eta_s = float(cfg.get("max_eta_s", .45))
        self.measurement_noise_px = float(cfg.get("measurement_noise_px", 3.0))
        self.max_uncertainty_s = float(cfg.get("max_uncertainty_s", .04))
        if not (1 <= self.min_tracks <= 16 and 3 <= self.min_samples <= 12 and
                3 <= self.history_size <= 32 and 1 <= self.max_tracks <= 64):
            raise ValueError("global_tap_timing track/history limits are outside bounds")
        if not (0.05 <= self.max_observation_age_s <= .5 and
                1 <= self.min_velocity < self.max_velocity <= 3000 and
                .05 <= self.max_speed_dispersion <= 1 and
                8 <= self.max_jump_px <= 240 and
                .1 <= self.max_eta_s <= 1.5 and
                .001 <= self.measurement_noise_px <= 20 and
                .01 <= self.max_uncertainty_s <= .2):
            raise ValueError("global_tap_timing limits are outside bounds")
        self.model = GlobalTapModel()
        self._version = 0
        self._capture_timestamp = -math.inf

    @property
    def active_enabled(self):
        return self.enabled and self.mode == "active" and self.allow_active

    @staticmethod
    def _real_history(track):
        history = []
        for item in getattr(track, "history", ()):
            try:
                if len(item) < 2:
                    continue
            except TypeError:
                continue
            try:
                timestamp, y = item[0], item[1]
            except (TypeError, IndexError, KeyError):
                continue
            try:
                timestamp, y = float(timestamp), float(y)
            except (TypeError, ValueError):
                continue
            if math.isfinite(timestamp) and math.isfinite(y):
                history.append((timestamp, y))
        return history

    def _track_velocity(self, track):
        history = self._real_history(track)[-self.history_size:]
        slopes = []
        for (t0, y0), (t1, y1) in zip(history, history[1:]):
            dt, dy = t1 - t0, y1 - y0
            if not (0 < dt <= self.max_observation_age_s * 2 and 0 < dy <= self.max_jump_px):
                continue
            speed = dy / dt
            if self.min_velocity <= speed <= self.max_velocity:
                slopes.append(speed)
        if len(slopes) < self.min_samples - 1:
            return None
        speed = float(median(slopes[-(self.history_size - 1):]))
        spread = float(median([abs(value - speed) for value in slopes])) if slopes else 0.0
        return speed, spread, history

    def update(self, tracks, *, trigger_y: float, capture_timestamp: float,
               now: float, playing: bool = True):
        self._version += 1
        try:
            capture_timestamp = float(capture_timestamp)
        except (TypeError, ValueError):
            capture_timestamp = float(now)
        self._capture_timestamp = capture_timestamp if math.isfinite(capture_timestamp) else float(now)
        if not self.enabled:
            self.model = GlobalTapModel(model_version=self._version, reason="DISABLED")
            return self.model
        if not playing:
            self.model = GlobalTapModel(model_version=self._version, reason="NOT_PLAYING")
            return self.model
        candidates = []
        for track in list(tracks)[:self.max_tracks * 2]:
            if (getattr(track, "confirmed_note_type", None) != "tap" or
                    getattr(track, "status", "") != "confirmed" or
                    getattr(track, "missed", 0) != 0):
                continue
            fitted = self._track_velocity(track)
            if fitted is None:
                continue
            speed, spread, history = fitted
            last_t = history[-1][0]
            observation_age = self._capture_timestamp - last_t
            if not (math.isfinite(observation_age) and 0 <= observation_age <= self.max_observation_age_s):
                continue
            candidates.append((track.track_id, speed, spread, last_t, len(history)))
        candidates = candidates[:self.max_tracks]
        if len(candidates) < self.min_tracks:
            self.model = GlobalTapModel(model_version=self._version,
                                        independent_tracks=len(candidates),
                                        sample_count=sum(row[4] for row in candidates),
                                        reason="insufficient_independent_tracks")
            return self.model
        speeds = [row[1] for row in candidates]
        velocity = float(median(speeds))
        mad = float(median([abs(value - velocity) for value in speeds]))
        relative = mad / max(abs(velocity), self.min_velocity)
        within_track_spread = float(median([row[2] for row in candidates]))
        if relative > self.max_speed_dispersion:
            reason = "speed_variation_too_high"
            self.model = GlobalTapModel(model_version=self._version,
                                        velocity_px_s=velocity,
                                        velocity_mad_px_s=mad,
                                        velocity_sigma_px_s=math.sqrt(
                                            mad * mad + within_track_spread * within_track_spread),
                                        quality=0.0,
                                        independent_tracks=len(candidates),
                                        sample_count=sum(row[4] for row in candidates),
                                        reason=reason)
            return self.model
        quality = max(0.0, min(1.0, 1.0 - relative /
                                max(self.max_speed_dispersion, .001)))
        if within_track_spread / max(velocity, self.min_velocity) > self.max_speed_dispersion:
            self.model = GlobalTapModel(
                velocity_px_s=velocity, velocity_mad_px_s=mad,
                velocity_sigma_px_s=math.sqrt(mad * mad + within_track_spread * within_track_spread),
                independent_tracks=len(candidates),
                sample_count=sum(row[4] for row in candidates),
                reason="speed_variation_too_high", model_version=self._version)
            return self.model
        self.model = GlobalTapModel(
            ready=quality > 0 and math.isfinite(velocity),
            velocity_px_s=velocity,
            velocity_mad_px_s=mad,
            velocity_sigma_px_s=math.sqrt(mad * mad + within_track_spread * within_track_spread),
            quality=quality,
            independent_tracks=len(candidates),
            sample_count=sum(row[4] for row in candidates),
            reason="ready" if quality > 0 else "model_quality_too_low",
            model_version=self._version)
        return self.model

    def estimate(self, track, *, trigger_y: float, now: float) -> GlobalTapEta:
        model = self.model
        history = self._real_history(track)
        if not model.ready or model.velocity_px_s is None:
            return GlobalTapEta(track.track_id, "NOT_READY", model.reason,
                                 quality=model.quality, model_version=model.model_version)
        if (getattr(track, "status", "") != "confirmed" or
                getattr(track, "confirmed_note_type", None) != "tap" or
                getattr(track, "missed", 0) != 0 or len(history) < self.min_samples):
            return GlobalTapEta(track.track_id, "NOT_READY", "track_not_current_confirmed",
                                 quality=model.quality, velocity_px_s=model.velocity_px_s,
                                 model_version=model.model_version)
        observed_at, observed_y = history[-1]
        # Observation freshness is measured in capture time.  Processing
        # latency must not move the model's timestamp or make a valid frame
        # look stale merely because the worker finished later.
        reference_time = self._capture_timestamp if math.isfinite(self._capture_timestamp) else now
        age = reference_time - observed_at
        if not math.isfinite(age) or age < 0 or age > self.max_observation_age_s:
            return GlobalTapEta(track.track_id, "NOT_READY", "stale_observation",
                                 quality=model.quality, velocity_px_s=model.velocity_px_s,
                                 observed_y=observed_y, observed_at=observed_at,
                                 model_version=model.model_version)
        distance = trigger_y - observed_y
        eta = distance / model.velocity_px_s
        hit_at = observed_at + eta
        velocity = model.velocity_px_s
        sigma_v = model.velocity_sigma_px_s
        sigma_y = self.measurement_noise_px
        if (not math.isfinite(velocity) or velocity <= 0 or sigma_v is None or
                not math.isfinite(sigma_v) or sigma_v < 0 or
                not math.isfinite(sigma_y) or sigma_y < 0):
            return GlobalTapEta(track.track_id, "NOT_READY", "invalid_uncertainty_inputs",
                                eta, hit_at, None, model.quality, velocity,
                                observed_y, observed_at, model.model_version)
        # First-order propagation for t = (target_y - observed_y) / v.
        # Both terms are seconds: position noise / speed and the distance
        # multiplied by speed uncertainty / speed squared.  Do not cap this
        # value before applying the safety gate; Shadow CSV must show the
        # actual uncertainty that caused a rejection.
        sigma_t_y = sigma_y / velocity
        sigma_t_v = abs(distance) * sigma_v / (velocity * velocity)
        uncertainty = max(.001, math.sqrt(sigma_t_y ** 2 + sigma_t_v ** 2))
        if (not math.isfinite(eta) or not math.isfinite(hit_at) or
                not math.isfinite(uncertainty) or eta <= 0 or hit_at <= now):
            reason = "hit_time_not_future"
            status = "REJECTED"
        elif eta > self.max_eta_s:
            reason, status = "eta_outside_horizon", "REJECTED"
        elif uncertainty > self.max_uncertainty_s:
            reason, status = "eta_uncertainty_too_high", "REJECTED"
        else:
            reason, status = "ready", "AVAILABLE"
        return GlobalTapEta(track.track_id, status, reason, eta, hit_at, uncertainty,
                            model.quality, model.velocity_px_s, observed_y, observed_at,
                            model.model_version)
