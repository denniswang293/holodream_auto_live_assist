import cv2
import numpy as np

from tools.geometry_scene.segmentation import SegmentationConfig, segment_frame


def _frame():
    return np.zeros((120, 180, 3), dtype=np.uint8)


def test_detects_panel_but_does_not_type_from_hue():
    frame = _frame()
    cv2.rectangle(frame, (40, 40), (79, 49), (255, 255, 0), -1)  # cyan in BGR
    result = segment_frame(frame)
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.bbox == (40, 40, 40, 10)
    assert candidate.kind == "UNKNOWN"
    assert "TYPE_UNRESOLVED" in candidate.provenance
    assert candidate.mask.shape == frame.shape[:2]
    assert np.count_nonzero(candidate.mask) > 0


def test_connected_green_body_is_only_an_ambiguous_hold_hypothesis():
    frame = _frame()
    cv2.rectangle(frame, (70, 15), (104, 25), (0, 255, 0), -1)
    cv2.rectangle(frame, (81, 26), (93, 88), (0, 255, 0), -1)
    result = segment_frame(frame)
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.kind == "HOLD"
    assert candidate.status == "AMBIGUOUS"
    assert candidate.body_link_evidence
    assert candidate.bbox == (70, 15, 35, 74)


def test_star_and_splash_like_negative_components_are_rejected():
    frame = _frame()
    # Low-solidity starburst and an irregular splash, both bright green.
    points = np.array([[30, 10], [35, 25], [50, 20], [40, 31], [52, 43],
                       [36, 39], [30, 55], [24, 39], [8, 43], [20, 31],
                       [10, 20], [25, 25]], dtype=np.int32)
    cv2.fillPoly(frame, [points], (0, 255, 0))
    cv2.circle(frame, (115, 32), 17, (0, 255, 0), -1)
    cv2.rectangle(frame, (108, 15), (113, 23), (0, 0, 0), -1)
    cv2.rectangle(frame, (118, 28), (129, 33), (0, 0, 0), -1)
    assert not segment_frame(frame).candidates


def test_sparse_horizontal_core_is_rejected_but_coherent_panel_is_kept():
    frame = _frame()
    # A hollow effect ring has a panel-like outer contour and enough area, but
    # its horizontal core is sparse. Keep a nearby solid panel as a control.
    cv2.rectangle(frame, (20, 40), (63, 55), (255, 255, 0), -1)
    cv2.rectangle(frame, (23, 43), (60, 52), (0, 0, 0), -1)
    cv2.rectangle(frame, (100, 42), (139, 53), (255, 255, 0), -1)

    result = segment_frame(frame)

    assert [candidate.bbox for candidate in result.candidates] == [(100, 42, 40, 12)]
    assert result.candidates[0].panel_fill_ratio >= 0.60


def test_touching_different_color_panels_stay_separate_and_partial_panel_is_uncertain():
    frame = _frame()
    cv2.rectangle(frame, (25, 50), (54, 59), (255, 255, 0), -1)
    cv2.rectangle(frame, (49, 50), (78, 59), (0, 255, 0), -1)
    cv2.rectangle(frame, (115, 50), (144, 59), (255, 255, 0), -1)
    result = segment_frame(frame)
    assert len(result.candidates) == 3
    overlap = result.candidates[0]
    assert overlap.bbox == (25, 50, 24, 10)
    assert overlap.kind == "UNKNOWN"
    assert overlap.status in ("AMBIGUOUS", "UNKNOWN")
    assert result.candidates[1].colors == ("green",)
    assert result.candidates[2].bbox == (115, 50, 30, 10)


def test_calibration_polygon_rejects_out_of_board_hud():
    frame = _frame()
    cv2.rectangle(frame, (50, 45), (89, 55), (255, 255, 0), -1)
    cv2.rectangle(frame, (5, 5), (44, 15), (255, 255, 0), -1)  # HUD-like
    cfg = SegmentationConfig(calibration_polygon=((20, 20), (160, 20), (160, 110), (20, 110)))
    result = segment_frame(frame, cfg)
    assert [c.bbox for c in result.candidates] == [(50, 45, 40, 11)]
    assert result.raw_mask[8, 10] == 0
