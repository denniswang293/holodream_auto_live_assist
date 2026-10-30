from dataclasses import replace

from src.detector import Candidate
from src.hold_tracker import HoldTracker
from src.judgment_time import JudgmentTimeEstimator
from src.live_input import ActionIntent, MockActuator, TapScheduler


def hold_candidate(u_min=.4, u_max=.55, path=20, appearance="green_candidate"):
    return Candidate((100, 200, 80, 8), appearance, .8, u_min, u_max, ["F"],
                     "unknown", path_bbox=(100, 170, 80, 30), hold_path_px=path)


def test_hold_tracker_requires_two_observations_and_keeps_short_dropout():
    tracker = HoldTracker(min_path_px=40, min_head_observations=2,
                          max_gap_s=.1, dropout_grace_ms=120)
    assert tracker.observe([hold_candidate(path=12)], 1.0) == []
    accepted = tracker.observe([hold_candidate(path=18)], 1.03)
    assert len(accepted) == 1
    assert tracker.evidence[0].accepted
    assert tracker.evidence[0].continuity_confidence == 1.0
    tracker.observe([], 1.10)
    assert tracker.evidence
    tracker.observe([], 1.27)
    assert not tracker.evidence


def test_judgment_time_does_not_activate_without_labeled_samples():
    estimator = JudgmentTimeEstimator(enabled=True, mode="active", offset_ms=15, min_samples=2)
    estimate = estimator.estimate(10.0)
    assert estimate.status == "shadow_insufficient_samples"
    assert estimate.game_judgment_at == 10.0
    estimator.add_labeled_sample(10.0, 10.01)
    estimator.add_labeled_sample(20.0, 20.02)
    estimate = estimator.estimate(30.0)
    assert estimate.status == "active"
    assert estimate.game_judgment_at == 30.015


def test_scheduler_amend_rejects_stale_revision_and_keeps_one_press():
    now = [10.0]
    actuator = MockActuator()
    scheduler = TapScheduler("assist", actuator, clock=lambda: now[0])
    scheduler.update_context(10.0, "PLAYING", True, True)
    scheduler.armed = True
    scheduler.arm_generation = 1
    first = ActionIntent("note", ("F",), 10.2, .01, revision=0)
    assert scheduler.offer(first).accepted
    amended = replace(first, hit_at=10.22, revision=1)
    assert scheduler.amend_pending(amended, expected_revision=0).accepted
    stale = replace(first, hit_at=10.24, revision=1)
    assert scheduler.amend_pending(stale, expected_revision=0).reason == "stale_intent_revision"
    now[0] = 10.22
    scheduler.update_context(10.18, "PLAYING", True, True)
    scheduler.poll()
    assert actuator.calls == [("down", "F")]
    scheduler.close()
