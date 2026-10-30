from src.live_profiling import StageProfiler
from src.live_input import ActionIntent
from tests.test_pf_eta_eligibility import good_particle_track
from tests.test_pf_schedule_integration import make_engine
from tools.replay_pf_mock import ReplayClock


def test_pf_decision_stages_have_measured_percentiles():
    profiler = StageProfiler()
    for value in (.001, .002, .004):
        profiler.record("tracking", value, "PLAYING")
        profiler.record("prediction", value / 2, "PLAYING")
        profiler.record("decision", value / 4, "PLAYING")
    rows = {(r["stage"], r["state"]): r for r in profiler.rows()}
    assert rows[("tracking", "PLAYING")]["samples"] == 3
    assert rows[("prediction", "PLAYING")]["p95_ms"] > 0
    assert rows[("decision", "PLAYING")]["status"] == "MEASURED"


def test_tap_decision_trace_follows_schedule_through_mock_key_down(make_candidate):
    engine, scheduler, _ = make_engine()
    rows=[]
    engine.diagnostic_sink=lambda name,row: rows.append((name,row))
    track=good_particle_track(make_candidate)
    frame=type("Frame",(),{"sequence":42})()
    event_id=f"{engine.session_id}:{track.track_id}"
    engine._emit_tap_decision(track,event_id,frame,1.0,"SCHEDULE_ELIGIBILITY",
                              "SCHEDULE_ELIGIBLE",scheduled=False)
    intent=ActionIntent(event_id,("F",),.2,.01,"tap")
    assert scheduler.offer(intent)
    engine._emit_tap_decision(track,event_id,frame,1.0,"SCHEDULE_OFFERED",
                              "SCHEDULE_ACCEPTED",scheduled=True)
    engine.record_scheduler_action({"action":"key_down","timestamp":.2,
                                    "event_id":event_id,"reason":"","key":"F"})
    decisions=[row for name,row in rows if name=="tap_decision"]
    assert [row["decision_stage"] for row in decisions][-1]=="KEY_DOWN_SENT"
    assert decisions[-1]["eventually_scheduled"]
    assert decisions[-1]["eventually_key_down"]
    assert decisions[-1]["physical_note_uid"]==track.physical_note_uid
    scheduler.close()


def test_replay_clock_depends_on_recorded_timestamps_not_machine_speed():
    clock=ReplayClock()
    clock.reset(12.5,True)
    assert clock()==12.5
    assert clock()==12.5
    clock.advance(12.6)
    assert clock()==12.6
