"""Pixel-backed semantic lane observations for offline V8.4 experiments."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any

import cv2
import numpy as np

from .lane_segmentation import LanePixelSegmenter, SegmentationResult
from .model import Geometry, KEYS

MASK_CHANNELS = ("lane", "tap_face", "hold_head", "hold_body", "hold_tail",
                 "effect_or_artifact", "unknown", "judgment_line")
PREVIEW_COLORS = {
    "TAP_FACE": (40, 220, 70), "HOLD_HEAD": (0, 220, 255),
    "HOLD_BODY": (255, 120, 20), "HOLD_TAIL": (220, 40, 220),
    "EFFECT": (40, 80, 255), "UNKNOWN": (170, 170, 170),
}
ROLE_MASK = {"TAP_FACE": "tap_face", "HOLD_HEAD": "hold_head",
             "HOLD_BODY": "hold_body", "HOLD_TAIL": "hold_tail",
             "EFFECT": "effect_or_artifact", "UNKNOWN": "unknown"}


@dataclass(frozen=True)
class LaneObservation:
    run_id: str
    source_frame: int
    video_frame: int
    captured_at: float
    acquired_at: float
    bbox_rectified: tuple[int, int, int, int]
    polygon_rectified: tuple[tuple[int, int], ...]
    lane_span: tuple[float, float]
    candidate_keys: tuple[str, ...]
    role: str
    color_evidence: str
    shape_evidence: str
    motion_evidence: str
    connection_evidence: str
    confidence_basis: str
    status: str
    fresh_observation: bool
    component_id: int
    candidate_id: str
    pixel_area: int
    mask_ref: str
    reason_codes: tuple[str, ...]
    positive_evidence: tuple[str, ...]
    negative_evidence: tuple[str, ...]
    ambiguity: tuple[str, ...]

    def csv_row(self) -> dict[str, Any]:
        row = asdict(self)
        for key, value in row.items():
            if isinstance(value, (tuple, list)):
                row[key] = "|".join(map(str, value))
        return row


class LaneFilter:
    """Runs independent current-frame pixel segmentation, never legacy boxes."""

    def __init__(self, geometry: Geometry, segmenter: LanePixelSegmenter | None = None):
        self.geometry = geometry
        self.segmenter = segmenter or LanePixelSegmenter()
        self._past: list[tuple[float, tuple[int, int, int, int], str, str]] = []

    def segment_rectified(self, rectified: np.ndarray, *, frame_index: int | None = None) -> SegmentationResult:
        return self.segmenter.segment(rectified, self.geometry, frame_index=frame_index)

    def process(self, image: np.ndarray, *, run_id: str, source_frame: int,
                video_frame: int, captured_at: float, acquired_at: float
                ) -> tuple[list[LaneObservation], dict[str, np.ndarray], np.ndarray, np.ndarray, SegmentationResult]:
        normalized = self.geometry.normalize(image)
        rectified = self.geometry.rectify(normalized)
        return self.process_rectified(rectified, run_id=run_id, source_frame=source_frame,
            video_frame=video_frame, captured_at=captured_at, acquired_at=acquired_at)

    def process_rectified(self, rectified: np.ndarray, *, run_id: str, source_frame: int,
                video_frame: int, captured_at: float, acquired_at: float
                ) -> tuple[list[LaneObservation], dict[str, np.ndarray], np.ndarray, np.ndarray, SegmentationResult]:
        """Process a caller's already normalized/rectified frame exactly once."""
        if not np.isfinite(captured_at) or not np.isfinite(acquired_at) or acquired_at < captured_at:
            raise ValueError("capture/acquired timestamps must be finite and ordered")
        segment_start=perf_counter()
        result = self.segment_rectified(rectified, frame_index=video_frame)
        segment_ms=(perf_counter()-segment_start)*1000
        observations: list[LaneObservation] = []
        lane_width = self.geometry.lane_pixels
        conversion_start=perf_counter()
        for component in result.components:
            role = {"tap_face": "TAP_FACE", "hold_head": "HOLD_HEAD", "hold_body": "HOLD_BODY",
                    "hold_tail": "HOLD_TAIL", "effect_or_artifact": "EFFECT"}.get(component.role, "UNKNOWN")
            x, y, width, height = component.bbox
            span = (x / self.geometry.plane_width, (x + width) / self.geometry.plane_width)
            keys = tuple(key for index, key in enumerate(KEYS)
                         if min(x + width, (index + 1) * lane_width) - max(x, index * lane_width) >= 4)
            prior = [(t, box) for t, box, old_role, old_color in self._past
                     if old_role == role and old_color == component.color and
                     0 < captured_at - t <= .25 and
                     min(x + width, box[0] + box[2]) > max(x, box[0])]
            motion = "no_prior_component_match"
            if prior:
                t, box = min(prior, key=lambda pair: abs((pair[1][1] + pair[1][3] / 2) - (y + height / 2)))
                dy = (y + height / 2) - (box[1] + box[3] / 2)
                motion = "past_same_role_downward" if dy > 0 else "past_same_role_static_or_upward"
            link = ("observed_connected_ribbon_endpoint" if role in ("HOLD_HEAD", "HOLD_TAIL")
                    else "same_frame_connected_region" if role == "HOLD_BODY" else "not_established")
            channel = ROLE_MASK.get(role, "unknown")
            reasons = list(component.ambiguity)
            if role == "UNKNOWN":
                reasons.extend(component.negative or ("semantic_role_not_confirmed",))
            observations.append(LaneObservation(
                run_id, int(source_frame), int(video_frame), float(captured_at), float(acquired_at),
                tuple(map(int, component.bbox)), tuple(component.polygon), tuple(map(float, span)), keys,
                role, component.color, f"bbox={width}x{height};observed_pixels={component.area}",
                motion, link, "current-frame HSV pixels, connected-component area/shape; no probability score",
                "OBSERVED" if component.role != "unknown" else "UNKNOWN",
                True, int(component.component_id), f"obs-{video_frame}-{component.component_id}",
                int(component.area), channel, tuple(sorted(set(reasons))), tuple(component.positive),
                tuple(component.negative), tuple(component.ambiguity)))
        association_start=perf_counter()
        self._past = (self._past + [(captured_at, c.bbox,
                                    {"tap_face": "TAP_FACE", "hold_head": "HOLD_HEAD",
                                     "hold_body": "HOLD_BODY", "hold_tail": "HOLD_TAIL",
                                     "effect_or_artifact": "EFFECT"}.get(c.role, "UNKNOWN"), c.color)
                                   for c in result.components])[-256:]
        temporal_ms=(perf_counter()-association_start)*1000
        conversion_ms=max(0.,(perf_counter()-conversion_start)*1000-temporal_ms)
        preview_start=perf_counter()
        preview = np.zeros_like(rectified)
        for role, mask_name in ROLE_MASK.items():
            color = PREVIEW_COLORS[role]
            preview[result.masks[mask_name] > 0] = color
        # Geometry lines are visualization only. Semantic masks remain only
        # source-supported pixels and never contain painted boxes.
        for lane in range(7):
            pts = []
            for yy in np.linspace(self.geometry.top_y, self.geometry.hit_y, 24):
                xx = self.geometry.boundaries(yy)[lane] * self.geometry.plane_width / self.geometry.width
                pts.append((round(xx), round(yy)))
            cv2.polylines(preview, [np.asarray(pts, np.int32)], False, (105, 105, 105), 1)
        cv2.line(preview, (0, round(self.geometry.hit_y)),
                 (self.geometry.plane_width - 1, round(self.geometry.hit_y)), (0, 230, 255), 2)
        self.segmenter.last_profile={**getattr(self.segmenter,"last_profile",{}),
            "segmentation_ms":segment_ms,"data_conversion_ms":conversion_ms,
            "temporal_association_ms":temporal_ms,
            "preview_render_ms":(perf_counter()-preview_start)*1000}
        # Exact same rectified coordinate space for source and segmentation preview.
        return observations, result.masks, preview, rectified, result
