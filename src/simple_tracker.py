"""Small motion-only tracker for the Simple Assist Tap path.

This tracker deliberately has no identity handoff, unknown-observation
retention, or scheduler lifecycle behavior. It associates current detections
to short, timestamped trajectories and exposes that evidence to a planner.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import math
import time

from .assignment import assign
from .detector import Candidate
from .particle_predictor import ParticlePredictor
from .predictor import Prediction


def is_simple_tap(candidate: Candidate) -> bool:
    return (candidate.note_type == "tap" and
            candidate.appearance in ("cyan_bar", "yellow_bar", "pink_candidate", "neutral_candidate") and
            not candidate.suspected_overlap and candidate.path_bbox is None and
            candidate.hold_path_px <= 0)


@dataclass
class SimpleTrack:
    track_id: int
    candidate: Candidate
    history: list[tuple[float, float, float]]
    first_time: float
    last_time: float
    prediction: Prediction = field(default_factory=Prediction)
    hit_history: list[float] = field(default_factory=list)
    key_history: list[tuple[str, ...]] = field(default_factory=list)
    stable_keys: list[str] = field(default_factory=list)
    observations: int = 1
    missed: int = 0
    status: str = "tentative"
    reason: str = "insufficient_observations"
    confirmed_note_type: str | None = None
    selected_key: str | None = None
    appearance_anchor: str = ""
    appearance_history: list[str] = field(default_factory=list)
    association_reject_reason: str = ""
    track_parent: int | None = None
    continuity: str = "new"
    particle_filter: ParticlePredictor | None = None
    last_association: dict = field(default_factory=dict)
    particle_rejection_streak: int = 0
    particle_reinitializations: int = 0

    @property
    def bbox(self):
        return self.candidate.bbox

    @property
    def kind(self):
        return self.confirmed_note_type or self.candidate.note_type

    @property
    def identity_state(self):
        return "CONFIRMED_TAP" if self.confirmed_note_type == "tap" else "UNCONFIRMED"

    @property
    def physical_note_uid(self):
        return f"simple:{self.track_id}"

    @property
    def source_track_ids(self):
        return [self.track_id]

    @property
    def reidentified_from_id(self):
        return None

    @property
    def identity_transitions(self):
        return []

    @property
    def current_observation_type(self):
        return self.candidate.note_type

    @property
    def was_confirmed(self):
        return self.confirmed_note_type == "tap"

    def eta(self, hit_y: float | None = None, lookahead: float = 1.5):
        return self.prediction.eta if self.status == "confirmed" else None


class SimpleTracker:
    """One-to-one motion association with a bounded missed-frame coast."""

    def __init__(self, cfg: dict | None = None, particle_cfg: dict | None = None,
                 hit_y: float = 310.5):
        self.cfg = dict(cfg or {})
        self.particle_cfg = dict(particle_cfg or {})
        self.hit_y = float(hit_y)
        self.tracks: list[SimpleTrack] = []
        self.finished: list[SimpleTrack] = []
        self.next_id = 1
        self.elapsed = 0.0
        self.stage_times = {"matching_s": 0.0, "unknown_association_s": 0.0}
        self.last_unknown_association_audit: list[dict] = []
        self.max_gap_s = float(self.cfg.get("max_gap_s", .16))
        self.max_missed = int(self.cfg.get("max_missed_frames", 8))
        self.max_u_step = float(self.cfg.get("max_u_step", .09))
        self.min_observations = int(self.cfg.get("confirm_observations", 5))
        self.max_eta_s = float(self.cfg.get("max_eta_s", 1.5))
        self.seed = int(self.particle_cfg.get("deterministic_seed", 20261030))
        # Pink visual effects can drift a few pixels at the judgment row while
        # remaining stationary.  Require the same small physical displacement
        # already used by the particle predictor before confirming pink; this
        # is pink-specific and does not relax any global confirmation gate.
        self.pink_min_displacement_px = float(
            self.cfg.get("pink_min_displacement_px",
                        self.particle_cfg.get("min_displacement_px", 5.0)))

    @staticmethod
    def _center(candidate: Candidate):
        x, y, w, h = candidate.bbox
        return y + h / 2, (candidate.u_min + candidate.u_max) / 2

    @staticmethod
    def _same_appearance_family(a: Candidate, b: Candidate) -> bool:
        if a.appearance == "pink_candidate" or b.appearance == "pink_candidate":
            return a.appearance == b.appearance == "pink_candidate"
        allowed = {"cyan_bar", "yellow_bar", "pink_candidate", "neutral_candidate"}
        return a.appearance in allowed and b.appearance in allowed

    def _pair_cost(self, track: SimpleTrack, candidate: Candidate, timestamp: float,
                   audit: dict | None = None):
        def reject(reason):
            if audit is not None:
                audit["accepted"] = False
                audit["reject_reason"] = reason
                audit["total_cost"] = "INF"
            return None
        dt = timestamp - track.last_time
        if audit is not None:
            old_y, old_u = self._center(track.candidate)
            audit.update({"track_id": track.track_id,
                          "candidate_id": getattr(candidate, "diagnostic_id", ""),
                          "track_status_before": track.status,
                          "track_last_time": track.last_time,
                          "last_real_observation_ts": track.last_time,
                          "observation_age_ms": max(0., dt * 1000),
                          "delta_t_ms": dt * 1000,
                          "predicted_y": None,
                          "predicted_u": None,
                          "observed_y": self._center(candidate)[0],
                          "observed_u": self._center(candidate)[1],
                          "dy_px": None, "du": None,
                          "motion_continuity": "unknown",
                          "accepted": False, "reject_reason": "",
                          "total_cost": "INF"})
        if not 0 < dt <= self.max_gap_s:
            return reject("timestamp_gap_or_nonpositive")
        if not self._same_appearance_family(track.candidate, candidate):
            track.association_reject_reason = "appearance_family_mismatch"
            return reject("appearance_family_mismatch")
        if not set(track.candidate.candidate_keys).intersection(candidate.candidate_keys):
            return reject("candidate_key_no_intersection")
        old_y, old_u = self._center(track.candidate)
        new_y, new_u = self._center(candidate)
        du = abs(new_u - old_u)
        if audit is not None:
            audit["du"] = du
        if du > self.max_u_step:
            return reject("lane_step_exceeded")
        old_width = max(track.candidate.u_max - track.candidate.u_min, .01)
        new_width = max(candidate.u_max - candidate.u_min, .01)
        ratio = new_width / old_width
        if not .45 <= ratio <= 2.2:
            return reject("span_width_ratio")
        velocity = track.prediction.velocity
        predicted_y = old_y + max(0., velocity or 0.) * dt
        tolerance = max(9., min(24., 8. + max(0., velocity or 0.) * dt * .65))
        residual = abs(new_y - predicted_y)
        if audit is not None:
            audit.update({"predicted_y": predicted_y, "predicted_u": old_u,
                          "dy_px": new_y - predicted_y,
                          "motion_continuity": "forward" if new_y >= old_y else "backward_or_jitter",
                          "residual_px": residual, "tolerance_px": tolerance,
                          "span_width_ratio": ratio})
        if new_y < old_y - max(3.5, track.candidate.bbox[3] * .35):
            return reject("backward_motion")
        if residual > tolerance:
            return reject("motion_residual")
        span_overlap = max(0., min(candidate.u_max, track.candidate.u_max) -
                           max(candidate.u_min, track.candidate.u_min))
        span_union = max(candidate.u_max, track.candidate.u_max) - min(candidate.u_min, track.candidate.u_min)
        transition_penalty = .12 if track.candidate.appearance != candidate.appearance else 0.0
        total_cost = (residual / tolerance + du / max(self.max_u_step, .001) +
                      .25 * abs(math.log(ratio)) + .1 * (1 - span_overlap / max(span_union, .001)) +
                      transition_penalty)
        if audit is not None:
            audit.update({"accepted": True, "reject_reason": "", "total_cost": total_cost,
                          "span_overlap": span_overlap / max(span_union, .001)})
        return total_cost

    @staticmethod
    def _deduplicate_visible(candidates: list[Candidate]):
        """Collapse only near-identical same-frame contours, never stacked notes."""
        kept = []
        for candidate in sorted(candidates, key=lambda c: (c.bbox[1], c.u_min, -c.score)):
            y = candidate.bbox[1] + candidate.bbox[3] / 2
            duplicate = False
            for old in kept:
                old_y = old.bbox[1] + old.bbox[3] / 2
                overlap = max(0., min(candidate.u_max, old.u_max) - max(candidate.u_min, old.u_min))
                min_width = min(candidate.u_max - candidate.u_min, old.u_max - old.u_min)
                if (SimpleTracker._same_appearance_family(candidate, old) and
                        candidate.candidate_keys == old.candidate_keys and
                        abs(y - old_y) <= max(2., min(candidate.bbox[3], old.bbox[3]) * .5) and
                        min_width > 0 and overlap / min_width >= .92):
                    duplicate = True
                    break
            if not duplicate:
                kept.append(candidate)
        return kept

    def _new_track(self, candidate: Candidate, timestamp: float):
        y, u = self._center(candidate)
        track = SimpleTrack(self.next_id, candidate, [(timestamp, y, u)], timestamp, timestamp,
                            appearance_anchor=candidate.appearance,
                            appearance_history=[candidate.appearance])
        self.next_id += 1
        track.key_history.append(tuple(candidate.candidate_keys))
        track.stable_keys = list(candidate.candidate_keys)
        track.particle_filter = ParticlePredictor(self.particle_cfg, seed=self.seed,
            track_id=track.track_id, physical_hit_y=self.hit_y)
        return track

    def _observe(self, track: SimpleTrack, candidate: Candidate, timestamp: float):
        y, u = self._center(candidate)
        track.candidate = candidate
        track.last_time = timestamp
        track.history.append((timestamp, y, u))
        track.history = track.history[-24:]
        track.observations += 1
        track.appearance_history.append(candidate.appearance)
        track.appearance_history = track.appearance_history[-12:]
        track.continuity = "continued" if track.observations > 1 else "new"
        track.association_reject_reason = ""
        track.missed = 0
        track.status = "tentative"
        track.reason = ""
        track.key_history.append(tuple(candidate.candidate_keys))
        track.key_history = track.key_history[-5:]
        counts = Counter(key for keys in track.key_history for key in keys)
        denominator = len(track.key_history)
        order = list("SDFJKL")
        track.stable_keys = sorted((key for key, n in counts.items() if n / denominator >= .6),
                                   key=lambda k: order.index(k) if k in order else len(order))
        prediction_started = time.perf_counter()
        track.prediction = track.particle_filter.update(track.history, self.hit_y)
        if track.prediction.measurement_status == "REJECTED_MEASUREMENT":
            track.particle_rejection_streak += 1
        else:
            track.particle_rejection_streak = 0
        if track.particle_rejection_streak >= 3:
            # The Simple Tracker has already accepted three consecutive
            # observations using position, lane span, and motion continuity.
            # Rebuild only the particle posterior from its latest seven
            # accepted observations when its measurement gate keeps rejecting
            # those same observations. This recovers stale PF position state
            # without changing planner ETA or uncertainty limits.
            replacement = ParticlePredictor(self.particle_cfg, seed=self.seed,
                track_id=track.track_id, physical_hit_y=self.hit_y)
            replacement_prediction = replacement.update(track.history[-7:], self.hit_y)
            track.particle_rejection_streak = 0
            if replacement_prediction.measurement_status == "INITIALIZED":
                track.particle_filter = replacement
                track.prediction = replacement_prediction
                track.particle_reinitializations += 1
        self.elapsed += time.perf_counter() - prediction_started
        if y > self.cfg.get("completion_y", 325.5):
            track.status, track.reason = "completed", "past_physical_completion_line"
            return
        velocity = track.prediction.velocity
        displacement_ok = True
        if candidate.appearance == "pink_candidate" and track.history:
            ys = [point[1] for point in track.history]
            displacement_ok = max(ys) - min(ys) >= self.pink_min_displacement_px
            if not displacement_ok and track.observations >= self.min_observations:
                track.reason = "pink_displacement_insufficient"
        if (track.observations >= self.min_observations and displacement_ok and
                velocity is not None and math.isfinite(velocity) and
                velocity >= track.particle_filter.min_velocity):
            track.status = "confirmed"
            track.confirmed_note_type = "tap"
        if track.prediction.hit_time is not None:
            track.hit_history.append(track.prediction.hit_time)
            track.hit_history = track.hit_history[-5:]

    def update(self, candidates: list[Candidate], timestamp: float, playing: bool = True,
               trace: dict | None = None, frame_index: int | None = None,
               capture_gap_ms: float | None = None):
        started = time.perf_counter()
        self.finished = []
        self.last_unknown_association_audit = []
        if not playing:
            for track in self.tracks:
                track.status, track.reason = "completed", "gameplay_gate_closed"
                self.finished.append(track)
            self.tracks = []
            self.stage_times = {"matching_s": 0., "unknown_association_s": 0.}
            return []
        candidates = self._deduplicate_visible([c for c in candidates if is_simple_tap(c)])
        if trace is not None:
            trace.setdefault("pair_rows", [])
            trace.setdefault("track_rows", [])
            trace.setdefault("assignment_rows", [])
            trace.setdefault("dropped_rows", 0)
        trace_limit = int(trace.get("max_rows", 10000)) if trace is not None else 0
        def trace_append(bucket, row):
            if trace is None:
                return
            target = trace.setdefault(bucket, [])
            if sum(len(trace.get(k, [])) for k in
                   ("pair_rows", "track_rows", "assignment_rows", "attempt_rows")) >= trace_limit:
                trace["dropped_rows"] = trace.get("dropped_rows", 0) + 1
                return
            target.append(row)
        previous = list(self.tracks)
        raw_candidate_count = len(candidates)
        if trace is not None and raw_candidate_count == 0:
            if previous:
                for track in previous:
                    trace_append("attempt_rows", {
                        "frame": frame_index, "timestamp": timestamp,
                        "track_id": track.track_id,
                        "track_uid": track.physical_note_uid,
                        "skip_reason": "zero_candidate",
                        "matched_this_frame": False,
                    })
            else:
                trace_append("attempt_rows", {
                    "frame": frame_index, "timestamp": timestamp,
                    "skip_reason": "zero_candidate_no_active_track",
                })
        if trace is not None and raw_candidate_count > len(candidates):
            trace_append("attempt_rows", {
                "frame": frame_index, "timestamp": timestamp,
                "skip_reason": "dedup_suppressed",
                "suppressed_count": raw_candidate_count - len(candidates),
            })
        costs = []
        unmatched_cost = 5.
        for track in previous:
            row = []
            for candidate in candidates:
                audit = {}
                cost = self._pair_cost(track, candidate, timestamp, audit=audit)
                audit.update({"frame": frame_index, "timestamp": timestamp,
                              "candidate_id": getattr(candidate, "diagnostic_id", ""),
                              "candidate_bbox": candidate.bbox,
                              "candidate_keys": "|".join(candidate.candidate_keys),
                              "candidate_appearance": candidate.appearance})
                trace_append("pair_rows", audit)
                row.append(cost if cost is not None else 1e6)
            row.extend([unmatched_cost] * len(previous))
            costs.append(row)
        pairs = assign(costs) if costs else []
        if trace is not None and candidates:
            for i, track in enumerate(previous):
                compatible = any(costs[i][j] < 1e6 for j in range(len(candidates)))
                if not compatible:
                    trace_append("attempt_rows", {
                        "frame": frame_index, "timestamp": timestamp,
                        "track_id": track.track_id,
                        "track_uid": track.physical_note_uid,
                        "skip_reason": "no_compatible_candidate",
                        "matched_this_frame": False,
                    })
            if not previous:
                trace_append("attempt_rows", {
                    "frame": frame_index, "timestamp": timestamp,
                    "skip_reason": "no_active_track",
                })
        selected_by_candidate = {j: i for i, j in pairs if j < len(candidates) and costs[i][j] < unmatched_cost}
        for row in (trace.get("pair_rows", []) if trace is not None else []):
            if row.get("frame") != frame_index or row.get("timestamp") != timestamp:
                continue
            candidate_id = row.get("candidate_id")
            candidate_index = next((j for j,c in enumerate(candidates)
                                    if getattr(c, "diagnostic_id", "") == candidate_id), None)
            assigned_track = selected_by_candidate.get(candidate_index) if candidate_index is not None else None
            row["assigned"] = assigned_track is not None and row.get("track_id") == previous[assigned_track].track_id
            competitors = [previous[i].track_id for i in range(len(previous))
                           if candidate_index is not None and costs[i][candidate_index] < unmatched_cost]
            row["competition_track_ids"] = "|".join(str(t) for t in competitors)
        matched_tracks, matched_candidates = set(), set()
        for i, j in pairs:
            if j < len(candidates) and costs[i][j] < unmatched_cost:
                self._observe(previous[i], candidates[j], timestamp)
                matched_tracks.add(i)
                matched_candidates.add(j)
                trace_append("assignment_rows", {"frame": frame_index, "timestamp": timestamp,
                    "track_id": previous[i].track_id, "candidate_id": getattr(candidates[j], "diagnostic_id", ""),
                    "assigned": True, "unmatched_cost": unmatched_cost, "competition_track_ids": "|".join(
                        str(previous[k].track_id) for k in range(len(previous)) if costs[k][j] < unmatched_cost)})
        active = []
        for i, track in enumerate(previous):
            if i not in matched_tracks:
                track.missed += 1
                track.status = "lost"
                track.reason = "no_current_observation"
                track.association_reject_reason = "no_current_observation"
                track.continuity = "coasting"
            expired_by_missed = track.missed > self.max_missed
            expired_by_gap = timestamp - track.last_time > self.max_gap_s
            if (expired_by_missed or expired_by_gap or track.status == "completed"):
                if track.reason != "past_physical_completion_line":
                    track.reason = ("track_expired_max_missed" if expired_by_missed else
                                    "track_expired_max_gap" if expired_by_gap else
                                    "track_expired")
                self.finished.append(track)
            else:
                active.append(track)
        for j, candidate in enumerate(candidates):
            if j not in matched_candidates:
                active.append(self._new_track(candidate, timestamp))
        self.tracks = active
        if trace is not None:
            for i, track in enumerate(previous):
                matched = i in matched_tracks
                trace_append("track_rows", {"frame": frame_index, "timestamp": timestamp,
                    "track_id": track.track_id, "track_uid": track.physical_note_uid,
                    "candidate_id": getattr(track.candidate, "diagnostic_id", ""),
                    "matched_this_frame": matched, "real_observation_this_frame": matched,
                    "coasting_this_frame": not matched and track in active,
                    "last_real_observation_timestamp": track.last_time,
                    "time_since_last_real_observation_ms": max(0., (timestamp-track.last_time)*1000),
                    "capture_gap_ms": capture_gap_ms if capture_gap_ms is not None else "",
                    "missed_frames": track.missed, "track_status": track.status,
                    "confirmed_note_type": track.confirmed_note_type or "",
                    "observation_count": track.observations,
                    "stable_keys": "|".join(track.stable_keys),
                    "appearance": track.candidate.appearance, "bbox": track.candidate.bbox,
                    "prediction_reason": track.prediction.reason,
                    "termination_reason": track.reason if track in self.finished else "",
                    "state_transition": "matched" if matched else "coasting" if track in active else "terminated"})
            for track in active:
                if track not in previous:
                    trace_append("track_rows", {"frame": frame_index, "timestamp": timestamp,
                        "track_id": track.track_id, "track_uid": track.physical_note_uid,
                        "candidate_id": getattr(track.candidate, "diagnostic_id", ""),
                        "matched_this_frame": False, "real_observation_this_frame": True,
                        "coasting_this_frame": False, "last_real_observation_timestamp": track.last_time,
                        "time_since_last_real_observation_ms": 0.,
                        "capture_gap_ms": capture_gap_ms if capture_gap_ms is not None else "",
                        "missed_frames": track.missed, "track_status": track.status,
                        "confirmed_note_type": track.confirmed_note_type or "",
                        "observation_count": track.observations,
                        "stable_keys": "|".join(track.stable_keys),
                        "appearance": track.candidate.appearance, "bbox": track.candidate.bbox,
                        "prediction_reason": track.prediction.reason,
                        "termination_reason": "", "state_transition": "new"})
        self.stage_times = {"matching_s": time.perf_counter() - started,
                            "unknown_association_s": 0.}
        return list(active)
