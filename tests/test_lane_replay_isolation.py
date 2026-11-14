import cv2
import numpy as np

from src.model import Geometry
from tools.replay_lane_filter import SegmentedProvider


def test_segmented_replay_provider_uses_current_pixels_without_legacy_detector():
    geometry = Geometry()
    image = np.zeros((geometry.height, geometry.width, 3), np.uint8)
    hue = cv2.cvtColor(np.uint8([[[62, 220, 230]]]), cv2.COLOR_HSV2BGR)[0, 0]
    cv2.line(image, (354, 70), (360, 170), tuple(map(int, hue)), 7)
    cv2.rectangle(image, (345, 164), (375, 173), tuple(map(int, hue)), -1)
    provider = SegmentedProvider(geometry)
    detections = provider.detect(image)
    assert hasattr(provider, "last_result")
    assert provider.last_path is not None
    assert np.count_nonzero(provider.last_path) > 0
    assert detections
    assert all(d.kind in {"hold_head", "body", "hold_tail", "tap"} for d in detections)
    assert not hasattr(provider, "legacy")
    assert provider.frame_index == 1
