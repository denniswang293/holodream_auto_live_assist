"""Visual Hold starts on a moving head and follows its green/yellow tail."""
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from src.assist_config import resolve_config, validate_effective_config
from src.geometry import CalibratedGeometry
from src.hold_visual import green_path_depth, green_runs, path_depth, path_runs
from src.hold_tracker import HoldTracker, select_hold_heads
from src.live_capture import CapturedFrame
from src.live_engine import LiveEngine
from src.live_input import ActionIntent, MockActuator, TapScheduler
from src.predictor import Prediction, Predictor
from src.tracker import Track
from src.tap_intent import TapIntent

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('body_height,depth,accepted', [(28,0,False), (60,0,True), (28,80,True)])
def test_small_yellow_head_contour_is_not_hold_body(make_candidate, body_height, depth, accepted):
    tracker = HoldTracker(min_path_px=40)
    c = replace(make_candidate(y=278, appearance='yellow_bar', keys=['F','J']),
                bbox=(282,275,158,3), path_bbox=(280,250,160,body_height), hold_path_px=depth)
    assert not tracker.observe([c], 1000.)
    assert bool(tracker.observe([c], 1000.02)) == accepted


@pytest.mark.parametrize('reverse', [False, True])
def test_finished_hold_cannot_follow_neighbouring_occupied_ribbon(monkeypatch, reverse):
    geometry, frame = scene()
    clock = SimpleNamespace(now=1000.)
    actuator = MockActuator()
    scheduler = TapScheduler('assist', actuator, clock=lambda: clock.now)
    scheduler.update_context(clock.now, 'PLAYING', True)
    scheduler.toggle(); scheduler.poll()
    engine = LiveEngine(resolve_config(profile='stable').config, geometry,
                        scheduler, clock=lambda: clock.now)
    holds = [ActionIntent('left', ('S',), 1000.01, .001, 'hold', .22, 'green_candidate'),
             ActionIntent('right', ('F',), 1000.01, .001, 'hold', .43, 'green_candidate')]
    for intent in holds[::-1] if reverse else holds:
        assert scheduler.offer(intent)
    clock.now = 1000.01; scheduler.poll()
    monkeypatch.setattr('src.live_engine.path_runs', lambda *args: [(.15,.30),(.37,.50)])
    engine._update_held_holds(frame, clock.now)
    # Right tail disappears; left ribbon is within the old 0.12 follow gap.
    # F must release after the normal gap, without stealing S's path.
    monkeypatch.setattr('src.live_engine.path_runs', lambda *args: [(.16,.32)])
    for t in [1000.03, 1000.06, 1000.10]:
        clock.now=t; engine._update_held_holds(frame,t)
    assert set(scheduler.held) == {'S'}
    assert ('up','F') in actuator.calls and ('up','S') not in actuator.calls
    scheduler.close()


@pytest.mark.parametrize('appearance', ['green_candidate', 'yellow_bar'])
def test_legacy_hold_uses_physical_crossing_and_explicit_lead(make_candidate, appearance):
    geometry, _ = scene()
    clock = SimpleNamespace(now=1000.30)
    scheduler = TapScheduler('assist', MockActuator(), clock=lambda: clock.now)
    engine = LiveEngine(resolve_config(profile='stable').config, geometry,
                        scheduler, clock=lambda: clock.now)
    candidate = replace(make_candidate(y=240, appearance=appearance, keys=['F']),
                        hold_path_px=80, note_type='unknown')
    track = Track(1, candidate)
    for i in range(16):
        head = replace(candidate, bbox=(280,237+4*i,70,6))
        track.observe(head, 1000.+i*.02, Predictor(), engine.trigger_y,
                      {'completion_y': geometry.hit_y, 'hold_input_lead_s': .06},
                      physical_hit_y=geometry.hit_y)
    physical = 1000.+(geometry.hit_y-240)/200
    assert track.prediction.physical_hit_time == pytest.approx(physical)
    assert track.prediction.hit_time == pytest.approx(physical-.060)
    assert track.history[-1][1] > engine.trigger_y
    assert track.status == 'confirmed' and track.prediction.hit_time > track.last_time
    assert engine._hold_press_at(track) == pytest.approx(physical-.060)
    # A highlight can hide the path on the following observation. It must
    # not switch an established Hold back to the old trigger clock.
    head = replace(candidate, bbox=(280,301,70,6), hold_path_px=0, path_bbox=None)
    track.observe(head, 1000.32, Predictor(), engine.trigger_y,
                  {'completion_y': geometry.hit_y, 'hold_input_lead_s': .06},
                  physical_hit_y=geometry.hit_y)
    assert track.prediction.physical_hit_time == pytest.approx(physical)
    assert track.prediction.hit_time == pytest.approx(physical-.060)
    # Arrival/processing delay must not shift either prediction's clock.
    clock.now += .03
    assert engine._hold_press_at(track) == pytest.approx(physical-.060)
    scheduler.close()


def test_hold_clock_transition_resets_only_mixed_basis_drift_history(make_candidate):
    candidate = replace(make_candidate(y=270, appearance='green_candidate', keys=['F', 'J']),
                        bbox=(322, 264, 121, 11),
                        path_bbox=(322, 190, 121, 85), hold_path_px=80)
    track = Track(7, candidate, history=[(1000.08, 250., .55)], bbox=candidate.bbox,
                  status='confirmed', was_confirmed=True, observations=10,
                  first_time=1000.0, last_time=1000.08,
                  # Deadlines from the earlier trigger-row clock.
                  hit_history=[1000.10, 1000.11, 1000.12])

    class ScriptedPredictor:
        cfg = {'min_velocity': 20}
        elapsed = 0.

        def __init__(self):
            self.physical_hits = iter([1000.29, 1000.30, 1000.46, 1000.47])

        def predict(self, history, hit_y):
            physical_hit = next(self.physical_hits)
            return Prediction(velocity=200., eta=.3, hit_time=physical_hit,
                              uncertainty=.001, reason='')

    predictor = ScriptedPredictor()
    kwargs = {'completion_y': 352, 'hold_input_lead_s': .06}
    for frame, t in enumerate((1000.13, 1000.15, 1000.17, 1000.19)):
        head = replace(candidate, bbox=(322, 264 + frame * 2, 121, 11))
        track.observe(head, t, predictor, 295.5, kwargs, physical_hit_y=325.5)
        assert track.physical_hold_clock
        assert track.hit_history == pytest.approx([1000.23, 1000.24, 1000.40, 1000.41][:frame + 1])
        if frame == 0:
            assert track.reason != 'hit_time_drift'
        if frame == 2:
            # The original drift threshold still catches a real change after
            # every estimate uses the same physical-row clock.
            assert track.reason == 'hit_time_drift'


@pytest.mark.parametrize('depth,velocity', [(0, None), (12, 600), (80, 1200)])
def test_pending_tap_avoids_hold_even_when_visible_tail_is_hidden_or_capped(depth, velocity):
    geometry, _ = scene()
    clock = SimpleNamespace(now=1000.)
    actuator = MockActuator()
    scheduler = TapScheduler('assist', actuator, clock=lambda: clock.now)
    scheduler.update_context(clock.now, 'PLAYING', True)
    scheduler.toggle(); scheduler.poll()
    engine = LiveEngine(resolve_config(profile='stable').config, geometry,
                        scheduler, clock=lambda: clock.now)
    tap = TapIntent('tap', 'K', 1000.25, scheduler.arm_generation, 1000., .001,
                    'verified', (.5,.83), 'cyan_bar', 250., valid_keys=('J','K'))
    engine.simple_core.intents.intents[tap.note_uid] = tap
    assert scheduler.offer(tap.action())
    hold = ActionIntent('hold', ('K',), 1000.1, .001, 'hold', .75, 'green_candidate')
    assert scheduler.offer(hold)
    track = SimpleNamespace(candidate=SimpleNamespace(hold_path_px=depth),
                            prediction=Prediction(velocity=velocity))
    engine._rekey_pending_taps_for_hold_conflict(track, hold, clock.now)
    replacement = scheduler.pending['tap']
    assert replacement.keys == ('J',) and replacement.hit_at == tap.hit_at
    for t in [1000.1, 1000.25, 1000.28]:
        clock.now = t
        scheduler.update_context(t, 'PLAYING', True)
        scheduler.poll()
    assert actuator.calls == [('down','K'), ('down','J'), ('up','J')]
    assert 'K' in scheduler.held
    scheduler.close()
    assert actuator.calls[-1] == ('up','K')


@pytest.mark.parametrize('same_path', [True, False])
@pytest.mark.parametrize('appearance', ['green_candidate', 'yellow_bar'])
def test_slide_tail_uses_current_visible_span_for_duplicate_hold_check(make_candidate, same_path, appearance):
    geometry, green = scene()
    clock = SimpleNamespace(now=1000.)
    actuator = MockActuator()
    scheduler = TapScheduler('assist', actuator, clock=lambda: clock.now, max_uncertainty=.1)
    scheduler.update_context(clock.now, 'PLAYING', True)
    scheduler.toggle(); scheduler.poll()
    engine = LiveEngine(resolve_config(profile='stable').config, geometry,
                        scheduler, clock=lambda: clock.now, detector=lambda *args: [])
    engine.gate.update = lambda *args: 'PLAYING'
    original = ActionIntent('original-slide', ('S',), 1000.01, .001, 'hold', .5, 'green_candidate')
    engine.hold_spans[original.event_id] = ((.05,.25), original.hit_at)
    engine.hold_colors[original.event_id] = 'green_candidate'
    assert scheduler.offer(original)
    clock.now = 1000.01; scheduler.poll()
    assert actuator.calls == [('down','S')]
    # The visible slide has moved into F/J, but the user rule keeps S held.
    c = replace(make_candidate(y=280, appearance=appearance, keys=['F','J'] if same_path else ['L']),
                u_min=.45 if same_path else .85, u_max=.55 if same_path else .98,
                hold_path_px=80)
    track = Track(2,c,history=[(1000.03,280.,.5 if same_path else .9)],bbox=c.bbox,
                  status='confirmed',observations=10,first_time=999.8,last_time=1000.03,
                  stable_keys=c.candidate_keys,hit_history=[1000.14]*3,
                  prediction=Prediction(velocity=300,eta=.11,hit_time=1000.14,uncertainty=.001))
    engine.tracker.update = lambda *args, **kwargs: [track]
    clock.now = 1000.03
    engine.process(CapturedFrame(1,green,clock.now,clock.now))
    if same_path and appearance == 'green_candidate':
        assert engine.last_decisions[2][1] == 'duplicate_hold_path'
        assert not scheduler.pending
    else:
        assert any(set(intent.keys).issubset(c.candidate_keys) for intent in scheduler.pending.values())
    assert actuator.calls == [('down','S')]
    scheduler.close()


@pytest.mark.parametrize('variant', ['connected', 'gap', 'other_color', 'full_head'])
def test_curved_hold_edge_requires_same_color_connection(make_candidate, variant):
    geometry, frame = scene()
    frame[:] = 0
    polygon = []
    for y in range(270, 326):
        # The ribbon moves from S at judgment to D/F at candidate height.
        u = .15 + (325-y)*.004
        left, right = geometry.bounds(y)
        polygon.append((round(left+(u-.07)*(right-left)), y))
    for y in range(325, 269, -1):
        u = .15 + (325-y)*.004
        left, right = geometry.bounds(y)
        polygon.append((round(left+(u+.07)*(right-left)), y))
    cv2.fillPoly(frame, [np.array(polygon, dtype=np.int32)], (0,255,0))
    if variant == 'gap':
        frame[298:316] = 0
    scheduler = TapScheduler('assist', MockActuator())
    engine = LiveEngine(resolve_config(profile='stable').config, geometry, scheduler)
    engine.hold_watch['old'] = {'u': .15}
    engine.hold_colors['old'] = 'green_candidate'
    c = replace(make_candidate(y=286, appearance='yellow_bar' if variant == 'other_color' else 'green_candidate', keys=['D','F']),
                bbox=(220,285,70,12 if variant == 'full_head' else 2), u_min=.27,u_max=.35)
    assert engine._edge_on_held_ribbon(frame, SimpleNamespace(candidate=c), {'old'}) == (variant == 'connected')
    scheduler.close()


@pytest.mark.parametrize('height', [3, 6, 12])
def test_adjacent_hold_candidate_is_not_suppressed_by_a_nearby_ribbon(make_candidate, height):
    geometry, frame = scene()
    clock = SimpleNamespace(now=1000.)
    scheduler = TapScheduler('assist', MockActuator(), clock=lambda: clock.now)
    scheduler.update_context(clock.now, 'PLAYING', True)
    scheduler.toggle(); scheduler.poll()
    engine = LiveEngine(resolve_config().config, geometry, scheduler,
                        clock=lambda: clock.now, detector=lambda *args: [])
    engine.gate.update = lambda *args: 'PLAYING'
    original = ActionIntent('original', ('S',), 1000.01, .001, 'hold', .15, 'green_candidate')
    engine.hold_spans['original'] = ((.05,.25), original.hit_at)
    engine.hold_colors['original'] = 'green_candidate'
    assert scheduler.offer(original)
    clock.now=1000.01; scheduler.poll()
    c = replace(make_candidate(y=280, appearance='green_candidate', keys=['F']),
                bbox=(280,280-height//2,80,height), u_min=.34,u_max=.49,hold_path_px=80)
    tr = Track(1,c,history=[(1000.,280.,.4)],bbox=c.bbox,status='confirmed',
               observations=10,first_time=999.8,last_time=1000.,stable_keys=['F'],
               hit_history=[1000.08]*3,prediction=Prediction(
                   velocity=200,eta=.08,hit_time=1000.08,uncertainty=.001))
    engine.tracker.update=lambda *args,**kwargs:[tr]
    engine.process(CapturedFrame(0,frame,clock.now,clock.now))
    assert len(scheduler.pending)==1
    assert engine.last_decisions[1][1]==''
    scheduler.close()


def test_hold_conflict_without_alternative_tap_key_logs_without_crashing():
    geometry, _ = scene()
    clock = SimpleNamespace(now=1000.)
    logs = []
    scheduler = TapScheduler('assist', MockActuator(), clock=lambda: clock.now,
                             on_log=logs.append)
    scheduler.update_context(clock.now, 'PLAYING', True)
    scheduler.toggle(); scheduler.poll()
    engine = LiveEngine(resolve_config(profile='stable').config, geometry,
                        scheduler, clock=lambda: clock.now)
    tap = TapIntent('tap-one-key', 'K', 1000.12, scheduler.arm_generation,
                    1000., .001, 'real_head', (.67, .83), 'cyan_bar', 280.,
                    valid_keys=('K',))
    engine.simple_core.intents.intents[tap.note_uid] = tap
    assert scheduler.offer(tap.action())
    hold = ActionIntent('hold', ('K',), 1000.06, .001, 'hold', .75, 'yellow_bar')
    track = SimpleNamespace(candidate=SimpleNamespace(hold_path_px=80),
                            prediction=Prediction(velocity=200))
    engine._rekey_pending_taps_for_hold_conflict(track, hold, clock.now)
    rejection = logs[-1]
    assert rejection['action'] == 'rekey_rejected'
    assert rejection['reason'] == 'alternative_key_not_verified'
    assert rejection['event_id'] == tap.note_uid and rejection['note_type'] == 'tap'
    assert scheduler.pending[tap.note_uid] == tap.action()
    assert tap.key == 'K' and tap.revision == 0
    scheduler.close()


def test_moving_yellow_head_with_highlight_gap_uses_hold_scheduler():
    geometry, _ = scene()
    clock = SimpleNamespace(now=1000.)
    actuator, logs = MockActuator(), []
    scheduler = TapScheduler('assist', actuator, clock=lambda: clock.now,
                             max_age=.06, max_uncertainty=.1, on_log=logs.append)
    scheduler.update_context(clock.now, 'PLAYING', True)
    scheduler.toggle(); scheduler.poll()
    engine = LiveEngine(resolve_config(profile='stable').config, geometry,
                        scheduler, clock=lambda: clock.now)
    engine.gate.update = lambda *args: 'PLAYING'
    for i in range(27):
        capture = 1000. + i*.016
        clock.now = capture + .005
        y = 220 + 4*i
        hsv = np.zeros((404,720,3), np.uint8)
        hsv[y-80:y-3,308:362] = (27,110,170)
        hsv[y:y+9,280:381] = (27,220,250)
        frame = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        engine.process(CapturedFrame(i, frame, capture, capture))
        scheduler.poll()
    downs = [row for row in logs if row['action'] == 'key_down']
    assert len(downs) == 1 and downs[0]['note_type'] == 'hold'
    assert actuator.calls == [('down', downs[0]['key'])]
    # Focus loss must still release the sustained key immediately.
    scheduler.update_context(clock.now, 'PLAYING', False)
    scheduler.poll()
    assert not scheduler.held
    assert actuator.calls[-1] == ('up', downs[0]['key'])
    scheduler.close()


def test_duplicate_hold_edge_keeps_wide_head_and_path_evidence(make_candidate):
    path = (362, 234, 110, 22)
    head = replace(make_candidate(y=241, appearance='green_candidate', keys=['J', 'K']),
                   bbox=(355, 234, 118, 14), u_min=.49, u_max=.75,
                   path_bbox=path, hold_path_px=0)
    edge = replace(make_candidate(y=254, appearance='green_candidate', keys=['J', 'K']),
                   bbox=(414, 252, 59, 5), u_min=.61, u_max=.74,
                   path_bbox=path, hold_path_px=80)
    selected = select_hold_heads([edge, head])
    assert len(selected) == 1
    assert selected[0].bbox == head.bbox
    assert selected[0].candidate_keys == ['J', 'K']
    assert selected[0].hold_path_px == 80


def test_multiple_hold_contours_in_one_frame_do_not_confirm(make_candidate):
    tracker = HoldTracker(min_path_px=40, min_head_observations=2)
    head = replace(make_candidate(y=278, appearance='green_candidate', keys=['J', 'K']),
                   path_bbox=(362,164,182,126), hold_path_px=80)
    fragment = replace(head, bbox=(439,260,96,21), candidate_keys=['K'])
    assert tracker.observe([head, fragment, head], 1000.) == []
    assert tracker.evidence[0].observations == 1
    assert tracker.observe([head], 1000.02) == [head]
    assert tracker.evidence[0].observations == 2


def test_distinct_hold_paths_and_lanes_remain_separate(make_candidate):
    base = replace(make_candidate(y=241, appearance='green_candidate', keys=['J', 'K']),
                   u_min=.49, u_max=.75, path_bbox=(362, 234, 110, 22))
    other_path = replace(base, path_bbox=(363, 236, 110, 22))
    other_lane = replace(base, u_min=.10, u_max=.24, candidate_keys=['S', 'D'])
    other_color = replace(base, appearance='yellow_bar')
    second_head_same_path = replace(base, bbox=(355, 262, 118, 12))
    edge_for_other_key = replace(base, bbox=(414, 252, 59, 5),
                                 candidate_keys=['K'], u_min=.61, u_max=.74)
    assert select_hold_heads([base, other_path, other_lane, other_color,
                              second_head_same_path, edge_for_other_key]) == [
        base, other_path, other_lane, other_color,
        second_head_same_path, edge_for_other_key]


def test_live_engine_passes_one_same_path_head_to_hold_tracker(make_candidate):
    geometry, frame = scene()
    clock = SimpleNamespace(now=1000.)
    scheduler = TapScheduler('assist', MockActuator(), clock=lambda: clock.now,
                             max_age=.06)
    head = replace(make_candidate(y=241, appearance='green_candidate', keys=['J', 'K']),
                   bbox=(355, 234, 118, 14), u_min=.49, u_max=.75,
                   path_bbox=(362, 234, 110, 22), hold_path_px=0)
    edge = replace(head, bbox=(414, 252, 59, 5), u_min=.61, u_max=.74,
                   hold_path_px=80)
    engine = LiveEngine(resolve_config(profile='stable').config, geometry,
                        scheduler, clock=lambda: clock.now,
                        detector=lambda *args, **kwargs: [head, edge])
    engine.gate.update = lambda *args: 'PLAYING'
    observed = []
    engine.tracker.update = lambda candidates, *args, **kwargs: (
        observed.append(candidates) or [])
    engine.process(CapturedFrame(0, frame, 1000., 1000.))
    clock.now = 1000.016
    engine.process(CapturedFrame(1, frame, clock.now, clock.now))
    assert len(observed[-1]) == 1
    assert observed[-1][0].bbox == head.bbox
    assert observed[-1][0].hold_path_px == 80


def scene(appearance='green_candidate'):
    geometry=CalibratedGeometry(json.loads((ROOT/'config/geometry_live_assist.json').read_text(encoding='utf-8-sig')))
    frame=np.zeros((404,720,3),np.uint8)
    color=(0,255,255) if appearance=='yellow_bar' else (0,255,0)
    cv2.rectangle(frame,(335,230),(384,316),color,-1)
    return geometry,frame


@pytest.mark.parametrize('appearance', ['green_candidate', 'yellow_bar'])
def test_pressed_key_strip_cannot_keep_finished_hold_alive(appearance):
    geometry, frame = scene(appearance)
    frame[:] = 0
    color = (0,255,0) if appearance == 'green_candidate' else (0,255,255)
    cv2.rectangle(frame, (30,313), (680,338), color, -1)
    clock = SimpleNamespace(now=1000.)
    actuator = MockActuator()
    scheduler = TapScheduler('assist', actuator, clock=lambda: clock.now)
    scheduler.update_context(clock.now, 'PLAYING', True)
    scheduler.toggle(); scheduler.poll()
    engine = LiveEngine(resolve_config(profile='stable').config, geometry, scheduler,
                        clock=lambda: clock.now)
    intent = ActionIntent('finished', ('S',), 1000.01, .001, 'hold', .15, appearance)
    assert scheduler.offer(intent)
    clock.now=1000.01; scheduler.poll()
    for t in (1000.01, 1000.05, 1000.10, 1000.20):
        clock.now=t; engine._update_held_holds(frame,t)
    assert not scheduler.held
    assert actuator.calls == [('down','S'), ('up','S')]
    scheduler.close()


def test_tail_release_waits_for_travel_to_physical_line():
    geometry, frame = scene()
    clock = SimpleNamespace(now=1000.)
    scheduler = TapScheduler('assist', MockActuator(), clock=lambda: clock.now)
    scheduler.update_context(clock.now, 'PLAYING', True)
    scheduler.toggle(); scheduler.poll()
    engine = LiveEngine(resolve_config(profile='stable').config, geometry, scheduler,
                        clock=lambda: clock.now)
    intent = ActionIntent('slow-tail', ('S',), 1000.01, .001, 'hold', .5, 'green_candidate')
    engine.hold_pending_coast[intent.event_id] = {'tail_travel_s': .185}
    assert scheduler.offer(intent)
    clock.now=1000.01; scheduler.poll()
    engine._update_held_holds(frame,clock.now)
    frame[:] = 0
    clock.now=1000.12; engine._update_held_holds(frame,clock.now)
    assert 'S' in scheduler.held
    clock.now=1000.21; engine._update_held_holds(frame,clock.now)
    assert not scheduler.held
    scheduler.close()


def test_small_judgment_flash_fragments_cannot_renew_a_hold():
    geometry, frame = scene()
    frame[:] = 0
    probe_y = round(geometry.document['live_measurement']['judgment_bar_top_y'] - 6)
    edges = geometry.lane_bounds_at_y(probe_y)
    # This is the size of the narrow green fragments present in the run's
    # post-tail hit flash (about 0.02 normalized playfield width).
    x0 = round(edges[0] + (edges[-1] - edges[0]) * .54)
    cv2.rectangle(frame, (x0, probe_y - 2), (x0 + 14, probe_y + 2), (0, 255, 0), -1)
    clock = SimpleNamespace(now=1000.)
    actuator = MockActuator()
    scheduler = TapScheduler('assist', actuator, clock=lambda: clock.now)
    scheduler.update_context(clock.now, 'PLAYING', True)
    scheduler.toggle(); scheduler.poll()
    engine = LiveEngine(resolve_config(profile='stable').config, geometry, scheduler,
                        clock=lambda: clock.now)
    assert path_runs(frame, geometry, probe_y, 'green_candidate')
    assert not engine._hold_tail_runs(frame, probe_y, 'green_candidate')
    intent = ActionIntent('flash-fragment', ('S',), 1000.01, .001, 'hold', .54,
                          'green_candidate')
    assert scheduler.offer(intent)
    clock.now = 1000.01; scheduler.poll()
    for t in (1000.01, 1000.05, 1000.10):
        clock.now = t
        engine._update_held_holds(frame, t)
    assert not scheduler.held
    assert actuator.calls == [('down', 'S'), ('up', 'S')]
    scheduler.close()


@pytest.mark.parametrize('appearance', ['green_candidate', 'yellow_bar'])
@pytest.mark.parametrize('continuous', [True, False])
@pytest.mark.parametrize('tail_disappears', [True, False])
def test_hold_white_hit_flash_requires_continuous_ribbon(appearance, continuous, tail_disappears):
    geometry, frame = scene(appearance)
    if not continuous:
        # An isolated colored head/particle on one sample row is insufficient.
        frame[:] = 0
        color = (0,255,0) if appearance == 'green_candidate' else (0,255,255)
        cv2.rectangle(frame, (335,299), (384,304), color, -1)
    probe_y = geometry.document['live_measurement']['judgment_bar_top_y']-6
    # Hide both direct observation rows. This is genuinely upper-only
    # evidence and must still expire after the original 250ms bridge.
    cv2.rectangle(frame, (0,round(probe_y)-7), (719,330), (255,255,255), -1)
    clock = SimpleNamespace(now=1000.)
    actuator = MockActuator()
    scheduler = TapScheduler('assist', actuator, clock=lambda: clock.now)
    scheduler.update_context(clock.now, 'PLAYING', True)
    scheduler.toggle(); scheduler.poll()
    engine = LiveEngine(resolve_config(profile='stable').config, geometry,
                        scheduler, clock=lambda: clock.now)
    intent = ActionIntent('flash-hold', ('S',), 1000.01, .001, 'hold', .5, appearance)
    assert scheduler.offer(intent)
    clock.now = 1000.01; scheduler.poll()
    for t in (1000.01, 1000.05, 1000.10, 1000.15):
        clock.now = t
        engine._update_held_holds(frame, t)
    assert ('S' in scheduler.held) == continuous
    # Following the visual ribbon must never switch from the original S key.
    assert [call for call in actuator.calls if call[0] == 'down'] == [('down','S')]
    if continuous:
        if tail_disappears:
            frame[:] = 0
        # Upper-row evidence cannot renew itself indefinitely. Even if it
        # remains visible, the physical row must return within 250ms.
        clock.now = 1000.40
        engine._update_held_holds(frame, clock.now)
        assert not scheduler.held
    scheduler.close()
    assert actuator.calls == [('down','S'), ('up','S')]


def test_green_path_depth_and_judgment_row_ignore_a_short_green_bar():
    geometry,frame=scene()
    assert green_path_depth(frame,geometry,300,.5)>=40
    assert green_runs(frame,geometry,304)
    short=np.zeros_like(frame)
    cv2.rectangle(short,(335,287),(384,300),(0,255,0),-1)
    assert green_path_depth(short,geometry,300,.5)<40
    assert not green_runs(short,geometry,304)


def test_yellow_path_evidence_is_color_specific():
    geometry,yellow=scene('yellow_bar')
    assert path_depth(yellow,geometry,300,.5,'yellow_bar')>=40
    assert path_runs(yellow,geometry,304,'yellow_bar')
    assert not path_runs(yellow,geometry,304,'green_candidate')


@pytest.mark.parametrize('appearance',['green_candidate','yellow_bar'])
def test_hold_keeps_key_down_until_its_own_tail_leaves_judgment_row(make_candidate,appearance):
    geometry,green=scene(appearance)
    config=json.loads((ROOT/'config.json').read_text())
    config['live']=json.loads((ROOT/'config/live_assist.json').read_text(encoding='utf-8-sig'))
    clock=SimpleNamespace(now=1000.)
    actuator=MockActuator()
    scheduler=TapScheduler('assist',actuator,clock=lambda:clock.now,max_uncertainty=.1)
    scheduler.update_context(clock.now,'PLAYING',True);scheduler.toggle();scheduler.poll()
    engine=LiveEngine(config,geometry,scheduler,clock=lambda:clock.now,detector=lambda *args:[])
    engine.gate.update=lambda *args:'PLAYING'
    c=replace(make_candidate(y=300,appearance=appearance,keys=['F','J']),
              u_min=.42,u_max=.58,hold_path_px=80)
    tr=Track(1,c,history=[(1000.,300.,.5)],bbox=c.bbox,status='confirmed',
             observations=10,first_time=999.8,last_time=1000.,stable_keys=['F','J'],
             hit_history=[1000.04]*3,
             prediction=Prediction(velocity=180,eta=.04,hit_time=1000.04,uncertainty=.001))
    engine.tracker.update=lambda *args,**kwargs:[tr]
    engine.process(CapturedFrame(0,green,1000.,1000.))
    assert len(scheduler.pending)==1
    assert next(iter(scheduler.pending.values())).note_type=='hold'
    assert next(iter(scheduler.pending.values())).path_appearance==appearance
    clock.now=1000.04;scheduler.poll()
    assert actuator.calls==[('down','F')]
    clock.now=1000.08
    engine.process(CapturedFrame(1,green,clock.now,clock.now))
    assert actuator.calls==[('down','F')]
    blank=np.zeros_like(green)
    # The other color at the same position cannot keep this Hold down.
    other=(0,255,0) if appearance=='yellow_bar' else (0,255,255)
    cv2.rectangle(blank,(335,230),(384,316),other,-1)
    clock.now=1000.12
    engine.process(CapturedFrame(2,blank,clock.now,clock.now))
    assert actuator.calls==[('down','F')]
    clock.now=1000.21
    engine.process(CapturedFrame(3,blank,clock.now,clock.now))
    assert actuator.calls==[('down','F'),('up','F')]
    assert scheduler.sent_holds==1 and scheduler.sent_taps==0
    scheduler.close()


@pytest.mark.parametrize('appearance',['green_candidate','yellow_bar'])
def test_focus_loss_releases_hold_immediately(make_candidate,appearance):
    geometry,green=scene(appearance)
    config=json.loads((ROOT/'config.json').read_text())
    config['live']=json.loads((ROOT/'config/live_assist.json').read_text(encoding='utf-8-sig'))
    clock=SimpleNamespace(now=1000.)
    actuator=MockActuator()
    scheduler=TapScheduler('assist',actuator,clock=lambda:clock.now,max_uncertainty=.1)
    scheduler.update_context(clock.now,'PLAYING',True);scheduler.toggle();scheduler.poll()
    engine=LiveEngine(config,geometry,scheduler,clock=lambda:clock.now,detector=lambda *args:[])
    engine.gate.update=lambda *args:'PLAYING'
    c=replace(make_candidate(y=300,appearance=appearance,keys=['F','J']),
              u_min=.42,u_max=.58,hold_path_px=80)
    tr=Track(1,c,history=[(1000.,300.,.5)],bbox=c.bbox,status='confirmed',
             observations=10,first_time=999.8,last_time=1000.,stable_keys=['F','J'],
             hit_history=[1000.04]*3,
             prediction=Prediction(velocity=180,eta=.04,hit_time=1000.04,uncertainty=.001))
    engine.tracker.update=lambda *args,**kwargs:[tr]
    engine.process(CapturedFrame(0,green,1000.,1000.))
    clock.now=1000.04;scheduler.poll()
    assert actuator.calls==[('down','F')]
    clock.now=1000.05
    engine.process(CapturedFrame(1,green,clock.now,clock.now),focused=False)
    assert actuator.calls==[('down','F'),('up','F')]
    assert not scheduler.armed and not scheduler.held
    scheduler.close()


def test_scheduled_hold_survives_brief_lost_track_at_original_deadline(make_candidate):
    geometry, frame = scene('yellow_bar')
    config = json.loads((ROOT/'config.json').read_text())
    config['live'] = json.loads((ROOT/'config/live_assist.json').read_text(encoding='utf-8-sig'))
    clock = SimpleNamespace(now=1000.)
    actuator = MockActuator()
    scheduler = TapScheduler('assist', actuator, clock=lambda: clock.now, max_uncertainty=.1)
    scheduler.update_context(clock.now, 'PLAYING', True)
    scheduler.toggle(); scheduler.poll()
    engine = LiveEngine(config, geometry, scheduler, clock=lambda: clock.now, detector=lambda *args: [])
    engine.gate.update = lambda *args: 'PLAYING'
    candidate = replace(make_candidate(y=272, appearance='yellow_bar', keys=['D', 'F']),
                        bbox=(240, 266, 90, 12), u_min=.28, u_max=.46, hold_path_px=80)
    track = Track(1, candidate, history=[(1000., 272., .37)], bbox=candidate.bbox,
                  status='confirmed', observations=10, first_time=999.8, last_time=1000.,
                  stable_keys=['D', 'F'], hit_history=[1000.08]*3,
                  prediction=Prediction(velocity=300, eta=.08, hit_time=1000.08, uncertainty=.001))
    engine.tracker.update = lambda *args, **kwargs: [track]
    engine.process(CapturedFrame(0, frame, 1000., 1000.))
    original = next(iter(scheduler.pending.values()))
    assert original.note_type == 'hold'
    clock.now = 1000.03
    track.status = 'lost'; track.missed = 1
    engine.process(CapturedFrame(1, frame, clock.now, clock.now))
    assert scheduler.pending[original.event_id] is original
    assert scheduler.pending[original.event_id].hit_at == original.hit_at
    clock.now = original.hit_at
    scheduler.update_context(clock.now, 'PLAYING', True)
    scheduler.poll()
    assert actuator.calls == [('down', original.keys[0])]
    scheduler.close()


@pytest.mark.parametrize('profile,expected_delay_s,earlier_amend', [
    ('stable', 0.0, True),
    ('tap-earlier', 0.0, True),
    ('timing-balance', .015, True),
])
def test_hold_start_delay_profile_reaches_scheduler_without_changing_tap_amend(
        make_candidate, profile, expected_delay_s, earlier_amend):
    geometry, frame = scene('green_candidate')
    config = resolve_config(profile=profile).config
    assert config['live']['tap_deadline_amend']['allow_earlier_amend'] is earlier_amend
    clock = SimpleNamespace(now=1000.)
    scheduler = TapScheduler('assist', MockActuator(), clock=lambda: clock.now, max_uncertainty=.1)
    scheduler.update_context(clock.now, 'PLAYING', True)
    scheduler.toggle(); scheduler.poll()
    engine = LiveEngine(config, geometry, scheduler, clock=lambda: clock.now, detector=lambda *args: [])
    engine.gate.update = lambda *args: 'PLAYING'
    candidate = replace(make_candidate(y=280, appearance='green_candidate', keys=['D', 'F']),
                        bbox=(240, 274, 90, 12), u_min=.28, u_max=.46, hold_path_px=80)
    track = Track(1, candidate, history=[(1000., 280., .37)], bbox=candidate.bbox,
                  status='confirmed', observations=10, first_time=999.8, last_time=1000.,
                  stable_keys=['D', 'F'], hit_history=[1000.1]*3,
                  prediction=Prediction(velocity=300, eta=.1, hit_time=1000.1, uncertainty=.001))
    engine.tracker.update = lambda *args, **kwargs: [track]
    engine.process(CapturedFrame(0, frame, 1000., 1000.))
    pending = next(iter(scheduler.pending.values()))
    assert pending.note_type == 'hold'
    assert pending.hit_at == pytest.approx(1000.1 + expected_delay_s)
    track.prediction = replace(track.prediction, physical_hit_time=1000.2)
    assert engine._hold_press_at(track) == pytest.approx(1000.2 - .060 + expected_delay_s)
    scheduler.close()


def test_hold_start_delay_above_bound_is_rejected():
    config = resolve_config(profile='timing-balance').config
    config['live']['hold_visual']['start_delay_ms'] = 21
    with pytest.raises(ValueError, match='start_delay_ms'):
        validate_effective_config(config)


def test_scheduled_hold_lost_track_grace_expires_without_new_deadline(make_candidate):
    geometry, frame = scene('green_candidate')
    config = json.loads((ROOT/'config.json').read_text())
    config['live'] = json.loads((ROOT/'config/live_assist.json').read_text(encoding='utf-8-sig'))
    clock = SimpleNamespace(now=1000.)
    actuator = MockActuator()
    scheduler = TapScheduler('assist', actuator, clock=lambda: clock.now, max_uncertainty=.1)
    scheduler.update_context(clock.now, 'PLAYING', True)
    scheduler.toggle(); scheduler.poll()
    engine = LiveEngine(config, geometry, scheduler, clock=lambda: clock.now, detector=lambda *args: [])
    engine.gate.update = lambda *args: 'PLAYING'
    candidate = replace(make_candidate(y=272, appearance='green_candidate', keys=['D', 'F']),
                        bbox=(240, 266, 90, 12), u_min=.28, u_max=.46, hold_path_px=80)
    track = Track(1, candidate, history=[(1000., 272., .37)], bbox=candidate.bbox,
                  status='confirmed', observations=10, first_time=999.8, last_time=1000.,
                  stable_keys=['D', 'F'], hit_history=[1000.25]*3,
                  prediction=Prediction(velocity=180, eta=.25, hit_time=1000.25, uncertainty=.001))
    engine.tracker.update = lambda *args, **kwargs: [track]
    engine.process(CapturedFrame(0, frame, 1000., 1000.))
    original = next(iter(scheduler.pending.values()))
    clock.now = 1000.14
    track.status = 'lost'; track.missed = 1
    engine.process(CapturedFrame(1, frame, clock.now, clock.now))
    assert original.event_id not in scheduler.pending
    assert not actuator.calls
    scheduler.close()


@pytest.mark.parametrize('fragment_appearance,fragment_keys,fragment_span,retained', [
    ('green_candidate', ['D', 'F'], (.28, .46), True),
    ('yellow_bar', ['D', 'F'], (.28, .46), False),
    ('green_candidate', ['J'], (.28, .46), False),
    ('green_candidate', ['D'], (.75, .90), False),
])
def test_committed_hold_fragment_retains_only_same_color_key_and_span(
        make_candidate, fragment_appearance, fragment_keys, fragment_span, retained):
    geometry, frame = scene('green_candidate')
    config = json.loads((ROOT/'config.json').read_text())
    config['live'] = json.loads((ROOT/'config/live_assist.json').read_text(encoding='utf-8-sig'))
    clock = SimpleNamespace(now=1000.)
    actuator = MockActuator()
    scheduler = TapScheduler('assist', actuator, clock=lambda: clock.now, max_uncertainty=.1)
    scheduler.update_context(clock.now, 'PLAYING', True)
    scheduler.toggle(); scheduler.poll()
    engine = LiveEngine(config, geometry, scheduler, clock=lambda: clock.now, detector=lambda *args: [])
    engine.gate.update = lambda *args: 'PLAYING'
    candidate = replace(make_candidate(y=280, appearance='green_candidate', keys=['D', 'F']),
                        bbox=(240, 274, 90, 12), u_min=.28, u_max=.46, hold_path_px=80)
    track = Track(1, candidate, history=[(1000., 280., .37)], bbox=candidate.bbox,
                  status='confirmed', observations=10, first_time=999.8, last_time=1000.,
                  stable_keys=['D', 'F'], hit_history=[1000.08]*3,
                  prediction=Prediction(velocity=300, eta=.08, hit_time=1000.08, uncertainty=.001))
    engine.tracker.update = lambda *args, **kwargs: [track]
    engine.process(CapturedFrame(0, frame, 1000., 1000.))
    original = next(iter(scheduler.pending.values()))
    assert engine.occlusion_commits
    clock.now = 1000.02
    track.candidate = replace(candidate, bbox=(240, 276, 90, 1),
                              appearance=fragment_appearance, candidate_keys=fragment_keys,
                              u_min=fragment_span[0], u_max=fragment_span[1],
                              hold_path_px=0, path_bbox=None)
    track.history = [(clock.now, 276.5, .37)]
    engine.process(CapturedFrame(1, frame, clock.now, clock.now))
    assert (original.event_id in scheduler.pending) is retained
    if retained:
        assert scheduler.pending[original.event_id] is original
        clock.now = original.hit_at
        scheduler.update_context(clock.now, 'PLAYING', True)
        scheduler.poll()
        assert actuator.calls == [('down', original.keys[0])]
    else:
        assert not actuator.calls
    scheduler.close()


@pytest.mark.parametrize('cross_y',[313.,327.])
def test_committed_hold_survives_early_target_crossing_only_until_physical_line(make_candidate,cross_y):
    geometry,green=scene()
    config=json.loads((ROOT/'config.json').read_text())
    config['live']=json.loads((ROOT/'config/live_assist.json').read_text(encoding='utf-8-sig'))
    clock=SimpleNamespace(now=1000.);actuator=MockActuator()
    scheduler=TapScheduler('assist',actuator,clock=lambda:clock.now,max_uncertainty=.1)
    scheduler.update_context(clock.now,'PLAYING',True);scheduler.toggle();scheduler.poll()
    engine=LiveEngine(config,geometry,scheduler,clock=lambda:clock.now,detector=lambda *args:[])
    engine.gate.update=lambda *args:'PLAYING'
    c=replace(make_candidate(y=300,appearance='green_candidate',keys=['D','F']),
              bbox=(280,294,80,12),u_min=.30,u_max=.49,hold_path_px=80)
    tr=Track(1,c,history=[(1000.,300.,.4)],bbox=c.bbox,status='confirmed',
             observations=10,first_time=999.8,last_time=1000.,stable_keys=['D','F'],
             hit_history=[1000.04]*3,
             prediction=Prediction(velocity=300,eta=.04,hit_time=1000.04,uncertainty=.001))
    engine.tracker.update=lambda *args,**kwargs:[tr]
    engine.process(CapturedFrame(0,green,1000.,1000.))
    original=next(iter(scheduler.pending.values()))
    assert original.note_type=='hold' and engine.occlusion_commits
    clock.now=1000.03;tr.status='tentative';tr.prediction=Prediction(reason='past_hit_line')
    tr.history=[(clock.now,cross_y,.4)]
    tr.candidate=replace(c,bbox=(280,int(cross_y-6),80,12))
    engine.process(CapturedFrame(1,green,clock.now,clock.now))
    if cross_y<geometry.hit_y:
        assert next(iter(scheduler.pending.values()))==original
        clock.now=1000.04;scheduler.poll()
        assert actuator.calls==[('down',original.keys[0])]
    else:
        assert not scheduler.pending and not actuator.calls
    scheduler.close()


def test_hold_scheduler_rejects_missing_path_and_caps_duration():
    clock=SimpleNamespace(now=1000.)
    actuator=MockActuator()
    scheduler=TapScheduler('assist',actuator,clock=lambda:clock.now,max_hold_s=.5)
    scheduler.update_context(clock.now,'PLAYING',True);scheduler.toggle();scheduler.poll()
    assert not scheduler.offer(ActionIntent('bad',('F',),1000.04,.001,'hold'))
    assert not scheduler.offer(ActionIntent('bad_color',('F',),1000.04,.001,'hold',.5,'pink_candidate'))
    assert scheduler.offer(ActionIntent('good',('F',),1000.04,.001,'hold',.5))
    clock.now=1000.04;scheduler.poll()
    assert actuator.calls==[('down','F')]
    clock.now=1000.55;scheduler.update_context(clock.now,'PLAYING',True);scheduler.poll()
    assert actuator.calls==[('down','F'),('up','F')]
    scheduler.close()


def test_wide_hold_head_suppresses_its_narrow_edge_fragment(make_candidate):
    geometry,green=scene()
    config=json.loads((ROOT/'config.json').read_text())
    config['live']=json.loads((ROOT/'config/live_assist.json').read_text(encoding='utf-8-sig'))
    clock=SimpleNamespace(now=1000.)
    scheduler=TapScheduler('assist',MockActuator(),clock=lambda:clock.now,max_uncertainty=.1)
    scheduler.update_context(clock.now,'PLAYING',True);scheduler.toggle();scheduler.poll()
    engine=LiveEngine(config,geometry,scheduler,clock=lambda:clock.now,detector=lambda *args:[])
    engine.gate.update=lambda *args:'PLAYING'
    tracks=[]
    for i,keys,u0,u1 in [(1,['F','J'],.34,.66),(2,['F'],.35,.49)]:
        c=replace(make_candidate(y=280,appearance='green_candidate',keys=keys),
                  u_min=u0,u_max=u1,hold_path_px=80)
        tracks.append(Track(i,c,history=[(1000.,280.,(u0+u1)/2)],bbox=c.bbox,
                            status='confirmed',observations=10,first_time=999.8,last_time=1000.,
                            stable_keys=keys,hit_history=[1000.12]*3,
                            prediction=Prediction(velocity=180,eta=.12,hit_time=1000.12,uncertainty=.001)))
    engine.tracker.update=lambda *args,**kwargs:tracks
    engine.process(CapturedFrame(0,green,1000.,1000.))
    assert len(scheduler.pending)==1
    assert next(iter(scheduler.pending.values())).note_type=='hold'
    assert engine.last_decisions[2][1]=='duplicate_hold_path'
    scheduler.close()
