import numpy as np

from src.engine import Engine
from src.model import Detection, Frame, Geometry, Note
from src.scheduler import MockActuator, Scheduler
from src.tracking import Tracker


def _tap(y, *, t=0.0, pending=False):
    return Detection((42, y, 40, 14), 'neutral' if pending else 'cyan',
        'plate_fragment' if pending else 'tap', ('D',), .9, plane_width=360,
        evidence=('v85_early_provider', 'neutral_full_face_candidate') if pending else
                 ('v85_early_provider', 'current_frame_hsv_chroma'),
        semantic_candidate='pending' if pending else 'tap', face_quality=.9,
        full_face=True, birth_zone=True)


def test_global_assignment_uses_both_feasible_edges_instead_of_greedy_choice():
    matrix=[[.10,.20,1.65,1.650001],
            [.11,1e6,1.650001,1.65]]
    assignment=Tracker._global_assignment(matrix)
    assert assignment[0]==1
    assert assignment[1]==0


def test_birth_identity_is_immutable_and_occlusion_never_becomes_observation():
    tracker=Tracker(Geometry('config/geometry_live_assist.json',plane_width=360))
    image_path=np.zeros((404,360),np.uint8)
    for i,(t,y) in enumerate(((10.0,60),(10.03,67),(10.06,75))):
        tracker.update([_tap(y)],t,image_path,image_path)
    note=next(iter(tracker.notes.values()))
    birth=note.birth_info
    assert note.confirmed and note.visibility_state=='CONFIRMED_VISIBLE'
    assert birth.captured_at==10.0 and birth.bbox==(42,60,40,14)
    tracker.update([],10.09,image_path,image_path)
    assert note.visibility_state=='CONFIRMED_OCCLUDED'
    assert note.last_seen==10.06
    assert note.head[-1][0]==10.06
    assert note.birth_info is birth
    tracker.update([],10.23,image_path,image_path)
    assert note.visibility_state=='AMBIGUOUS_ASSOCIATION'
    assert note.last_seen==10.06


def test_neutral_full_face_stays_type_pending_without_positive_tap_evidence():
    tracker=Tracker(Geometry('config/geometry_live_assist.json',plane_width=360))
    for t,y in ((20.0,60),(20.03,67),(20.06,75)):
        tracker.update([_tap(y,pending=True)],t)
    note=next(iter(tracker.notes.values()))
    assert note.confirmed
    assert note.kind=='pending'
    assert note.identity_state=='CANDIDATE'
    tracker.update([_tap(83,pending=True)],20.09)
    assert note.kind=='pending'
    assert not note.kind_locked
    assert note.confirmed


def test_engine_never_offers_an_unresolved_type_pending_note():
    geometry=Geometry('config/geometry_live_assist.json',plane_width=360)
    actuator=MockActuator();scheduler=Scheduler(actuator,clock=lambda:30.0)
    engine=Engine(geometry,scheduler,'config/reference_timing.json')
    note=Note('note:pending','pending','neutral',_tap(75,pending=True))
    note.head.append((30.,82.,.1,.22));note.confirmed=True
    engine.tracker.notes[note.uid]=note
    frame=Frame(1,np.zeros((720,1280,3),np.uint8),30.,30.)
    info,decisions=engine.decide({'frame':frame,'playing':True,'notes':[note],
        'detections':[],'cpu_ms':0.,'image':frame.image},processed_at=30.)
    assert decisions[0]['reason']=='type_pending'
    assert not scheduler.pending
    assert not actuator.calls

