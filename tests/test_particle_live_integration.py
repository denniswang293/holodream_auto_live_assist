from copy import deepcopy
import json
from pathlib import Path

import numpy as np

from src.calibration import geometry_hash
from src.live_capture import CapturedFrame
from src.live_engine import LiveEngine
from src.live_input import MockActuator, TapScheduler
from src.geometry import CalibratedGeometry


ROOT=Path(__file__).resolve().parents[1]


class Clock:
    def __init__(self): self.now=1000.
    def __call__(self): return self.now


def test_particle_prediction_reaches_mock_scheduler_without_changing_hold_or_safety(make_candidate):
    config=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    config['predictor']['mode']='particle'
    config['predictor']['particle']['count']=128
    geometry=CalibratedGeometry(json.loads((ROOT/'config/geometry_live_assist.json').read_text(encoding='utf-8-sig')))
    config['live']={'verified_key_mapping':{
        'geometry_sha256':geometry_hash(geometry.document), 'reviewer':'test fixture',
        'evidence':'synthetic only', 'keys':list('SDFJKL')}}
    clock,actuator=Clock(),MockActuator()
    scheduler=TapScheduler('assist',actuator,clock=clock,max_age=.06,max_lateness=.015)
    scheduler.update_context(999.99,'PLAYING',True,True)
    assert scheduler.toggle(); scheduler.poll(); assert scheduler.armed
    engine=LiveEngine(config,geometry,scheduler,clock=clock,detector=lambda *a:[])
    engine.gate.update=lambda *a:'PLAYING'
    statuses=[]
    image=np.zeros((404,720,3),np.uint8)
    for i in range(54):
        capture=1000+i/60
        clock.now=capture+.002
        candidate=make_candidate(y=170+i*3.5,keys=['F'])
        engine.detector=lambda *a,c=candidate:[c]
        _,tracks,events,_=engine.process(CapturedFrame(i,image,capture,capture+.001),focused=True)
        statuses.extend(e['predictor_mode'] for e in events)
        next_capture=1000+(i+1)/60
        while clock.now < next_capture:
            clock.now=min(clock.now+.003,next_capture)
            scheduler.poll()
    clock.now=1001.1
    scheduler.poll()
    assert statuses and all(mode=='particle' for mode in statuses)
    assert actuator.calls and actuator.calls[0]==('down','F')
    assert ('up','F') in actuator.calls
    assert not scheduler.armed  # stale capture safely disarmed after the replay
    scheduler.disarm('test_end'); scheduler.close()


def test_live_particle_fail_closed_for_stale_frame_and_legacy_is_explicit(make_candidate):
    config=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    config['predictor']['mode']='legacy'
    geometry=CalibratedGeometry(json.loads((ROOT/'config/geometry_live_assist.json').read_text(encoding='utf-8-sig')))
    clock,actuator=Clock(),MockActuator()
    scheduler=TapScheduler('assist',actuator,clock=clock)
    engine=LiveEngine(config,geometry,scheduler,clock=clock,detector=lambda *a:[make_candidate(keys=['F'])])
    engine.gate.update=lambda *a:'PLAYING'
    clock.now=1000.2
    _,tracks,_,_=engine.process(CapturedFrame(1,np.zeros((404,720,3),np.uint8),1000.,1000.001),focused=True)
    assert not tracks and not actuator.calls
    assert engine.tracker.predictor_mode=='legacy'
    scheduler.close()
