from collections import deque
import math
import numpy as np
import pytest
from src.model import Detection,Geometry
from src.tracking import Tracker
from src.timing import Timing


def plate(y,x=180,kind='tap',color='cyan',width=90):
    return Detection((x,round(y)-3,width,3),color,kind,('J','K'),.95)


def test_real_bevel_measurement_jitter_keeps_one_head_uid():
    g=Geometry();t=Tracker(g)
    # Recorded REF1 head: a full face and its bevel alternate at frames61-64.
    samples=[(1262.120171,179),(1262.1603121,192),(1262.1985454,197),
             (1262.236626,197),(1262.2756773,211),(1262.3145,217),
             (1262.3541,223),(1262.3924,232)]
    for at,y in samples:t.update([plate(y,kind='hold_head',color='green')],at)
    assert len(t.notes)==1
    n=next(iter(t.notes.values()))
    assert n.observations==len(samples) and n.confirmed


def test_same_height_independent_heads_and_same_lane_successive_heads():
    t=Tracker(Geometry())
    for i in range(8):
        t.update([plate(100+6*i,0),plate(100+6*i,270),plate(160+6*i,0)],i*.04)
    assert len(t.notes)==3
    assert len({n.uid for n in t.notes.values()})==3


def test_short_observation_gap_reacquires_without_new_uid():
    t=Tracker(Geometry())
    for i in range(10):
        t.update([] if i in (5,6) else [plate(100+5*i)],i*.04)
    assert len(t.notes)==1
    assert next(iter(t.notes.values())).observations==8


def test_stationary_judgment_light_does_not_confirm():
    t=Tracker(Geometry())
    for i in range(12):t.update([plate(317+(i%2))],i*.04)
    assert not any(n.confirmed for n in t.notes.values())


def test_component_number_from_previous_frame_cannot_link_unrelated_tail():
    from dataclasses import replace
    t=Tracker(Geometry())
    for i in range(5):
        t.update([replace(plate(250+i*10,180,'hold_head','green'),component=7)],i*.04)
    n=next(iter(t.notes.values()));assert n.confirmed
    for i in range(2):
        t.update([replace(plate(100+i*5,0,'hold_tail','green'),component=7)],.20+i*.04)
    assert not n.tail_uid


def test_two_current_ribbons_keep_distinct_tail_ownership():
    from dataclasses import replace
    t=Tracker(Geometry())
    for i in range(5):
        ds=[]
        for x,component in ((0,10),(270,20)):
            ds.extend([replace(plate(250+i*8,x,'hold_head','green',60),component=component),
                       replace(plate(150+i*8,x,'hold_tail','green',60),component=component)])
        t.update(ds,i*.04)
    ns=list(t.notes.values());assert len(ns)==2
    assert all(n.tail_uid for n in ns) and len({n.tail_uid for n in ns})==2


def timing():
    g=Geometry()
    return Timing(g,dict(geometry_sha256=g.sha256,model='log',kind='reference_success_timing',input_offset_s=.03))


def points(model,cross=2.,rate=1.,fps=30):
    ts=np.arange(1.45,1.82,1/fps)
    return [(float(t),(model.geometry.hit_y-model.vanish)*math.exp(rate*(t-cross))+model.vanish,.3,.5) for t in ts]


@pytest.mark.parametrize('fps',[25,30,60,120])
def test_real_timestamp_fit_does_not_assume_fps(fps):
    m=timing();p=points(m,fps=fps);r=m.predict(p,p[-1][0])
    assert r.reason=='ready'
    assert r.crossing_at==pytest.approx(2.,abs=1e-6)
    assert r.press_at==pytest.approx(1.97,abs=1e-6)


def test_dropout_reduces_eta_without_moving_crossing_or_press():
    m=timing();p=points(m)
    a=m.predict(p,p[-1][0]);b=m.predict(p,p[-1][0]+.06)
    assert b.crossing_at==a.crossing_at and b.press_at==a.press_at
    assert b.eta_s==pytest.approx(a.eta_s-.06)
    assert m.predict(p,p[-1][0]+.2).reason=='stale_observation'


def test_future_and_expired_prediction_never_shift_to_now():
    m=timing();p=points(m)
    assert m.predict(p,p[-1][0]-.01).reason=='invalid_or_future_observations'
    q=points(m,cross=1.7)
    r=m.predict(q,q[-1][0])
    assert r.reason=='crossing_in_past' and r.press_at is None


def test_different_song_speed_is_estimated_from_its_own_observations():
    m=timing()
    for speed in (.4,.8,1.8):
        p=points(m,rate=speed)
        assert m.predict(p,p[-1][0]).crossing_at==pytest.approx(2.,abs=1e-6)


def test_missing_calibration_does_not_claim_an_input_center():
    m=Timing(Geometry());p=points(m)
    r=m.predict(p,p[-1][0]);assert r.crossing_at is not None
    assert r.press_at is None and r.reason=='input_calibration_missing'
