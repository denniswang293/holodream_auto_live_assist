"""Visual Hold starts on a moving head and follows its green/yellow tail."""
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from src.geometry import CalibratedGeometry
from src.hold_visual import green_path_depth, green_runs, path_depth, path_runs
from src.live_capture import CapturedFrame
from src.live_engine import LiveEngine
from src.live_input import ActionIntent, MockActuator, TapScheduler
from src.predictor import Prediction
from src.tracker import Track

ROOT=Path(__file__).resolve().parents[1]


def scene(appearance='green_candidate'):
    geometry=CalibratedGeometry(json.loads((ROOT/'config/geometry_live_assist.json').read_text(encoding='utf-8-sig')))
    frame=np.zeros((404,720,3),np.uint8)
    color=(0,255,255) if appearance=='yellow_bar' else (0,255,0)
    cv2.rectangle(frame,(335,230),(384,316),color,-1)
    return geometry,frame


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
