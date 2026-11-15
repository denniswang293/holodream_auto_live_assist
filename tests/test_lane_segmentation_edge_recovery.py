import cv2
import numpy as np

from src.lane_segmentation import LanePixelSegmenter
from src.model import Geometry


def color(h, s=220, v=230):
    return tuple(int(x) for x in cv2.cvtColor(
        np.uint8([[[h, s, v]]]), cv2.COLOR_HSV2BGR)[0, 0])


def geometry():
    return Geometry("config/geometry_live_assist.json", plane_width=360)


def test_outer_cyan_panels_recover_separately_without_labeling_the_bridge():
    g = geometry()
    image = np.zeros((g.height, g.plane_width, 3), dtype=np.uint8)
    cyan = color(96, 220, 230)
    left = np.zeros((g.height, g.plane_width), dtype=bool)
    right = np.zeros_like(left)
    left[288:315, 0:120] = True
    right[288:315, 240:360] = True
    image[left | right] = cyan
    # A thin connecting glow merges the raw chroma into one screen-wide
    # component, but has no panel-like vertical fill of its own.
    image[301, 120:240] = cyan

    result = LanePixelSegmenter().segment(image, g, frame_index=373)
    faces = [c for c in result.components if c.role == "tap_face" and c.color == "cyan"]
    assert len(faces) == 2
    assert {c.bbox[0] for c in faces} == {0, 240}
    assert np.all(result["tap_face"][left])
    assert np.all(result["tap_face"][right])
    assert np.count_nonzero(result["tap_face"][301, 120:240]) == 0
    assert np.all(result["unknown"][301, 120:240] == 255)
    # Recovery only assigns pixels measured in the source image.
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    observed_cyan = ((hsv[:, :, 0] >= 84) & (hsv[:, :, 0] <= 112) &
                     (hsv[:, :, 1] >= 65) & (hsv[:, :, 2] >= 135))
    assert np.all(result["tap_face"][~observed_cyan] == 0)


def test_outer_lane_glow_without_a_panel_stays_unknown():
    g = geometry()
    image = np.zeros((g.height, g.plane_width, 3), dtype=np.uint8)
    cyan = color(96, 220, 230)
    # Even a screen-spanning near-hit glow must not become two edge Taps.
    image[301:303, :] = cyan

    result = LanePixelSegmenter().segment(image, g, frame_index=374)
    assert not any(c.role == "tap_face" and c.color == "cyan"
                   for c in result.components)
    assert np.count_nonzero(result["tap_face"]) == 0
    assert np.count_nonzero(result["unknown"]) > 0
