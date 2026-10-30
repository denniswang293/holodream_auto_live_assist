from src.live_input import ActionIntent
from tests.test_pf_identity_continuity import build_confirmed_tap
from tests.test_pf_schedule_integration import make_engine


def test_tap_unknown_sequence_keeps_one_uid_key_and_deadline(make_candidate):
    tracker,track=build_confirmed_tap(make_candidate)
    engine,scheduler,_=make_engine()
    track.selected_key="F"
    track.source_track_ids=[track.track_id]
    track.physical_note_uid="physical:test"
    engine.input_eligible_ids[track.track_id]=scheduler.arm_generation
    event_id=f"{engine.session_id}:{track.track_id}"
    intent=ActionIntent(event_id,("F",),.20,.01,"tap")
    assert scheduler.offer(intent)
    uid=track.physical_note_uid; pf=track.particle_filter
    for frame in range(6,10):
        tracks=tracker.update([make_candidate(y=150+frame*4,appearance="neutral_candidate",keys=["F"])],frame/60)
        track=tracks[0]
        assert track.physical_note_uid==uid
        assert track.particle_filter is pf
        assert track.identity_state=="TAP_DEGRADED_OBSERVATION"
        assert engine._tap_identity_intent_still_valid(track,event_id,intent,frame/60,
            state="PLAYING",focused=True,roi_valid=True,stale=False)
        assert scheduler.pending[event_id] is intent
        assert intent.keys==("F",) and intent.hit_at==.20
    assert len(scheduler.pending)==1
    scheduler.close()


def test_scheduler_failure_trace_names_all_failed_safety_predicates(make_candidate):
    tracker,track=build_confirmed_tap(make_candidate)
    tracker.update([make_candidate(y=178,appearance="neutral_candidate",keys=["F"])],6/60)
    engine,scheduler,_=make_engine()
    track.selected_key="F"; track.source_track_ids=[track.track_id]
    track.physical_note_uid="physical:test"
    engine.input_eligible_ids[track.track_id]=scheduler.arm_generation
    event_id=f"{engine.session_id}:{track.track_id}"
    intent=ActionIntent(event_id,("F",),.20,.01,"tap")
    scheduler.offer(intent)
    reasons=engine._tap_identity_intent_failures(track,event_id,intent,.12,
        state="PAUSED",focused=False,roi_valid=False,stale=True)
    assert reasons[:3]==["GAME_NOT_PLAYING","FOCUS_LOST","ROI_INVALID"]
    assert "STALE_FRAME" in reasons
    assert scheduler.pending[event_id] is intent
    scheduler.close()
