from types import SimpleNamespace

import pytest

from src.assist_config import resolve_config
from src.global_tap_timing import GlobalTapTimingEstimator
from src.assist_profiles import profile_config
from src.detector import Candidate
from src.simple_tracker import SimpleTracker
from src.tap_planner import TapPlanner
from src.live_input import MockActuator, TapScheduler
from src.simple_core import SimpleAssistCore


def track(track_id, history, *, status="confirmed"):
    return SimpleNamespace(track_id=track_id, history=history, status=status,
                           confirmed_note_type="tap", missed=0)


def _good(track_id):
    ts = [1.00, 1.15, 1.30, 1.45, 1.60]
    ys = [20, 70, 120, 170, 230]
    return track(track_id, list(zip(ts, ys)))


def _high_variance(track_id):
    ts = [1.10, 1.22, 1.34, 1.46, 1.58]
    ys = [20, 35, 50, 65, 80]
    return track(track_id, list(zip(ts, ys)))


def _estimator(enabled):
    return GlobalTapTimingEstimator({
        "enabled": True, "mode": "active", "allow_active": True,
        "guarded_reuse_enabled": enabled, "guarded_reuse_max_age_ms": 80,
        "timing_reference": "trigger_legacy", "input_lead_ms": 0,
        "min_tracks": 2, "min_samples": 3, "profile_segments": 4,
        "profile_ttl_ms": 3000, "max_eta_s": .45, "max_uncertainty_s": .04,
    })


def test_profile_ab_only_changes_guarded_reuse_and_keeps_lead_and_earlier_flag():
    stable = resolve_config(profile="stable").config
    rescue = resolve_config(profile="stable-global-rescue").config
    stable["live"]["tap_deadline_amend"]["allow_earlier_amend"] = None
    rescue["live"]["tap_deadline_amend"]["allow_earlier_amend"] = None
    assert stable["live"]["global_tap_timing"]["input_lead_ms"] == 60
    assert rescue["live"]["global_tap_timing"]["input_lead_ms"] == 60
    assert stable["live"]["global_tap_timing"]["guarded_reuse_enabled"] is False
    assert rescue["live"]["global_tap_timing"]["guarded_reuse_enabled"] is True
    stable_guarded = stable["live"]["global_tap_timing"].pop("guarded_reuse_enabled")
    rescue_guarded = rescue["live"]["global_tap_timing"].pop("guarded_reuse_enabled")
    assert stable_guarded is False and rescue_guarded is True
    assert stable == rescue
    assert stable["live"]["tap_deadline_amend"] == rescue["live"]["tap_deadline_amend"]


def test_guarded_reuse_recovers_only_transient_speed_variation_with_fresh_cache():
    baseline = _estimator(False)
    rescue = _estimator(True)
    good = [_good(1), _good(2)]
    assert baseline.update(good, trigger_y=220, capture_timestamp=1.61, now=1.61).source == "global_profile"
    assert rescue.update(good, trigger_y=220, capture_timestamp=1.61, now=1.61).source == "global_profile"
    bad = [_high_variance(3), _high_variance(4)]
    model_a = baseline.update(bad, trigger_y=220, capture_timestamp=1.66, now=1.66)
    model_b = rescue.update(bad, trigger_y=220, capture_timestamp=1.66, now=1.66)
    assert model_a.reason == model_b.reason == "speed_variation_too_high"
    eta_a = baseline.estimate(bad[0], trigger_y=220, now=1.66)
    eta_b, meta = rescue.guarded_reuse_estimate(bad[0], trigger_y=220, now=1.66)
    assert eta_a.status == "NOT_READY"
    assert eta_b is not None and eta_b.status == "AVAILABLE"
    assert eta_b.timing_source == "global_profile_guarded_reuse"
    assert meta["passed_rescue_gate"] is True
    assert eta_b.uncertainty_s <= .04


@pytest.mark.parametrize("capture,reason", [
    (1.691, "CACHE_OLDER_THAN_80MS"),
    (1.60, "CACHE_NEGATIVE_AGE"),
])
def test_guarded_reuse_rejects_expired_or_negative_cache(capture, reason):
    estimator = _estimator(True)
    good = [_good(1), _good(2)]
    estimator.update(good, trigger_y=220, capture_timestamp=1.61, now=1.61)
    bad = [_high_variance(3), _high_variance(4)]
    estimator.update(bad, trigger_y=220, capture_timestamp=capture, now=capture)
    _, meta = estimator.guarded_reuse_estimate(bad[0], trigger_y=220, now=capture)
    assert meta["passed_rescue_gate"] is False
    assert meta["rescue_rejected_reason"] == reason


def test_guarded_reuse_never_uses_bootstrap_or_coasting_track():
    estimator = _estimator(True)
    single = [_good(1)]
    model = estimator.update(single, trigger_y=220, capture_timestamp=1.61, now=1.61)
    assert model.source != "global_profile"
    _, meta = estimator.guarded_reuse_estimate(single[0], trigger_y=220, now=1.61)
    assert meta["passed_rescue_gate"] is False
    assert meta["rescue_rejected_reason"] in {"ORIGINAL_MODEL_NOT_SPEED_VARIATION", "NO_CACHE"}
    estimator = _estimator(True)
    estimator.update([_good(1), _good(2)], trigger_y=220, capture_timestamp=1.61, now=1.61)
    bad = _high_variance(3); bad.status = "coasting"
    estimator.update([_high_variance(4), _high_variance(5)], trigger_y=220,
                     capture_timestamp=1.66, now=1.66)
    _, meta = estimator.guarded_reuse_estimate(bad, trigger_y=220, now=1.66)
    assert meta["passed_rescue_gate"] is False
    assert meta["rescue_rejected_reason"] == "TRACK_NOT_CURRENT"


def test_guarded_cache_is_invalidated_by_reset_and_geometry_change():
    estimator = _estimator(True)
    estimator.update([_good(1), _good(2)], trigger_y=220,
                     capture_timestamp=1.61, now=1.61)
    estimator.reset()
    estimator.update([_high_variance(3), _high_variance(4)], trigger_y=220,
                     capture_timestamp=1.66, now=1.66)
    _, meta = estimator.guarded_reuse_estimate(_high_variance(3), trigger_y=220, now=1.66)
    assert meta["rescue_rejected_reason"] in {"NO_CACHE", "ORIGINAL_MODEL_NOT_SPEED_VARIATION"}

    estimator = _estimator(True)
    estimator.update([_good(1), _good(2)], trigger_y=220,
                     capture_timestamp=1.61, now=1.61)
    estimator.update([_high_variance(3), _high_variance(4)], trigger_y=221,
                     capture_timestamp=1.66, now=1.66)
    _, meta = estimator.guarded_reuse_estimate(_high_variance(3), trigger_y=221, now=1.66)
    assert meta["rescue_rejected_reason"] in {"NO_CACHE", "GEOMETRY_MISMATCH", "ORIGINAL_MODEL_NOT_SPEED_VARIATION"}


def test_a_rejects_b_produces_one_legal_global_proposal():
    a = _estimator(False)
    b = _estimator(True)
    good = [_good(1), _good(2)]
    a.update(good, trigger_y=220, capture_timestamp=1.61, now=1.61)
    b.update(good, trigger_y=220, capture_timestamp=1.61, now=1.61)
    history = [(t, y, .40) for t, y in _high_variance(3).history]
    candidate = Candidate((260, 77, 60, 7), "cyan_bar", .95, .34, .46,
                          ["F"], "tap", body_bbox=(260, 77, 60, 7))
    track_obj = SimpleTracker({"confirm_observations": 3},
                              {"min_observations": 3})._new_track(candidate, 1.10)
    track_obj.track_id = 3; track_obj.history = history
    track_obj.status = "confirmed"; track_obj.confirmed_note_type = "tap"
    track_obj.observations = 5; track_obj.stable_keys = ["F"]; track_obj.missed = 0
    bad_tracks = [track(3, _high_variance(3).history), _high_variance(4)]
    model_a = a.update(bad_tracks, trigger_y=220, capture_timestamp=1.66, now=1.66)
    model_b = b.update(bad_tracks, trigger_y=220, capture_timestamp=1.66, now=1.66)
    eta_a = a.estimate(bad_tracks[0], trigger_y=220, now=1.66)
    eta_b, _ = b.guarded_reuse_estimate(bad_tracks[0], trigger_y=220, now=1.66)
    scheduler = TapScheduler("assist", MockActuator(), clock=lambda: 1.66)
    scheduler.update_context(1.66, "PLAYING", True, True)
    scheduler.armed = True; scheduler.arm_generation = 1
    planner = TapPlanner({"max_eta_s": .45}, min_y=10)
    decisions_a, proposals_a = planner.global_plan([track_obj], {3: eta_a}, 1.66, {"F"}, scheduler,
                                                   note_uids={3: "uid-a"})
    decisions, proposals = planner.global_plan([track_obj], {3: eta_b}, 1.66, {"F"}, scheduler,
                                                note_uids={3: "uid-b"})
    assert model_a.reason == model_b.reason == "speed_variation_too_high"
    assert not proposals_a and decisions_a[3].reason == "speed_variation_too_high"
    assert decisions[3].status == "schedule" and proposals[3].key == "F"
    scheduler.close()


def test_simple_core_routes_rescue_through_intent_and_scheduler():
    scheduler = TapScheduler("assist", MockActuator(), clock=lambda: 1.66)
    scheduler.update_context(1.66, "PLAYING", True, True)
    scheduler.armed = True; scheduler.arm_generation = 1
    core = SimpleAssistCore(
        session_id="rescue", tracker_cfg={"confirm_observations": 3},
        particle_cfg={"min_observations": 3}, hit_y=220,
        event_cfg={"max_eta_s": .45}, min_y=10, known_keys={"F"},
        timing_cfg={"global_tap_timing": {
            "enabled": True, "mode": "active", "allow_active": True,
            "guarded_reuse_enabled": True, "guarded_reuse_max_age_ms": 80,
            "timing_reference": "trigger_legacy", "input_lead_ms": 0,
            "min_tracks": 2, "min_samples": 3, "profile_segments": 4,
            "profile_ttl_ms": 3000, "max_eta_s": .45, "max_uncertainty_s": .04},
            "tap_deadline_amend": {"enabled": True, "freeze_window_ms": 30,
                                   "max_amend_step_ms": 40, "max_total_amend_ms": 80}},
        profile_name="stable-global-rescue")
    # Prime the cache through the same core owner.
    good_tracks = []
    for index in (1, 2):
        c = Candidate((260, 20, 60, 7), "cyan_bar", .95, .34, .46,
                      ["F"], "tap", body_bbox=(260, 20, 60, 7))
        t = core.tracker._new_track(c, 1.0)
        t.track_id = index; t.history = [(time, y, .40) for time, y in zip(
            [1.0, 1.15, 1.30, 1.45, 1.60], [20, 70, 120, 170, 230])]
        t.status = "confirmed"; t.confirmed_note_type = "tap"; t.observations = 5
        t.stable_keys = ["F"]; t.missed = 0
        good_tracks.append(t)
    core.plan_tracks(good_tracks, 1.61, 1.61, scheduler, enabled=True)
    bad_tracks = []
    for index in (3, 4):
        c = Candidate((260, 77, 60, 7), "cyan_bar", .95, .34, .46,
                      ["F"], "tap", body_bbox=(260, 77, 60, 7))
        t = core.tracker._new_track(c, 1.1)
        t.track_id = index; t.history = [(time, y, .40) for time, y in zip(
            [1.10, 1.22, 1.34, 1.46, 1.58], [20, 35, 50, 65, 80])]
        t.status = "confirmed"; t.confirmed_note_type = "tap"; t.observations = 5
        t.stable_keys = ["F"]; t.missed = 0
        bad_tracks.append(t)
    _, accepted = core.plan_tracks(bad_tracks, 1.66, 1.66, scheduler, enabled=True)
    rows = core.drain_global_rescue_rows()
    assert accepted and any(row.get("scheduler_action") == "scheduled" for row in rows)
    assert any(row.get("model_source") == "global_profile_guarded_reuse" for row in rows)
    assert len(scheduler.pending) == 1
    scheduler.close()
