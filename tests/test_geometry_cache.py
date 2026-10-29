"""Caching must preserve calibration, rejection rules and detector outputs."""
from copy import deepcopy
from dataclasses import fields
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from src.calibration import geometry_hash
from src.detector import detect
from src.geometry import CalibratedGeometry
from src.geometry_render import draw_geometry

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def document():
    return json.loads((ROOT/"config/geometry_live_assist.json").read_text(encoding="utf-8-sig"))


@pytest.mark.parametrize("model",["linear","piecewise","homography"])
def test_exact_mapping_and_overlay_for_all_models(document,model):
    document["model_type"] = model
    if model=="piecewise":
        document["controls"]["lane_rows"][1]["points"][2]["x"] += 5
    plain = CalibratedGeometry(document,cache_enabled=False)
    cached = CalibratedGeometry(document)
    heights = list(np.arange(0,404,.5))+[28-1e-9,28-1e-7,352+1e-9,352+1e-7,
                                              190.123456789,float("nan"),float("inf"),-1]
    for y in heights:
        for name in ("lane_bounds_at_y","outer_bounds_at_y","row_lane_width"):
            assert getattr(cached,name)(y)==getattr(plain,name)(y)
        row = plain.lane_bounds_at_y(y)
        if row is None:
            assert cached.screen_to_uv(360,y) is None
            continue
        for x in (row[0]-1,row[0],(row[2]+row[3])/2,row[-1],row[-1]+1):
            assert cached.screen_to_uv(x,y)==plain.screen_to_uv(x,y)
            assert cached.safe_lane(x,y)==plain.safe_lane(x,y)
        assert cached.safe_bbox_interval(row[1],row[3],y)==plain.safe_bbox_interval(row[1],row[3],y)
        assert cached.safe_candidate_lanes(row[1],row[3],y,.15)==plain.safe_candidate_lanes(row[1],row[3],y,.15)
    for uv in ((0,0),(.23,.37),(.5,.5),(1,1)):
        assert cached.uv_to_screen(*uv)==plain.uv_to_screen(*uv)
    a,b = np.zeros((404,720,3),np.uint8),np.zeros((404,720,3),np.uint8)
    draw_geometry(a,plain,{})
    draw_geometry(b,cached,{})
    np.testing.assert_array_equal(a,b)
    assert geometry_hash(cached.document)==geometry_hash(document)
    assert cached.cache_info()["lookups"]["lane_bounds_at_y"]["hits"]>0


def test_cache_is_bounded_and_calibration_edits_get_new_cache(document):
    original = deepcopy(document)
    cached = CalibratedGeometry(document)
    before = cached.lane_bounds_at_y(28)
    document["controls"]["lane_rows"][0]["points"][3]["x"] += 2
    changed = CalibratedGeometry(document)
    assert changed.lane_bounds_at_y(28)!=before
    assert cached.lane_bounds_at_y(28)==before
    assert cached.document==original
    assert changed.cache_info()["lookups"]["lane_bounds_at_y"]["misses"]==1
    for y in np.linspace(28,352,2300):
        cached.lane_bounds_at_y(y)
        cached.outer_bounds_at_y(y)
        cached.row_lane_width(y)
    assert all(info["currsize"]<=2048 and info["maxsize"]==2048
               for info in cached.cache_info()["lookups"].values())
    assert not CalibratedGeometry(original,cache_enabled=False).cache_info()["enabled"]


@pytest.mark.parametrize("scale",[.5,1,2])
@pytest.mark.parametrize("model",["linear","piecewise","homography"])
def test_detector_and_rejection_diagnostics_exactly_match(document,scale,model):
    document["model_type"] = model
    cached = CalibratedGeometry(document)
    plain = CalibratedGeometry(document,cache_enabled=False)
    config = json.loads((ROOT/"config.json").read_text())
    cfg = {**config["detector"],"reference_resolution":document["reference_resolution"]}
    image = np.zeros((404,720,3),np.uint8)
    # Separate tap, neutral and head/tail appearances, plus out-of-span evidence.
    cv2.rectangle(image,(280,200),(345,207),(255,255,0),-1)
    cv2.rectangle(image,(310,100),(320,177),(0,255,0),-1)
    cv2.rectangle(image,(280,170),(345,177),(0,255,0),-1)
    cv2.rectangle(image,(380,250),(450,258),(230,230,230),-1)
    cv2.rectangle(image,(2,200),(80,208),(255,70,255),-1)
    image = cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST)
    a,b = {},{}
    expected = detect(image,plain,config["key_map"],cfg,a)
    actual = detect(image,cached,config["key_map"],cfg,b)
    assert expected and len(actual)==len(expected)
    assert a==b
    for left,right in zip(expected,actual):
        for field in fields(left):
            av,bv = getattr(left,field.name),getattr(right,field.name)
            if isinstance(av,np.ndarray):
                np.testing.assert_array_equal(av,bv)
            else:
                assert av==bv,field.name
