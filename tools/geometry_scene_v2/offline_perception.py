#!/usr/bin/env python3
"""Offline-only source-coordinate observation fallbacks for Scene rebuilding.

The legacy rectified detector remains the primary observer. This wrapper adds
conservative native-frame edge-pair candidates when the rectification clips a
wide cyan Tap face at the playfield boundary. These are observations only;
Tracker association and Scene outputs remain provisional.
"""
from __future__ import annotations

import cv2
import numpy as np

from src.model import Detection, KEYS
from src.perception import Perception


class OfflinePerception:
    def __init__(self, geometry):
        self.geometry = geometry
        self.legacy = Perception(geometry)
        self.last_rect = None
        self.last_labels = None
        self.last_path = None

    def _native_cyan_tap_candidates(self, native: np.ndarray) -> list[tuple[Detection, list[float], int]]:
        height, width = native.shape[:2]
        sx, sy = width / 1280.0, height / 720.0
        hsv = cv2.cvtColor(native, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(native, cv2.COLOR_BGR2GRAY)
        gradient = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        cyan = cv2.inRange(hsv, np.array((84, 65, 110)), np.array((112, 255, 255)))
        colored = cv2.dilate(cyan, np.ones((3, 1), np.uint8))
        bright = hsv[:, :, 2] >= 135
        edge_top = max(0, round(self.geometry.top_y + 12 * sy))
        edge_bottom = min(height, round(self.geometry.hit_y + 5 * sy))
        raw_edges = (
            ((gradient >= 65) & bright).astype(np.uint8) * 255,
            ((gradient <= -65) & bright).astype(np.uint8) * 255,
        )
        kernel_width = max(20, round(56 * sx))
        edges: list[tuple[int, int, int, int]] = []
        for polarity, raw in ((1, raw_edges[0]), (-1, raw_edges[1])):
            raw[:edge_top] = 0
            raw[edge_bottom:] = 0
            lines = cv2.morphologyEx(
                raw & colored,
                cv2.MORPH_OPEN,
                cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_width, 1)),
            )
            contours, _ = cv2.findContours(lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                if w >= 70 * sx and h <= max(5, round(6 * sy)):
                    edges.append((x, y, w, polarity))

        minimum_width = 80 * sx
        minimum_height, maximum_height = 18 * sy, 100 * sy
        candidates: list[tuple[float, tuple[int, int, int, int], int, list[float]]] = []
        positive = [edge for edge in edges if edge[3] > 0]
        negative = [edge for edge in edges if edge[3] < 0]
        for x, y, w, _ in positive:
            for a, b, other_w, _ in negative:
                gap = b - y
                if not minimum_height - 6 * sy <= gap <= maximum_height:
                    continue
                overlap = max(0, min(x + w, a + other_w) - max(x, a))
                if overlap / min(w, other_w) < 0.68:
                    continue
                if max(w, other_w) > 1.8 * min(w, other_w):
                    continue
                # Use the union of the two measured horizontal edges. The
                # rectified playfield may have clipped one side of the face.
                left, right = min(x, a), max(x + w, a + other_w)
                top, bottom = y, b + max(2, round(3 * sy))
                box_w, box_h = right - left, bottom - top
                if box_w < minimum_width or box_h < minimum_height or box_h > maximum_height:
                    continue
                if box_w / box_h < 2.2:
                    continue
                fill = float(np.mean(cyan[top:bottom, left:right] > 0))
                if fill < 0.20:
                    continue
                center_x, center_y = (left + right) / 2, (top + bottom) / 2
                if center_y < edge_top or center_y > edge_bottom:
                    continue
                boundaries = np.asarray(self.geometry.boundaries(center_y), dtype=float)
                if center_x < boundaries[0] - 12 * sx or center_x > boundaries[-1] + 12 * sx:
                    continue
                lane = int(np.clip(np.searchsorted(boundaries, center_x, side="right") - 1, 0, 5))

                def to_rectified(source_x: float) -> float:
                    lane_index = int(np.clip(np.searchsorted(boundaries, source_x, side="right") - 1, 0, 5))
                    lane_width = max(1e-6, boundaries[lane_index + 1] - boundaries[lane_index])
                    fraction = np.clip((source_x - boundaries[lane_index]) / lane_width, 0.0, 1.0)
                    return float((lane_index + fraction) * self.geometry.lane_pixels)

                rect_left = max(0.0, min(float(self.geometry.plane_width), to_rectified(left)))
                rect_right = max(0.0, min(float(self.geometry.plane_width), to_rectified(right)))
                rect_width = rect_right - rect_left
                if rect_width < 12:
                    continue
                quality = 0.5 * fill + 0.5 * (overlap / min(w, other_w))
                candidates.append((
                    quality,
                    (round(rect_left), top, round(rect_width), box_h),
                    lane,
                    [float(left), float(top), float(box_w), float(box_h)],
                ))

        # Multiple pairings often describe the bevels of one plate. Retain one
        # stable candidate for each strongly overlapping face region.
        candidates.sort(key=lambda item: (item[0], item[1][2] * item[1][3]), reverse=True)
        kept: list[tuple[float, tuple[int, int, int, int], int, list[float]]] = []
        for item in candidates:
            _, (x, y, w, h), lane, _ = item
            duplicate = False
            for _, (a, b, aw, ah), kept_lane, _ in kept:
                ix = max(0, min(x + w, a + aw) - max(x, a))
                iy = max(0, min(y + h, b + ah) - max(y, b))
                union = w * h + aw * ah - ix * iy
                vertical_gap = max(y - (b + ah), b - (y + h), 0)
                adjacent_same_face = (
                    lane == kept_lane
                    and ix / max(1, min(w, aw)) >= 0.65
                    and vertical_gap <= 12 * (height / 720.0)
                )
                if (union > 0 and ix * iy / union >= 0.38) or adjacent_same_face:
                    duplicate = True
                    break
            if not duplicate:
                kept.append(item)

        return [
            (Detection(
                bbox=box,
                color="cyan",
                kind="tap",
                keys=(KEYS[lane],),
                score=quality,
                plane_width=self.geometry.plane_width,
                evidence=("OFFLINE_NATIVE_CYAN_EDGE_PAIR", "PROVISIONAL", "NOT_GROUND_TRUTH"),
                semantic_candidate="tap",
                face_quality=quality,
                full_face=True,
            ), source_bbox, lane)
            for quality, box, lane, source_bbox in kept
        ]

    @staticmethod
    def _overlap_over_min(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        intersection = max(0, min(ax + aw, bx + bw) - max(ax, bx)) * max(0, min(ay + ah, by + bh) - max(ay, by))
        return intersection / max(1, min(aw * ah, bw * bh))

    def detect(self, native: np.ndarray) -> list[Detection]:
        detections = self.legacy.detect(native)
        self.last_rect = self.legacy.last_rect
        self.last_labels = self.legacy.last_labels
        self.last_path = self.legacy.last_path
        native_observations = self._native_cyan_tap_candidates(native)
        additions = [record[0] for record in native_observations]
        self.last_native_observations = native_observations
        if not additions:
            return detections

        filtered: list[Detection] = []
        for detection in detections:
            duplicate_edge = False
            if detection.color == "cyan":
                dx, dy, dw, dh = detection.bbox
                for candidate in additions:
                    cx, cy, cw, ch = candidate.bbox
                    horizontal_overlap = max(0, min(dx + dw, cx + cw) - max(dx, cx))
                    horizontal_ratio = horizontal_overlap / max(1, min(dw, cw))
                    vertical_gap = max(dy - (cy + ch), cy - (dy + dh), 0)
                    thin_edge_near_face = (
                        (detection.kind == "plate_fragment" or dh <= 12 * (native.shape[0] / 720.0))
                        and vertical_gap <= 12 * (native.shape[0] / 720.0)
                        and horizontal_ratio >= 0.45
                    )
                    if (
                        self._overlap_over_min(detection.bbox, candidate.bbox) >= 0.30
                        or thin_edge_near_face
                    ):
                        duplicate_edge = True
                        break
            if duplicate_edge:
                continue
            filtered.append(detection)
        return filtered + additions
