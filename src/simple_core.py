"""Composition root for the deliberately small ordinary-Tap control path."""
from __future__ import annotations

from .simple_tracker import SimpleTracker
from .tap_intent import TapIntentManager
from .tap_planner import TapPlanner


class SimpleAssistCore:
    def __init__(self, *, session_id: str, tracker_cfg: dict,
                 particle_cfg: dict, hit_y: float,
                 event_cfg: dict, min_y: float, known_keys: set[str],
                 on_transition=None):
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
        self.intents = TapIntentManager(record)
        self.last_reasons: dict[int, str] = {}

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
        accepted, rejected = self.intents.schedule(proposals, scheduler, processed_at)
        self.last_reasons = {**reasons, **{
            track.track_id: rejected[uid]
            for track in tracks
            for uid in (note_uids.get(track.track_id, ""),)
            if uid in rejected
        }}
        return proposals, accepted

    def drain_transitions(self):
        rows, self.transitions = self.transitions, []
        return rows

    def record_scheduler_action(self, action: dict):
        self.intents.record_action(action)
