from tools.analyze_tap_geometry_eta import _crossing
import pytest


def test_crossing_interpolates_using_the_selected_anchor_coordinate():
    # A bottom anchor and a center anchor must be evaluated independently.
    bottom = _crossing([(1.0, 100.0), (1.2, 200.0)], 150.0)
    center = _crossing([(1.0, 80.0), (1.2, 180.0)], 150.0)
    assert bottom[1] == "INTERPOLATED"
    assert center[1] == "INTERPOLATED"
    assert bottom[0] == pytest.approx(1.1)
    assert center[0] == pytest.approx(1.14)


def test_crossing_handles_variable_speed_without_fixed_fps_assumption():
    result, status = _crossing([(2.0, 100.0), (2.1, 110.0), (2.4, 200.0)], 150.0)
    assert status == "INTERPOLATED"
    assert 2.1 < result < 2.4


def test_crossing_labels_bounded_extrapolation_and_rejects_stale_gap():
    result, status = _crossing([(3.0, 100.0), (3.1, 120.0)], 150.0)
    assert status == "BOUNDED_EXTRAPOLATION"
    assert result == pytest.approx(3.25)
    result, status = _crossing([(3.0, 100.0)], 150.0)
    assert result is None
    assert status == "INSUFFICIENT_OBSERVATIONS"
