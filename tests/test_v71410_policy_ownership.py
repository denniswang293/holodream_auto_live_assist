import json

import pytest

from src.assist_config import resolve_config
from src.global_tap_timing import GlobalTapTimingEstimator, GlobalTapTimingPolicy
from src.particle_predictor import ParticlePredictor, ParticleTrackingPolicy
from src.simple_tracker import SimpleTracker, SimpleTrackerPolicy
from src.tap_intent import TapDeadlinePolicy, TapIntentManager


def test_module_policies_are_immutable_and_validate_fail_closed():
    policy = GlobalTapTimingPolicy.from_mapping({"enabled": True, "input_lead_ms": 60})
    with pytest.raises(Exception):
        policy.input_lead_ms = 10
    with pytest.raises(ValueError):
        GlobalTapTimingPolicy.from_mapping({"max_uncertainty_s": .3})
    with pytest.raises(ValueError):
        ParticleTrackingPolicy.from_mapping({"count": 16})
    with pytest.raises(ValueError):
        SimpleTrackerPolicy.from_mapping({"max_gap_s": 1.0})


def test_source_first_policy_snapshot_matches_current_work_values():
    resolved = resolve_config(profile="stable")
    global_policy = GlobalTapTimingPolicy.from_mapping(
        resolved.config["live"]["global_tap_timing"])
    deadline = TapDeadlinePolicy.from_mapping(
        resolved.config["live"]["tap_deadline_amend"])
    assert global_policy.input_lead_ms == 60
    assert global_policy.timing_reference == "physical_calibrated"
    assert deadline.freeze_window_ms == 30
    assert deadline.max_amend_step_ms == 40
    assert deadline.max_total_amend_ms == 80
    assert deadline.allow_earlier_amend is False


def test_legacy_manager_adapter_keeps_nested_deadline_values():
    manager = TapIntentManager(amend_enabled=True, freeze_window_ms=30,
                               max_amend_step_ms=40, max_total_amend_ms=80)
    assert manager.policy.to_dict() == {
        "enabled": True, "freeze_window_ms": 30, "max_amend_step_ms": 40,
        "max_total_amend_ms": 80, "allow_earlier_amend": False}


def test_particle_policy_is_tracking_only():
    pf = ParticlePredictor(policy=ParticleTrackingPolicy(count=64), timing_enabled=False)
    assert pf.timing_enabled is False
    assert pf.policy.count == 64
