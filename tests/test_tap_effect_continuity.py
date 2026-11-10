from collections import deque
from dataclasses import replace
from pathlib import Path

import cv2
import pytest

from src.model import Detection, Geometry, Note
from src.perception import Perception
from src.scheduler import Action, MockActuator, Scheduler
from src.tracking import Cap, Tracker


def established_tap():
    tracker = Tracker(Geometry())
    face = Detection((240, 200, 60, 20), 'yellow', 'tap', ('K',), .9)
    note = Note('note:1', 'tap', 'yellow', face, origin_y=40,
                confirmed=True, observations=40)
    note.head = deque([(10+i*.02, 195+i*5, *face.span) for i in range(6)], maxlen=32)
    tracker.notes[note.uid] = note
    cap = Cap('cap:1', face, samples=deque(note.head, maxlen=16),
              votes={'tap': 40}, note_uid=note.uid)
    tracker.caps[cap.uid] = cap
    return tracker, note, cap


@pytest.mark.parametrize('role', ['body', 'hold_head', 'hold_tail'])
def test_real_tap_plate_survives_yellow_ribbon_appearance(role):
    tracker, note, cap = established_tap()
    candidate = replace(cap.detection, bbox=(240, 207, 60, 20), kind=role,
                        above=84, below=84)
    tracker.update([candidate], 10.14)
    assert len(tracker.notes) == 1
    assert note.last_seen == 10.14
    assert note.kind == note.detection.kind == 'tap'
    assert note.full_head_observations == 0


@pytest.mark.parametrize('change', ['real_hold', 'early_head', 'unconfirmed', 'late_origin', 'fragment'])
def test_no_blanket_conversion_of_holds_noise_or_fragments(change):
    tracker, note, cap = established_tap()
    candidate = replace(cap.detection, kind='hold_head', above=84)
    if change == 'real_hold': note.kind = 'hold'
    if change == 'early_head': note.full_head_observations = 2
    if change == 'unconfirmed': note.confirmed = False
    if change == 'late_origin': note.origin_y = 205
    if change == 'fragment': candidate = replace(candidate, bbox=(240, 207, 60, 4))
    assert not tracker._complete_tap_in_effect(cap, candidate)


def test_tap_semantics_do_not_bypass_spatial_association():
    tracker, note, cap = established_tap()
    candidate = replace(cap.detection, bbox=(0, 207, 40, 20), kind='hold_tail')
    tracker.update([candidate], 10.14)
    assert note.last_seen == 10.10
    assert cap.detection.kind == 'tap'


def test_recovery_face_cannot_create_or_confirm_a_note():
    tracker = Tracker(Geometry())
    face = Detection((140, 270, 70, 25), 'cyan', 'tap', ('F',), .9, recovery_only=True)
    assert tracker.update([face], 10.) == []
    assert not tracker.caps


def test_late_yellow_bevel_does_not_gain_a_note_origin():
    tracker = Tracker(Geometry())
    for i in range(5):
        face = Detection((140, 240+i*4, 30, 3), 'yellow', 'hold_head', ('F',), .9)
        tracker.update([face], 10+i*.02)
    assert not tracker.notes
    # A complete face can still create an identity, using its own actual
    # first full-face position, not the earlier bevel's convenient origin.
    tracker.update([replace(face,bbox=(140,262,30,12),kind='tap')],10.10)
    assert len(tracker.notes)==1
    note=next(iter(tracker.notes.values()))
    assert note.origin_y==274
    assert not note.confirmed


def test_thin_spawn_area_plate_can_still_start_a_track():
    tracker = Tracker(Geometry())
    face = Detection((140, 30, 30, 3), 'yellow', 'tap', ('F',), .9)
    assert len(tracker.update([face],10.))==1


def test_scheduler_still_requires_arm_and_releases_hold_on_focus_loss():
    clock = [10.]
    focused = [True]
    actuator = MockActuator()
    s = Scheduler(actuator, clock=lambda: clock[0], focus_check=lambda: focused[0])
    s.update_context(10., True, True)
    action = Action('one', 'J', 'hold', 10.02, .02)
    assert s.offer(action).reason == 'disarmed'
    s.toggle(); s.poll()
    assert s.offer(action)
    clock[0] = 10.02; s.poll()
    assert actuator.calls == [('down', 'J')]
    focused[0] = False
    s.poll()
    assert actuator.calls == [('down', 'J'), ('up', 'J')]
    assert not s.armed


def test_consumed_uid_cannot_fire_again():
    clock = [10.]
    actuator = MockActuator()
    s = Scheduler(actuator, clock=lambda: clock[0])
    s.update_context(10., True, True); s.toggle(); s.poll()
    assert s.offer(Action('one', 'K', 'tap', 10.01, .02))
    clock[0] = 10.01; s.poll()
    clock[0] = 10.04; s.poll()
    assert s.offer(Action('one', 'K', 'tap', 10.05, .02)).reason == 'uid_used'
    assert actuator.calls == [('down', 'K'), ('up', 'K')]


def test_recorded_complete_yellow_face_is_not_a_fragment():
    g = Geometry()
    image = cv2.imread(str(Path(__file__).parent/'fixtures/tap_effect/frame_3460.png'))
    detections = Perception(g).detect(image)
    face = next(d for d in detections if d.color=='yellow' and
                abs(g.native_bbox(d.bbox)[0]-434)<=3 and abs(d.bbox[1]-214)<=2)
    assert face.bbox[3]>=8
    # The current image alone still sees the golden judgment effect as band.
    # The correction must rely on this same plate's earlier real Tap identity.
    assert face.kind in ('body', 'hold_head', 'hold_tail')
    tracker, note, cap = established_tap()
    tracker._observe(cap, face, 10.14)
    assert note.detection.kind == 'tap'
    assert note.kind == 'tap'


def test_recorded_cyan_face_recovery_stays_existing_track_only():
    g = Geometry()
    image = cv2.imread(str(Path(__file__).parent/'fixtures/tap_effect/frame_6294.png'))
    recovery = [d for d in Perception(g).detect(image) if d.color=='cyan' and d.recovery_only]
    assert recovery
    assert any(d.bbox[3]>=8 for d in recovery)
    tracker = Tracker(g)
    assert tracker.update(recovery, 10.) == []
