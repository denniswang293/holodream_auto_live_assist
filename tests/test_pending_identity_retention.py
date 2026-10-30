from src.live_input import ActionIntent
from tests.test_pf_identity_continuity import build_confirmed_tap
from tests.test_pf_schedule_integration import make_engine


def test_pending_tap_keeps_original_key_deadline_during_short_track_loss(make_candidate):
    tracker, track = build_confirmed_tap(make_candidate)
    engine, scheduler, _ = make_engine()
    event_id = f"{engine.session_id}:{track.track_id}"
    track.selected_key = "F"
    track.source_track_ids = [track.track_id]
    intent = ActionIntent(event_id, ("F",), .20, .01, "tap")
    assert scheduler.offer(intent)
    tracks = tracker.update([], 6 / 60)
    assert len(tracks) == 1
    lost = tracks[0]
    engine.input_eligible_ids[lost.track_id] = scheduler.arm_generation
    assert lost.physical_note_uid == track.physical_note_uid
    assert engine._tap_identity_intent_still_valid(
        lost, event_id, intent, 6 / 60, state="PLAYING", focused=True,
        roi_valid=True, stale=False)
    assert scheduler.pending[event_id] is intent
    assert intent.keys == ("F",) and intent.hit_at == .20
    assert not scheduler.actuator.calls
    scheduler.close()


def test_expired_original_pending_tap_is_not_extended(make_candidate):
    _, track = build_confirmed_tap(make_candidate)
    engine, scheduler, _ = make_engine()
    event_id = f"{engine.session_id}:{track.track_id}"
    track.selected_key = "F"
    track.source_track_ids = [track.track_id]
    intent = ActionIntent(event_id, ("F",), .15, .01, "tap")
    assert scheduler.offer(intent)
    assert not engine._tap_identity_intent_still_valid(
        track, event_id, intent, .17, state="PLAYING", focused=True,
        roi_valid=True, stale=False)
    assert scheduler.pending[event_id] is intent
    assert intent.hit_at == .15
    scheduler.close()
