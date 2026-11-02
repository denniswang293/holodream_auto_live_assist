"""Composition root for the ordinary-Tap Global ETA control path."""
from __future__ import annotations

import json

from .simple_tracker import SimpleTracker
from .tap_intent import TapIntentManager
from .tap_planner import TapPlanner
from .timing_estimator import LinearTimingEstimator
from .global_tap_timing import GlobalTapTimingEstimator


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
        self.global_timing = GlobalTapTimingEstimator(
            timing_cfg.get("global_tap_timing", {}) or {})
        amend_cfg = dict(timing_cfg.get("tap_deadline_amend", {}) or {})
        # LiveEngine also supplies flattened values for compatibility, while
        # direct callers/tests commonly provide the nested config only.
        amend_enabled = amend_cfg.get("enabled", timing_cfg.get("enabled", False))
        freeze_window_ms = amend_cfg.get("freeze_window_ms", timing_cfg.get("freeze_window_ms", 30))
        max_amend_step_ms = amend_cfg.get("max_amend_step_ms", timing_cfg.get("max_amend_step_ms", 40))
        max_total_amend_ms = amend_cfg.get("max_total_amend_ms", timing_cfg.get("max_total_amend_ms", 80))
        self.transitions = []
        def record(row):
            self.transitions.append(dict(row))
            if on_transition:
                on_transition(row)
        self.intents = TapIntentManager(record,
            amend_enabled=bool(amend_enabled),
            freeze_window_ms=freeze_window_ms,
            max_amend_step_ms=max_amend_step_ms,
            max_total_amend_ms=max_total_amend_ms)
        self.last_reasons: dict[int, str] = {}
        self.last_traces = {}
        self.decision_rows = []
        self.shadow_rows = []
        self.eta_rows = []
        # Event-triggered, bounded evidence for the single PF-width gate
        # experiment.  This is diagnostic-only and never enters scheduling.
        self.pf_gate_shadow_rows = []
        self.global_rows = []
        self.shadow_decisions = {}
        self.global_decisions = {}
        self.global_model_frames = 0
        self.global_ready_frames = 0
        self.global_status_counts = {}
        self.global_first_schedule_at = {}
        self._last_decision_fingerprints = {}

    def note_uid(self, track_id: int):
        return f"{self.session_id}:simple:{track_id}"

    def update(self, candidates, captured_at: float, processed_at: float,
               scheduler, *, playing: bool):
        tracks = self.tracker.update(candidates, captured_at, playing=playing)
        return tracks, self.plan_tracks(tracks, captured_at, processed_at, scheduler,
                                        enabled=playing)

    def plan_tracks(self, tracks, captured_at: float, processed_at: float,
                    scheduler, *, enabled: bool, source_frame=None):
        note_uids = {}
        for track in tracks if enabled else ():
            uid = self.note_uid(track.track_id)
            note_uids[track.track_id] = uid
            self.intents.note_seen(uid, captured_at)
            if track.confirmed_note_type == "tap":
                self.intents.note_confirmed(uid, captured_at)
        fixed = {uid: intent.key for uid, intent in self.intents.intents.items()
                 if intent.state == "PENDING"}
        # Global fixed-speed ETA is the only ordinary Tap timing source when
        # explicitly enabled for Active use.  The legacy PF timing planner is
        # retained only for backwards-compatible Shadow/disabled callers and
        # is never a fallback in the Global Active path.
        global_model = self.global_timing.update(
            tracks if enabled else [], trigger_y=self.tracker.hit_y,
            capture_timestamp=captured_at, now=processed_at, playing=enabled)
        self.global_model_frames += 1
        if global_model.ready:
            self.global_ready_frames += 1
        global_etas = {
            track.track_id: self.global_timing.estimate(
                track, trigger_y=self.tracker.hit_y, now=processed_at)
            for track in tracks
        }
        global_decisions, global_proposals = self.planner.global_plan(
            tracks if enabled else [], global_etas, processed_at, self.known_keys,
            scheduler, note_uids=note_uids, fixed_keys=fixed)
        self.global_decisions = global_decisions
        for decision in global_decisions.values():
            self.global_status_counts[decision.reason] = self.global_status_counts.get(decision.reason, 0) + 1
            if decision.status == "schedule":
                self.global_first_schedule_at.setdefault(decision.note_uid, captured_at)
        global_active = enabled and self.global_timing.active_enabled
        if self.global_timing.enabled:
            # Global Shadow is strictly observational: it must not call the
            # intent manager or Scheduler.offer.  Global Active is the only
            # enabled scheduling path and has no PF/Linear fallback.
            proposals = dict(global_proposals) if global_active else {}
            reasons = {track_id: decision.reason for track_id, decision in global_decisions.items()
                       if decision.status != "schedule"}
            if not global_active:
                reasons.update({track_id: "global_shadow_only"
                                for track_id, decision in global_decisions.items()
                                if decision.status == "schedule"})
            traces = {}
            shadow = {}
        else:
            proposals, reasons = self.planner.plan(tracks if enabled else [], processed_at,
                self.known_keys, scheduler, note_uids=note_uids, fixed_keys=fixed)
            traces = self.planner.last_traces
            # The simplified planner remains a read-only comparator unless a
            # caller explicitly requests its old Active experiment.
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
        self.shadow_decisions = shadow
        accepted, rejected = self.intents.schedule(proposals, scheduler, processed_at)
        self.last_reasons = {**reasons, **{
            track.track_id: rejected[uid]
            for track in tracks
            for uid in (note_uids.get(track.track_id, ""),)
            if uid in rejected
        }}
        self.last_traces = traces
        linear_estimates = {}
        if not global_active:
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
                                 linear_estimates, source_frame,
                                 global_model, global_etas, global_decisions,
                                 global_active)
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
                            linear_estimates, source_frame=None,
                            global_model=None, global_etas=None,
                            global_decisions=None, global_active=False):
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
            pf_status = ("tracking_only" if global_active else
                         "available" if prediction.hit_time is not None and prediction.eta is not None else
                         "prediction_unavailable")
            if not global_active and prediction.eta is not None and prediction.eta <= 0:
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
                "pf_eta_s": "" if global_active else prediction.eta if prediction.eta is not None else "",
                "pf_hit_at": "" if global_active else prediction.hit_time if prediction.hit_time is not None else "",
                "pf_uncertainty_s": "" if global_active else prediction.uncertainty if prediction.uncertainty is not None else "",
                "pf_eta_p10": "" if global_active else prediction.eta_p10 if prediction.eta_p10 is not None else "",
                "pf_eta_p50": "" if global_active else prediction.eta_p50 if prediction.eta_p50 is not None else "",
                "pf_eta_p90": "" if global_active else prediction.eta_p90 if prediction.eta_p90 is not None else "",
                "pf_crossing_mass": "" if global_active else prediction.valid_crossing_mass if prediction.valid_crossing_mass is not None else "",
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
            global_eta = (global_etas or {}).get(track.track_id)
            global_decision = (global_decisions or {}).get(track.track_id)
            self.global_rows.append({
                "capture_timestamp": captured_at,
                "processing_timestamp": processed_at,
                "note_uid": uid,
                "track_id": track.track_id,
                "model_status": "ready" if global_model and global_model.ready else "not_ready",
                "model_reason": global_model.reason if global_model else "disabled",
                "model_version": global_model.model_version if global_model else 0,
                "independent_tracks": global_model.independent_tracks if global_model else 0,
                "sample_count": global_model.sample_count if global_model else 0,
                "velocity_px_s": global_model.velocity_px_s if global_model and global_model.velocity_px_s is not None else "",
                "velocity_mad_px_s": global_model.velocity_mad_px_s if global_model and global_model.velocity_mad_px_s is not None else "",
                "velocity_sigma_px_s": global_model.velocity_sigma_px_s if global_model and global_model.velocity_sigma_px_s is not None else "",
                "model_quality": global_model.quality if global_model else 0.0,
                "eta_status": global_eta.status if global_eta else "NOT_READY",
                "eta_reason": global_eta.reason if global_eta else "prediction_unavailable",
                "eta_s": global_eta.eta_s if global_eta and global_eta.eta_s is not None else "",
                "hit_at": global_eta.hit_at if global_eta and global_eta.hit_at is not None else "",
                "uncertainty_s": global_eta.uncertainty_s if global_eta and global_eta.uncertainty_s is not None else "",
                "observed_y": global_eta.observed_y if global_eta and global_eta.observed_y is not None else "",
                "observed_at": global_eta.observed_at if global_eta and global_eta.observed_at is not None else "",
                "planner_status": global_decision.status if global_decision else "disabled",
                "planner_reason": global_decision.reason if global_decision else "",
                "planner_key": global_decision.key if global_decision and global_decision.key else "",
                "active_enabled": bool(self.global_timing.active_enabled),
                "input_sent": False,
            })
            # Record only the narrow case required by V7.11 work order 0E:
            # Legacy was blocked solely by posterior width according to the
            # recorded gate trace, while every other recorded gate passed.
            # Do not call any planner, intent manager, or scheduler method
            # here; this row is a passive observation only.
            if planner_reason == "particle_posterior_too_wide" and trace is not None:
                other_gates = {name: value for name, value in trace.gates.items()
                               if name != "particle_posterior_width"}
                if all(other_gates.values()):
                    width_s = None
                    if prediction.eta_p10 is not None and prediction.eta_p90 is not None:
                        width_s = prediction.eta_p90 - prediction.eta_p10
                    candidate_keys = list(track.candidate.candidate_keys)
                    uid = self.note_uid(track.track_id)
                    pending = [
                        {"event_id": event_id, "key": intent.keys[0],
                         "hit_at": intent.hit_at}
                        for event_id, intent in list(scheduler.pending.items())[:8]
                    ]
                    held = [
                        {"key": key, "release_at": release_at,
                         "event_id": intent.event_id}
                        for key, (release_at, intent) in list(scheduler.held.items())[:8]
                    ]
                    recent = [{"key": key, "hit_at": hit}
                              for key, hit in list(scheduler.recent)[-8:]]
                    competition = [
                        row for row in pending + recent
                        if row.get("key") in candidate_keys
                    ]
                    self.pf_gate_shadow_rows.append({
                        "capture_timestamp": captured_at,
                        "processing_timestamp": processed_at,
                        "source_frame": source_frame if source_frame is not None else "",
                        "track_id": track.track_id,
                        "note_uid": uid,
                        "posterior_width_ms": width_s * 1000 if width_s is not None else "",
                        "hit_at": prediction.hit_time if prediction.hit_time is not None else "",
                        "last_safe_time": trace.last_safe_schedule_at or "",
                        "valid_keys": "|".join(candidate_keys),
                        "legacy_result": "rejected",
                        "legacy_reason": planner_reason,
                        "b_gate_result": "eligible_if_only_width_removed",
                        "b_input_sent": False,
                        "pending_summary": json.dumps(pending, sort_keys=True),
                        "held_summary": json.dumps(held, sort_keys=True),
                        "recent_summary": json.dumps(recent, sort_keys=True),
                        "competition_summary": json.dumps(competition, sort_keys=True),
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

    def drain_pf_gate_shadow_rows(self):
        rows, self.pf_gate_shadow_rows = self.pf_gate_shadow_rows, []
        return rows

    def drain_global_rows(self):
        rows, self.global_rows = self.global_rows, []
        return rows

    def global_stats(self):
        return {
            "model_frames": self.global_model_frames,
            "ready_frames": self.global_ready_frames,
            "ready_ratio": (self.global_ready_frames / self.global_model_frames
                             if self.global_model_frames else 0.0),
            "status_counts": dict(self.global_status_counts),
            "first_schedule_at": dict(self.global_first_schedule_at),
        }

    def record_scheduler_action(self, action: dict):
        self.intents.record_action(action)
