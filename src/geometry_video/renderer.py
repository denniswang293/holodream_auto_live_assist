"""Draw geometry primitives on a clean background; never composites source pixels."""
from __future__ import annotations

import cv2
import numpy as np

from .geometry import VideoGeometry
from .segmenter import PALETTE, Candidate


def _fill_polygon(image: np.ndarray, points, color, *, alpha: float = 1.0, outline=None, thickness=2):
    if len(points) < 3:
        return
    polygon = np.asarray(points, dtype=np.int32).reshape((-1, 1, 2))
    if alpha >= 1.0:
        cv2.fillPoly(image, [polygon], color, cv2.LINE_AA)
    else:
        layer = image.copy()
        cv2.fillPoly(layer, [polygon], color, cv2.LINE_AA)
        cv2.addWeighted(layer, alpha, image, 1-alpha, 0, dst=image)
    if outline is not None:
        cv2.polylines(image, [polygon], True, outline, thickness, cv2.LINE_AA)


def render_geometry_frame(geometry: VideoGeometry, objects: list[Candidate]) -> np.ndarray:
    image = np.full((geometry.height, geometry.width, 3), (10, 13, 22), dtype=np.uint8)
    bottom = round(geometry.judgment_y)
    lane_colors = ((18, 22, 34), (15, 19, 31))
    for lane in range(6):
        polygon = geometry.lane_polygon(lane, 0, bottom)
        _fill_polygon(image, polygon, lane_colors[lane % 2], alpha=1.0)
    for rail in geometry.rails:
        pts = np.array([[round(rail.x(0)), 0], [round(rail.x(bottom)), bottom]], np.int32)
        cv2.line(image, tuple(pts[0]), tuple(pts[1]), (54, 66, 86), 2, cv2.LINE_AA)
    for candidate in objects:
        if candidate.class_name == "TAP":
            color = PALETTE[candidate.color_name]
            _fill_polygon(image, candidate.polygon, color, alpha=.92,
                          outline=(230, 240, 255), thickness=2)
        elif candidate.class_name == "HOLD":
            color = PALETTE[candidate.color_name]
            part_colors = {"HOLD_BODY": color, "HOLD_TAIL": tuple(int(v*.72) for v in color),
                           "HOLD_HEAD": tuple(min(255, int(v*1.12)) for v in color)}
            for part in candidate.parts:
                _fill_polygon(image, part["polygon"], part_colors[part["kind"]], alpha=.9,
                              outline=(225, 242, 252), thickness=1)
    outer_left = round(geometry.rails[0].x(bottom))
    outer_right = round(geometry.rails[-1].x(bottom))
    cv2.line(image, (outer_left, bottom), (outer_right, bottom), (235, 246, 255), 3, cv2.LINE_AA)
    return image

