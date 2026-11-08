import math
import pytest
from tools.calibrate_reference import calibrate
from src.model import Geometry
from src.timing import Timing


def test_calibration_uses_only_reviewed_development_visual_crossings():
    g=Geometry();model=Timing(g);notes=[];matches=[];actions=[];review=[]
    for i in range(25):
        run='dev' if i<24 else 'validation';cross=10.+i
        points=[(cross-.8+j*.04,(g.hit_y-model.vanish)*math.exp(-.8+j*.04)+model.vanish,.0,1/6) for j in range(23)]
        notes.append(dict(run_id=run,physical_note_id=str(i),kind='tap',
            crossing_status='OBSERVED_INTERPOLATION',visual_crossing_timestamp=cross,
            head_samples_json=__import__('json').dumps(points)))
        actions.append(dict(action_id=str(i),down_timestamp=cross+(.02 if run=='dev' else .18)))
        matches.append(dict(record_type='MATCH',physical_note_id=str(i),action_id=str(i),
                            source_video_frame=i,capture_timestamp=cross-.04))
        review.append(dict(action_id=str(i),accepted_visual_match='true'))
    c,evidence=calibrate(notes,matches,actions,review,g,['dev'])
    assert c['reviewed_head_samples']==24 and len(evidence)==24
    assert c['input_offset_s']==pytest.approx(-.02)
    assert c['release_guard_samples']==0
    assert c['validation_used_for_training'] is False


def test_no_optimistic_prediction_below_calibrated_visual_height():
    g=Geometry();m=Timing(g,dict(geometry_sha256=g.sha256,model='log',
        kind='reference_success_timing',input_offset_s=0.,
        visual_error_bands=[dict(from_y=270,p90_absolute_s=.03)]))
    points=[(t,(g.hit_y-m.vanish)*math.exp(t-2)+m.vanish,.0,.2) for t in (1.4,1.44,1.48,1.52,1.56)]
    result=m.predict(points,1.56)
    assert result.reason=='uncalibrated_visual_height' and result.press_at is None
