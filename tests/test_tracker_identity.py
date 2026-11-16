import numpy as np
import threading

from src.engine import Engine
from src.model import Detection, Frame, Geometry, Note
from src.scheduler import Action, MockActuator, Scheduler
from src.tracking import Tracker
from src.timing import Estimate


def _tap(y):
    return Detection((42, y, 40, 14), 'cyan', 'tap', ('D',), .9, plane_width=360,
        evidence=('legacy_perception', 'current_frame_hsv_chroma'),
        semantic_candidate='tap', face_quality=.9,
        full_face=True, birth_zone=True)


def test_global_assignment_uses_both_feasible_edges_instead_of_greedy_choice():
    matrix=[[.10,.20,1.65,1.650001],
            [.11,1e6,1.650001,1.65]]
    assignment=Tracker._global_assignment(matrix)
    assert assignment[0]==1
    assert assignment[1]==0


def test_sparse_component_assignment_matches_dense_gated_assignment():
    offers={(0,0):.20,(0,1):.10,(1,0):.05,
            (2,2):.35,(3,2):.11,(4,4):.70}
    blocked={4}
    unmatched=Tracker.UNMATCHED_ASSOCIATION_COST
    forbidden=1e6
    dense=[]
    for row in range(5):
        costs=[forbidden if detection in blocked else offers.get((row,detection),forbidden)
               for detection in range(5)]
        costs.extend(unmatched+0.000001*abs(row-other) for other in range(5))
        dense.append(costs)
    picked=Tracker._global_assignment(dense)
    expected={row:detection for row,detection in picked.items()
              if detection<5 and dense[row][detection]<unmatched}
    sparse,components=Tracker._sparse_global_assignment(5,5,offers,unmatched,blocked)
    assert sparse==expected=={0:1,1:0,3:2}
    assert sorted(components)==[(2,1),(2,2)]


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


def test_scheduler_uid_state_flags_match_full_snapshot_without_exposing_history():
    scheduler=Scheduler(MockActuator(),clock=lambda:30.0)
    pending=Action('pending-uid','S','tap',30.1,.01)
    held=Action('held-uid','D','hold',30.1,.01,30.5)
    scheduler.pending[pending.uid]=pending
    scheduler.held['D']=held
    scheduler.consumed.add('consumed-uid')
    scheduler.fired.add('fired-uid')

    expected={
        pending.uid:(False,False,True,False),
        held.uid:(False,False,False,True),
        'consumed-uid':(False,True,False,False),
        'fired-uid':(True,False,False,False),
        'unused-uid':(False,False,False,False),
    }
    for uid,flags in expected.items():
        snapshot=scheduler.snapshot()
        assert scheduler.uid_state_flags(uid)==(
            uid in snapshot['fired'],uid in snapshot['consumed'],
            uid in snapshot['pending'],any(action.uid==uid for action in snapshot['held'].values()))
        assert scheduler.uid_state_flags(uid)==flags


def test_scheduler_uid_state_flags_wait_for_atomic_poll_transition():
    entered_key_down=threading.Event()
    allow_key_down=threading.Event()
    query_started=threading.Event()
    query_done=threading.Event()
    query_result=[]

    class BlockingActuator(MockActuator):
        def key_down(self,key):
            super().key_down(key)
            entered_key_down.set()
            assert allow_key_down.wait(2.0)

    now=[30.05]
    scheduler=Scheduler(BlockingActuator(),clock=lambda:now[0])
    scheduler.update_context(30.05,True,True)
    scheduler.armed=True
    action=Action('atomic-uid','S','hold',30.1,.01,30.5)
    assert scheduler.offer(action)

    now[0]=30.1
    poller=threading.Thread(target=scheduler.poll)
    poller.start()
    assert entered_key_down.wait(1.0)

    def query():
        query_started.set()
        query_result.append(scheduler.uid_state_flags(action.uid))
        query_done.set()

    reader=threading.Thread(target=query)
    reader.start()
    assert query_started.wait(1.0)
    assert not query_done.wait(.02)
    allow_key_down.set()
    poller.join(1.0);reader.join(1.0)
    assert not poller.is_alive() and not reader.is_alive()
    assert query_result==[(True,True,False,True)]

    assert scheduler.release_hold(action.uid)
    assert scheduler.uid_state_flags(action.uid)==(True,True,False,False)


def test_engine_reuses_pending_key_when_current_lane_evidence_differs():
    geometry=Geometry('config/geometry_live_assist.json',plane_width=360)
    actuator=MockActuator();scheduler=Scheduler(actuator,clock=lambda:30.1)
    scheduler.update_context(30.1,True,True)
    scheduler.armed=True
    committed=Action('note:committed','S','tap',30.2,.01)
    assert scheduler.offer(committed)

    engine=Engine(geometry,scheduler,'config/reference_timing.json')
    engine.timing.predict=lambda samples,capture_timestamp,*,kind='tap': Estimate(
        crossing_at=30.3,press_at=30.2,eta_s=.1,uncertainty=.01,reason='ready',velocity=100.)
    detection=Detection((300,260,40,14),'cyan','tap',('L',),.9,plane_width=360,
        evidence=('current_frame_hsv_chroma',),semantic_candidate='tap',face_quality=.9,
        full_face=True,birth_zone=True)
    note=Note('note:committed','tap','cyan',detection)
    note.head.extend((t,y,.83,.95) for t,y in ((30.0,230.),(30.03,240.),(30.06,250.),(30.09,260.)))
    note.confirmed=True
    engine.tracker.notes[note.uid]=note
    frame=Frame(1,np.zeros((720,1280,3),np.uint8),30.1,30.1)

    _,decisions=engine.decide({'frame':frame,'playing':True,'notes':[note],
        'detections':[detection],'cpu_ms':0.,'image':frame.image},processed_at=30.1)

    assert decisions[0]['key']=='S'
    assert decisions[0]['reason']=='updated'
    assert scheduler.snapshot()['pending'][note.uid].key=='S'
    assert scheduler.snapshot()['error'] is None
    assert not any(event['event'] in ('rejected','disarmed') for event in scheduler.events)
    assert not actuator.calls

