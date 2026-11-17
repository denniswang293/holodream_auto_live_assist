from __future__ import annotations

import base64
import zlib
from dataclasses import dataclass
from functools import lru_cache

import cv2
import numpy as np

from .geometry import Geometry


COLOR_RANGES = {
    # Source pixel histograms on broad playfield samples show the stationary
    # blue background at H=78..86, while cyan panels cluster at H>=87. Keep a
    # deliberate hue gap so playfield color cannot connect separate notes.
    "cyan": ((88, 62, 120), (112, 255, 255)),
    "green": ((34, 48, 78), (77, 255, 255)),
    "yellow": ((16, 55, 90), (38, 255, 255)),
    "pink": ((135, 45, 90), (179, 255, 255)),
}
PRIMITIVE_COLORS = {
    "cyan": (220, 195, 80), "green": (90, 210, 90),
    "yellow": (70, 205, 225), "pink": (210, 100, 210), "neutral": (205, 205, 205),
}


@dataclass
class Candidate:
    candidate_type: str
    color: str
    confidence: float
    bbox: tuple[int, int, int, int]
    area_px: int
    polygon: list[list[float]]
    mask_rle_zlib_b64: str
    mask_shape: tuple[int, int]
    lane_span: tuple[int, int] | None
    pixel_evidence: dict
    reason: str | None = None
    parts: list[dict] | None = None

    def to_dict(self) -> dict:
        return {"type": self.candidate_type, "color": self.color,
                "confidence": round(float(self.confidence), 4), "bbox": list(self.bbox),
                "area_px": int(self.area_px), "polygon": self.polygon,
                "pixel_mask_encoding": "zlib-packed-bits-row-major-v1",
                "pixel_mask_shape": list(self.mask_shape),
                "pixel_mask": self.mask_rle_zlib_b64,
                "lane_span": list(self.lane_span) if self.lane_span is not None else None,
                "pixel_evidence": self.pixel_evidence,
                "uncertainty_reason": self.reason, "hold_parts": self.parts}


@lru_cache(maxsize=8)
def field_mask(shape: tuple[int, int], geometry: Geometry) -> np.ndarray:
    h, w = shape
    stop = min(h - 1, int(geometry.judgment_band[1] + 45))
    left_top = geometry.rails[0].x(0)
    right_top = geometry.rails[-1].x(0)
    left_bottom = geometry.rails[0].x(stop)
    right_bottom = geometry.rails[-1].x(stop)
    poly = np.asarray([[round(left_top), 0], [round(right_top), 0],
                       [round(right_bottom), stop], [round(left_bottom), stop]], np.int32)
    mask = np.zeros((h, w), np.uint8)
    cv2.fillConvexPoly(mask, poly, 255)
    return mask


def _compressed_mask(mask: np.ndarray) -> str:
    packed = np.packbits(mask.astype(np.uint8).reshape(-1), bitorder="little")
    return base64.b64encode(zlib.compress(packed.tobytes(), level=6)).decode("ascii")


def _lane_span(geometry: Geometry, bbox: tuple[int, int, int, int]) -> tuple[int, int] | None:
    x, y, w, h = bbox
    cy = y + h * .5
    boundaries = geometry.boundaries(cy)
    i0 = next((i for i in range(6) if x + w >= boundaries[i] and x < boundaries[i + 1]), None)
    i1 = next((i for i in range(5, -1, -1) if x + w >= boundaries[i] and x < boundaries[i + 1]), None)
    return (i0, i1) if i0 is not None and i1 is not None else None


def _bbox_iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax, ay, aw, ah = a; bx, by, bw, bh = b
    iw = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    ih = max(0, min(ay + ah, by + bh) - max(ay, by))
    inter = iw * ih
    union = aw * ah + bw * bh - inter
    return inter / union if union else 0.0


def _poly(contour: np.ndarray, x: int, y: int) -> list[list[float]]:
    eps = 1.4
    approx = cv2.approxPolyDP(contour, eps, True)
    if len(approx) > 40:
        approx = cv2.approxPolyDP(contour, 2.8, True)
    return [[round(float(px + x), 2), round(float(py + y), 2)]
            for [[px, py]] in approx]


def _hold_parts(mask_component: np.ndarray, bbox: tuple[int, int, int, int],
                color: str, y_clip: int) -> list[dict]:
    x, y, w, h = bbox
    top = y
    bottom = min(y + h, y_clip)
    return [
        {"role": "HOLD_TAIL", "bbox": [x, top, w, max(1, round(h * .2))],
         "visible_pixel_backed": True, "ownership": "screen_top_provisional"},
        {"role": "HOLD_BODY", "bbox": [x, top + round(h * .2), w, max(1, round(h * .6))],
         "visible_pixel_backed": True, "ownership": "same_connected_component"},
        {"role": "HOLD_HEAD", "bbox": [x, max(top, bottom - round(h * .2)), w, max(1, round(h * .2))],
         "visible_pixel_backed": True, "ownership": "screen_bottom_provisional"},
    ]


def _merge_horizontal_edges(frame: np.ndarray, geometry: Geometry,
                            hsv: np.ndarray, valid_field: np.ndarray,
                            color_masks: dict[str, np.ndarray]) -> tuple[list[Candidate], int]:
    """Find independent panel proposals from paired grayscale horizontal edges.

    This path is deliberately independent of connected HSV components; it can
    recover a bright panel when a similarly colored playfield halo connects to
    its color mask. A pair alone is insufficient: the enclosed region must
    contain source pixels from a supported color family.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 65, 180)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 720, threshold=35,
                            minLineLength=25, maxLineGap=4)
    if lines is None:
        return [], 0
    raw = []
    for x1, y1, x2, y2 in lines[:, 0, :]:
        dx, dy = int(x2 - x1), int(y2 - y1)
        if abs(dy) > 3 or abs(dx) < 25:
            continue
        y = int(round((y1 + y2) * .5)); left, right = sorted((int(x1), int(x2)))
        if y < 2 or y >= geometry.judgment_band[1] + 50 or right <= 0 or left >= frame.shape[1]:
            continue
        if y >= valid_field.shape[0] or not np.any(valid_field[y, max(0, left):min(frame.shape[1], right + 1)]):
            continue
        raw.append((left, right, y))
    raw.sort(key=lambda r: (r[2], r[0]))
    merged: list[list[int]] = []
    for left, right, y in raw:
        match = next((group for group in reversed(merged)
                      if abs(group[2] - y) <= 2 and left <= group[1] + 5 and right >= group[0] - 5), None)
        if match is None:
            merged.append([left, right, y, 1])
        else:
            match[0] = min(match[0], left); match[1] = max(match[1], right)
            match[2] = round((match[2] * match[3] + y) / (match[3] + 1)); match[3] += 1
    rows = sorted(((g[0], g[1], g[2]) for g in merged), key=lambda row: (row[2], row[0]))
    proposals: list[Candidate] = []
    pairs_seen = 0
    for ai, top in enumerate(rows):
        for bottom in rows[ai + 1:]:
            dy = bottom[2] - top[2]
            if dy > 62:
                break
            if dy < 4:
                continue
            overlap = min(top[1], bottom[1]) - max(top[0], bottom[0])
            small_w = min(top[1] - top[0], bottom[1] - bottom[0])
            large_w = max(top[1] - top[0], bottom[1] - bottom[0])
            if small_w < 14 or overlap / max(small_w, 1) < .5 or large_w / max(small_w, 1) > 2.4:
                continue
            x1, x2 = max(0, min(top[0], bottom[0])), min(frame.shape[1], max(top[1], bottom[1]) + 1)
            y1, y2 = top[2], bottom[2] + 1
            bw, bh = x2 - x1, y2 - y1
            if bw < 14 or bw > 480 or bh > 60:
                continue
            pairs_seen += 1
            region = hsv[y1:y2, x1:x2]
            field = valid_field[y1:y2, x1:x2] > 0
            # Reuse the full-frame masks already computed for connected
            # components. Re-running five inRange operations for each
            # candidate edge pair dominated this path on effect-heavy frames.
            family_masks = {name: color_mask[y1:y2, x1:x2] > 0
                            for name, color_mask in color_masks.items()}
            family_counts = {name: int(np.count_nonzero(m & field)) for name, m in family_masks.items()}
            color = max(family_counts, key=family_counts.get)
            color_mask = family_masks[color] & field
            support = float(np.count_nonzero(color_mask)) / max(bw * bh, 1)
            if family_counts[color] < 16 or support < .045:
                continue
            component = color_mask.astype(np.uint8)
            ymid = y1 + bh / 2
            lane_span = _lane_span(geometry, (x1, y1, bw, bh))
            near_judgment = abs(ymid - geometry.judgment_y) < 42
            confidence = min(.91, .63 + .13 * min(overlap / max(small_w, 1), 1) + .18 * min(support, .6))
            reason = "judgment_band_effect_overlap" if near_judgment else None
            if color == "neutral" and 330 <= ymid <= 470 and abs((x1 + x2) * .5 - frame.shape[1] * .5) <= 115:
                reason = "center_judgment_flash_or_text_overlap"
            if lane_span is None:
                reason = "unresolved_lane_ownership"
            min_panel_height = 6 if ymid < 150 else 9 if ymid < 300 else 12 if ymid < 500 else 15
            if bh < min_panel_height:
                reason = "edge_fragment_too_thin_for_panel"
            contour = np.asarray([[[0, 0]], [[bw - 1, 0]], [[bw - 1, bh - 1]], [[0, bh - 1]]], np.int32)
            candidate = Candidate("UNKNOWN" if reason else "TAP", color,
                                  min(confidence, .49) if reason else confidence,
                                  (x1, y1, bw, bh), int(np.count_nonzero(component)),
                                  _poly(contour, x1, y1), _compressed_mask(component), (bh, bw),
                                  lane_span,
                                  {"mean_hsv": [round(float(x), 2) for x in np.mean(region[component.astype(bool)], axis=0)] if component.any() else [],
                                   "pixel_count": int(component.sum()), "paired_horizontal_edge_overlap_px": int(overlap),
                                   "independent_edge_pair": True, "color_is_support_not_type_rule": True,
                                   "capture_frame_only": True}, reason)
            if any(c.candidate_type == "HOLD" and _bbox_iou((x1, y1, bw, bh), c.bbox) > .10 for c in proposals):
                continue
            proposals.append(candidate)
    # Collapse duplicate edge-pairs from the same visible panel.
    deduped: list[Candidate] = []
    for candidate in sorted(proposals, key=lambda c: c.confidence, reverse=True):
        duplicate = False
        for other in deduped:
            if _bbox_iou(candidate.bbox, other.bbox) > .35:
                duplicate = True; break
            ax, ay, aw, ah = candidate.bbox; bx, by, bw, bh = other.bbox
            overlap_w = max(0, min(ax + aw, bx + bw) - max(ax, bx))
            small_h, large_h = min(ah, bh), max(ah, bh)
            if small_h / max(large_h, 1) < .38 and overlap_w / max(min(aw, bw), 1) > .70:
                if ay <= by + bh and by <= ay + ah:
                    duplicate = True; break
        if not duplicate:
            deduped.append(candidate)
    return deduped, pairs_seen


def detect_candidates(frame_bgr: np.ndarray, geometry: Geometry,
                      frame_index: int | None = None) -> tuple[list[Candidate], list[dict], dict]:
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    valid_field = field_mask(frame_bgr.shape[:2], geometry)
    h_img, w_img = frame_bgr.shape[:2]
    candidates: list[Candidate] = []
    uncertain: list[dict] = []
    diagnostics = {"scene_background_components_rejected": 0}

    masks: list[tuple[str, np.ndarray]] = []
    color_masks: dict[str, np.ndarray] = {}
    for color, (lo, hi) in COLOR_RANGES.items():
        mask = cv2.inRange(hsv, np.asarray(lo, np.uint8), np.asarray(hi, np.uint8))
        mask = cv2.bitwise_and(mask, valid_field)
        color_masks[color] = mask
        masks.append((color, mask))
    neutral = cv2.inRange(hsv, np.asarray((0, 0, 168), np.uint8),
                          np.asarray((179, 54, 248), np.uint8))
    color_masks["neutral"] = cv2.bitwise_and(neutral, valid_field)
    masks.append(("neutral", color_masks["neutral"]))

    for color, mask in masks:
        # Minimal 2x2 closing repairs single-pixel texture holes without
        # bridging the several-pixel gaps between neighboring note panels.
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE,
                                np.ones((2, 2), np.uint8), iterations=1)
        count, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
        for label in range(1, count):
            x, y, bw, bh, area = map(int, stats[label])
            if area < 28 or bw < 6 or bh < 3:
                continue
            if bw > w_img * .72 and bh > h_img * .42 and area > w_img * h_img * .07:
                diagnostics["scene_background_components_rejected"] += 1
                continue
            if y > geometry.judgment_band[1] + 48 or x > w_img - 4 or x + bw < 4:
                continue
            component = (labels[y:y + bh, x:x + bw] == label).astype(np.uint8)
            contours, _ = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                continue
            contour = max(contours, key=cv2.contourArea)
            contour_area = cv2.contourArea(contour)
            if contour_area < 16:
                continue
            aspect = bw / max(bh, 1)
            solidity = contour_area / max(bw * bh, 1)
            center_y = y + bh / 2
            local_boundaries = geometry.boundaries(center_y)
            local_lane_width = float(np.median(np.diff(local_boundaries)))
            occupied_rows = np.count_nonzero(component.sum(axis=1) >= max(2, int(bw * .28)))
            occupied_cols = np.count_nonzero(component.sum(axis=0) >= max(2, int(bh * .24)))
            vertical_support = occupied_rows / max(bh, 1)
            horizontal_support = occupied_cols / max(bw, 1)
            x1, y1 = max(0, x), max(0, y)
            x2, y2 = min(w_img, x + bw), min(h_img, y + bh)
            hsv_crop = hsv[y1:y2, x1:x2]
            comp_crop = component[:y2-y1, :x2-x1].astype(bool)
            if not comp_crop.any():
                continue
            hsv_pixels = hsv_crop[comp_crop]
            mean_h, mean_s, mean_v = np.mean(hsv_pixels, axis=0)
            center_y = y + bh / 2
            band_distance = abs(center_y - geometry.judgment_y)
            field_stop = min(h_img - 1, int(geometry.judgment_band[1] + 45))
            clipped = (y <= 1 or y + bh >= geometry.height - 2 or
                       y + bh >= field_stop - 1 or x <= 1 or x + bw >= geometry.width - 2)
            score = .52
            kind = "UNKNOWN"
            reason = "shape_does_not_separate_tap_from_hold"
            parts = None
            tap_min_h = 3 if center_y < 150 else 7 if center_y < 300 else 11 if center_y < 500 else 14
            tap_max_h = max(12, local_lane_width * .62)
            if aspect >= 1.7 and tap_min_h <= bh <= tap_max_h and horizontal_support >= .36 and solidity >= .52 and area >= 34:
                kind = "TAP"
                score = min(.92, .61 + .07 * min(aspect / 3.0, 1.0) + .10 * horizontal_support + .12 * solidity)
                reason = None
            elif bh >= max(38, local_lane_width * .70) and vertical_support >= .48 and solidity >= .38 and area >= 130:
                kind = "HOLD"
                score = min(.91, .66 + .13 * vertical_support + .06 * min(bh / 140, 1.0))
                reason = None
                parts = _hold_parts(component, (x, y, bw, bh), color,
                                    int(geometry.judgment_band[1] + 45))
            if band_distance < 42:
                kind, score = "UNKNOWN", min(score, .49)
                reason = "judgment_band_effect_overlap"
            if color == "neutral" and 330 <= center_y <= 470 and abs((x + bw / 2) - w_img / 2) <= 115:
                kind, score = "UNKNOWN", min(score, .48)
                reason = "center_judgment_flash_or_text_overlap"
            if clipped:
                kind, score = "UNKNOWN", min(score, .45)
                reason = "candidate_touches_field_crop" if y + bh >= field_stop - 1 else "component_clipped_at_frame_edge"
            lane_span = _lane_span(geometry, (x, y, bw, bh))
            if bw > 440 or lane_span is None:
                kind, score = "UNKNOWN", min(score, .45)
                reason = "spans_multiple_or_unresolved_lane_boundaries"
            polygon = _poly(contour, x, y)
            evidence_mask = component.astype(bool)
            evidence = {"mean_hsv": [round(float(mean_h), 2), round(float(mean_s), 2), round(float(mean_v), 2)],
                        "color_family_is_observation_only": True,
                        "mask_pixel_count": int(np.count_nonzero(evidence_mask)),
                        "horizontal_support": round(float(horizontal_support), 4),
                        "vertical_support": round(float(vertical_support), 4),
                        "component_solidity": round(float(solidity), 4),
                        "capture_frame_only": True,
                        "future_frames_used": False}
            candidate = Candidate(kind, color, score, (x, y, bw, bh), area,
                                  polygon, _compressed_mask(evidence_mask),
                                  (bh, bw), lane_span, evidence, reason, parts)
            if kind == "UNKNOWN":
                uncertain.append({"frame": frame_index, "bbox": [x, y, bw, bh],
                                  "color": color, "confidence": round(score, 4),
                                  "reason": reason, "pixel_area": area,
                                  "pixel_mask": candidate.mask_rle_zlib_b64,
                                  "mask_shape": [bh, bw]})
            candidates.append(candidate)
    panel_candidates, panel_pairs = _merge_horizontal_edges(
        frame_bgr, geometry, hsv, valid_field, color_masks)
    diagnostics["paired_edge_hypotheses"] = panel_pairs
    for panel in panel_candidates:
        overlaps_hold = any(c.candidate_type == "HOLD" and _bbox_iou(panel.bbox, c.bbox) > .12 for c in candidates)
        if overlaps_hold:
            continue
        duplicates = [i for i, c in enumerate(candidates)
                      if c.candidate_type in ("TAP", "UNKNOWN") and
                      _bbox_iou(panel.bbox, c.bbox) > (.25 if c.candidate_type == "TAP" else .42)]
        if duplicates:
            candidates[duplicates[0]] = panel
            for duplicate in reversed(duplicates[1:]):
                candidates.pop(duplicate)
        else:
            candidates.append(panel)
        if panel.candidate_type == "UNKNOWN":
            x, y, w, h = panel.bbox
            uncertain.append({"frame": frame_index, "bbox": [x, y, w, h], "color": panel.color,
                              "confidence": panel.confidence, "reason": panel.reason,
                              "pixel_area": panel.area_px, "pixel_mask": panel.mask_rle_zlib_b64,
                              "mask_shape": [h, w]})
    return candidates, uncertain, diagnostics
