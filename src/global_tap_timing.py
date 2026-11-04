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


@dataclass(frozen=True)
class GlobalTapTimingPolicy:
    """Typed owner for the Global ETA safety policy.

    The mapping adapter is intentionally kept at the boundary for legacy
    callers.  The estimator itself only reads this immutable policy, so the
    active path cannot accidentally depend on a mutable configuration tree.
    """
    enabled: bool = True
    mode: str = "active"
    allow_active: bool = True
    min_tracks: int = 2
    min_samples: int = 3
    history_size: int = 8
    max_tracks: int = 32
    max_observation_age_s: float = .180
    min_velocity: float = 20.0
    max_velocity: float = 1800.0
    max_speed_dispersion: float = .25
    max_jump_px: float = 80.0
    max_eta_s: float = .45
    measurement_noise_px: float = 3.0
    max_uncertainty_s: float = .04
    profile_segments: int = 4
    profile_ttl_s: float = 3.0
    profile_min_samples: int = 1
    timing_reference: str = "physical_calibrated"
    input_lead_ms: float = 60.0
    guarded_reuse_enabled: bool = False
    guarded_reuse_max_age_s: float = .080

    @classmethod
    def from_mapping(cls, config: dict | None = None):
        cfg = dict(config or {})
        # Empty mappings are the compatibility constructor used by isolated
        # unit tests/legacy callers. Source-first Active always supplies the
        # complete mapping (or a typed policy) from resolve_config.
        if not cfg:
            return cls(enabled=False, mode="shadow", allow_active=False,
                       profile_ttl_s=.45, timing_reference="trigger_legacy",
                       input_lead_ms=0.0).validate()
        def strict_bool(name, default):
            value = cfg.get(name, default)
            if not isinstance(value, bool):
                raise ValueError(f"global_tap_timing.{name} must be a boolean")
            return value
        values = {
            "enabled": strict_bool("enabled", cls.enabled),
            "mode": str(cfg.get("mode", cls.mode)).lower(),
            "allow_active": strict_bool("allow_active", cls.allow_active),
            "min_tracks": int(cfg.get("min_tracks", cls.min_tracks)),
            "min_samples": int(cfg.get("min_samples", cls.min_samples)),
            "history_size": int(cfg.get("history_size", cls.history_size)),
            "max_tracks": int(cfg.get("max_tracks", cls.max_tracks)),
            "max_observation_age_s": float(cfg.get("max_observation_age_ms", cls.max_observation_age_s * 1000)) / 1000,
            "min_velocity": float(cfg.get("min_velocity", cls.min_velocity)),
            "max_velocity": float(cfg.get("max_velocity", cls.max_velocity)),
            "max_speed_dispersion": float(cfg.get("max_speed_dispersion", cls.max_speed_dispersion)),
            "max_jump_px": float(cfg.get("max_jump_px", cls.max_jump_px)),
            "max_eta_s": float(cfg.get("max_eta_s", cls.max_eta_s)),
            "measurement_noise_px": float(cfg.get("measurement_noise_px", cls.measurement_noise_px)),
            "max_uncertainty_s": float(cfg.get("max_uncertainty_s", cls.max_uncertainty_s)),
            "profile_segments": int(cfg.get("profile_segments", cls.profile_segments)),
            "profile_ttl_s": float(cfg.get("profile_ttl_ms", cls.profile_ttl_s * 1000)) / 1000,
            "profile_min_samples": int(cfg.get("profile_min_samples", cls.profile_min_samples)),
            # Partial legacy mappings retain the historical trigger clock;
            # source-first config supplies these fields explicitly.
            "timing_reference": str(cfg.get("timing_reference", "trigger_legacy")).lower(),
            "input_lead_ms": float(cfg.get("input_lead_ms", 0.0)),
            "guarded_reuse_enabled": strict_bool("guarded_reuse_enabled", False),
            "guarded_reuse_max_age_s": float(cfg.get("guarded_reuse_max_age_ms", 80.0)) / 1000,
        }
        policy = cls(**values)
        policy.validate()
        return policy

    def validate(self):
        if self.mode not in {"shadow", "active"}:
            raise ValueError("global_tap_timing.mode must be shadow or active")
        if self.timing_reference not in {"trigger_legacy", "physical_calibrated"}:
            raise ValueError("global_tap_timing.timing_reference must be trigger_legacy or physical_calibrated")
        if not (0 <= self.input_lead_ms <= 250):
            raise ValueError("global_tap_timing.input_lead_ms must be between 0 and 250ms")
        if not (1 <= self.min_tracks <= 16 and 3 <= self.min_samples <= 12 and
                3 <= self.history_size <= 32 and 1 <= self.max_tracks <= 64 and
                2 <= self.profile_segments <= 6 and 1 <= self.profile_min_samples <= 8):
            raise ValueError("global_tap_timing track/history limits are outside bounds")
        if not (0.05 <= self.max_observation_age_s <= .5 and
                1 <= self.min_velocity < self.max_velocity <= 3000 and
                .05 <= self.max_speed_dispersion <= 1 and 8 <= self.max_jump_px <= 240 and
                .1 <= self.max_eta_s <= 1.5 and .001 <= self.measurement_noise_px <= 20 and
                .01 <= self.max_uncertainty_s <= .2 and .1 <= self.profile_ttl_s <= 5):
            raise ValueError("global_tap_timing limits are outside bounds")
        if not isinstance(self.guarded_reuse_enabled, bool) or not (0 <= self.guarded_reuse_max_age_s <= .080):
            raise ValueError("guarded reuse must be disabled or bounded to 80ms")
        return self

    def to_dict(self):
        return {
            "enabled": self.enabled, "mode": self.mode, "allow_active": self.allow_active,
            "min_tracks": self.min_tracks, "min_samples": self.min_samples,
            "history_size": self.history_size, "max_tracks": self.max_tracks,
            "max_observation_age_ms": self.max_observation_age_s * 1000,
            "min_velocity": self.min_velocity, "max_velocity": self.max_velocity,
            "max_speed_dispersion": self.max_speed_dispersion, "max_jump_px": self.max_jump_px,
            "max_eta_s": self.max_eta_s, "measurement_noise_px": self.measurement_noise_px,
            "max_uncertainty_s": self.max_uncertainty_s, "profile_segments": self.profile_segments,
            "profile_ttl_ms": self.profile_ttl_s * 1000, "profile_min_samples": self.profile_min_samples,
            "timing_reference": self.timing_reference, "input_lead_ms": self.input_lead_ms,
            "guarded_reuse_enabled": self.guarded_reuse_enabled,
            "guarded_reuse_max_age_ms": self.guarded_reuse_max_age_s * 1000,
        }


class GlobalTapTimingEstimator:
    """Estimate one bounded motion model from multiple reliable tracks."""

    def __init__(self, config: dict | None = None, *, policy: GlobalTapTimingPolicy | None = None):
        self.policy = policy or GlobalTapTimingPolicy.from_mapping(config)
        self.policy.validate()
        self.enabled = self.policy.enabled
        self.mode = self.policy.mode
        self.allow_active = self.policy.allow_active
        self.min_tracks = self.policy.min_tracks
        self.min_samples = self.policy.min_samples
        self.history_size = self.policy.history_size
        self.max_tracks = self.policy.max_tracks
        self.max_observation_age_s = self.policy.max_observation_age_s
        self.min_velocity = self.policy.min_velocity
        self.max_velocity = self.policy.max_velocity
        self.max_speed_dispersion = self.policy.max_speed_dispersion
        self.max_jump_px = self.policy.max_jump_px
        self.max_eta_s = self.policy.max_eta_s
        self.measurement_noise_px = self.policy.measurement_noise_px
        self.max_uncertainty_s = self.policy.max_uncertainty_s
        self.profile_segments = self.policy.profile_segments
        self.profile_ttl_s = self.policy.profile_ttl_s
        self.profile_min_samples = self.policy.profile_min_samples
        self.timing_reference = self.policy.timing_reference
        self.input_lead_ms = self.policy.input_lead_ms
        self.guarded_reuse_enabled = self.policy.guarded_reuse_enabled
        self.guarded_reuse_max_age_s = self.policy.guarded_reuse_max_age_s
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
        self._last_good_model: GlobalTapModel | None = None
        self._last_good_capture = -math.inf
        self._last_good_target_y: float | None = None
        self._last_good_edges: tuple[float, ...] = ()
        self._last_good_timing_reference = self.timing_reference

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
        self._last_good_model = None
        self._last_good_capture = -math.inf
        self._last_good_target_y = None
        self._last_good_edges = ()
        self._last_good_timing_reference = self.timing_reference
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
            self._last_good_model = None
            self._last_good_capture = -math.inf
            self._last_good_target_y = None
            self._last_good_edges = ()
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
        if (self.model.ready and self.model.reason == "ready" and
                self.model.source == "global_profile" and
                self.model.profile_speeds and
                all(math.isfinite(value) and value > 0 for value in self.model.profile_speeds)):
            self._last_good_model = self.model
            self._last_good_capture = self._capture_timestamp
            self._last_good_target_y = float(trigger_y)
            self._last_good_edges = tuple(edges)
            self._last_good_timing_reference = self.timing_reference
        return self.model

    def _profile_eta(self, observed_y: float, trigger_y: float, model=None):
        model = model or self.model
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
                 input_lead_ms: float | None = None,
                 model_override: GlobalTapModel | None = None,
                 uncertainty_penalty_s: float = 0.0,
                 timing_source_override: str | None = None) -> GlobalTapEta:
        model = model_override or self.model
        use_physical = (self.timing_reference == "physical_calibrated" and
                        physical_hit_y is not None and math.isfinite(float(physical_hit_y)))
        target_y = float(physical_hit_y) if use_physical else float(trigger_y)
        lead_ms = self.input_lead_ms if input_lead_ms is None else float(input_lead_ms)
        timing_source = (timing_source_override or
                         ("global_physical_calibrated" if use_physical
                          else "global_trigger_legacy"))
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
        profile = self._profile_eta(observed_y, target_y, model=model)
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
        if uncertainty_penalty_s:
            uncertainty = math.hypot(uncertainty, max(0.0, float(uncertainty_penalty_s)))
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

    def guarded_reuse_estimate(self, track, *, trigger_y: float, now: float,
                               physical_hit_y: float | None = None,
                               geometry_target_y: float | None = None):
        """Try the bounded last-good profile only for a transient variance gate.

        Returns ``(eta, metadata)``.  No state is mutated and no scheduler is
        touched; the caller still routes a successful estimate through the
        existing Planner → IntentManager → Scheduler path.
        """
        meta = {"attempted": False, "passed_rescue_gate": False,
                "rescue_rejected_reason": "GUARDED_REUSE_DISABLED",
                "cache_available": self._last_good_model is not None,
                "cache_age_ms": "", "cache_source": "",
                "same_epoch": False, "same_geometry": False,
                "real_observation_age_ms": ""}
        if not self.guarded_reuse_enabled:
            return None, meta
        meta["attempted"] = True
        if self.model.reason != "speed_variation_too_high":
            meta["rescue_rejected_reason"] = "ORIGINAL_MODEL_NOT_SPEED_VARIATION"
            return None, meta
        cached = self._last_good_model
        if cached is None:
            meta["rescue_rejected_reason"] = "NO_CACHE"
            return None, meta
        age = self._capture_timestamp - self._last_good_capture
        meta["cache_age_ms"] = age * 1000 if math.isfinite(age) else ""
        meta["cache_source"] = cached.source
        if not math.isfinite(age) or age < 0:
            meta["rescue_rejected_reason"] = "CACHE_NEGATIVE_AGE"
            return None, meta
        if age > self.guarded_reuse_max_age_s:
            meta["rescue_rejected_reason"] = "CACHE_OLDER_THAN_80MS"
            return None, meta
        target = (float(geometry_target_y) if geometry_target_y is not None else float(trigger_y))
        same_epoch = cached.speed_epoch == self.speed_epoch == self.model.speed_epoch
        same_geometry = (tuple(cached.profile_edges) == tuple(self._profile_edges) == tuple(self._last_good_edges)
                         and self._last_good_target_y is not None
                         and abs(float(self._last_good_target_y) - target) <= 1e-6
                         and self._last_good_timing_reference == self.timing_reference)
        meta["same_epoch"] = same_epoch; meta["same_geometry"] = same_geometry
        if not same_epoch:
            meta["rescue_rejected_reason"] = "EPOCH_MISMATCH"
            return None, meta
        if not same_geometry:
            meta["rescue_rejected_reason"] = "GEOMETRY_MISMATCH"
            return None, meta
        history = self._real_history(track)
        if (getattr(track, "status", "") != "confirmed" or
                getattr(track, "confirmed_note_type", None) != "tap" or
                getattr(track, "missed", 0) != 0 or not history):
            meta["rescue_rejected_reason"] = "TRACK_NOT_CURRENT"
            return None, meta
        observation_age = self._capture_timestamp - history[-1][0]
        meta["real_observation_age_ms"] = observation_age * 1000 if math.isfinite(observation_age) else ""
        if not math.isfinite(observation_age) or observation_age < 0 or observation_age > self.max_observation_age_s:
            meta["rescue_rejected_reason"] = "STALE_OBSERVATION"
            return None, meta
        penalty = .25 * age
        base_eta = self.estimate(track, trigger_y=trigger_y, now=now,
                                 physical_hit_y=physical_hit_y, model_override=cached,
                                 uncertainty_penalty_s=0.0,
                                 timing_source_override="global_profile_guarded_reuse")
        meta["original_uncertainty_ms"] = (base_eta.uncertainty_s * 1000
                                            if base_eta.uncertainty_s is not None else "")
        eta = self.estimate(track, trigger_y=trigger_y, now=now,
                            physical_hit_y=physical_hit_y, model_override=cached,
                            uncertainty_penalty_s=penalty,
                            timing_source_override="global_profile_guarded_reuse")
        if eta.status != "AVAILABLE":
            meta["rescue_rejected_reason"] = {
                "eta_uncertainty_too_high": "UNCERTAINTY_TOO_HIGH",
                "press_time_not_future": "PAST_DEADLINE",
                "hit_time_not_future": "PAST_DEADLINE",
                "eta_outside_horizon": "ETA_OUTSIDE_HORIZON",
            }.get(eta.reason, eta.reason.upper() if eta.reason else "RESCUE_ESTIMATE_REJECTED")
            meta["effective_uncertainty_ms"] = eta.uncertainty_s * 1000 if eta.uncertainty_s is not None else ""
            return None, meta
        meta["passed_rescue_gate"] = True
        meta["rescue_rejected_reason"] = ""
        meta["effective_uncertainty_ms"] = eta.uncertainty_s * 1000 if eta.uncertainty_s is not None else ""
        return eta, meta
