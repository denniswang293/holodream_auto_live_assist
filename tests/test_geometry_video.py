from pathlib import Path

import cv2
import numpy as np

from src.geometry_video.geometry import VideoGeometry
from src.geometry_video.renderer import render_geometry_frame
from src.geometry_video.segmenter import Candidate, PixelGeometryConverter


CONFIG = Path("config/geometry_video_v1.json")


def _fill(frame, points, bgr):
    cv2.fillPoly(frame, [np.asarray(points, np.int32)], bgr)


def test_candidate_confidence_is_always_clamped_to_a_probability():
    candidate = Candidate("TAP", "cyan", -0.04, (0, 0, 1, 1), 1,
                          [[0, 0]], {"mask_pixel_count": 1}, [], [])
    assert candidate.confidence == 0.0


def test_calibrated_rails_are_ordered_and_render_only_geometric_primitives():
    geometry = VideoGeometry(CONFIG)
    frame = np.full((720, 1280, 3), (0, 0, 0), np.uint8)
    rendered = render_geometry_frame(geometry, [])
    assert len(geometry.boundaries(300)) == 7
    row = geometry.boundaries(300)
    assert all(a < b for a, b in zip(row, row[1:]))
    # The far background contains no copied source pixels; output has only the
    # fixed dark field, rails, and judgment line.
    assert rendered.shape == frame.shape
    assert tuple(rendered[680, 10]) == (10, 13, 22)
    assert np.max(rendered[100, 0:20]) < 100


def test_judgment_line_is_clipped_to_outer_rails():
    geometry = VideoGeometry(CONFIG)
    rendered = render_geometry_frame(geometry, [])
    row = round(geometry.judgment_y)
    background = (10, 13, 22)
    assert tuple(rendered[row, 0]) == background
    assert tuple(rendered[row, geometry.width - 1]) == background
    assert np.any(np.all(rendered[row, :] == (235, 246, 255), axis=1))


def test_piecewise_rails_match_source_visual_anchors_at_the_judgment_band():
    geometry = VideoGeometry(CONFIG)
    expected = [61, 254, 447, 640, 833, 1026, 1219]
    assert np.allclose(geometry.boundaries(560), expected, atol=0.01)
    at_judgment = geometry.boundaries(geometry.judgment_y)
    assert at_judgment[0] < 60 and at_judgment[-1] > 1215
    assert all(a < b for a, b in zip(at_judgment, at_judgment[1:]))


def test_two_taps_and_a_hold_remain_separate_and_pixel_supported():
    geometry = VideoGeometry(CONFIG)
    converter = PixelGeometryConverter(geometry)
    frame = np.zeros((720, 1280, 3), np.uint8)
    cyan = (255, 160, 30)
    green = (30, 235, 50)
    _fill(frame, [(380, 300), (500, 300), (500, 325), (380, 325)], cyan)
    _fill(frame, [(514, 300), (634, 300), (634, 325), (514, 325)], cyan)
    _fill(frame, [(650, 100), (700, 100), (700, 450), (650, 450)], green)
    objects, uncertain = converter.segment(frame)
    taps = [candidate for candidate in objects if candidate.class_name == "TAP"]
    holds = [candidate for candidate in objects if candidate.class_name == "HOLD"]
    assert len(taps) == 2
    assert len(holds) == 1
    assert len(holds[0].parts) == 3
    assert {part["kind"] for part in holds[0].parts} == {"HOLD_HEAD", "HOLD_BODY", "HOLD_TAIL"}
    assert not any(candidate.bbox[0] == taps[0].bbox[0] and candidate.class_name == "UNKNOWN" for candidate in uncertain)
    assert all(candidate.pixel_evidence["mask_pixel_count"] > 0 for candidate in taps + holds)
    rendered = render_geometry_frame(geometry, objects)
    assert not np.array_equal(rendered, frame)
    assert np.all(rendered[:30, :] != frame[:30, :])


def test_large_bright_effect_is_not_promoted_to_a_tap():
    converter = PixelGeometryConverter(VideoGeometry(CONFIG))
    frame = np.zeros((720, 1280, 3), np.uint8)
    # A broad near-judgment flash resembles a colored bar but is too tall to be
    # promoted as a Tap; it remains explicit uncertainty instead.
    _fill(frame, [(350, 520), (930, 520), (930, 590), (350, 590)], (255, 160, 30))
    objects, uncertain = converter.segment(frame)
    assert not any(candidate.class_name == "TAP" for candidate in objects)
    assert uncertain

