"""Composition root for the deliberately small ordinary-Tap control path."""
from __future__ import annotations

import json

from .simple_tracker import SimpleTracker
from .tap_intent import TapIntentManager
from .tap_planner import TapPlanner
from .timing_estimator import LinearTimingEstimator


class SimpleAssistCore:
    def __init__(self, *, session_id: str, tracker_cfg: dict,
                 particle_cfg: dict, hit_y: float,
                 event_cfg: dict, min_y: float, known_keys: set[str],
                 on_transition=None, timing_cfg: dict | None = None):
        self.session_id = session_id
        self.known_keys = set(known_keys)
        self.tracker = SimpleTracker(tracker_cfg, particle_cfg, hit_y=hit_y)
        timing_cfg = dict(timing_cfg or {})
        simplified_cfg = dict(timing_cfg.get("simplified_tap_planner", {}) or {})
        self._simplified_cfg = simplified_cfg
        self.planner_mode = str(simplified_cfg.get("mode", "legacy")).lower()
        if self.planner_mode not in {"legacy", "shadow", "active"}:
            self.planner_mode = "legacy"
        self.simplified_enabled = bool(simplified_cfg.get("enabled", False))
        self.planner = TapPlanner(event_cfg, min_y=min_y,
            max_uncertainty_s=float(particle_cfg.get("max_uncertainty_s", .04)),
            simplified_mode=self.planner_mode == "active" and self.simplified_enabled)
        linear_cfg = timing_cfg.get("linear_timing", {})
        self.linear_timing = LinearTimingEstimator(
            window=linear_cfg.get("window", 5),
            min_velocity=linear_cfg.get("min_velocity", 20),
            max_observation_age_s=linear_cfg.get("max_observation_age_ms", 200) / 1000
        ) if linear_cfg.get("enabled", True) else None
        self.transitions = []
        def record(row):
            self.transitions.append(dict(row))
            if on_transition:
                on_transition(row)
        self.intents = TapIntentManager(record,
            amend_enabled=timing_cfg.get("enabled", timing_cfg.get("tap_deadline_amend", False)),
            freeze_window_ms=timing_cfg.get("freeze_window_ms", 30),
            max_amend_step_ms=timing_cfg.get("max_amend_step_ms", 40),
            max_total_amend_ms=timing_cfg.get("max_total_amend_ms", 80))
        self.last_reasons: dict[int, str] = {}
        self.last_traces = {}
        self.decision_rows = []
        self.shadow_rows = []
        self.eta_rows = []
        self.shadow_decisions = {}
        self._last_decision_fingerprints = {}

    def note_uid(self, track_id: int):
        return f"{self.session_id}:simple:{track_id}"

    def update(self, candidates, captured_at: float, processed_at: float,
               scheduler, *, playing: bool):
        tracks = self.tracker.update(candidates, captured_at, playing=playing)
        return tracks, self.plan_tracks(tracks, captured_at, processed_at, scheduler,
                                        enabled=playing)

    def plan_tracks(self, tracks, captured_at: float, processed_at: float,
                    scheduler, *, enabled: bool):
        note_uids = {}
        for track in tracks if enabled else ():
            uid = self.note_uid(track.track_id)
            note_uids[track.track_id] = uid
            self.intents.note_seen(uid, captured_at)
            if track.confirmed_note_type == "tap":
                self.intents.note_confirmed(uid, captured_at)
        fixed = {uid: intent.key for uid, intent in self.intents.intents.items()
                 if intent.state == "PENDING"}
        proposals, reasons = self.planner.plan(tracks if enabled else [], processed_at,
            self.known_keys, scheduler, note_uids=note_uids, fixed_keys=fixed)
        traces = self.planner.last_traces
        # The simplified planner is a read-only comparator by default.  An
        # active switch exists for controlled rollback experiments, but cannot
        # be enabled accidentally by merely setting mode=active.
        shadow = (self.planner.simplified_plan(tracks if enabled else [], processed_at,
                    self.known_keys, scheduler, note_uids=note_uids, fixed_keys=fixed)
                  if self.planner_mode in {"shadow", "active"} else {})
        self.shadow_decisions = shadow
        active_switch = (enabled and self.planner_mode == "active" and
                         self.simplified_enabled and
                         bool(self._active_config().get("allow_active", False)))
        if active_switch:
            proposals = self.planner.simplified_proposals(tracks if enabled else [], shadow)
            reasons = {track_id: decision.reason for track_id, decision in shadow.items()
                       if decision.status != "schedule"}
        accepted, rejected = self.intents.schedule(proposals, scheduler, processed_at)
        self.last_reasons = {**reasons, **{
            track.track_id: rejected[uid]
            for track in tracks
            for uid in (note_uids.get(track.track_id, ""),)
            if uid in rejected
        }}
        self.last_traces = traces
        linear_estimates = {}
        for track in tracks:
            trace = traces.get(track.track_id)
            if trace is None or self.linear_timing is None:
                continue
            linear = self.linear_timing.estimate(track.history, self.tracker.hit_y, captured_at,
                                                  now=processed_at)
            linear_estimates[track.track_id] = linear
            trace.linear_eta_s = linear.eta
            trace.linear_hit_at = linear.hit_at
            trace.linear_quality = linear.quality
        self._append_diagnostics(tracks, captured_at, processed_at, proposals,
                                 reasons, rejected, traces, shadow, scheduler,
                                 linear_estimates)
        for track in tracks:
            uid = self.note_uid(track.track_id)
            trace = traces.get(track.track_id)
            intent = self.intents.intents.get(uid)
            reason = self.last_reasons.get(track.track_id, "")
            if intent is not None:
                lifecycle = "SCHEDULED" if intent.state == "PENDING" else intent.state
                key = intent.key
                reason = next((t["reason"] for t in reversed(intent.transitions) if t.get("reason")), "")
            elif not enabled:
                lifecycle, key = "CANCELED", ""
                reason = "safe_context_disabled"
            elif track.status != "confirmed":
                lifecycle, key = "TRACKING", ""
            elif track.confirmed_note_type == "tap" and not reason:
                lifecycle, key = "ELIGIBLE", proposals.get(track.track_id).key if track.track_id in proposals else ""
            else:
                lifecycle, key = "TRACK_CONFIRMED", ""
            gates = trace.gates if trace else {}
            conflicts = trace.key_conflicts if trace else {}
            fingerprint = (lifecycle, reason, key, tuple(sorted(gates.items())),
                           tuple(sorted(conflicts.items())))
            if fingerprint == self._last_decision_fingerprints.get(track.track_id):
                continue
            self._last_decision_fingerprints[track.track_id] = fingerprint
            self.decision_rows.append({
                "timestamp": processed_at, "note_uid": uid, "track_id": track.track_id,
                "lifecycle_state": lifecycle, "reason": reason, "key": key,
                "eta_s": trace.eta_s if trace and trace.eta_s is not None else "",
                "hit_at": trace.hit_at if trace and trace.hit_at is not None else "",
                "uncertainty_s": trace.uncertainty_s if trace and trace.uncertainty_s is not None else "",
                "motion_reliable": trace.motion_reliable if trace else "",
                "timing_reliable": trace.timing_reliable if trace else "",
                "timing_quality": trace.timing_quality if trace and trace.timing_quality is not None else "",
                "linear_eta_s": trace.linear_eta_s if trace and trace.linear_eta_s is not None else "",
                "linear_hit_at": trace.linear_hit_at if trace and trace.linear_hit_at is not None else "",
                "linear_quality": trace.linear_quality if trace and trace.linear_quality is not None else "",
                "first_possible_schedule_at": (trace.first_possible_schedule_at
                    if trace and trace.first_possible_schedule_at is not None else ""),
                "last_safe_schedule_at": (trace.last_safe_schedule_at
                    if trace and trace.last_safe_schedule_at is not None else ""),
                "gates_json": json.dumps(gates, sort_keys=True) if trace else "{}",
                "key_conflicts_json": json.dumps(conflicts, sort_keys=True) if trace else "{}",
            })
        return proposals, accepted

    def _active_config(self):
        return self._simplified_cfg

    def _append_diagnostics(self, tracks, captured_at, processed_at, proposals,
                            reasons, rejected, traces, shadow, scheduler,
                            linear_estimates):
        """Append one ETA/shadow row per current track, every frame.

        These rows intentionally do not use the lifecycle fingerprint.  A
        note whose tracker identity is unchanged still gets fresh PF/linear
        observations and planner outcomes for offline pairing.
        """
        for track in tracks:
            uid = self.note_uid(track.track_id)
            trace = traces.get(track.track_id)
            prediction = track.prediction
            linear_reason = "prediction_unavailable"
            linear = linear_estimates.get(track.track_id)
            if linear is not None:
                linear_reason = linear.reason
            last_obs = track.history[-1][0] if track.history else ""
            pf_status = "available" if prediction.hit_time is not None and prediction.eta is not None else "prediction_unavailable"
            if prediction.eta is not None and prediction.eta <= 0:
                pf_status = "prediction_unavailable"
            planner_reason = reasons.get(track.track_id, "")
            if track.track_id in proposals:
                planner_result = "eligible"
            elif planner_reason:
                planner_result = "rejected" if planner_reason in {
                    "particle_posterior_too_wide", "particle_crossing_mass_too_low",
                    "no_stable_verified_covered_key", "tap_key_conflict",
                    "hit_time_not_future", "invalid_eta"} else "deferred"
            else:
                planner_result = "unavailable"
            intent = self.intents.intents.get(uid)
            scheduler_result = "pending" if intent and intent.state == "PENDING" else (
                "rejected" if uid in rejected else "none")
            scheduler_reason = rejected.get(uid, "")
            self.eta_rows.append({
                "capture_timestamp": captured_at, "processing_timestamp": processed_at,
                "note_uid": uid, "track_id": track.track_id,
                "last_observation_timestamp": last_obs,
                "pf_eta_s": prediction.eta if prediction.eta is not None else "",
                "pf_hit_at": prediction.hit_time if prediction.hit_time is not None else "",
                "pf_uncertainty_s": prediction.uncertainty if prediction.uncertainty is not None else "",
                "pf_eta_p10": prediction.eta_p10 if prediction.eta_p10 is not None else "",
                "pf_eta_p50": prediction.eta_p50 if prediction.eta_p50 is not None else "",
                "pf_eta_p90": prediction.eta_p90 if prediction.eta_p90 is not None else "",
                "pf_crossing_mass": prediction.valid_crossing_mass if prediction.valid_crossing_mass is not None else "",
                "linear_eta_s": linear.eta if linear else "",
                "linear_hit_at": linear.hit_at if linear else "",
                "linear_velocity_px_s": linear.velocity if linear else "",
                "linear_quality": linear.quality if linear else "",
                "prediction_status": pf_status,
                "linear_reason": linear_reason,
                "stale_observation": linear_reason == "stale_observation",
                "legacy_planner_result": planner_result,
                "legacy_planner_reason": planner_reason,
                "shadow_planner_result": shadow.get(track.track_id).status if track.track_id in shadow else "disabled",
                "shadow_planner_reason": shadow.get(track.track_id).reason if track.track_id in shadow else "",
                "scheduler_result": scheduler_result, "scheduler_reason": scheduler_reason,
                "appearance": track.candidate.appearance,
            })
            decision = shadow.get(track.track_id)
            self.shadow_rows.append({
                "capture_timestamp": captured_at, "processing_timestamp": processed_at,
                "note_uid": uid, "track_id": track.track_id,
                "mode": self.planner_mode,
                "status": decision.status if decision else "disabled",
                "reason": decision.reason if decision else "",
                "key": decision.key if decision and decision.key else "",
                "hit_at": decision.hit_at if decision and decision.hit_at is not None else "",
                "timing_quality": decision.timing_quality if decision and decision.timing_quality is not None else "",
                "legacy_result": planner_result, "legacy_reason": planner_reason,
                "legacy_key": proposals[track.track_id].key if track.track_id in proposals else "",
                "legacy_hit_at": proposals[track.track_id].hit_at if track.track_id in proposals else "",
                "input_sent": False,
            })

    def drain_transitions(self):
        rows, self.transitions = self.transitions, []
        return rows

    def drain_decisions(self):
        rows, self.decision_rows = self.decision_rows, []
        return rows

    def drain_shadow_rows(self):
        rows, self.shadow_rows = self.shadow_rows, []
        return rows

    def drain_eta_rows(self):
        rows, self.eta_rows = self.eta_rows, []
        return rows

    def record_scheduler_action(self, action: dict):
        self.intents.record_action(action)
