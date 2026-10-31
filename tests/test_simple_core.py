from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from src.geometry import CalibratedGeometry
from src.live_capture import CapturedFrame
from src.live_engine import LiveEngine
from src.detector import Candidate
from src.live_input import ActionIntent, MockActuator, TapScheduler, OfferResult
from src.predictor import Prediction
from src.simple_tracker import SimpleTracker
from src.tap_intent import TapIntentManager
from src.tap_planner import TapPlanner, TapProposal


def candidate(y, *, u=.40, appearance="cyan_bar", keys=("F",), width=.12):
    return Candidate((250, round(y-3), 60, 6), appearance, .9, u-width/2, u+width/2,
                     list(keys), "tap", body_bbox=(250, round(y-3), 60, 6))


def test_simple_tracker_keeps_track_id_across_short_detector_dropout():
    tracker = SimpleTracker({"confirm_observations": 3, "max_gap_s": .16},
        {"min_observations": 3, "min_duration_s": .02, "min_velocity": 20,
         "min_displacement_px": 1, "max_uncertainty_s": .04}, hit_y=310.5)
    for i in range(4):
        tracks = tracker.update([candidate(200+i*5)], 1+i/60)
    track_id = tracks[0].track_id
    tracks = tracker.update([], 1.08)
    assert tracks[0].track_id == track_id
    tracks = tracker.update([candidate(225)], 1.10)
    assert tracks[0].track_id == track_id
    assert tracks[0].missed == 0


def test_neutral_to_neutral_tracks_across_frames():
    tracker = SimpleTracker({"confirm_observations": 3},
        {"min_observations": 3, "min_duration_s": .02}, hit_y=310.5)
    for i in range(4):
        tracks = tracker.update([candidate(180 + i * 8, appearance="neutral_candidate")], 1 + i / 60)
    assert len(tracks) == 1
    assert tracks[0].observations == 4
    assert tracks[0].appearance_history == ["neutral_candidate"] * 4


def test_neutral_cyan_neutral_keeps_physical_identity():
    tracker = SimpleTracker({"confirm_observations": 3},
        {"min_observations": 3, "min_duration_s": .02}, hit_y=310.5)
    appearances = ("neutral_candidate", "cyan_bar", "neutral_candidate", "cyan_bar")
    for i, appearance in enumerate(appearances):
        tracks = tracker.update([candidate(180 + i * 8, appearance=appearance)], 1 + i / 60)
    assert len(tracks) == 1
    assert tracks[0].track_id == 1
    assert tracks[0].appearance_history == list(appearances)


def test_two_close_gray_taps_not_merged():
    tracker = SimpleTracker({"confirm_observations": 3},
        {"min_observations": 3, "min_duration_s": .02}, hit_y=310.5)
    tracks = tracker.update([
        candidate(180, appearance="neutral_candidate", u=.35),
        candidate(205, appearance="neutral_candidate", u=.65),
    ], 1.0)
    assert len(tracks) == 2


def test_gray_background_line_never_becomes_tap_without_motion():
    tracker = SimpleTracker({"confirm_observations": 3},
        {"min_observations": 3, "min_duration_s": .02}, hit_y=310.5)
    for i in range(8):
        tracks = tracker.update([candidate(180, appearance="neutral_candidate")], 1 + i / 60)
    assert len(tracks) == 1
    assert tracks[0].confirmed_note_type is None
    assert tracks[0].status != "confirmed"


def test_simple_tracker_does_not_merge_two_visible_same_lane_notes():
    tracker = SimpleTracker({"confirm_observations": 3},
        {"min_observations": 3, "min_duration_s": .02}, hit_y=310.5)
    tracks = tracker.update([candidate(200), candidate(230)], 1.0)
    assert len(tracks) == 2
    assert tracks[0].track_id != tracks[1].track_id


def test_simple_tracker_collapses_only_same_frame_duplicate_contours():
    tracker = SimpleTracker()
    a = candidate(200)
    b = replace(a, bbox=(251, 198, 60, 6), score=.8)
    tracks = tracker.update([a, b], 1.0)
    assert len(tracks) == 1


def make_ready_track(track_id=1, hit_at=10.20, key="F", uncertainty=.01):
    track = SimpleTracker()._new_track(candidate(280, keys=(key,)), 10.0)
    track.track_id = track_id
    track.status = "confirmed"
    track.confirmed_note_type = "tap"
    track.observations = 6
    track.history = [(9.9, 250, .4), (10.0, 280, .4)]
    track.stable_keys = [key]
    track.prediction = Prediction(velocity=300, fitted_y=280, eta=hit_at-10,
        hit_time=hit_at, uncertainty=uncertainty, reason="")
    return track


def add_particle_evidence(track):
    track.particle_filter = SimpleNamespace(initialized=True, cfg={"min_real_observations": 4,
        "max_posterior_width_ms": 40, "min_valid_crossing_mass": .95})
    track.prediction = replace(track.prediction, real_observation_count=5,
        eta_p10=.19, eta_p90=.21, valid_crossing_mass=.99)
    return track


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


def armed_scheduler(now=10.0):
    clock = Clock(now)
    actuator = MockActuator()
    rows = []
    scheduler = TapScheduler("assist", actuator, clock=clock, on_log=rows.append)
    scheduler.update_context(now, "PLAYING", True, True)
    scheduler.armed = True
    scheduler.arm_generation = 1
    return clock, actuator, rows, scheduler


def test_tap_planner_requires_confirmation_eta_and_stable_covered_key():
    _, _, _, scheduler = armed_scheduler()
    planner = TapPlanner({"max_eta_s": .45}, min_y=190)
    unconfirmed = make_ready_track()
    unconfirmed.status = "tentative"
    proposals, reasons = planner.plan([unconfirmed], 10., {"F"}, scheduler)
    assert not proposals
    assert reasons[1] == "track_not_current_confirmed"

    ready = add_particle_evidence(make_ready_track())
    proposals, reasons = planner.plan([ready], 10., {"F"}, scheduler)
    assert proposals[1].key == "F"
    assert reasons[1] == ""
    scheduler.close()


def test_offer_result_has_fresh_structured_rejection_reason():
    clock, _, _, scheduler = armed_scheduler()
    scheduler.last_reason = "stale_old_reason"
    scheduler.update_context(9.0, "PLAYING", True, True)
    result = scheduler.offer(ActionIntent("uid", ("F",), 10.2, .01, "tap"))
    assert isinstance(result, OfferResult)
    assert result.accepted is False
    assert result.reason == "validated_capture_expired"
    assert result.reason != scheduler.last_reason
    scheduler.update_context(10.0, "PLAYING", True, True)
    result = scheduler.offer(ActionIntent("uid", ("F",), 10.2, .01, "tap"))
    assert result.accepted is True and result.reason == "accepted"
    assert result.intent_id == "uid" and result.timestamp == pytest.approx(10.0)
    scheduler.close()


def test_planner_emits_per_gate_trace_and_candidate_key_conflicts():
    _, _, _, scheduler = armed_scheduler()
    planner = TapPlanner({"max_eta_s": .45}, min_y=190)
    track = add_particle_evidence(make_ready_track())
    track.history[-1] = (10.0, 280, .4)
    scheduler.recent.append(("F", 10.20))
    proposals, reasons = planner.plan([track], 10., {"F"}, scheduler)
    assert proposals == {}
    assert reasons[track.track_id] == "tap_key_conflict"
    trace = planner.last_traces[track.track_id]
    assert all(value for key, value in trace.gates.items() if key not in {"motion_reliable"})
    assert trace.final_reason == "tap_key_conflict"
    assert trace.key_conflicts["F"] == "reserved_same_key_time"
    scheduler.close()


def test_planner_traces_candidate_without_eta_without_crashing():
    _, _, _, scheduler = armed_scheduler()
    planner = TapPlanner({"max_eta_s": .45}, min_y=190)
    track = make_ready_track()
    track.prediction = replace(track.prediction, eta=None, hit_time=None, uncertainty=None)
    proposals, reasons = planner.plan([track], 10., {"F"}, scheduler)
    assert proposals == {}
    assert reasons[track.track_id] == "eta_unavailable"
    assert planner.last_traces[track.track_id].hit_at is None
    scheduler.close()


def test_intent_rejection_is_logged_with_its_offer_reason():
    _, _, _, scheduler = armed_scheduler()
    scheduler.armed = False
    transitions = []
    manager = TapIntentManager(transitions.append)
    proposal = TapProposal("session:simple:reject", 7, "F", 10.20, .01, "evidence")
    accepted, rejected = manager.schedule({7: proposal}, scheduler, 10.)
    assert not accepted and rejected[proposal.note_uid] == "assist_disarmed"
    row = next(row for row in transitions if row["state"] == "NOT_SCHEDULED")
    assert row["reason"] == "assist_disarmed"
    scheduler.close()


def test_pending_amend_replaces_deadline_once_with_new_revision():
    clock, _, rows, scheduler = armed_scheduler()
    transitions = []
    manager = TapIntentManager(transitions.append, amend_enabled=True, freeze_window_ms=10,
                               max_amend_step_ms=40, max_total_amend_ms=80)
    first = TapProposal("session:simple:amend", 8, "F", 10.20, .01, "first")
    accepted, rejected = manager.schedule({8: first}, scheduler, 10.0)
    assert accepted and not rejected
    clock.now = 10.02
    scheduler.update_context(10.02, "PLAYING", True, True)
    amended = TapProposal(first.note_uid, 8, "F", 10.22, .012, "updated")
    manager.schedule({8: amended}, scheduler, 10.02)
    intent = scheduler.pending[first.note_uid]
    assert intent.hit_at == pytest.approx(10.22)
    assert intent.revision == 1
    assert manager.intents[first.note_uid].revision == 1
    assert any(row.get("state") == "AMENDED" for row in transitions if row.get("note_uid") == first.note_uid)
    scheduler.close()


def test_pending_amend_freeze_window_does_not_move_deadline():
    clock, _, _, scheduler = armed_scheduler()
    transitions = []
    manager = TapIntentManager(transitions.append, amend_enabled=True, freeze_window_ms=30)
    first = TapProposal("session:simple:freeze", 9, "F", 10.20, .01, "first")
    manager.schedule({9: first}, scheduler, 10.0)
    clock.now = 10.18
    scheduler.update_context(10.18, "PLAYING", True, True)
    manager.schedule({9: TapProposal(first.note_uid, 9, "F", 10.21, .01, "late")}, scheduler, 10.18)
    assert scheduler.pending[first.note_uid].hit_at == pytest.approx(10.20)
    assert any(row.get("reason") == "deadline_freeze_window" for row in transitions)
    scheduler.close()


def test_planner_ignores_same_note_pending_reservation_but_keeps_other_conflict():
    clock, _, _, scheduler = armed_scheduler()
    manager = TapIntentManager(amend_enabled=True)
    first = TapProposal("session:simple:self", 10, "F", 10.20, .01, "first")
    manager.schedule({10: first}, scheduler, 10.0)
    track = add_particle_evidence(make_ready_track(track_id=10, hit_at=10.21, key="F"))
    planner = TapPlanner({"max_eta_s": .45}, min_y=190)
    proposals, reasons = planner.plan([track], 10.02, {"F"}, scheduler,
                                      note_uids={10: first.note_uid},
                                      fixed_keys={first.note_uid: "F"})
    assert reasons[10] == ""
    assert proposals[10].key == "F"
    scheduler.close()


def test_intent_manager_freezes_key_and_deadline_after_acceptance():
    clock, _, rows, scheduler = armed_scheduler()
    transitions = []
    manager = TapIntentManager(transitions.append)
    first = TapProposal("session:simple:1", 1, "F", 10.20, .01, "first fit")
    accepted, rejected = manager.schedule({1: first}, scheduler, 10.)
    assert len(accepted) == 1 and not rejected
    original = scheduler.pending[first.note_uid]

    later = TapProposal(first.note_uid, 1, "F", 10.26, .02, "later fit")
    manager.schedule({1: later}, scheduler, 10.03)
    assert scheduler.pending[first.note_uid] is original
    assert original.hit_at == pytest.approx(10.20)
    assert original.keys == ("F",)

    clock.now = 10.20
    scheduler.update_context(10.16, "PLAYING", True, True)
    scheduler.poll()
    manager.record_action(rows[-1])
    assert manager.state_for(first.note_uid) == "FIRED"
    assert [row["state"] for row in transitions if row.get("note_uid") == first.note_uid] == [
        "PENDING", "SCHEDULED", "FIRED"]
    scheduler.close()


def test_disarm_cancels_pending_intent_and_no_retry_is_created():
    _, _, rows, scheduler = armed_scheduler()
    manager = TapIntentManager()
    proposal = TapProposal("session:simple:2", 2, "D", 10.20, .01, "evidence")
    manager.schedule({2: proposal}, scheduler, 10.)
    scheduler.on_log = lambda row: (rows.append(row), manager.record_action(row))
    scheduler.disarm("focus_loss")
    assert manager.state_for(proposal.note_uid) == "CANCELED"
    scheduler.update_context(10., "PLAYING", True, True)
    scheduler.armed = True
    scheduler.arm_generation += 1
    manager.schedule({2: proposal}, scheduler, 10.)
    assert proposal.note_uid not in scheduler.pending
    assert manager.state_for(proposal.note_uid) == "CANCELED"
    scheduler.close()


def test_existing_intent_does_not_extend_deadline_after_track_loss():
    clock, actuator, rows, scheduler = armed_scheduler()
    manager = TapIntentManager()
    proposal = TapProposal("session:simple:3", 3, "S", 10.10, .01, "evidence")
    manager.schedule({3: proposal}, scheduler, 10.)
    scheduler.on_log = lambda row: (rows.append(row), manager.record_action(row))
    # No proposal represents a lost observation. The manager owns the already
    # accepted action and does not require an ETA refresh to keep its deadline.
    clock.now = 10.10
    scheduler.update_context(10.10, "PLAYING", True, True)
    scheduler.poll()
    assert actuator.calls == [("down", "S")]
    assert manager.state_for(proposal.note_uid) == "FIRED"
    scheduler.close()


def test_live_engine_particle_core_schedules_tap_once():
    root = Path(__file__).resolve().parents[1]
    geometry = CalibratedGeometry(json.loads(
        (root / "config/geometry_live_assist.json").read_text(encoding="utf-8-sig")))
    config = json.loads((root / "config.json").read_text(encoding="utf-8-sig"))
    config["live"] = json.loads((root / "config/live_assist.json").read_text(encoding="utf-8-sig"))
    config["live"].update(input_advance_px=15)
    config["live"]["hold_visual"]["enabled"] = False
    config["predictor"]["mode"] = "particle"
    config["tracker"].update(confirm_observations=5, max_gap_s=.16)

    clock, actuator, rows, scheduler = armed_scheduler(1000.)
    current = [candidate(220)]
    engine = LiveEngine(config, geometry, scheduler, clock=clock,
                        detector=lambda *args: current)
    # Replay tooling may replace the diagnostic session label after engine
    # construction; the Tap owner remains the authority for its own IDs.
    engine.session_id = "replay-session"
    engine.gate.update = lambda *args: "PLAYING"
    scheduler.on_log = lambda row: (rows.append(row), engine.record_scheduler_action(row))
    image = np.zeros((404, 720, 3), np.uint8)

    for i in range(5):
        timestamp = 1000. + i * .02
        clock.now = timestamp
        y = 220 + (timestamp - 1000.) * 300
        current[:] = [candidate(y)]
        engine.process(CapturedFrame(i, image, timestamp, timestamp))
        if i == 0:
            scheduler.armed = True
            scheduler.arm_generation = 1

    assert len(scheduler.pending) == 1
    event_id, intent = next(iter(scheduler.pending.items()))
    assert event_id.startswith(f"{engine.simple_core.session_id}:simple:")
    original_hit = intent.hit_at
    original_key = intent.keys

    # A later estimate and a temporarily absent observation cannot replace or
    # extend the accepted action.
    for i, timestamp in enumerate((1000.10, 1000.12), start=5):
        clock.now = timestamp
        current[:] = []
        engine.process(CapturedFrame(i, image, timestamp, timestamp))
    assert scheduler.pending[event_id].hit_at == original_hit
    assert scheduler.pending[event_id].keys == original_key

    clock.now = original_hit
    scheduler.update_context(original_hit - .01, "PLAYING", True, True)
    scheduler.poll()
    assert actuator.calls == [("down", original_key[0])]
    assert engine.simple_core.intents.state_for(event_id) == "FIRED"
    assert not any(action.get("event_id", "").startswith("replay-session:")
                   for action in rows if action.get("action") == "key_down")
    scheduler.close()
