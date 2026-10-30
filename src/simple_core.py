"""Composition root for the deliberately small ordinary-Tap control path."""
from __future__ import annotations

import json

from .simple_tracker import SimpleTracker
from .tap_intent import TapIntentManager
from .tap_planner import TapPlanner


class SimpleAssistCore:
    def __init__(self, *, session_id: str, tracker_cfg: dict,
                 particle_cfg: dict, hit_y: float,
                 event_cfg: dict, min_y: float, known_keys: set[str],
                 on_transition=None, timing_cfg: dict | None = None):
        self.session_id = session_id
        self.known_keys = set(known_keys)
        self.tracker = SimpleTracker(tracker_cfg, particle_cfg, hit_y=hit_y)
        self.planner = TapPlanner(event_cfg, min_y=min_y,
            max_uncertainty_s=float(particle_cfg.get("max_uncertainty_s", .04)))
        self.transitions = []
        def record(row):
            self.transitions.append(dict(row))
            if on_transition:
                on_transition(row)
        timing_cfg = dict(timing_cfg or {})
        self.intents = TapIntentManager(record,
            amend_enabled=timing_cfg.get("enabled", timing_cfg.get("tap_deadline_amend", False)),
            freeze_window_ms=timing_cfg.get("freeze_window_ms", 30),
            max_amend_step_ms=timing_cfg.get("max_amend_step_ms", 40),
            max_total_amend_ms=timing_cfg.get("max_total_amend_ms", 80))
        self.last_reasons: dict[int, str] = {}
        self.last_traces = {}
        self.decision_rows = []
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
        accepted, rejected = self.intents.schedule(proposals, scheduler, processed_at)
        self.last_reasons = {**reasons, **{
            track.track_id: rejected[uid]
            for track in tracks
            for uid in (note_uids.get(track.track_id, ""),)
            if uid in rejected
        }}
        self.last_traces = traces
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
                "gates_json": json.dumps(gates, sort_keys=True) if trace else "{}",
                "key_conflicts_json": json.dumps(conflicts, sort_keys=True) if trace else "{}",
            })
        return proposals, accepted

    def drain_transitions(self):
        rows, self.transitions = self.transitions, []
        return rows

    def drain_decisions(self):
        rows, self.decision_rows = self.decision_rows, []
        return rows

    def record_scheduler_action(self, action: dict):
        self.intents.record_action(action)
