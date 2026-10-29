from copy import deepcopy
from dataclasses import replace
import csv
import json
from pathlib import Path
from types import SimpleNamespace
import threading

import numpy as np
import pytest

from src.calibration import geometry_hash
from src.geometry import CalibratedGeometry
from src.live_capture import CapturedFrame, CaptureWorker, LatestFrameBuffer, Region, normalize_frame
from src.live_engine import LiveEngine, track_decision
from src.live_input import ActionIntent, MockActuator, NoInputActuator, TapScheduler, verified_keys
from src.live import new_run_directory
from src.predictor import Prediction

ROOT = Path(__file__).resolve().parents[1]


class Clock:
    def __init__(self, now=1000.):
        self.now = now

    def __call__(self):
        return self.now


@pytest.fixture
def live_config():
    return json.loads((ROOT/"config.json").read_text(encoding="utf-8"))


def hud():
    image = np.zeros((404, 720, 3), np.uint8)
    image[10:38,80:280] = (255,255,0)
    image[10:40,550:655] = (255,255,0)
    return image


@pytest.fixture
def live_geometry():
    document = json.loads((ROOT/"config/geometry_live_assist.json").read_text(encoding="utf-8-sig"))
    return CalibratedGeometry(document)


def test_region_and_aspect_do_not_stretch_ui_or_guess_crop():
    client = Region(-1200, 20, 1000, 800)
    game = client.crop((20, 30, 720, 404))
    assert game.bounds == (-1180, 50, -460, 454)
    assert normalize_frame(np.zeros((808,1440,3), np.uint8)).shape == (404,720,3)
    with pytest.raises(ValueError, match="16:9"):
        normalize_frame(np.zeros((800,1000,3), np.uint8))
    for crop in ((-1,0,720,404), (500,0,720,404), (0,0,0,404)):
        with pytest.raises(ValueError):
            client.crop(crop)


def test_latest_frame_buffer_overwrites_and_shutdown_wakes():
    buffer = LatestFrameBuffer()
    for i in range(10):
        buffer.put(CapturedFrame(i, hud(), i, i+.001))
    assert buffer.dropped == 9
    assert buffer.take().sequence == 9
    assert buffer.take(.001) is None
    buffer.close()
    buffer.put(CapturedFrame(11, hud(), 11, 11.001))
    assert buffer.take() is None


def test_capture_resources_have_one_owner_and_explicit_shutdown():
    captured, closed = threading.Event(), threading.Event()
    owners = []
    class Backend:
        name = "synthetic"
        def __init__(self):
            owners.append(threading.get_ident())
            self.count = 0
        def grab(self):
            owners.append(threading.get_ident())
            self.count += 1
            if self.count >= 4:
                captured.set()
            return hud()
        def close(self):
            owners.append(threading.get_ident())
            closed.set()
    worker = CaptureWorker(Backend, fps=500).start()
    # Wait for publication, not the backend's earlier "grab started" signal.
    with worker.buffer.condition:
        assert worker.buffer.condition.wait_for(lambda: worker.buffer.dropped >= 3, timeout=2)
    worker.close()
    assert closed.is_set() and not worker.thread.is_alive()
    assert len(set(owners)) == 1 and owners[0] != threading.get_ident()
    assert worker.captured >= 4 and worker.buffer.dropped >= 3
    assert worker.actual_fps > 0 and worker.error is None


def test_capture_missing_dependency_and_dx_runtime_fallback(monkeypatch):
    import src.live_capture as capture
    def unavailable(*args, **kwargs):
        raise ImportError("missing synthetic dependency")
    monkeypatch.setattr(capture, "DXCapture", unavailable)
    monkeypatch.setattr(capture, "MSSCapture", unavailable)
    with pytest.raises(RuntimeError, match="requirements-live.txt"):
        capture.AutoCapture(Region(0,0,720,404))
    closed = []
    class DX:
        name = "dxcam"
        def __init__(self, region): pass
        def grab(self): raise RuntimeError("lost synthetic DX output")
        def close(self): closed.append("dx")
    class MSS:
        name = "mss"
        def __init__(self, region): pass
        def grab(self): return hud()
        def close(self): closed.append("mss")
    monkeypatch.setattr(capture, "DXCapture", DX)
    monkeypatch.setattr(capture, "MSSCapture", MSS)
    backend = capture.AutoCapture(Region(0,0,720,404))
    assert backend.grab().shape == (404,720,3) and backend.name == "mss"
    assert "lost synthetic" in backend.fallback_reason
    backend.close()
    assert closed == ["dx", "mss"]




def armed_scheduler():
    clock = Clock()
    actuator = MockActuator()
    scheduler = TapScheduler("assist", actuator, clock=clock)
    scheduler.update_context(clock.now, "PLAYING", True)
    assert scheduler.toggle()
    scheduler.poll()
    assert scheduler.armed
    return clock, actuator, scheduler


def test_hotkey_is_required_and_key_is_released_on_toggle():
    clock, actuator = Clock(), MockActuator()
    scheduler = TapScheduler("assist", actuator, clock=clock)
    scheduler.update_context(clock.now, "PLAYING", True)
    intent = ActionIntent("note", ("S",), clock.now+.01, .001)
    assert not scheduler.offer(intent)
    assert not actuator.calls
    scheduler.toggle()
    scheduler.poll()
    assert scheduler.offer(intent)
    clock.now += .01
    scheduler.poll()
    assert actuator.calls == [("down", "S")]
    scheduler.toggle()
    assert actuator.calls == [("down", "S"), ("up", "S")]
    assert not scheduler.armed
    scheduler.close()


def test_wait_for_hotkey_modifiers_and_no_accidental_ctrl_s():
    clock, actuator, modifiers = Clock(), MockActuator(), [True]
    scheduler = TapScheduler("assist", actuator, clock=clock, modifiers_check=lambda: modifiers[0])
    scheduler.update_context(clock.now, "PLAYING", True)
    scheduler.toggle()
    scheduler.poll()
    assert scheduler.arm_requested and not scheduler.armed
    assert not scheduler.offer(ActionIntent("x", ("S",), clock.now+.01, .001))
    modifiers[0] = False
    scheduler.poll()
    assert scheduler.armed
    scheduler.offer(ActionIntent("x", ("S",), clock.now+.01, .001))
    modifiers[0] = True
    clock.now += .01
    scheduler.poll()
    assert not actuator.calls and not scheduler.pending
    assert scheduler.armed
    scheduler.toggle()  # pressing the combo while armed still turns OFF
    assert not scheduler.armed


@pytest.mark.parametrize("loss", ["stale", "focus", "game", "roi", "emergency"])
def test_every_loss_releases_keys_and_requires_rearming(loss):
    clock, actuator, scheduler = armed_scheduler()
    scheduler.offer(ActionIntent("x", ("F",), clock.now+.01, .001))
    clock.now += .01
    scheduler.poll()
    assert actuator.calls == [("down", "F")]
    if loss == "stale":
        clock.now += .06
        scheduler.poll()
    elif loss == "focus":
        scheduler.focus_check = lambda: False
        scheduler.poll()
    elif loss == "game":
        scheduler.update_context(clock.now, "NOT_PLAYING", True)
    elif loss == "roi":
        scheduler.update_context(clock.now, "PLAYING", True, False)
    else:
        scheduler.disarm("F12")
    assert actuator.calls == [("down", "F"), ("up", "F")]
    assert not scheduler.armed and not scheduler.held
    scheduler.focus_check = lambda: True
    scheduler.update_context(clock.now, "PLAYING", True)
    scheduler.poll()
    assert not scheduler.armed


def test_fresh_inflight_frame_keeps_latch_but_cannot_send_from_expired_context():
    clock,actuator,scheduler=armed_scheduler()
    logs=[];scheduler.on_log=logs.append
    generation=scheduler.arm_generation
    assert scheduler.offer(ActionIntent('pending',('F',),1000.062,.001))
    clock.now=1000.043
    scheduler.begin_decision(1000.031)
    clock.now=1000.0624
    scheduler.poll()
    assert scheduler.armed and scheduler.arm_generation==generation
    assert scheduler.waiting_for_decision and not actuator.calls
    assert not scheduler.offer(ActionIntent('unvalidated',('S',),1000.07,.001))
    clock.now=1000.0629
    scheduler.update_context(1000.031,'PLAYING',True)
    scheduler.poll()
    assert actuator.calls==[('down','F')]
    assert scheduler.armed and scheduler.arm_generation==generation
    assert [r['action'] for r in logs if r['action'].startswith('decision_')]==['decision_wait','decision_resumed']
    scheduler.close()


@pytest.mark.parametrize('loss',['focus','capture_expired','no_inflight','modifiers','emergency','game','roi'])
def test_inflight_frame_never_hides_actual_loss_or_rearms_after_it(loss):
    clock,actuator,scheduler=armed_scheduler()
    assert scheduler.offer(ActionIntent('pending',('F',),1000.08,.001))
    clock.now=1000.04
    if loss!='no_inflight':scheduler.begin_decision(1000.031)
    clock.now=1000.06
    if loss=='focus':scheduler.focus_check=lambda:False
    if loss=='capture_expired':clock.now=1000.09
    if loss=='modifiers':scheduler.modifiers_check=lambda:True
    if loss=='emergency':scheduler.disarm('F12')
    if loss=='game':scheduler.update_context(clock.now,'NOT_PLAYING',True)
    if loss=='roi':scheduler.update_context(clock.now,'PLAYING',True,False)
    scheduler.poll()
    assert not scheduler.armed and not scheduler.pending and not actuator.calls
    scheduler.focus_check=lambda:True;scheduler.modifiers_check=lambda:False
    scheduler.update_context(clock.now,'PLAYING',True)
    scheduler.poll()
    assert not scheduler.armed
    scheduler.close()


def test_waiting_for_fresh_decision_releases_taps_and_abstains_expired_deadlines():
    clock,actuator,scheduler=armed_scheduler()
    assert scheduler.offer(ActionIntent('tap',('S',),1000.01,.001))
    assert scheduler.offer(ActionIntent('pending',('F',),1000.052,.001))
    clock.now=1000.01;scheduler.poll()
    clock.now=1000.043;scheduler.begin_decision(1000.031)
    clock.now=1000.075;scheduler.poll()
    assert scheduler.armed and actuator.calls==[('down','S'),('up','S')]
    scheduler.update_context(1000.031,'PLAYING',True)
    scheduler.poll()
    assert scheduler.armed and 'pending' in scheduler.consumed
    assert actuator.calls==[('down','S'),('up','S')]
    scheduler.close()


def test_engine_announces_fresh_frame_before_cv_can_outlast_previous_context(live_config,live_geometry):
    clock,actuator,scheduler=armed_scheduler()
    def detector(*args):
        assert scheduler.processing_capture==1000.031
        clock.now=1000.0624
        scheduler.poll()
        assert scheduler.armed and scheduler.waiting_for_decision and not actuator.calls
        return []
    engine=LiveEngine(live_config,live_geometry,scheduler,clock=clock,detector=detector)
    engine.gate.update=lambda *args:'PLAYING'
    clock.now=1000.043
    _,_,_,info=engine.process(CapturedFrame(1,np.zeros((404,720,3),np.uint8),1000.031,1000.032))
    assert info['gameplay_state']=='PLAYING' and info['input_armed']
    assert not scheduler.waiting_for_decision and scheduler.processing_capture is None
    assert not actuator.calls
    scheduler.close()


def test_due_late_duplicate_and_recurring_same_lane_taps():
    clock, actuator, scheduler = armed_scheduler()
    base = clock.now
    assert scheduler.offer(ActionIntent("a", ("D",), base+.02, .001))
    assert not scheduler.offer(ActionIntent("fragment", ("D",), base+.025, .001))
    assert scheduler.offer(ActionIntent("b", ("F",), base+.02, .001))
    clock.now = base+.02
    scheduler.poll()
    assert actuator.calls == [("down", "D"), ("down", "F")]
    assert not scheduler.offer(ActionIntent("a", ("D",), base+.12, .001))
    clock.now = base+.05
    scheduler.update_context(clock.now, "PLAYING", True)
    scheduler.poll()
    assert scheduler.offer(ActionIntent("recurring", ("D",), base+.10, .001))
    clock.now = base+.10
    scheduler.update_context(clock.now, "PLAYING", True)
    scheduler.poll()
    assert actuator.calls.count(("down", "D")) == 2
    scheduler.close()
    assert actuator.calls.count(("up", "D")) == 2
    clock, actuator, scheduler = armed_scheduler()
    scheduler.offer(ActionIntent("late", ("J",), clock.now+.005, .001))
    clock.now += .03
    scheduler.poll()
    assert not actuator.calls


@pytest.mark.parametrize('stage,outcome',[
    ('normalization','playing'),('state_gate','playing'),
    ('normalization','not_playing'),('state_gate','focus_loss'),
    ('normalization','capture_expired'),('state_gate','emergency'),
])
def test_new_capture_handoff_covers_normalization_and_state_check(
        live_config,live_geometry,make_candidate,monkeypatch,stage,outcome):
    from src.tracker import Track
    import src.live_engine as engine_module
    clock,actuator,scheduler=armed_scheduler()
    config=deepcopy(live_config)
    config['live']={'verified_key_mapping':{
        'geometry_sha256':geometry_hash(live_geometry.document),
        'reviewer':'synthetic fixture','evidence':'synthetic fixture only','keys':['F']}}
    engine=LiveEngine(config,live_geometry,scheduler,clock,lambda *args:[])
    generation=scheduler.arm_generation
    # Recorded capture 5482, relative to the preceding validated capture:
    # old decision expired just before normalization, new capture is only 18.6ms old.
    capture=1000.0316576
    deadline=1000.0792473
    assert scheduler.offer(ActionIntent('held_start',('D',),1000.001,.001,'hold',.25))
    clock.now=1000.001;scheduler.poll()
    event_id=f'{engine.session_id}:7'
    assert scheduler.offer(ActionIntent(event_id,('F',),deadline,.001))
    c=make_candidate(y=300,keys=['F'])
    tr=Track(7,c,bbox=c.bbox,status='confirmed',observations=10,first_time=999.8,
             history=[(capture,300,.4)],stable_keys=['F'],hit_history=[deadline]*3,
             prediction=Prediction(velocity=180,eta=deadline-capture,hit_time=deadline,
                                   uncertainty=.001,reason=''))
    engine.seen_ids.add(7)
    engine.input_eligible_ids[7]=generation
    engine.tracker.update=lambda *args,**kwargs:[tr] if kwargs.get('playing',True) else []
    original_normalize=engine_module.normalize_frame
    during=[]

    def checkpoint():
        clock.now=1000.0516587 if outcome!='capture_expired' else 1000.09
        if outcome=='focus_loss':scheduler.focus_check=lambda:False
        if outcome=='emergency':scheduler.disarm('F12')
        scheduler.poll()
        during.append((scheduler.armed,list(actuator.calls)))
        clock.now=1000.0685507 if outcome!='capture_expired' else 1000.10

    def normalize(*args):
        if stage=='normalization':checkpoint()
        return original_normalize(*args)

    def gate(*args):
        if stage=='state_gate':checkpoint()
        return 'NOT_PLAYING' if outcome=='not_playing' else 'PLAYING'

    monkeypatch.setattr(engine_module,'normalize_frame',normalize)
    engine.gate.update=gate
    clock.now=1000.0502708
    engine.process(CapturedFrame(5482,hud(),capture,capture+.004),focused=True)
    if outcome=='playing':
        assert during==[(True,[('down','D')])]
        assert scheduler.armed and scheduler.arm_generation==generation
        assert scheduler.pending[event_id].hit_at==deadline
        clock.now=deadline;scheduler.poll()
        assert actuator.calls==[('down','D'),('down','F')]
    else:
        assert not scheduler.armed and not scheduler.held and not scheduler.pending
        assert actuator.calls==[('down','D'),('up','D')]
        scheduler.focus_check=lambda:True
        scheduler.update_context(clock.now,'PLAYING',True);scheduler.poll()
        assert not scheduler.armed  # No automatic re-arm after an actual loss.
    scheduler.close()


def test_retimed_pending_reservation_moves_with_the_actual_deadline():
    clock,actuator,scheduler=armed_scheduler()
    assert scheduler.offer(ActionIntent('moving',('F',),1000.12,.001))
    assert scheduler.offer(ActionIntent('moving',('F',),1000.22,.001))
    assert scheduler.pending_reservations['moving']==('F',1000.22)
    assert ('F',1000.12) not in scheduler.recent
    assert scheduler.offer(ActionIntent('earlier_note',('F',),1000.12,.001))
    assert not scheduler.offer(ActionIntent('same_deadline_fragment',('F',),1000.225,.001))
    clock.now=1000.12;scheduler.update_context(clock.now,'PLAYING',True);scheduler.poll()
    clock.now=1000.22;scheduler.update_context(clock.now,'PLAYING',True);scheduler.poll()
    assert actuator.calls==[('down','F'),('up','F'),('down','F')]
    scheduler.close()


@pytest.mark.parametrize('stop_before_due',[False,True])
def test_worker_meets_tap_deadline_despite_coarse_event_wait(monkeypatch,stop_before_due):
    clock,actuator,scheduler=armed_scheduler()
    assert scheduler.offer(ActionIntent('near_tick',('D',),1000.0005,.001))
    logs=[]
    scheduler.on_log=logs.append

    def advance(seconds):
        clock.now+=seconds
        if stop_before_due or clock.now>=1000.04:
            scheduler.stop_event.set()

    def coarse_wait(timeout):
        # Reproduce the measured Windows Event.wait(2ms) wakeup (~16ms).
        advance(.016)
        return scheduler.stop_event.is_set()

    class InlineThread:
        def __init__(self,*,target,**kwargs):self.target=target
        def start(self):self.target()
        def join(self,timeout=None):pass
        def is_alive(self):return False

    monkeypatch.setattr(scheduler.stop_event,'wait',coarse_wait)
    monkeypatch.setattr('src.live_input.threading.Thread',InlineThread)
    monkeypatch.setattr('src.live_input.time',SimpleNamespace(sleep=advance))
    scheduler.start()
    scheduler.close()
    assert scheduler.error is None
    if stop_before_due:
        assert not actuator.calls
    else:
        assert actuator.calls==[('down','D'),('up','D')]
        down=next(row for row in logs if row['action']=='key_down')
        assert 0<=down['timestamp']-1000.0005<=scheduler.max_lateness


@pytest.mark.parametrize('retryable',[False,True])
def test_canceled_unsent_action_does_not_reserve_time_for_other_notes(retryable):
    clock,actuator,scheduler=armed_scheduler()
    assert scheduler.offer(ActionIntent('canceled',('F',),1000.04,.001))
    scheduler.withdraw('canceled','test_cancellation',retryable=retryable)
    assert not scheduler.recent and not scheduler.pending_reservations
    assert ('canceled' in scheduler.consumed)==(not retryable)
    assert scheduler.offer(ActionIntent('new_note',('F',),1000.04,.001))
    clock.now=1000.04;scheduler.poll()
    assert actuator.calls==[('down','F')]
    scheduler.close()


def test_late_unsent_action_does_not_block_a_fresh_note():
    clock,actuator,scheduler=armed_scheduler()
    assert scheduler.offer(ActionIntent('late',('J',),1000.02,.001))
    clock.now=1000.04;scheduler.poll()
    assert not actuator.calls and not scheduler.recent
    assert scheduler.offer(ActionIntent('fresh',('J',),1000.05,.001))
    clock.now=1000.05;scheduler.poll()
    assert actuator.calls==[('down','J')]
    scheduler.close()


def test_disarm_removes_only_unsent_time_reservations():
    clock,actuator,scheduler=armed_scheduler()
    assert scheduler.offer(ActionIntent('sent',('S',),1000.01,.001))
    assert scheduler.offer(ActionIntent('not_sent',('F',),1000.04,.001))
    clock.now=1000.01;scheduler.poll()
    scheduler.disarm('F12')
    assert ('S',1000.01) in scheduler.recent and ('F',1000.04) not in scheduler.recent
    assert not scheduler.pending_reservations and not scheduler.armed
    assert actuator.calls==[('down','S'),('up','S')]
    scheduler.close()


@pytest.mark.parametrize("intent", [ActionIntent("multi", ("S","D"),1000.01,.001),
                                    ActionIntent("special", ("F",),1000.01,.001,"flick"),
                                    ActionIntent("uncertain", ("F",),1000.01,.08),
                                    ActionIntent("old", ("F",),999.,.001)])
def test_scheduler_abstains_ambiguity_special_uncertainty_and_past(intent):
    _, actuator, scheduler = armed_scheduler()
    assert not scheduler.offer(intent)
    assert not actuator.calls




def test_manual_key_evidence_is_pinned_to_geometry(live_config, live_geometry):
    identity = geometry_hash(live_geometry.document)
    assert verified_keys(live_config, identity) == set()
    live_config["live"] = {"verified_key_mapping":{"geometry_sha256":identity,"reviewer":"synthetic test only", "evidence":"synthetic fixture", "keys":["F"]}}
    assert verified_keys(live_config, identity) == {"F"}
    assert not verified_keys(live_config, "changed geometry")


def synthetic_stream(live_config, live_geometry, batches, focused=None, known=False):
    clock = Clock()
    config = deepcopy(live_config)
    if known:
        config["live"] = {"verified_key_mapping":{"geometry_sha256":geometry_hash(live_geometry.document),
                           "reviewer":"synthetic fixture","evidence":"synthetic only","keys":list("SDFJKL")}}
    pending = iter(batches)
    engine = LiveEngine(config, live_geometry, TapScheduler("assist", NoInputActuator(), clock=clock),
                        clock=clock, detector=lambda *a: next(pending))
    rows = []
    for i in range(len(batches)):
        timestamp = 1000+i/60
        clock.now = timestamp+.002
        _, _, events, _ = engine.process(CapturedFrame(i, hud(), timestamp, timestamp+.001),
                                         True if focused is None else focused[i])
        rows.extend(events)
    return engine, rows


def test_shared_engine_ambiguous_notes_abstain_not_chords(live_config,live_geometry,make_candidate):
    batches = [[make_candidate(y=275+i*3, keys=["D","F"])] for i in range(20)]
    engine, rows = synthetic_stream(live_config,live_geometry,batches,known=True)
    assert len(rows) == 1
    assert rows[0]["abstain_reason"] == "ambiguous_or_unstable_keys"
    assert rows[0]["resolved_keys"] == "" and engine.scheduler.sent == 0


def test_shared_engine_real_chord_is_two_singletons_and_repeated_lane_is_new_note(live_config,live_geometry,make_candidate):
    batches = [[make_candidate(y=275+i*3,u=.4,keys=["F"]), make_candidate(y=275+i*3,u=.6,keys=["J"])] for i in range(20)]
    batches += [[] for _ in range(12)]
    batches += [[make_candidate(y=275+i*3,u=.4,keys=["F"])] for i in range(20)]
    engine, rows = synthetic_stream(live_config,live_geometry,batches,known=True)
    assert len(rows) == 3 and len({r["event_id"] for r in rows}) == 3
    assert sorted(r["resolved_keys"] for r in rows) == ["F","F","J"]
    assert engine.scheduler.sent == 0


@pytest.mark.parametrize("appearance", ["pink_candidate","green_candidate","neutral_candidate"])
def test_special_effect_semantics_stay_unknown(live_config,live_geometry,make_candidate,appearance):
    batches = [[make_candidate(y=275+i*3,appearance=appearance,keys=["F"])] for i in range(20)]
    engine, rows = synthetic_stream(live_config,live_geometry,batches,known=True)
    assert len(rows) == 1 and rows[0]["type"] == "unknown"
    assert rows[0]["abstain_reason"] == "unverified_special_or_neutral"
    assert engine.scheduler.sent == 0


def test_occlusion_and_focus_loss_do_not_recycle_track_ids(live_config,live_geometry,make_candidate):
    batches = [[make_candidate(y=275+i*3,keys=["F"])] for i in range(10)]
    batches += [[] for _ in range(4)]
    batches += [[make_candidate(y=317+i*3,keys=["F"])] for i in range(7)]
    batches += [[] for _ in range(2)]
    batches += [[make_candidate(y=275+i*3,keys=["F"])] for i in range(20)]
    focused = [True]*len(batches)
    focused[21] = False
    engine, rows = synthetic_stream(live_config,live_geometry,batches,focused,known=True)
    assert len(rows) == 2 and len({r["track_id"] for r in rows}) == 2
    assert not engine.scheduler.armed


def test_stale_and_invalid_clock_never_reach_detector(live_config,live_geometry):
    clock = Clock(1000.1)
    scheduler = TapScheduler("assist", clock=clock)
    def forbidden(*args): pytest.fail("Stale frame reached detector")
    engine = LiveEngine(live_config,live_geometry,scheduler,clock,forbidden)
    packet = CapturedFrame(0,hud(),1000,1000.001)
    _,_,events,info = engine.process(packet)
    assert info["gameplay_state"] == "STALE" and not events and engine.stale == 1
    with pytest.raises(ValueError,match="monotonic"):
        engine.process(packet)








def test_due_intent_is_canceled_before_new_ambiguous_frame_and_ids_cannot_recycle(live_config,live_geometry,make_candidate):
    from src.tracker import Track
    clock, actuator, scheduler = armed_scheduler()
    config = deepcopy(live_config)
    config["live"] = {"verified_key_mapping":{"geometry_sha256":geometry_hash(live_geometry.document),
                       "reviewer":"synthetic fixture","evidence":"synthetic fixture only","keys":["F"]}}
    engine = LiveEngine(config,live_geometry,scheduler,clock,lambda *a: [])
    candidate = make_candidate(y=300,keys=["F"])
    tr = Track(7,candidate,bbox=candidate.bbox,status="confirmed",observations=10,first_time=999.8,
               history=[(1000,300,.4)],stable_keys=["F"],hit_history=[1000.02]*3,
               prediction=Prediction(velocity=180,eta=.02,hit_time=1000.02,uncertainty=.001,reason=""))
    engine.gate.update = lambda *a: "PLAYING"
    engine.tracker.update = lambda *a,**k: [tr]
    engine.process(CapturedFrame(0,hud(),1000,1000))
    assert len(scheduler.pending) == 1 and not actuator.calls
    clock.now = 1000.02
    tr.stable_keys = ["D","F"]
    tr.candidate = replace(candidate,candidate_keys=["D","F"])
    engine.process(CapturedFrame(1,hud(),1000.02,1000.02))
    assert not scheduler.pending and not actuator.calls
    tr.first_time = 1000.03  # simulate a broken/recycled upstream track ID
    tr.stable_keys, tr.candidate = ["F"], candidate
    tr.prediction = replace(tr.prediction,hit_time=1000.06)
    clock.now = 1000.04
    engine.process(CapturedFrame(2,hud(),1000.04,1000.04))
    assert engine.recycled_ids == {7} and not scheduler.pending
    assert engine.events == 1 and not actuator.calls


def test_rearming_does_not_execute_previous_arm_proposals(live_config,live_geometry,make_candidate):
    from src.tracker import Track
    clock, actuator, scheduler = armed_scheduler()
    config = deepcopy(live_config)
    config["live"] = {"verified_key_mapping":{"geometry_sha256":geometry_hash(live_geometry.document),
                       "reviewer":"synthetic fixture","evidence":"synthetic fixture only","keys":["F"]}}
    engine = LiveEngine(config,live_geometry,scheduler,clock,lambda *a: [])
    c = make_candidate(y=300,keys=["F"])
    tr = Track(7,c,bbox=c.bbox,status="confirmed",observations=10,first_time=999.8,
               history=[(1000,300,.4)],stable_keys=["F"],hit_history=[1000.02]*3,
               prediction=Prediction(velocity=180,eta=.02,hit_time=1000.02,uncertainty=.001,reason=""))
    engine.gate.update = lambda *a: "PLAYING"
    engine.tracker.update = lambda *a,**k: [tr]
    engine.process(CapturedFrame(0,hud(),1000,1000))
    old_generation = scheduler.arm_generation
    scheduler.toggle()
    scheduler.toggle()
    scheduler.poll()
    assert scheduler.arm_generation > old_generation
    clock.now += .01
    engine.process(CapturedFrame(1,hud(),1000.01,1000.01))
    assert not scheduler.pending and not actuator.calls


def test_disarm_attempts_all_key_releases_if_one_backend_call_fails():
    clock, actuator, scheduler = armed_scheduler()
    for key in ("S","D"):
        scheduler.offer(ActionIntent(key,(key,),clock.now+.01,.001))
    clock.now += .01
    scheduler.poll()
    released = []
    def release(key):
        released.append(key)
        if key == "S":
            raise OSError("synthetic release failure")
    actuator.key_up = release
    scheduler.disarm("F12")
    assert released == ["S","D"] and not scheduler.armed
    assert scheduler.error and set(scheduler.held) == {"S"}
    actuator.key_up = lambda key: released.append(key)
    scheduler.close()
    assert not scheduler.held




def test_global_hotkey_is_norepeat_and_f12_works_without_overlay_focus(monkeypatch):
    import src.windows_runtime as win
    stopped, toggled = threading.Event(), threading.Event()
    calls, delivered = [], [False]
    class Function:
        def __init__(self, fn): self.fn = fn
        def __call__(self, *args): return self.fn(*args)
    def peek(message, *args):
        if delivered[0]: return 0
        delivered[0] = True
        message._obj.message, message._obj.wParam = 0x0312, 1
        return 1
    api = SimpleNamespace(
        RegisterHotKey=Function(lambda *args: calls.append(("register",args)) or 1),
        UnregisterHotKey=Function(lambda *args: calls.append(("unregister",args)) or 1),
        PeekMessageW=Function(peek),
        GetAsyncKeyState=Function(lambda vk: 0x8000 if toggled.is_set() and vk == 0x7B else 0))
    monkeypatch.setattr(win,"user32",lambda: api)
    controls = win.GlobalControls(toggled.set,stopped.set,assist=True).start()
    assert stopped.wait(1)
    controls.close()
    assert toggled.is_set() and not controls.thread.is_alive()
    assert calls[0] == ("register",(None,1,0x4007,ord("Q")))
    assert calls[-1] == ("unregister",(None,1))


def test_hotkey_registration_failure_cannot_start_assist(monkeypatch):
    import src.windows_runtime as win
    class Function:
        def __init__(self, fn): self.fn = fn
        def __call__(self, *args): return self.fn(*args)
    api = SimpleNamespace(RegisterHotKey=Function(lambda *args: 0),
                          UnregisterHotKey=Function(lambda *args: 1), PeekMessageW=Function(lambda *args: 0))
    monkeypatch.setattr(win,"user32",lambda: api)
    with pytest.raises(RuntimeError,match="unavailable"):
        win.GlobalControls(lambda: pytest.fail("Failed registration toggled input"),lambda: None,assist=True).start()
