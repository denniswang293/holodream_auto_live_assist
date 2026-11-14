import cv2
import numpy as np
import pytest

from src.lane_filter import LaneFilter, PREVIEW_COLORS
from src.model import Geometry


def hsv(h, s=220, v=230):
    return tuple(int(x) for x in cv2.cvtColor(np.uint8([[[h, s, v]]]), cv2.COLOR_HSV2BGR)[0, 0])


def test_filter_returns_provenance_and_pixels_not_filled_detection_boxes():
    geometry = Geometry()
    image = np.zeros((geometry.height, 720, 3), np.uint8)
    image[40:390, 180:540] = hsv(98, 90, 85)
    green = hsv(62)
    curve = np.array([[354, 100], [360, 130], [372, 150], [385, 166], [390, 185]], np.int32)
    cv2.polylines(image, [curve], False, green, 6)
    cv2.rectangle(image, (382, 181), (412, 190), green, -1)

    lane_filter = LaneFilter(geometry)
    observations, masks, preview, rectified, result = lane_filter.process(
        image, run_id="synthetic", source_frame=51, video_frame=50,
        captured_at=10.0, acquired_at=10.006)
    assert any(o.role == "HOLD_BODY" for o in observations)
    assert any(o.role == "HOLD_HEAD" for o in observations)
    assert all(o.source_frame == 51 and o.video_frame == 50 for o in observations)
    assert all(o.captured_at == 10.0 and o.acquired_at == 10.006 for o in observations)
    body = masks["hold_body"] > 0
    observed_hsv = cv2.cvtColor(rectified, cv2.COLOR_BGR2HSV)
    source_green = (observed_hsv[:, :, 0] >= 38) & (observed_hsv[:, :, 0] <= 83) & (observed_hsv[:, :, 1] >= 55)
    assert np.count_nonzero(body) > 100
    assert np.all(body <= source_green)
    expected = np.asarray(PREVIEW_COLORS["HOLD_BODY"], np.uint8)
    assert np.count_nonzero(np.all(preview == expected, axis=2)) > 0
    assert not hasattr(lane_filter, "perception")
    assert result.frame_index == 50


def test_filter_rejects_future_acquisition_clock():
    lane_filter = LaneFilter(Geometry())
    with pytest.raises(ValueError, match="timestamps"):
        lane_filter.process(np.zeros((404, 720, 3), np.uint8), run_id="r",
            source_frame=1, video_frame=1, captured_at=2.0, acquired_at=1.0)
