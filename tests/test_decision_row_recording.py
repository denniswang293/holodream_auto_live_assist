import numpy as np

from src.engine import Engine
from src.model import Detection, Frame, Geometry, Note
from src.scheduler import MockActuator, Scheduler
from src.timing import Estimate


def _run(record_decisions):
    geometry=Geometry('config/geometry_live_assist.json',plane_width=360)
    actuator=MockActuator()
    scheduler=Scheduler(actuator,clock=lambda:30.1)
    scheduler.armed=True
    engine=Engine(geometry,scheduler,'config/reference_timing.json')
    engine.timing.predict=lambda samples,capture_timestamp,*,kind='tap': Estimate(
        crossing_at=30.3,press_at=30.2,eta_s=.1,uncertainty=.01,reason='ready',velocity=100.)
    detection=Detection((60,288,120,31),'cyan','tap',('S','D'),.9,plane_width=360,
        evidence=('current_frame_hsv_chroma',),semantic_candidate='tap',face_quality=.9,
        full_face=True,birth_zone=True)
    note=Note('note:row-mode','tap','cyan',detection)
    note.head.extend((30.1-i*.03,280.+i,0.,1/3) for i in range(8))
    note.confirmed=True
    engine.tracker.notes[note.uid]=note
    frame=Frame(1,np.zeros((404,720,3),np.uint8),30.1,30.1)
    observation={'frame':frame,'playing':True,'notes':[note],
        'detections':[detection],'cpu_ms':0.,'image':frame.image}
    if record_decisions is None:
        info,rows=engine.decide(observation,processed_at=30.1)
    else:
        info,rows=engine.decide(observation,processed_at=30.1,record_decisions=record_decisions)
    note_state=(note.state,note.reason,note.key,note.press_at,note.release_at,
                note.crossing_at,note.uncertainty,note.identity_state)
    snapshot=scheduler.snapshot()
    pending={uid:(a.key,a.kind,a.press_at,a.uncertainty,a.release_at)
             for uid,a in snapshot['pending'].items()}
    held={key:(a.uid,a.kind,a.press_at,a.release_at) for key,a in snapshot['held'].items()}
    return info,note_state,pending,held,list(actuator.calls),rows,engine.last_decision_profile


def test_skipping_decision_rows_preserves_actions_and_default_row_schema():
    full=_run(None)
    detailed=_run(True)
    skipped=_run(False)

    assert skipped[:5]==full[:5]
    assert detailed[:5]==full[:5]
    assert full[6]['decision_row_count']==1
    assert detailed[6]['decision_row_count']==1
    assert skipped[6]['decision_row_count']==1
    assert len(full[5])==1
    assert detailed[5]==full[5]
    assert skipped[5]==[]
    assert {'sequence','capture_timestamp','note_uid','state','reason','key',
            'visibility_state','identity_state','tail_last_kind','aliases'} <= full[5][0].keys()
