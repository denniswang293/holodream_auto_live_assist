"""Causal, reviewable semantic observations for offline lane-filter experiments.

This module adapts current V8.3 detections into an auditable format. It is not
an independently validated replacement detector and is deliberately not wired
into the live engine.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import cv2
import numpy as np

from .model import Detection, Geometry
from .perception import Perception


CHANNELS = ("lane", "tap_face", "hold_head", "hold_body", "hold_tail",
            "judgment_line", "effect_or_artifact", "unknown")
ROLE_COLORS = {
    "TAP_FACE": (40, 220, 80), "HOLD_HEAD": (0, 220, 255),
    "HOLD_BODY": (220, 120, 30), "HOLD_TAIL": (220, 40, 220),
    "FRAGMENT": (120, 160, 200), "EFFECT": (90, 90, 220),
    "UNKNOWN": (180, 180, 180),
}


@dataclass(frozen=True)
class LaneObservation:
    run_id: str
    source_frame: int
    video_frame: int
    captured_at: float
    acquired_at: float
    bbox_rectified: tuple[int, int, int, int]
    lane_span: tuple[float, float]
    candidate_keys: tuple[str, ...]
    role: str
    color_evidence: str
    shape_evidence: str
    motion_evidence: str
    connection_evidence: str
    confidence_basis: str
    fresh_observation: bool
    component_id: int
    candidate_id: str
    mask_ref: str
    reason_codes: tuple[str, ...]
    positive_evidence: tuple[str, ...]
    negative_evidence: tuple[str, ...]

    def csv_row(self) -> dict[str, Any]:
        row = asdict(self)
        for k, v in list(row.items()):
            if isinstance(v, (tuple, list)):
                row[k] = "|".join(map(str, v))
        return row


def role_for(d: Detection) -> str:
    return {"tap": "TAP_FACE", "hold_head": "HOLD_HEAD", "body": "HOLD_BODY",
            "hold_tail": "HOLD_TAIL", "plate_fragment": "FRAGMENT",
            "ambiguous": "UNKNOWN"}.get(d.kind, "UNKNOWN")


class LaneFilter:
    """Per-frame adapter with strictly past-only motion association."""

    def __init__(self, geometry: Geometry):
        self.geometry = geometry
        self.perception = Perception(geometry)
        self._past: list[tuple[float, Detection]] = []
        self._counter = 0

    def process(self, image: np.ndarray, *, run_id: str, source_frame: int,
                video_frame: int, captured_at: float, acquired_at: float
                ) -> tuple[list[LaneObservation], dict[str, np.ndarray], np.ndarray]:
        if acquired_at < captured_at:
            raise ValueError("acquired_at must be >= captured_at")
        normalized = self.geometry.normalize(image)
        rect = self.geometry.rectify(normalized)
        detections = self.perception.detect(normalized)
        masks = {name: np.zeros(rect.shape[:2], np.uint8) for name in CHANNELS}
        masks["lane"][:] = 255
        y = int(round(self.geometry.hit_y))
        cv2.line(masks["judgment_line"], (0, y), (self.geometry.plane_width - 1, y), 255, 2)
        canvas = np.zeros_like(rect)
        # Boundary lines document the configured lanes; no game background is retained.
        for row_y in (int(self.geometry.top_y), int(self.geometry.hit_y)):
            boundaries = self.geometry.boundaries(row_y)
            for x in boundaries:
                cv2.line(canvas, (int(round(x / self.geometry.width * self.geometry.plane_width)),
                                  int(row_y)),
                         (int(round(x / self.geometry.width * self.geometry.plane_width)),
                          int(row_y)), (100, 100, 100), 1)
        observations: list[LaneObservation] = []
        current: list[tuple[float, Detection]] = []
        for d in detections:
            role = role_for(d)
            self._counter += 1
            x, yy, w, h = d.bbox
            x0, y0 = max(0, x), max(0, yy)
            x1, y1 = min(rect.shape[1], x + w), min(rect.shape[0], yy + h)
            if x1 <= x0 or y1 <= y0:
                continue
            mask_name = {"TAP_FACE": "tap_face", "HOLD_HEAD": "hold_head",
                         "HOLD_BODY": "hold_body", "HOLD_TAIL": "hold_tail"}.get(role)
            if mask_name:
                masks[mask_name][y0:y1, x0:x1] = 255
            else:
                masks["unknown"][y0:y1, x0:x1] = 255
            motion = "no_prior_match"
            prior = [p for t, p in self._past if 0 < captured_at - t <= .25
                     and p.kind == d.kind and p.keys == d.keys and p.color == d.color]
            if prior:
                nearest = min(prior, key=lambda p: abs(p.y - d.y))
                dt = captured_at - max(t for t, p in self._past if p is nearest)
                dy = d.y - nearest.y
                motion = "past_same_direction_down" if dy > 0 and dt > 0 else "past_non_down_or_static"
            positive = ["legacy_panel_or_ribbon_detector", "six_lane_geometry_overlap"]
            negative = []
            if d.kind in ("ambiguous", "plate_fragment"):
                negative.append("incomplete_or_ambiguous_panel_evidence")
            if motion != "past_same_direction_down":
                negative.append("causal_motion_not_yet_confirmed")
            if d.kind in ("hold_head", "body", "hold_tail"):
                connection = f"same_frame_ribbon_depth_above={d.above:.1f},below={d.below:.1f}px"
                positive.append("local_ribbon_depth")
            else:
                connection = "not_established"
            observations.append(LaneObservation(
                run_id, int(source_frame), int(video_frame), float(captured_at), float(acquired_at),
                tuple(map(int, d.bbox)), tuple(map(float, d.span)), tuple(d.keys), role,
                f"hsv_class={d.color}", f"legacy_kind={d.kind};box={w}x{h};detector_score={d.score:.3f}",
                motion, connection, "measured_geometry+legacy_shape/color; score is not probability",
                True, int(d.component), f"obs-{video_frame}-{self._counter}",
                mask_name or "unknown", tuple(["legacy_perception_adapter"]), tuple(positive), tuple(negative)))
            cv2.rectangle(canvas, (x0, y0), (x1 - 1, y1 - 1), ROLE_COLORS.get(role, ROLE_COLORS["UNKNOWN"]), -1)
            current.append((captured_at, d))
        # Preserve only bounded history. No future frames, labels, or key events enter this path.
        self._past = (self._past + current)[-128:]
        return observations, masks, canvas
