from dataclasses import replace
from types import SimpleNamespace

import pytest

from src.engine import Engine
from src.model import Detection, Geometry
from src.scheduler import MockActuator, Scheduler
from src.tracking import Tracker


def observed(color, kind, *, top=70, count=5):
    tracker = Tracker(Geometry())
    face = Detection((140, top, 60, 12), color, kind, ('F',), .9)
    for i in range(count):
        tracker.update([replace(face, bbox=(140, top+i*5, 60, 12))], 10+i*.02)
    note = next(iter(tracker.notes.values()))
    return tracker, note, tracker.caps['cap:1']


@pytest.mark.parametrize('color', ['green', 'yellow'])
def test_confirmed_hold_cannot_become_tap_under_late_marker(color):
    tracker, note, cap = observed(color, 'hold_head')
    assert note.confirmed and note.kind_locked and note.kind == 'hold'
    for i in range(4):
        face = replace(cap.detection, bbox=(140, 250+i*5, 60, 12),
                       kind='tap', tap_marker=True)
        tracker._observe(cap, face, 10.10+i*.02)
    assert note.kind == 'hold'
    assert not note.tap_marker
    assert note.tap_marker_observations == 0
    # Preserve the actual observation, not an invented Hold-shaped image.
    assert note.detection.kind == 'tap'
    assert note.last_seen == pytest.approx(10.16)


@pytest.mark.parametrize('color', ['green', 'yellow'])
def test_confirmed_tap_cannot_gain_hold_evidence_near_judgment(color):
    tracker, note, cap = observed(color, 'tap')
    assert note.kind_locked and note.kind == 'tap'
    for i in range(4):
        tracker._observe(cap, replace(cap.detection, kind='hold_head',
                         bbox=(140, 250+i*5, 60, 12)), 10.10+i*.02)
    assert note.kind == 'tap'
    assert note.full_head_observations == 0


def test_motion_confirmation_or_late_birth_alone_does_not_lock_type():
    tracker, note, cap = observed('green', 'plate_fragment')
    assert note.confirmed and not note.kind_locked
    tracker._observe(cap, replace(cap.detection, kind='hold_head'), 10.10)
    tracker._observe(cap, replace(cap.detection, kind='hold_head'), 10.12)
    assert note.kind == 'hold' and note.kind_locked
    _, late, _ = observed('green', 'hold_head', top=200)
    assert late.confirmed and not late.kind_locked


def test_locked_semantics_cannot_bypass_motion_association():
    tracker, note, cap = observed('green', 'hold_head')
    last_seen = note.last_seen
    tracker.update([replace(cap.detection, bbox=(0, 280, 25, 12), kind='tap')], 10.10)
    assert note.last_seen == last_seen


def test_engine_does_not_correct_a_locked_hold_to_tap():
    tracker, note, _ = observed('yellow', 'hold_head')
    # Even pre-existing contradictory evidence cannot trigger input conversion.
    note.tap_marker_observations = 2
    note.last_tap_marker_at = 10.08
    scheduler = Scheduler(MockActuator(), clock=lambda: 10.08)
    engine = Engine(Geometry(), scheduler, 'config/reference_timing.json')
    engine.tracker = tracker
    scheduler.correct_hold_to_tap = lambda uid: pytest.fail('locked Hold was converted')
    frame = SimpleNamespace(sequence=5, captured_at=10.08, acquired_at=10.08,
                            focused=True, roi_valid=True)
    _, rows = engine.decide(dict(frame=frame, playing=True, notes=[note],
                                detections=[], cpu_ms=0), processed_at=10.08)
    assert note.kind == 'hold'
    assert rows[0]['kind_locked'] is True
