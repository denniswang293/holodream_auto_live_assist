import math
import numpy as np
import pytest
from src.engine import Engine
from src.model import Detection,Frame,Geometry
from src.scheduler import Scheduler,MockActuator,Action


def system():
    clock=[10.];act=MockActuator();s=Scheduler(act,clock=lambda:clock[0])
    g=Geometry();e=Engine(g,s,dict(geometry_sha256=g.sha256,model='log',
        kind='reference_success_timing',input_offset_s=.02))
    e.gate.update=lambda image:True
    e.perception.last_labels=None;e.perception.last_path=None
    return clock,act,s,e


def observe(clock,e,t,detections,focused=True):
    clock[0]=t
    e.perception.detect=lambda image:detections
    f=Frame(round(t*1000),np.zeros((404,720,3),np.uint8),t,t,focused,True)
    o=e.observe(f);return e.decide(o)


def test_independent_chord_plans_survive_one_missing_detection_without_duplicate():
    c,a,s,e=system()
    s.update_context(10.,True,True);s.toggle();s.poll()
    vanish=e.timing.vanish;target=e.geometry.hit_y
    for i in range(24):
        t=10.+i*.04
        y=(target-vanish)*math.exp(t-10.65)+vanish
        ds=[Detection((x,round(y)-5,54,5),'cyan','tap',(key,),.95) for x,key in ((0,'S'),(300,'L'))]
        if i in (13,14):ds=[]
        observe(c,e,t,ds)
    downs=[key for event,key in a.calls if event=='down']
    assert sorted(downs)==['L','S']
    assert s.sent_taps==2


def test_hold_keeps_start_key_during_invisible_body_then_observed_tail_releases():
    c,a,s,e=system();s.update_context(10.,True,True);s.toggle();s.poll()
    ds=lambda y:[Detection((180,y-8,60,8),'green','hold_head',('J',),.95)]
    for i,y in enumerate((260,270,280,290,300,310)):
        observe(c,e,10.+i*.04,ds(y))
    n=next(iter(e.tracker.notes.values()))
    # This test isolates the release stage from its already tested ETA fitter.
    if not s.snapshot()['held']:
        s.pending.clear();s.consumed.clear()
        assert s.offer(Action(n.uid,'J','hold',c[0]+.005,.005))
        c[0]+=.005;s.poll()
    assert ('down','J') in a.calls
    for i in range(1,4):observe(c,e,10.2+i*.04,[])
    assert ('up','J') not in a.calls
    from src.tracking import Cap
    from collections import deque
    tail=Detection((180,327,60,8),'green','hold_tail',('J',),.95)
    n.tail_uid='tail'
    points=[(10.32,300.,.5,2/3),(10.36,309.,.5,2/3),(10.40,318.,.5,2/3),(10.44,327.,.5,2/3)]
    cap=Cap('tail',tail,deque(points,maxlen=16),{'hold_tail':4})
    e.tracker.caps['tail']=cap;n.tail=deque(points,maxlen=16)
    observe(c,e,10.44,[])
    assert a.calls.count(('up','J'))==1


def test_focus_loss_releases_hold_and_requires_explicit_arm_again():
    c,a,s,e=system();s.update_context(10.,True,True);s.toggle();s.poll()
    s.offer(Action('held','D','hold',10.01,.005));c[0]=10.01;s.poll()
    observe(c,e,10.02,[],False)
    assert a.calls==[('down','D'),('up','D')]
    observe(c,e,10.04,[])
    assert not s.armed


def test_same_height_tap_and_hold_have_independent_lifecycles():
    c,a,s,e=system();s.update_context(10.,True,True);s.toggle();s.poll()
    vanish=e.timing.vanish;target=e.geometry.hit_y
    for i in range(24):
        at=10.+i*.04;y=round((target-vanish)*math.exp(at-10.65)+vanish)
        ds=[Detection((0,y-5,54,5),'cyan','tap',('S',),.95),
            Detection((300,y-8,54,8),'green','hold_head',('L',),.95)]
        observe(c,e,at,ds)
    assert a.calls.count(('down','S'))==1 and a.calls.count(('down','L'))==1
    assert ('up','S') in a.calls and ('up','L') not in a.calls
    s.disarm('test_stop');assert a.calls[-1]==('up','L')


@pytest.mark.parametrize('already_fired',[False,True])
def test_recovered_face_keeps_one_action_and_consumes_fragment_uid(already_fired):
    from collections import deque
    from src.model import Note
    from src.tracking import Cap
    c,a,s,e=system();c[0]=2.05;s.update_context(2.04,True,True);s.toggle();s.poll()
    old=Note('old','tap','cyan',Detection((180,257,36,17),'cyan','tap',('J',),.95),origin_y=30.,confirmed=True,key='J',state='SCHEDULED')
    old.head=deque([(1.5,180.,.4,.7),(1.6,200.,.4,.7),(1.7,220.,.4,.7),
                    (1.8,240.,.4,.7),(1.9,260.,.5,.6),(2.,274.,.5,.6)],maxlen=12)
    new=Note('fragment','tap','cyan',Detection((144,266,108,27),'cyan','tap',('F','J','K'),.95),origin_y=260.,confirmed=True)
    new.head=deque([(1.96,275.,.4,.7),(2.,284.,.4,.7),(2.04,293.,.4,.7)],maxlen=12)
    e.tracker.notes={'old':old,'fragment':new}
    e.tracker.caps={'cap_old':Cap('cap_old',old.detection,deque(old.head,maxlen=16),{'tap':20},'old'),
                    'cap_new':Cap('cap_new',new.detection,deque(new.head,maxlen=16),{'tap':3},'fragment')}
    assert s.offer(Action('old','J','tap',2.3,.005))
    assert s.offer(Action('fragment','K','tap',2.051 if already_fired else 2.25,.005))
    if already_fired:c[0]=2.055;s.poll()
    e._consolidate_tap_identity(Frame(1,np.zeros((404,720,3),np.uint8),2.04,2.05))
    if already_fired:
        assert list(e.tracker.notes)==['fragment']
        assert 'old' not in s.snapshot()['pending'] and 'fragment' in s.snapshot()['fired']
        c[0]=2.3;s.update_context(c[0],True,True);s.poll()
        assert [key for event,key in a.calls if event=='down']==['K']
        return
    assert list(e.tracker.notes)==['old']
    assert old.aliases==['fragment'] and old.last_seen==2.04
    assert s.snapshot()['pending']['old'].press_at==2.3
    assert s.snapshot()['pending']['old'].key=='J'
    assert 'fragment' not in s.snapshot()['pending'] and 'fragment' in s.snapshot()['consumed']
    c[0]=2.3;s.update_context(c[0],True,True);s.poll()
    assert a.calls==[('down','J')]
