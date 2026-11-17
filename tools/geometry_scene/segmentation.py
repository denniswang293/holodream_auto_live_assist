"""Low-level, source-frame color segmentation for Geometry Scene V2.

This module emits pixel evidence only. Hue is never treated as note identity;
candidate geometry is returned in the input frame's native coordinates.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Literal

import cv2
import numpy as np

CandidateKind = Literal["TAP", "HOLD", "UNKNOWN"]
CandidateStatus = Literal["OBSERVED", "AMBIGUOUS", "UNKNOWN"]


@dataclass(frozen=True)
class HSVBand:
    lower: tuple[int, int, int]
    upper: tuple[int, int, int]


@dataclass(frozen=True)
class SegmentationConfig:
    # OpenCV HSV values (H: 0..179, S/V: 0..255).
    cyan: tuple[HSVBand, ...] = (HSVBand((78, 65, 100), (108, 255, 255)),)
    green: tuple[HSVBand, ...] = (HSVBand((35, 55, 65), (78, 255, 255)),)
    calibration_polygon: tuple[tuple[int, int], ...] | None = None
    min_area: int = 28
    min_panel_width: int = 12
    min_panel_height: int = 4
    max_panel_aspect: float = 14.0
    panel_solidity: float = 0.72
    # A candidate panel should have a substantially filled horizontal core;
    # sparse spark/effect fragments can otherwise pass contour solidity alone.
    panel_min_fill_ratio: float = 0.60
    # A linked body must extend at least this far below a compact cap.
    body_min_vertical_ratio: float = 1.65
    body_max_width_ratio: float = 3.0


@dataclass(frozen=True)
class PixelCandidate:
    bbox: tuple[int, int, int, int]  # x, y, width, height
    kind: CandidateKind
    status: CandidateStatus
    colors: tuple[str, ...]
    provenance: tuple[str, ...]
    body_link_evidence: bool
    solidity: float
    component_area: int
    # Full-frame binary mask for this connected component; source geometry retained.
    mask: np.ndarray = field(compare=False, repr=False)
    outline: tuple[tuple[int, int], ...] = ()
    panel_outline: tuple[tuple[int, int], ...] = ()
    panel_fill_ratio: float = 0.0
    panel_profile_cv: float = 1.0


@dataclass(frozen=True)
class FrameObservations:
    width: int
    height: int
    candidates: tuple[PixelCandidate, ...]
    # Combined accepted color mask, before connected-component filtering.
    raw_mask: np.ndarray = field(compare=False, repr=False)
    stage_ms: dict[str, float] = field(default_factory=dict, compare=False)


def _roi_mask(shape: tuple[int, int], polygon: tuple[tuple[int, int], ...] | None) -> np.ndarray:
    h, w = shape
    mask = np.full((h, w), 255, np.uint8)
    if polygon:
        mask[:] = 0
        cv2.fillPoly(mask, [np.asarray(polygon, dtype=np.int32)], 255)
    return mask


def _band_mask(hsv: np.ndarray, bands: tuple[HSVBand, ...]) -> np.ndarray:
    result = np.zeros(hsv.shape[:2], np.uint8)
    for band in bands:
        result = cv2.bitwise_or(result, cv2.inRange(hsv, band.lower, band.upper))
    return result


def segment_frame(frame_bgr: np.ndarray, config: SegmentationConfig | None = None) -> FrameObservations:
    """Extract colorful panel-like connected components from one BGR source frame.

    Components with overlapping color ownership or weak panel geometry are retained
    only when panel-like; ambiguous single blobs are marked UNKNOWN for review.
    No temporal tracking or rendering is performed.
    """
    cfg = config or SegmentationConfig()
    if not isinstance(frame_bgr, np.ndarray) or frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
        raise ValueError("frame_bgr must be an HxWx3 BGR numpy array")
    h, w = frame_bgr.shape[:2]
    t0 = perf_counter()
    if cfg.calibration_polygon:
        x0 = max(0, min(p[0] for p in cfg.calibration_polygon))
        y0 = max(0, min(p[1] for p in cfg.calibration_polygon))
        x1 = min(w, max(p[0] for p in cfg.calibration_polygon) + 1)
        y1 = min(h, max(p[1] for p in cfg.calibration_polygon) + 1)
        image = frame_bgr[y0:y1, x0:x1]
        local_polygon = tuple((x - x0, y - y0) for x, y in cfg.calibration_polygon)
        roi = _roi_mask(image.shape[:2], local_polygon)
    else:
        x0, y0, x1, y1 = 0, 0, w, h
        image = frame_bgr
        roi = _roi_mask((h, w), None)
    t_roi = perf_counter()
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    t_hsv = perf_counter()
    by_color = {
        "cyan": cv2.bitwise_and(_band_mask(hsv, cfg.cyan), roi),
        "green": cv2.bitwise_and(_band_mask(hsv, cfg.green), roi),
    }
    # Remove isolated sparkle pixels and one-pixel traces before components;
    # keep the two color families separate so a nearby glow cannot bridge them.
    clean_kernel = np.ones((3, 3), dtype=np.uint8)
    by_color = {name: cv2.morphologyEx(mask, cv2.MORPH_OPEN, clean_kernel)
                for name, mask in by_color.items()}
    combined = cv2.bitwise_or(by_color["cyan"], by_color["green"])
    t_mask = perf_counter()
    candidates: list[PixelCandidate] = []
    cc_ms = 0.0
    for color_name, color_mask in by_color.items():
        cc_start = perf_counter()
        count, labels, stats, _ = cv2.connectedComponentsWithStats(color_mask, 8)
        cc_ms += (perf_counter() - cc_start) * 1000
        other = by_color["green" if color_name == "cyan" else "cyan"]
        for label in range(1, count):
            lx, ly, bw, bh, area = (int(v) for v in stats[label])
            x, y = lx + x0, ly + y0
            if area < cfg.min_area or bw < cfg.min_panel_width or bh < cfg.min_panel_height:
                continue
            component_roi = (labels[ly:ly+bh, lx:lx+bw] == label).astype(np.uint8) * 255
            contours, _ = cv2.findContours(component_roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            contour = max(contours, key=cv2.contourArea, default=None)
            contour_area = cv2.contourArea(contour) if contour is not None else 0.0
            solidity = min(1.0, float(contour_area / max(1.0, area)))
            outline: tuple[tuple[int, int], ...] = ()
            if contour is not None:
                epsilon = max(1.5, min(bw, bh) * 0.04)
                polygon = cv2.approxPolyDP(contour, epsilon, True)
                while len(polygon) > 48:
                    epsilon *= 1.5
                    polygon = cv2.approxPolyDP(contour, epsilon, True)
                outline = tuple((int(p[0][0] + x), int(p[0][1] + y)) for p in polygon)
            # Extract the stable horizontal plate core separately from connected
            # arrow tips / nearby glow. Keep both raw contour and cleaned panel quad.
            row_counts = np.count_nonzero(component_roi, axis=1)
            max_row = int(np.max(row_counts, initial=0))
            strong_rows = np.flatnonzero(row_counts >= max(6, int(max_row * 0.70)))
            panel_outline: tuple[tuple[int, int], ...] = ()
            panel_fill = 0.0
            panel_cv = 1.0
            if len(strong_rows) >= 3:
                spans = []
                for ry in strong_rows:
                    xs = np.flatnonzero(component_roi[ry])
                    if len(xs) >= 3:
                        spans.append((int(xs[0]), int(xs[-1]), len(xs)))
                if len(spans) >= 3:
                    px0 = int(np.median([v[0] for v in spans]))
                    px1 = int(np.median([v[1] for v in spans]))
                    py0, py1 = int(strong_rows[0]), int(strong_rows[-1])
                    widths = np.asarray([v[1] - v[0] + 1 for v in spans], dtype=np.float64)
                    panel_cv = float(np.std(widths) / max(1.0, np.mean(widths)))
                    rect_area = max(1, (px1 - px0 + 1) * (py1 - py0 + 1))
                    panel_fill = float(np.count_nonzero(component_roi[py0:py1+1, px0:px1+1]) / rect_area)
                    if px1 - px0 + 1 >= 12 and py1 - py0 + 1 >= 4:
                        panel_outline = ((x + px0, y + py0), (x + px1, y + py0),
                                         (x + px1, y + py1), (x + px0, y + py1))
            horizontal_aspect = bw / max(1, bh)
            color_overlap = bool(np.any(other[ly:ly+bh, lx:lx+bw][component_roi > 0]))

            # Long continuous green components are Hold-body evidence even when
            # perspective makes the overall bounding box wider than it is tall.
            body_link = False
            if color_name == "green" and bh >= 60 and area >= min(1500, cfg.min_area * 5):
                row_counts = np.count_nonzero(component_roi, axis=1)
                active_rows = int(np.count_nonzero(row_counts))
                occupancy = area / max(1, bw * bh)
                median_width = float(np.median(row_counts[row_counts > 0])) if active_rows else 0.0
                body_link = (active_rows >= max(30, int(0.65 * bh)) and
                             occupancy >= 0.12 and median_width >= 8)

            panel_like = (1.5 <= horizontal_aspect <= cfg.max_panel_aspect and
                          solidity >= cfg.panel_solidity and
                          panel_fill >= cfg.panel_min_fill_ratio)
            if not panel_like and not body_link:
                continue
            colors = (color_name,)
            if area > 0.15 * h * w:
                kind: CandidateKind = "UNKNOWN"
                status: CandidateStatus = "UNKNOWN"
                why = ("OBSERVED_COLOR_COMPONENT", "MERGED_OR_OCCLUDED_REGION", "OWNERSHIP_UNRESOLVED")
            elif color_overlap:
                kind = "UNKNOWN"
                status = "AMBIGUOUS"
                why = ("CONNECTED_COLOR_OVERLAP", "PANEL_GEOMETRY")
            elif body_link:
                kind = "HOLD"
                status = "AMBIGUOUS"
                why = ("OBSERVED_COLOR_COMPONENT", "CONNECTED_BODY_LINK", "TYPE_HYPOTHESIS_ONLY")
            else:
                # A short panel cannot be distinguished as Tap vs Hold head from one frame.
                kind = "UNKNOWN"
                status = "UNKNOWN" if solidity < 0.90 else "AMBIGUOUS"
                why = ("OBSERVED_COLOR_COMPONENT", "PANEL_GEOMETRY", "TYPE_UNRESOLVED")
            full_component = np.zeros((h, w), np.uint8)
            full_component[y:y+bh, x:x+bw] = component_roi
            candidates.append(PixelCandidate((x, y, bw, bh), kind, status, colors, why,
                                             body_link, solidity, area, full_component, outline,
                                             panel_outline, panel_fill, panel_cv))
    candidates.sort(key=lambda c: (c.bbox[1], c.bbox[0]))
    raw_mask = np.zeros((h, w), np.uint8)
    raw_mask[y0:y1, x0:x1] = combined
    t_extract = perf_counter()
    component_total_ms = (t_extract - t_mask) * 1000
    return FrameObservations(w, h, tuple(candidates), raw_mask,
                             {"roi_ms": (t_roi-t0)*1000, "hsv_ms": (t_hsv-t_roi)*1000,
                              "mask_ms": (t_mask-t_hsv)*1000, "connected_components_ms": cc_ms,
                              "candidate_extraction_ms": max(0.0, component_total_ms - cc_ms)})
