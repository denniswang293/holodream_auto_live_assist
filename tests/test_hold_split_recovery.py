import json
from collections import deque
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.engine import Engine
from src.model import Detection,Geometry,Note
from src.scheduler import Action,MockActuator,Scheduler
from src.tracking import Cap


def state():
    data=json.loads((Path(__file__).parent/'fixtures/hold_terminal/split_head_state.json').read_text())
    clock=[data['timestamp']]
    s=Scheduler(MockActuator(),clock=lambda:clock[0])
    e=Engine(Geometry(),s,'config/reference_timing.json')
    for row in data['notes']:
        d=Detection(tuple(row['bbox']),'green','hold_head',('K','L'),.9)
        n=Note(row['uid'],'hold','green',d,origin_y=row['origin_y'],confirmed=True,
               state=row['state'],full_head_observations=row['full_heads'],tail_uid=row['tail'])
        n.head=deque(map(tuple,row['head']),maxlen=32)
        e.tracker.notes[n.uid]=n
        e.tracker.caps['head:'+n.uid]=Cap('head:'+n.uid,d,note_uid=n.uid,samples=deque(n.head,maxlen=16))
    for row in data['caps']:
        d=Detection(tuple(row['bbox']),'green',row['kind'],('K',),.9,
                    above=row['above'],below=row['below'])
        c=Cap(row['uid'],d,full_tail_observations=row['full'],connection_owner_uid=row['connection'],
              terminal_owner_uid=row['terminal'],tail_locked=True)
        c.samples.append((row['seen'],d.bbox[1],*d.span))
        e.tracker.caps[c.uid]=c
    return e,s,clock,e.tracker.notes['note:55'],e.tracker.notes['note:87']


def test_recorded_recovered_face_preserves_pending_key_deadline_and_real_tail():
    e,s,clock,old,young=state()
    s.update_context(clock[0],True,True);s.toggle();s.poll()
    action=Action(young.uid,'L','hold',clock[0]+.22,.02)
    assert s.offer(action)
    e._consolidate_hold_fragments(SimpleNamespace(captured_at=clock[0]))
    assert s.snapshot()['pending']=={young.uid:action}
    assert young.tail_uid=='cap:67'
    assert old.state=='DONE'
    assert old.uid in young.aliases
    assert e.tracker.caps['cap:67'].connection_owner_uid==young.uid
    clock[0]=action.press_at;s.update_context(clock[0],True,True);s.poll()
    assert s.actuator.calls==[('down','L')]


@pytest.mark.parametrize('change',['unverified_tail','wrong_owner','different_endpoint','different_motion','different_span','insufficient_views'])
def test_partial_similarity_cannot_merge_independent_or_unproven_heads(change):
    e,s,clock,old,young=state()
    if change=='unverified_tail':e.tracker.caps[old.tail_uid].full_tail_observations=0
    if change=='wrong_owner':e.tracker.caps[old.tail_uid].connection_owner_uid='other'
    if change=='different_endpoint':young.tail_uid='independent-tail'
    if change=='different_motion':
        young.head=deque([(t,y+65,a,b) for t,y,a,b in young.head],maxlen=32)
        x,y,w,h=young.detection.bbox;young.detection=replace(young.detection,bbox=(x,y+65,w,h))
    if change=='different_span':
        young.head=deque([(t,y,.1,.3) for t,y,a,b in young.head],maxlen=32)
        x,y,w,h=young.detection.bbox;young.detection=replace(young.detection,bbox=(36,y,72,h))
    if change=='insufficient_views':young.head=deque([young.head[0],young.head[-2],young.head[-1]],maxlen=32)
    e._consolidate_hold_fragments(SimpleNamespace(captured_at=clock[0]))
    assert old.state!='DONE'
    assert young.state!='DONE'
    assert not s.snapshot()['consumed']


def test_already_consumed_head_cannot_be_rebooked_by_identity_recovery():
    e,s,clock,old,young=state()
    s.consumed.add(young.uid)
    e._consolidate_hold_fragments(SimpleNamespace(captured_at=clock[0]))
    assert not s.snapshot()['pending']
    assert not s.actuator.calls
