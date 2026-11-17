from __future__ import annotations

import base64
import json
import zlib

import cv2
import numpy as np

from src.geometry_rebuild_v1.geometry import Geometry, Rail, assert_round_trip
from src.geometry_rebuild_v1.render import geometry_frame
from src.geometry_rebuild_v1.segment import detect_candidates


def synthetic_geometry() -> Geometry:
    rails = tuple(Rail(slope, intercept) for slope, intercept in [
        (-.84, 608), (-.56, 619), (-.28, 629), (0, 640),
        (.28, 650), (.56, 660), (.84, 671)])
    return Geometry(1280, 720, rails, 580, (558, 603), ("synthetic",))


def frame() -> np.ndarray:
    return np.zeros((720, 1280, 3), dtype=np.uint8)


def draw_hsv(image: np.ndarray, xyxy: tuple[int, int, int, int], hsv: tuple[int, int, int]) -> None:
    color = cv2.cvtColor(np.uint8([[hsv]]), cv2.COLOR_HSV2BGR)[0, 0].tolist()
    x1, y1, x2, y2 = xyxy
    cv2.rectangle(image, (x1, y1), (x2, y2), color, -1)
    # Bright horizontal end edges model the visible panel boundary.
    cv2.line(image, (x1, y1), (x2, y1), (245, 245, 245), 2)
    cv2.line(image, (x1, y2), (x2, y2), (245, 245, 245), 2)


def test_geometry_round_trip_and_six_ordered_lanes() -> None:
    geometry = synthetic_geometry()
    assert len(geometry.boundaries(500)) == 7
    assert all(a < b for a, b in zip(geometry.boundaries(580), geometry.boundaries(580)[1:]))
    assert_round_trip(geometry, [(0, 0), (640, 404), (1100, 580), (1279, 719)])


def test_separate_same_height_taps_stay_separate() -> None:
    image = frame(); geometry = synthetic_geometry()
    draw_hsv(image, (405, 250, 475, 274), (95, 190, 245))
    draw_hsv(image, (510, 250, 580, 274), (95, 190, 245))
    candidates, _, _ = detect_candidates(image, geometry, 1)
    taps = [c for c in candidates if c.candidate_type == "TAP" and c.color == "cyan" and c.bbox[1] < 300]
    assert len(taps) == 2
    assert taps[0].bbox[0] + taps[0].bbox[2] < taps[1].bbox[0]


def test_hold_has_connected_pixel_backed_head_body_tail_parts() -> None:
    image = frame(); geometry = synthetic_geometry()
    draw_hsv(image, (430, 100, 474, 390), (60, 220, 220))
    candidates, _, _ = detect_candidates(image, geometry, 2)
    holds = [c for c in candidates if c.candidate_type == "HOLD" and c.color == "green"]
    assert holds
    hold = max(holds, key=lambda c: c.area_px)
    assert [part["role"] for part in hold.parts] == ["HOLD_TAIL", "HOLD_BODY", "HOLD_HEAD"]
    raw = zlib.decompress(base64.b64decode(hold.mask_rle_zlib_b64))
    assert len(np.unpackbits(np.frombuffer(raw, np.uint8), bitorder="little")) >= hold.mask_shape[0] * hold.mask_shape[1]


def test_two_simultaneous_holds_remain_distinct() -> None:
    image = frame(); geometry = synthetic_geometry()
    draw_hsv(image, (380, 100, 420, 385), (60, 220, 220))
    draw_hsv(image, (485, 115, 525, 400), (60, 220, 220))
    candidates, _, _ = detect_candidates(image, geometry, 3)
    holds = [c for c in candidates if c.candidate_type == "HOLD" and c.color == "green"]
    assert len(holds) == 2
    assert holds[0].bbox[0] != holds[1].bbox[0]


def test_judgment_flash_panel_is_unknown_and_not_rendered() -> None:
    image = frame(); geometry = synthetic_geometry()
    draw_hsv(image, (410, 565, 510, 590), (95, 190, 245))
    candidates, uncertain, _ = detect_candidates(image, geometry, 4)
    assert any(c.candidate_type == "UNKNOWN" and c.reason == "judgment_band_effect_overlap" for c in candidates)
    out = geometry_frame(geometry, candidates)
    assert np.count_nonzero(out[565:590, 410:510] != image[565:590, 410:510]) > 0  # geometry rails only
    assert not any(c.candidate_type == "TAP" and c.bbox[1] >= 565 for c in candidates)


def test_neutral_gray_tap_is_not_dropped_as_background() -> None:
    image = frame(); geometry = synthetic_geometry()
    draw_hsv(image, (410, 180, 490, 203), (0, 0, 220))
    candidates, _, _ = detect_candidates(image, geometry, 5)
    assert any(c.candidate_type == "TAP" and c.color == "neutral" for c in candidates)


def test_wide_curved_green_ribbon_is_not_forced_to_tap() -> None:
    image = frame(); geometry = synthetic_geometry()
    draw_hsv(image, (485, 117, 639, 191), (60, 220, 220))
    candidates, _, _ = detect_candidates(image, geometry, 7)
    assert any(c.candidate_type == "HOLD" and c.color == "green" for c in candidates)
    assert not any(c.candidate_type == "TAP" and c.color == "green" and
                   c.bbox[0] <= 485 and c.bbox[0] + c.bbox[2] >= 639 for c in candidates)


def test_center_white_flash_is_review_only_not_a_neutral_tap() -> None:
    image = frame(); geometry = synthetic_geometry()
    draw_hsv(image, (600, 400, 700, 424), (0, 0, 225))
    candidates, uncertain, _ = detect_candidates(image, geometry, 8)
    assert any(c.candidate_type == "UNKNOWN" and
               c.reason == "center_judgment_flash_or_text_overlap" for c in candidates)
    assert not any(c.candidate_type == "TAP" and c.color == "neutral" for c in candidates)


def test_hold_clipped_by_field_crop_is_review_only() -> None:
    image = frame(); geometry = synthetic_geometry()
    draw_hsv(image, (430, 620, 470, 647), (60, 220, 220))
    candidates, _, _ = detect_candidates(image, geometry, 6)
    assert any(c.candidate_type == "UNKNOWN" and c.reason == "candidate_touches_field_crop" for c in candidates)
