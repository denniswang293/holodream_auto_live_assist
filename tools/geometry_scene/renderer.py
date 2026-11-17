"""Pure Scene-to-raster renderer. It has no source-video or perception API."""
from __future__ import annotations

from functools import lru_cache

import cv2
import numpy as np

from .scene import Keyframe, Scene


def _polygon_area(points: np.ndarray) -> float:
    return float(np.sum(points[:, 0] * np.roll(points[:, 1], -1) -
                        points[:, 1] * np.roll(points[:, 0], -1)))


@lru_cache(maxsize=8192)
def _resample_outline(outline: tuple, count: int = 32) -> tuple:
    """Normalize a polygon so changing contour vertex counts remain interpolable."""
    if len(outline) < 3:
        return outline
    points = np.asarray([(p.x, p.y) for p in outline], dtype=np.float64)
    if np.linalg.norm(points[0] - points[-1]) < 1e-6:
        points = points[:-1]
    keep = np.ones(len(points), dtype=bool)
    if len(points) > 1:
        keep[1:] = np.linalg.norm(np.diff(points, axis=0), axis=1) > 1e-6
    points = points[keep]
    if len(points) < 3:
        return outline
    if _polygon_area(points) < 0:
        points = points[::-1]
    start = min(range(len(points)), key=lambda i: (points[i, 1], points[i, 0]))
    points = np.roll(points, -start, axis=0)
    edges = np.roll(points, -1, axis=0) - points
    lengths = np.linalg.norm(edges, axis=1)
    perimeter = float(lengths.sum())
    if perimeter <= 1e-6:
        return outline
    cumulative = np.concatenate(([0.0], np.cumsum(lengths)))
    samples = []
    for distance in np.linspace(0.0, perimeter, count, endpoint=False):
        edge_idx = min(len(lengths) - 1, int(np.searchsorted(cumulative, distance, side="right") - 1))
        frac = (distance - cumulative[edge_idx]) / max(1e-9, lengths[edge_idx])
        samples.append(points[edge_idx] + frac * edges[edge_idx])
    return tuple(type(outline[0])(*map(float, p)) for p in samples)


@lru_cache(maxsize=8192)
def _matching_outlines(left: tuple, right: tuple) -> tuple[tuple, tuple]:
    """Resample both contours and align their cyclic starting vertex."""
    a = _resample_outline(left)
    b = _resample_outline(right)
    if len(a) != len(b) or len(a) < 3:
        return (), ()
    aa = np.asarray([(p.x, p.y) for p in a])
    bb = np.asarray([(p.x, p.y) for p in b])
    best = min((np.roll(bb, shift, axis=0) for shift in range(len(bb))),
               key=lambda candidate: float(np.sum((aa - candidate) ** 2)))
    point_type = type(a[0])
    return a, tuple(point_type(float(x), float(y)) for x, y in best)


def _at(keyframes: tuple[Keyframe, ...], t: float) -> Keyframe | None:
    """Linear interpolation only between adjacent compatible known keyframes."""
    ordered = keyframes  # SceneNote normalizes keyframe order once at construction.
    for k in ordered:
        if t == k.pts and k.status in ("OBSERVED", "INFERRED_OCCLUSION"):
            return k
    for left, right in zip(ordered, ordered[1:]):
        if left.pts <= t <= right.pts:
            if (left.status not in ("OBSERVED", "INFERRED_OCCLUSION") or
                    right.status not in ("OBSERVED", "INFERRED_OCCLUSION") or
                    left.status != right.status or right.pts == left.pts):
                return None
            f = (t - left.pts) / (right.pts - left.pts)
            outline = ()
            if left.outline and right.outline:
                left_outline, right_outline = _matching_outlines(left.outline, right.outline)
                outline = tuple(type(a)(a.x + f * (b.x - a.x), a.y + f * (b.y - a.y))
                                for a, b in zip(left_outline, right_outline))
            return Keyframe(t, *(getattr(left, n) + f * (getattr(right, n) - getattr(left, n))
                                 for n in ("x", "y", "width", "height")),
                            status=left.status, outline=outline)
    return None


def render_scene_frame(scene: Scene, t: float) -> np.ndarray:
    """Return a fresh BGR frame containing only scene rails, judgment line, notes."""
    image = np.empty((scene.height, scene.width, 3), dtype=np.uint8)
    image[:] = scene.background
    for rail in scene.rails:
        cv2.line(image, (round(rail.start.x), round(rail.start.y)),
                 (round(rail.end.x), round(rail.end.y)), (76, 82, 96), 1, cv2.LINE_AA)
    j = scene.judgment_line
    cv2.line(image, (round(j.start.x), round(j.start.y)), (round(j.end.x), round(j.end.y)), (130, 140, 160), 2, cv2.LINE_AA)
    # Draw long Hold geometry first so a concurrent Tap remains visibly distinct.
    for note in scene.notes:
        lo, hi = note.evidence_interval
        if note.kind == "UNKNOWN" or not lo <= t <= hi:
            continue
        k = _at(note.keyframes, t)
        if k is None:
            continue
        x1, x2 = round(k.x), round(k.x + k.width)
        y1, y2 = round(k.y), round(k.y + k.height)
        if len(k.outline) >= 3:
            polygon = np.asarray([[(round(p.x), round(p.y)) for p in k.outline]], dtype=np.int32)
            cv2.fillPoly(image, polygon, note.color)
            continue
        if note.kind == "TAP":
            cv2.rectangle(image, (x1, y1), (x2, y2), note.color, -1)
        elif note.kind == "HOLD":
            h = max(1, round((y2-y1) * note.head_fraction))
            tail = max(1, round((y2-y1) * note.tail_fraction))
            # Adjacent filled bands share their boundary: one connected object.
            cv2.rectangle(image, (x1, y1), (x2, min(y2, y1+h)), note.color, -1)
            cv2.rectangle(image, (x1, min(y2, y1+h)), (x2, max(y1+h, y2-tail)), note.color, -1)
            cv2.rectangle(image, (x1, max(y1+h, y2-tail)), (x2, y2), note.color, -1)
    return image
