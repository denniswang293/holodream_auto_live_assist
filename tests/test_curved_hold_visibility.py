from pathlib import Path
from types import SimpleNamespace
from dataclasses import replace

import cv2
import numpy as np
import pytest

from src.assist_config import resolve_config
from src.calibration import load_calibration
from src.hold_visual import connected_hold_runs, continuous_hold_body
from src.live_engine import LiveEngine
from src.live_input import ActionIntent, MockActuator, TapScheduler
from src.detector import Candidate, detect


def test_narrow_curve_edge_requires_connected_wider_body():
    # Source video 1434, capture 401022.3930763: lower edge is below the
    # quarter-lane width filter, but connects through the two real rows above.
    lower, middle, upper = [(.020,.044)], [(0.,.054)], [(.023,.043)]
    assert connected_hold_runs(lower, middle, upper, .25/6) == lower
    assert not connected_hold_runs(lower, [], upper, .25/6)
    assert not connected_hold_runs(lower, middle, [], .25/6)
    assert not connected_hold_runs(lower, [(.4,.6)], upper, .25/6)
    assert not connected_hold_runs(lower, lower, lower, .25/6)


@pytest.mark.parametrize('dark_gap,cap_kind', [
    (False,'tail'), (True,'tail'), (False,'none'), (False,'future_head')])
def test_recorded_curved_hold_does_release_without_tail_evidence(dark_gap,cap_kind):
    root = Path(__file__).resolve().parents[1]
    geometry = load_calibration(root/'config/geometry_live_assist.json')
    frame = cv2.imread(str(root/'tests/fixtures/curved_hold_white_occlusion.png'))
    if dark_gap:
        frame[305:310] = 0
    clock = SimpleNamespace(now=401022.20)
    actuator = MockActuator()
    scheduler = TapScheduler('assist', actuator, clock=lambda: clock.now, max_age=.06)
    scheduler.update_context(clock.now, 'PLAYING', True)
    scheduler.toggle(); scheduler.poll()
    intent = ActionIntent('curve', ('S',), 401022.21, .001, 'hold', .0543488597, 'green_candidate')
    assert scheduler.offer(intent)
    clock.now = 401022.21; scheduler.poll()
    engine = LiveEngine(resolve_config(profile='stable').config, geometry, scheduler,
                        clock=lambda: clock.now)
    # The actual baseline watch state immediately preceding the false release.
    engine.hold_watch['curve'] = dict(u=.0543488597, start=401022.21,
        last_direct=401022.2161287, last_visible=401022.4505226, span=(0.,.1442527))
    engine.hold_pending_coast['curve'] = {'tail_travel_s': .08}
    clock.now = 401022.5552873
    scheduler.update_context(401022.5329713, 'PLAYING', True)
    candidates = detect(frame, geometry, engine.config['key_map'], engine.dc)
    if cap_kind == 'none':
        candidates = []
    elif cap_kind == 'future_head':
        candidates = [replace(c,path_bbox=(82,200,158,112)) for c in candidates]
    if cap_kind != 'tail':
        # Only a short residual near-line cloud, without a continuous body.
        frame[:292] = 0
    engine._update_held_holds(frame, clock.now, candidates)
    if dark_gap or cap_kind != 'tail':
        assert not scheduler.held
        assert actuator.calls == [('down', 'S'), ('up', 'S')]
        scheduler.close()
        return
    assert set(scheduler.held) == {'S'}
    assert engine.hold_watch['curve']['last_direct'] == 401022.2161287
    assert engine.hold_watch['curve']['observation_y'] == engine.hold_probe_y-4
    assert actuator.calls == [('down', 'S')]
    # Actual image support disappearing still releases the original key.
    clock.now = 401022.71
    scheduler.update_context(clock.now, 'PLAYING', True)
    engine._update_held_holds(np.zeros_like(frame), clock.now)
    assert not scheduler.held
    assert actuator.calls == [('down', 'S'), ('up', 'S')]
    scheduler.close()


@pytest.mark.parametrize('evidence', ['body','short_cloud','dark_gap','missing_cap','departed_particles'])
def test_recorded_midbody_flash_does_not_require_departing_tail_cap(evidence):
    root = Path(__file__).resolve().parents[1]
    geometry = load_calibration(root/'config/geometry_live_assist.json')
    frame = cv2.imread(str(root/'tests/fixtures/curved_hold_midbody_occlusion.png'))
    if evidence == 'departed_particles':
        frame = cv2.imread(str(root/'tests/fixtures/hold_departed_particles.png'))
    if evidence == 'short_cloud':
        frame[:292] = 0
    elif evidence == 'dark_gap':
        frame[305:310] = 0
    clock = SimpleNamespace(now=417646.20)
    actuator = MockActuator()
    scheduler = TapScheduler('assist',actuator,clock=lambda: clock.now)
    scheduler.update_context(clock.now,'PLAYING',True)
    scheduler.toggle(); scheduler.poll()
    try:
        assert scheduler.offer(ActionIntent('curve',('S',),417646.237955,.001,
                                           'hold',.0648826241,'green_candidate'))
        clock.now = 417646.237955; scheduler.poll()
        engine = LiveEngine(resolve_config(profile='stable').config,geometry,scheduler,
                            clock=lambda: clock.now)
        engine.hold_watch['curve'] = dict(u=.0648826241,start=clock.now,
            last_direct=417646.3181773,last_visible=417646.5137933,
            span=(.0265094629,.1802524240))
        engine.hold_pending_coast['curve'] = {'tail_travel_s':.08}
        if evidence == 'departed_particles':
            engine.hold_watch['curve']['u'] = .3071592047
            engine.hold_watch['curve']['span'] = (.2269871601,.2962430918)
        clock.now = 417646.63
        scheduler.update_context(417646.6171018,'PLAYING',True)
        candidates = detect(frame,geometry,engine.config['key_map'],engine.dc)
        if evidence in ('missing_cap','short_cloud'):
            # Blacking out the upper image must not invent an artificial cap
            # along the new crop boundary.
            candidates = []
        engine._update_held_holds(frame,clock.now,candidates)
        assert bool(scheduler.held) == (evidence == 'body')
        if evidence == 'body':
            assert engine.hold_watch['curve']['last_direct'] == 417646.3181773
            assert actuator.calls == [('down','S')]
            clock.now += .15
            engine._update_held_holds(np.zeros_like(frame),clock.now)
            assert actuator.calls == [('down','S'),('up','S')]
    finally:
        scheduler.close()


def test_continuous_body_requires_every_row_and_broad_upper_endpoint():
    rows = [[(.1,.2)] for _ in range(8)]
    assert continuous_hold_body(rows,(.1,.2),.04)
    broken = [list(row) for row in rows]; broken[4] = []
    assert not continuous_hold_body(broken,(.1,.2),.04)
    detached = [list(row) for row in rows]; detached[4] = [(.4,.5)]
    assert not continuous_hold_body(detached,(.1,.2),.04)
    rows[-1] = [(.1,.12)]
    assert not continuous_hold_body(rows,(.1,.2),.04)


def test_strong_body_and_weak_fallback_cannot_reuse_one_color_band(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    geometry = load_calibration(root/'config/geometry_live_assist.json')
    clock = SimpleNamespace(now=1000.)
    actuator = MockActuator()
    scheduler = TapScheduler('assist',actuator,clock=lambda: clock.now)
    scheduler.update_context(clock.now,'PLAYING',True)
    scheduler.toggle(); scheduler.poll()
    try:
        engine = LiveEngine(resolve_config(profile='stable').config,geometry,scheduler,
                            clock=lambda: clock.now)
        for uid,key,u,span in [('a','S',.1,(.1,.2)),('b','F',.36,(.4,.5))]:
            assert scheduler.offer(ActionIntent(uid,(key,),1000.01,.001,'hold',u,'green_candidate'))
            engine.hold_watch[uid] = dict(u=u,span=span,start=1000.01,
                                         last_visible=1000.01,last_direct=1000.01)
        clock.now=1000.01; scheduler.poll()
        monkeypatch.setattr('src.live_engine.path_runs',lambda f,g,y,a:
                            [(.21,.33)] if 275 <= y <= 303 else [])
        cap = Candidate((160,200,130,15),'green_candidate',1.,.2,.4,['D'],
                        path_bbox=(150,200,180,120))
        clock.now=1000.31
        engine._update_held_holds(np.full((404,720,3),255,np.uint8),clock.now,[cap])
        assert set(scheduler.held) == {'S'}
        assert ('up','F') in actuator.calls
    finally:
        scheduler.close()


def test_projected_near_curve_cannot_keep_its_neighbor_alive(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    geometry = load_calibration(root/'config/geometry_live_assist.json')
    frame = np.full((404,720,3), 255, np.uint8)
    clock = SimpleNamespace(now=1000.)
    actuator = MockActuator()
    scheduler = TapScheduler('assist', actuator, clock=lambda: clock.now)
    scheduler.update_context(clock.now, 'PLAYING', True)
    scheduler.toggle(); scheduler.poll()
    engine = LiveEngine(resolve_config(profile='stable').config, geometry, scheduler,
                        clock=lambda: clock.now)
    for uid,key,u,span in [('left','S',.2,(.14,.25)),('right','F',.35,(.32,.43))]:
        assert scheduler.offer(ActionIntent(uid,(key,),1000.01,.001,'hold',u,'green_candidate'))
        engine.hold_watch[uid] = dict(u=u,span=span,start=1000.01,
                                     last_visible=1000.01,last_direct=1000.01)
    clock.now=1000.01; scheduler.poll()
    def rows(_frame,_geometry,y,_appearance):
        if y == 307: return [(.32,.43)]
        if y == 303: return [(.205,.33)]
        if y in (299,295): return [(.20,.35)]
        return []
    monkeypatch.setattr('src.live_engine.path_runs', rows)
    clock.now=1000.30
    cap = Candidate((180,265,100,10),'green_candidate',1.,.2,.35,['D'],
                    path_bbox=(150,260,180,55))
    engine._update_held_holds(frame,clock.now,[cap])
    assert set(scheduler.held) == {'F'}
    assert ('up','S') in actuator.calls and ('up','F') not in actuator.calls
    scheduler.close()
