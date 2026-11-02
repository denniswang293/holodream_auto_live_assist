"""Bounded shared ETA model for independently tracked Tap notes.

The estimator shares only motion timing evidence.  Track identity, position,
lane coverage and the existing PF remain per-note and are never merged.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import median
from collections import defaultdict, deque


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
    source: str = "none"
    profile_edges: tuple[float, ...] = ()
    profile_speeds: tuple[float, ...] = ()
    profile_sigmas: tuple[float, ...] = ()
    profile_counts: tuple[int, ...] = ()
    profile_age_s: float | None = None
    speed_epoch: int = 0
    song_scale: float = 1.0
    calibration_state: str = "unavailable"
    timing_source: str = "global_trigger_legacy"


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
    physical_cross_at: float | None = None
    press_at: float | None = None
    physical_eta_s: float | None = None
    lead_ms: float = 0.0
    timing_source: str = "global_trigger_legacy"
    speed_epoch: int = 0


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
        self.profile_segments = int(cfg.get("profile_segments", 4))
        self.profile_ttl_s = float(cfg.get("profile_ttl_ms", 450)) / 1000
        self.profile_min_samples = int(cfg.get("profile_min_samples", 1))
        self.timing_reference = str(cfg.get("timing_reference", "trigger_legacy")).lower()
        if self.timing_reference not in {"trigger_legacy", "physical_calibrated"}:
            raise ValueError("global_tap_timing.timing_reference must be trigger_legacy or physical_calibrated")
        self.input_lead_ms = float(cfg.get("input_lead_ms", 0.0))
        if not (0.0 <= self.input_lead_ms <= 250.0):
            raise ValueError("global_tap_timing.input_lead_ms must be between 0 and 250ms")
        if not (1 <= self.min_tracks <= 16 and 3 <= self.min_samples <= 12 and
                3 <= self.history_size <= 32 and 1 <= self.max_tracks <= 64 and
                2 <= self.profile_segments <= 6 and 1 <= self.profile_min_samples <= 8):
            raise ValueError("global_tap_timing track/history limits are outside bounds")
        if not (0.05 <= self.max_observation_age_s <= .5 and
                1 <= self.min_velocity < self.max_velocity <= 3000 and
                .05 <= self.max_speed_dispersion <= 1 and
                8 <= self.max_jump_px <= 240 and
                .1 <= self.max_eta_s <= 1.5 and
                .001 <= self.measurement_noise_px <= 20 and
                .01 <= self.max_uncertainty_s <= .2 and
                .1 <= self.profile_ttl_s <= 5.0):
            raise ValueError("global_tap_timing limits are outside bounds")
        self.model = GlobalTapModel()
        self._version = 0
        self._capture_timestamp = -math.inf
        self._profile_history = defaultdict(lambda: defaultdict(lambda: deque(maxlen=6)))
        self._profile_edges: tuple[float, ...] = ()
        self._profile_last_capture = -math.inf
        self._profile_pair_seen: dict[tuple, float] = {}
        self.speed_epoch = 1
        self._was_playing = False
        self._song_reference_velocity: float | None = None

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
        samples = []
        for (t0, y0), (t1, y1) in zip(history, history[1:]):
            dt, dy = t1 - t0, y1 - y0
            if not (0 < dt <= self.max_observation_age_s * 2 and 0 < dy <= self.max_jump_px):
                continue
            speed = dy / dt
            if self.min_velocity <= speed <= self.max_velocity:
                slopes.append(speed)
                samples.append(((y0 + y1) / 2.0, speed, t0, t1))
        if len(slopes) < self.min_samples - 1:
            return None
        speed = float(median(slopes[-(self.history_size - 1):]))
        spread = float(median([abs(value - speed) for value in slopes])) if slopes else 0.0
        return speed, spread, history, samples

    def _profile_edges_for(self, trigger_y: float):
        trigger_y = float(trigger_y)
        if not math.isfinite(trigger_y) or trigger_y <= 0:
            return ()
        if self.profile_segments == 4:
            fractions = (0.0, .30, .55, .78, 1.0)
        else:
            fractions = tuple(index / self.profile_segments
                              for index in range(self.profile_segments + 1))
        return tuple(trigger_y * fraction for fraction in fractions)

    @staticmethod
    def _profile_segment(y: float, edges: tuple[float, ...]):
        if len(edges) < 2 or not math.isfinite(y) or y < edges[0] or y >= edges[-1]:
            return None
        for index in range(len(edges) - 1):
            if edges[index] <= y < edges[index + 1]:
                return index
        return len(edges) - 2

    def reset(self):
        self._profile_history.clear()
        self._profile_edges = ()
        self._profile_last_capture = -math.inf
        self._profile_pair_seen.clear()
        self.speed_epoch += 1
        self._was_playing = False
        self._song_reference_velocity = None
        self.model = GlobalTapModel(model_version=self._version, reason="RESET",
                                    speed_epoch=self.speed_epoch,
                                    timing_source=("global_physical_calibrated"
                                                   if self.timing_reference == "physical_calibrated"
                                                   else "global_trigger_legacy"))

    def update(self, tracks, *, trigger_y: float, capture_timestamp: float,
               now: float, playing: bool = True):
        self._version += 1
        try:
            capture_timestamp = float(capture_timestamp)
        except (TypeError, ValueError):
            capture_timestamp = float(now)
        self._capture_timestamp = capture_timestamp if math.isfinite(capture_timestamp) else float(now)
        if not self.enabled:
            self.model = GlobalTapModel(model_version=self._version, reason="DISABLED",
                                        speed_epoch=self.speed_epoch,
                                        timing_source=("global_physical_calibrated"
                                                       if self.timing_reference == "physical_calibrated"
                                                       else "global_trigger_legacy"))
            return self.model
        if not playing:
            if self._was_playing:
                self.reset()
            self._was_playing = False
            self.model = GlobalTapModel(model_version=self._version, reason="NOT_PLAYING",
                                        speed_epoch=self.speed_epoch,
                                        timing_source=("global_physical_calibrated"
                                                       if self.timing_reference == "physical_calibrated"
                                                       else "global_trigger_legacy"))
            return self.model
        self._was_playing = True
        edges = self._profile_edges_for(trigger_y)
        # Segment IDs are defined relative to the judgment line.  Never mix
        # samples collected under a different geometry/trigger coordinate.
        if self._profile_edges and edges != self._profile_edges:
            self._profile_history.clear()
            self._profile_last_capture = -math.inf
        self._profile_edges = edges
        candidates = []
        current_segment_values = defaultdict(lambda: defaultdict(list))
        for track in list(tracks)[:self.max_tracks * 2]:
            if (getattr(track, "confirmed_note_type", None) != "tap" or
                    getattr(track, "status", "") != "confirmed" or
                    getattr(track, "missed", 0) != 0):
                continue
            fitted = self._track_velocity(track)
            if fitted is None:
                continue
            speed, spread, history, samples = fitted
            last_t = history[-1][0]
            observation_age = self._capture_timestamp - last_t
            if not (math.isfinite(observation_age) and 0 <= observation_age <= self.max_observation_age_s):
                continue
            candidates.append((track.track_id, speed, spread, last_t, len(history)))
            for sample_y, sample_speed, t0, t1 in samples:
                segment = self._profile_segment(sample_y, edges)
                if segment is not None:
                    pair_key = (track.track_id, round(float(t0), 7),
                                round(float(t1), 7), segment)
                    if pair_key not in self._profile_pair_seen:
                        self._profile_pair_seen[pair_key] = self._capture_timestamp
                        current_segment_values[segment][track.track_id].append(sample_speed)
        candidates = candidates[:self.max_tracks]
        # A single confirmed Tap with enough independent real observations is
        # a valid cold-start source.  It may seed the shared model, but never
        # uses a synthetic/default speed.  Later frames continue to update it
        # from additional tracks when available.
        for segment, tracks_by_id in current_segment_values.items():
            for track_id, values in tracks_by_id.items():
                if values:
                    self._profile_history[segment][track_id].append(
                        (self._capture_timestamp, float(median(values))))
        for segment in list(self._profile_history):
            for track_id in list(self._profile_history[segment]):
                history = self._profile_history[segment][track_id]
                while history and self._capture_timestamp - history[0][0] > self.profile_ttl_s:
                    history.popleft()
                if not history:
                    del self._profile_history[segment][track_id]
            if not self._profile_history[segment]:
                del self._profile_history[segment]
        self._profile_pair_seen = {
            key: seen_at for key, seen_at in self._profile_pair_seen.items()
            if self._capture_timestamp - seen_at <= self.profile_ttl_s
        }

        profile_speeds, profile_sigmas, profile_counts = [], [], []
        profile_track_ids = set()
        profile_latest_capture = -math.inf
        for tracks_by_id in self._profile_history.values():
            profile_track_ids.update(tracks_by_id)
            for history in tracks_by_id.values():
                if history:
                    profile_latest_capture = max(profile_latest_capture, history[-1][0])
        for segment in range(len(edges) - 1):
            tracks_by_id = self._profile_history.get(segment, {})
            values = [float(median(value for _, value in history))
                      for history in tracks_by_id.values() if history]
            if len(values) < self.profile_min_samples:
                continue
            segment_speed = float(median(values))
            segment_sigma = float(median([abs(value - segment_speed) for value in values]))
            profile_speeds.append((segment, segment_speed))
            profile_sigmas.append((segment, segment_sigma))
            profile_counts.append((segment, len(values)))

        usable_profile = bool(profile_speeds)
        profile_age = (self._capture_timestamp - profile_latest_capture
                       if math.isfinite(profile_latest_capture) else math.inf)
        unreliable_segments = []
        sigma_by_segment = dict(profile_sigmas)
        for segment, speed in profile_speeds:
            sigma = sigma_by_segment.get(segment, float("nan"))
            if (speed > 0 and math.isfinite(sigma) and
                    sigma / speed > self.max_speed_dispersion):
                unreliable_segments.append((speed, sigma))
        if len(candidates) >= self.min_tracks and unreliable_segments:
            self.model = GlobalTapModel(
                velocity_px_s=float(median([speed for speed, _ in unreliable_segments])),
                velocity_sigma_px_s=float(median([sigma for _, sigma in unreliable_segments])),
                independent_tracks=len(candidates),
                sample_count=sum(row[4] for row in candidates),
                reason="speed_variation_too_high", model_version=self._version,
                source="global_profile", profile_edges=edges,
                profile_speeds=tuple(dict(profile_speeds).get(i, float("nan")) for i in range(len(edges)-1)),
                profile_sigmas=tuple(dict(profile_sigmas).get(i, float("nan")) for i in range(len(edges)-1)),
                profile_counts=tuple(dict(profile_counts).get(i, 0) for i in range(len(edges)-1)),
                profile_age_s=(profile_age if math.isfinite(profile_age) else None),
                speed_epoch=self.speed_epoch,
                calibration_state="temporarily_stale" if profile_age > 0 else "unavailable",
                timing_source=("global_physical_calibrated" if self.timing_reference == "physical_calibrated"
                               else "global_trigger_legacy"))
            return self.model
        single_track_bootstrap = (len(candidates) == 1 and candidates[0][4] >= self.min_samples)
        cached_age = profile_age
        if not usable_profile or (len(candidates) < self.min_tracks and
                                  not single_track_bootstrap and cached_age > self.profile_ttl_s):
            self.model = GlobalTapModel(model_version=self._version,
                                        independent_tracks=len(candidates),
                                        sample_count=sum(row[4] for row in candidates),
                                        reason="insufficient_independent_tracks",
                                        profile_edges=edges,
                                        profile_age_s=(cached_age if math.isfinite(cached_age) else None),
                                        speed_epoch=self.speed_epoch,
                                        calibration_state=("temporarily_stale" if math.isfinite(cached_age) and cached_age > 0
                                                           else "unavailable"),
                                        timing_source=("global_physical_calibrated" if self.timing_reference == "physical_calibrated"
                                                       else "global_trigger_legacy"))
            return self.model
        if candidates:
            self._profile_last_capture = self._capture_timestamp
        representative = [speed for _, speed in profile_speeds]
        velocity = float(median(representative))
        if self._song_reference_velocity is None and math.isfinite(velocity) and velocity > 0:
            self._song_reference_velocity = velocity
        song_scale = (velocity / self._song_reference_velocity
                      if self._song_reference_velocity else 1.0)
        mad = float(median([abs(value - velocity) for value in representative])) if representative else 0.0
        sigma_values = [sigma for _, sigma in profile_sigmas]
        sigma_v = math.sqrt(mad * mad + (median(sigma_values) if sigma_values else 0.0) ** 2)
        quality = max(0.0, min(1.0, 1.0 -
                                (median(sigma_values) if sigma_values else 0.0) /
                                max(velocity, self.min_velocity)))
        source = ("global_profile" if len(profile_speeds) >= 2 and
                  len(profile_track_ids) >= self.min_tracks else "global_bootstrap")
        calibration_state = ("calibrated" if source == "global_profile" and
                              all(count >= 2 for _, count in profile_counts)
                              else "bootstrap")
        profile_by_segment = dict(profile_speeds)
        sigma_by_segment = dict(profile_sigmas)
        count_by_segment = dict(profile_counts)
        self.model = GlobalTapModel(
            ready=quality > 0 and math.isfinite(velocity),
            velocity_px_s=velocity,
            velocity_mad_px_s=mad,
            velocity_sigma_px_s=sigma_v,
            quality=quality,
            independent_tracks=max(len(candidates), len(profile_track_ids)),
            sample_count=sum(row[4] for row in candidates),
            reason="ready" if quality > 0 else "model_quality_too_low",
            model_version=self._version, source=source,
            profile_edges=edges,
            profile_speeds=tuple(profile_by_segment.get(i, float("nan")) for i in range(len(edges)-1)),
            profile_sigmas=tuple(sigma_by_segment.get(i, float("nan")) for i in range(len(edges)-1)),
            profile_counts=tuple(count_by_segment.get(i, 0) for i in range(len(edges)-1)),
            profile_age_s=(profile_age if math.isfinite(profile_age) else None),
            speed_epoch=self.speed_epoch,
            song_scale=song_scale,
            calibration_state=calibration_state,
            timing_source=("global_physical_calibrated" if self.timing_reference == "physical_calibrated"
                           else "global_trigger_legacy"))
        return self.model

    def _profile_eta(self, observed_y: float, trigger_y: float):
        model = self.model
        if not model.profile_edges or not model.profile_speeds:
            return None
        if not (math.isfinite(observed_y) and math.isfinite(trigger_y) and trigger_y > observed_y):
            return None
        edges = model.profile_edges
        total = 0.0
        variance = 0.0
        used = 0
        known = [index for index, speed in enumerate(model.profile_speeds)
                 if math.isfinite(speed) and speed > 0]
        if not known:
            return None
        for index in range(len(edges) - 1):
            left = max(observed_y, edges[index])
            right = min(trigger_y, edges[index + 1])
            if right <= left:
                continue
            source_index = index if index in known else min(known, key=lambda item: abs(item - index))
            speed = model.profile_speeds[source_index]
            sigma_v = model.profile_sigmas[source_index] if source_index < len(model.profile_sigmas) else float("nan")
            if not math.isfinite(speed) or speed <= 0:
                return None
            segment_time = (right - left) / speed
            total += segment_time
            if math.isfinite(sigma_v) and sigma_v >= 0:
                variance += ((right - left) * sigma_v / (speed * speed)) ** 2
            else:
                variance += (segment_time * self.max_speed_dispersion) ** 2
            segment_count = (model.profile_counts[source_index]
                             if source_index < len(model.profile_counts) else 0)
            if segment_count < 2 and model.timing_source == "global_physical_calibrated":
                # Sparse sections remain usable only with an explicit,
                # bounded uncertainty penalty; do not silently treat one
                # observation as a high-confidence calibrated segment.
                variance += (segment_time * .10) ** 2
            # A bounded same-segment process floor keeps a zero-MAD sample
            # from claiming perfect timing and grows with traversed time. It
            # is not a cross-height gradient penalty.
            variance += (segment_time * .05) ** 2
            used += 1
        if used == 0 or not math.isfinite(total):
            return None
        return total, max(0.0, math.sqrt(max(0.0, variance))), used

    def estimate(self, track, *, trigger_y: float, now: float,
                 physical_hit_y: float | None = None,
                 input_lead_ms: float | None = None) -> GlobalTapEta:
        model = self.model
        use_physical = (self.timing_reference == "physical_calibrated" and
                        physical_hit_y is not None and math.isfinite(float(physical_hit_y)))
        target_y = float(physical_hit_y) if use_physical else float(trigger_y)
        lead_ms = self.input_lead_ms if input_lead_ms is None else float(input_lead_ms)
        timing_source = ("global_physical_calibrated" if use_physical
                         else "global_trigger_legacy")
        history = self._real_history(track)
        if not model.ready or model.velocity_px_s is None:
            return GlobalTapEta(track.track_id, "NOT_READY", model.reason,
                                 quality=model.quality, model_version=model.model_version,
                                 timing_source=timing_source, lead_ms=lead_ms,
                                 speed_epoch=model.speed_epoch)
        if (getattr(track, "status", "") != "confirmed" or
                getattr(track, "confirmed_note_type", None) != "tap" or
                getattr(track, "missed", 0) != 0 or len(history) < self.min_samples):
            return GlobalTapEta(track.track_id, "NOT_READY", "track_not_current_confirmed",
                                 quality=model.quality, velocity_px_s=model.velocity_px_s,
                                 model_version=model.model_version, timing_source=timing_source,
                                 lead_ms=lead_ms, speed_epoch=model.speed_epoch)
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
                                 model_version=model.model_version, timing_source=timing_source,
                                 lead_ms=lead_ms, speed_epoch=model.speed_epoch)
        distance = target_y - observed_y
        profile = self._profile_eta(observed_y, target_y)
        if profile is None:
            return GlobalTapEta(track.track_id, "NOT_READY", "profile_not_ready",
                                None, None, None, model.quality, model.velocity_px_s,
                                observed_y, observed_at, model.model_version,
                                timing_source=timing_source, lead_ms=lead_ms,
                                speed_epoch=model.speed_epoch)
        physical_eta, profile_uncertainty, used_segments = profile
        physical_cross_at = observed_at + physical_eta
        press_at = physical_cross_at - lead_ms / 1000.0 if use_physical else physical_cross_at
        hit_at = press_at
        eta = press_at - observed_at
        velocity = model.velocity_px_s
        sigma_y = self.measurement_noise_px
        if (not math.isfinite(velocity) or velocity <= 0 or
                not math.isfinite(sigma_y) or sigma_y < 0):
            return GlobalTapEta(track.track_id, "NOT_READY", "invalid_uncertainty_inputs",
                                eta, hit_at, None, model.quality, velocity,
                                observed_y, observed_at, model.model_version,
                                physical_cross_at=physical_cross_at, press_at=press_at,
                                physical_eta_s=physical_eta, lead_ms=lead_ms,
                                timing_source=timing_source, speed_epoch=model.speed_epoch)
        # Position noise is converted with the local v(y).  Do not append the
        # old full-distance/global-sigma term: profile_uncertainty already
        # propagated segment-local speed residuals and extrapolation risk.
        local_segment = self._profile_segment(observed_y, model.profile_edges)
        known_segments = [index for index, speed in enumerate(model.profile_speeds)
                          if math.isfinite(speed) and speed > 0]
        if local_segment is None or not known_segments:
            local_index = min(known_segments, key=lambda item: abs(item - (local_segment or 0)))
        else:
            local_index = (local_segment if local_segment in known_segments else
                            min(known_segments, key=lambda item: abs(item - local_segment)))
        local_velocity = model.profile_speeds[local_index]
        sigma_t_y = sigma_y / max(local_velocity, self.min_velocity)
        uncertainty = max(.001, math.sqrt(profile_uncertainty ** 2 + sigma_t_y ** 2))
        if (not math.isfinite(eta) or not math.isfinite(hit_at) or
                not math.isfinite(uncertainty) or eta <= 0 or hit_at <= now):
            reason = "press_time_not_future" if use_physical else "hit_time_not_future"
            status = "REJECTED"
        elif eta > self.max_eta_s:
            reason, status = "eta_outside_horizon", "REJECTED"
        elif uncertainty > self.max_uncertainty_s:
            reason, status = "eta_uncertainty_too_high", "REJECTED"
        else:
            reason, status = "ready", "AVAILABLE"
        return GlobalTapEta(track.track_id, status, reason, eta, hit_at, uncertainty,
                            model.quality, model.velocity_px_s, observed_y, observed_at,
                            model.model_version, physical_cross_at=physical_cross_at,
                            press_at=press_at, physical_eta_s=physical_eta, lead_ms=lead_ms,
                            timing_source=timing_source, speed_epoch=model.speed_epoch)
