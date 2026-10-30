import json
from pathlib import Path

import pytest

from src.geometry import CalibratedGeometry
from src.live_engine import LiveEngine
from src.live_input import NoInputActuator, TapScheduler

ROOT = Path(__file__).resolve().parents[1]


def test_assist_timing_advance_changes_prediction_target_without_moving_geometry():
    config=json.loads((ROOT/'config.json').read_text(encoding='utf-8-sig'))
    config['live']=json.loads((ROOT/'config/live_assist.json').read_text(encoding='utf-8-sig'))
    geometry=CalibratedGeometry(json.loads((ROOT/'config/geometry_live_assist.json').read_text(encoding='utf-8-sig')))
    before=json.dumps(geometry.document,sort_keys=True)
    hit_times=[]
    for advance in (0,15):
        config['live']['input_advance_px']=advance
        engine=LiveEngine(config,geometry,TapScheduler('assist',NoInputActuator()))
        assert engine.geometry.hit_y==325.5
        assert engine.tracker.hit_y==engine.trigger_y==325.5-advance
        assert engine.commit_entry_y==(313. if advance==0 else 298.)
        history=[(1000+i*.02,260+i*4,.4) for i in range(6)]
        prediction=engine.tracker.predictor.predict(history,engine.tracker.hit_y)
        assert prediction.hit_time is not None
        hit_times.append(prediction.hit_time)
    assert hit_times[0]-hit_times[1]==pytest.approx(.075,abs=1e-6)
    assert json.dumps(geometry.document,sort_keys=True)==before


@pytest.mark.parametrize('advance',[-1,41,float('nan')])
def test_assist_rejects_invalid_timing_advance(advance):
    config=json.loads((ROOT/'config.json').read_text(encoding='utf-8-sig'))
    config['live']=json.loads((ROOT/'config/live_assist.json').read_text(encoding='utf-8-sig'))
    config['live']['input_advance_px']=advance
    geometry=CalibratedGeometry(json.loads((ROOT/'config/geometry_live_assist.json').read_text(encoding='utf-8-sig')))
    with pytest.raises(ValueError,match='input advance'):
        LiveEngine(config,geometry,TapScheduler('assist',NoInputActuator()))
