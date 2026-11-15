import importlib.util
from pathlib import Path
import pytest

PATH = Path(__file__).parents[1] / "tools" / "render_lane_filter_window.py"
SPEC = importlib.util.spec_from_file_location("render_lane_filter_window", PATH)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


@pytest.mark.parametrize("start,end", [(0,0),(3,8)])
def test_validate_range_accepts_inclusive_window(start,end):
    MOD.validate_range(start,end)


@pytest.mark.parametrize("start,end", [(-1,0),(2,1)])
def test_validate_range_rejects_invalid_window(start,end):
    with pytest.raises(ValueError): MOD.validate_range(start,end)


def test_index_mapping_checks_requested_video_frame():
    index={7:{"video_frame":"7","source_frame":"19","capture_timestamp":"1.25","acquired_timestamp":"1.30"}}
    assert MOD.index_row(index,7)["source_frame"] == "19"
    with pytest.raises(ValueError): MOD.index_row(index,8)


def test_index_mapping_rejects_timestamp_order():
    with pytest.raises(ValueError):
        MOD.index_row({1:{"video_frame":"1","source_frame":"1","capture_timestamp":"2","acquired_timestamp":"1"}},1)
