import numpy as np

from src.engine import Engine
from src.model import Detection, Frame, Geometry, Note
from src.scheduler import MockActuator, Scheduler
from src.timing import Estimate


def _decide_for_edge_spanning_tap(spans,bbox=(0,288,120,31)):
    geometry=Geometry('config/geometry_live_assist.json',plane_width=360)
    actuator=MockActuator()
    scheduler=Scheduler(actuator,clock=lambda:30.1)
    scheduler.armed=True
    engine=Engine(geometry,scheduler,'config/reference_timing.json')
    engine.timing.predict=lambda samples,capture_timestamp,*,kind='tap': Estimate(
        crossing_at=30.3,press_at=30.2,eta_s=.1,uncertainty=.01,reason='ready',velocity=100.)
    detection=Detection(bbox,'cyan','tap',('S','D'),.9,plane_width=360,
        evidence=('current_frame_hsv_chroma',),semantic_candidate='tap',face_quality=.9,
        full_face=True,birth_zone=True)
    note=Note('note:key-tie','tap','cyan',detection)
    note.head.extend((30.1-i*.03,280.+i,lo,hi) for i,(lo,hi) in enumerate(spans))
    note.confirmed=True
    engine.tracker.notes[note.uid]=note
    frame=Frame(1,np.zeros((404,720,3),np.uint8),30.1,30.1)
    _,decisions=engine.decide({'frame':frame,'playing':True,'notes':[note],
        'detections':[detection],'cpu_ms':0.,'image':frame.image},processed_at=30.1)
    return scheduler,actuator,note,decisions[0]


def test_exact_vote_and_center_tie_abstains_without_scheduler_offer():
    spans=[(0.,1/3)]*8
    scheduler,actuator,note,decision=_decide_for_edge_spanning_tap(spans)

    assert decision['reason']=='ambiguous_key_coverage'
    assert decision['key']==''
    assert note.state=='TRACKING'
    assert not scheduler.pending
    assert not actuator.calls


def test_unequal_votes_preserve_current_center_choice():
    spans=[(0.,1/3)]*7+[(0.,.15)]
    scheduler,actuator,note,decision=_decide_for_edge_spanning_tap(spans,bbox=(60,288,120,31))

    assert decision['key']=='D'
    assert decision['reason']=='accepted'
    assert scheduler.snapshot()['pending'][note.uid].key=='D'
    assert not actuator.calls
