"""The identity path can retain an existing intent only under live safety gates."""

import json
from pathlib import Path
from types import SimpleNamespace

from src.calibration import geometry_hash
from src.geometry import CalibratedGeometry
from src.live_engine import LiveEngine
from src.live_input import ActionIntent, MockActuator, TapScheduler
from tests.test_pf_identity_continuity import build_confirmed_tap


ROOT = Path(__file__).resolve().parents[1]


def make_engine():
    geometry = CalibratedGeometry(json.loads(
        (ROOT / "config/geometry_live_assist.json").read_text(encoding="utf-8-sig")))
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8-sig"))
    live = json.loads((ROOT / "config/live_assist_v5.json").read_text(encoding="utf-8-sig"))
    config["live"] = live
    clock = SimpleNamespace(now=.12)
    actuator = MockActuator()
    scheduler = TapScheduler("assist", actuator, clock=lambda: clock.now,
                             focus_check=lambda: True, modifiers_check=lambda: False)
    scheduler.armed = True
    scheduler.arm_generation = 2
    scheduler.update_context(.12, "PLAYING", True, True)
    engine = LiveEngine(config, geometry, scheduler, clock=lambda: clock.now,
                        detector=lambda *args: [])
    return engine, scheduler, clock


def test_unknown_retains_same_key_and_original_deadline_only(make_candidate):
    tracker, tr = build_confirmed_tap(make_candidate)
    # Feed the degraded frame through the real PF tracker update.
    tracker.update([make_candidate(y=178, appearance="neutral_candidate", keys=["F"])], 6 / 60)
    engine, scheduler, clock = make_engine()
    event_id = f"{engine.session_id}:{tr.track_id}"
    intent = ActionIntent(event_id, ("F",), .15, .01, "tap")
    assert scheduler.offer(intent)
    tr.selected_key = "F"
    tr.source_track_ids = [tr.track_id]
    tr.physical_note_uid = "physical:one"
    engine.input_eligible_ids[tr.track_id] = scheduler.arm_generation
    valid = engine._tap_identity_intent_still_valid(
        tr, event_id, intent, .12, state="PLAYING", focused=True, roi_valid=True, stale=False)
    assert valid
    assert scheduler.pending[event_id] is intent
    assert scheduler.pending[event_id].keys == ("F",)
    assert scheduler.pending[event_id].hit_at == .15
    assert not any(action[0] == "down" for action in scheduler.actuator.calls)
    scheduler.close()


def test_identity_retention_fails_closed_for_focus_stale_expiry_and_wrong_key(make_candidate):
    tracker, tr = build_confirmed_tap(make_candidate)
    tracker.update([make_candidate(y=178, appearance="neutral_candidate", keys=["F"])], 6 / 60)
    engine, scheduler, clock = make_engine()
    event_id = f"{engine.session_id}:{tr.track_id}"
    intent = ActionIntent(event_id, ("F",), .15, .01, "tap")
    scheduler.offer(intent)
    tr.selected_key = "F"
    tr.source_track_ids = [tr.track_id]
    tr.physical_note_uid = "physical:one"
    engine.input_eligible_ids[tr.track_id] = scheduler.arm_generation
    args = dict(state="PLAYING", focused=True, roi_valid=True, stale=False)
    assert not engine._tap_identity_intent_still_valid(tr,event_id,intent,.12,**{**args,"focused":False})
    assert not engine._tap_identity_intent_still_valid(tr,event_id,intent,.12,**{**args,"stale":True})
    assert not engine._tap_identity_intent_still_valid(tr,event_id,intent,.17,**args)
    tr.stable_keys = ["D"]
    assert not engine._tap_identity_intent_still_valid(tr,event_id,intent,.12,**args)
    scheduler.close()

