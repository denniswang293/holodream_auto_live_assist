from __future__ import annotations

import csv
import base64
import json
import zlib
from pathlib import Path

import cv2
import numpy as np

from .geometry import Geometry
from .segment import Candidate, PRIMITIVE_COLORS


BG = (12, 16, 24)
RAIL = (54, 72, 91)
JUDGMENT = (30, 220, 250)


def blank_geometry(geometry: Geometry) -> np.ndarray:
    h, w = geometry.height, geometry.width
    out = np.empty((h, w, 3), np.uint8)
    out[:] = BG
    ys = np.arange(0, h, dtype=np.float32)
    rail_pts = []
    for rail in geometry.rails:
        pts = np.asarray([[round(rail.x(float(y))), round(float(y))]
                          for y in ys if y <= geometry.judgment_band[1] + 45], np.int32)
        rail_pts.append(pts)
    lane_fill = out.copy()
    y_end = min(h - 1, int(geometry.judgment_band[1] + 45))
    for i in range(6):
        poly = np.asarray([[round(geometry.rails[i].x(0)), 0],
                           [round(geometry.rails[i + 1].x(0)), 0],
                           [round(geometry.rails[i + 1].x(y_end)), y_end],
                           [round(geometry.rails[i].x(y_end)), y_end]], np.int32)
        cv2.fillConvexPoly(lane_fill, poly, (18 + i % 2, 23, 32))
    out = cv2.addWeighted(out, .45, lane_fill, .55, 0)
    for pts in rail_pts:
        cv2.polylines(out, [pts], False, RAIL, 2, cv2.LINE_AA)
    y = geometry.judgment_y
    cv2.line(out, (round(geometry.rails[0].x(y)), round(y)),
             (round(geometry.rails[-1].x(y)), round(y)), JUDGMENT, 3, cv2.LINE_AA)
    return out


def _color_bgr(name: str) -> tuple[int, int, int]:
    return PRIMITIVE_COLORS.get(name, (195, 195, 195))


def draw_candidate(canvas: np.ndarray, candidate: Candidate) -> None:
    if candidate.candidate_type not in ("TAP", "HOLD") or candidate.confidence < .62:
        return
    pts = np.asarray(candidate.polygon, dtype=np.int32).reshape((-1, 1, 2))
    if len(pts) < 3:
        return
    color = _color_bgr(candidate.color)
    cv2.fillPoly(canvas, [pts], color, cv2.LINE_AA)
    x, y, w, h = candidate.bbox
    if candidate.candidate_type == "HOLD":
        # Role shading is clipped to observed source-supported component
        # pixels. It never extends a hidden endpoint or bridges an occlusion.
        try:
            packed = zlib.decompress(base64.b64decode(candidate.mask_rle_zlib_b64))
            mask = np.unpackbits(np.frombuffer(packed, np.uint8), bitorder="little")
            mask = mask[:h * w].reshape(h, w).astype(bool)
            roi = canvas[y:y+h, x:x+w]
            top_end = max(1, round(h * .2)); bottom_start = max(top_end + 1, round(h * .8))
            tail_color = tuple(min(255, c + 24) for c in color)
            head_color = tuple(max(0, c - 24) for c in color)
            roi[:top_end][mask[:top_end]] = tail_color
            roi[top_end:bottom_start][mask[top_end:bottom_start]] = color
            roi[bottom_start:][mask[bottom_start:]] = head_color
        except (ValueError, zlib.error):
            pass


def geometry_frame(geometry: Geometry, candidates: list[Candidate]) -> np.ndarray:
    out = blank_geometry(geometry)
    for candidate in candidates:
        draw_candidate(out, candidate)
    return out


def write_frame_index(path: Path, rows: list[dict]) -> None:
    cols = ["output_frame", "source_frame", "video_pts_s", "capture_timestamp",
            "acquired_timestamp", "elapsed_s", "encoded_at_host", "frame_join"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader(); writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n")
