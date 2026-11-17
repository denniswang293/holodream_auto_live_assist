"""Deterministic offline association of pixel candidates into scene-local tracks.

Tracks describe visual identity only. They do not establish physical note truth or
TAP/HOLD type. Candidate references and uncertainty are retained verbatim.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from .segmentation import FrameObservations, PixelCandidate

EvidenceStatus = Literal["OBSERVED", "INFERRED_OCCLUSION", "AMBIGUOUS", "UNKNOWN"]


@dataclass(frozen=True)
class TimedFrame:
    frame: int
    pts: float
    observations: FrameObservations


@dataclass(frozen=True)
class TrackObservation:
    frame: int
    pts: float
    candidate_ref: str
    bbox: tuple[int, int, int, int]
    status: EvidenceStatus
    candidate: PixelCandidate


@dataclass(frozen=True)
class TrackInterval:
    start_pts: float
    end_pts: float
    status: EvidenceStatus
    before_ref: str
    after_ref: str


@dataclass(frozen=True)
class SceneTrack:
    track_id: str
    kind: str
    colors: tuple[str, ...]
    observations: tuple[TrackObservation, ...]
    intervals: tuple[TrackInterval, ...]


@dataclass(frozen=True)
class AssociationConfig:
    max_gap_ms: float = 120.0
    max_speed_px_per_second: float = 1800.0
    max_center_error_px: float = 52.0
    max_x_center_error_px: float = 38.0
    max_height_ratio: float = 2.4
    ambiguity_margin: float = 0.18
    min_panel_aspect: float = 2.5
    min_panel_solidity: float = 0.88
    max_panel_height: int = 48
    max_panel_width: int = 280


def _center(b: tuple[int, int, int, int]) -> tuple[float, float]:
    return b[0] + b[2] / 2, b[1] + b[3] / 2


def _compatible_colors(a: Sequence[str], b: Sequence[str]) -> bool:
    return not a or not b or bool(set(a) & set(b))


def _trackable(candidate: PixelCandidate, cfg: AssociationConfig) -> bool:
    if len(candidate.colors) != 1:
        return False
    if any(marker in candidate.provenance for marker in
           ("MERGED_OR_OCCLUDED_REGION", "CONNECTED_COLOR_OVERLAP", "OWNERSHIP_UNRESOLVED")):
        return False
    x, y, width, height = candidate.bbox
    panel_aspect = width / max(1, height)
    panel_geometry = (cfg.min_panel_aspect <= panel_aspect and
                      width <= cfg.max_panel_width and height <= cfg.max_panel_height and
                      candidate.solidity >= cfg.min_panel_solidity)
    body_geometry = candidate.body_link_evidence and height >= 60 and candidate.component_area >= 1500
    return panel_geometry or body_geometry


def _predict(track: list[TrackObservation], pts: float) -> tuple[float, float]:
    x1, y1 = _center(track[-1].bbox)
    if len(track) < 2:
        return x1, y1
    prev = track[-2]
    dt = track[-1].pts - prev.pts
    if dt <= 0:
        return x1, y1
    x0, y0 = _center(prev.bbox)
    scale = min(2.0, max(0.0, (pts - track[-1].pts) / dt))
    return x1 + (x1 - x0) * scale, y1 + (y1 - y0) * scale


def associate_frames(frames: Sequence[TimedFrame], config: AssociationConfig | None = None) -> tuple[SceneTrack, ...]:
    """Associate ordered source observations; use ``frame_N/region_M`` references.

    Matching is one-to-one and gated by time, predicted displacement, width/height,
    and color family. UNKNOWN candidates can form UNKNOWN-only review tracks, but
    cannot join a candidate track that may support typing. A short gap is labeled
    inferred only for non-UNKNOWN evidence; missing observations never create a
    candidate.
    """
    cfg = config or AssociationConfig()
    if cfg.max_gap_ms < 0:
        raise ValueError("max_gap_ms must be non-negative")
    ordered = sorted(frames, key=lambda f: (f.pts, f.frame))
    if any(b.pts < a.pts for a, b in zip(ordered, ordered[1:])):
        raise ValueError("frame PTS must be monotonic")
    tracks: list[list[TrackObservation]] = []
    kinds: list[str] = []
    colors: list[tuple[str, ...]] = []
    active_tracks: list[int] = []
    serial = 0
    for tf in ordered:
        candidates = [(idx, c) for idx, c in enumerate(tf.observations.candidates) if _trackable(c, cfg)]
        active: list[int] = []
        for ti in active_tracks:
            tr = tracks[ti]
            age_ms = (tf.pts - tr[-1].pts) * 1000
            if 0 < age_ms <= cfg.max_gap_ms:
                active.append(ti)
        edges: list[tuple[float, int, int]] = []
        for ci, (region_idx, c) in enumerate(candidates):
            cx, cy = _center(c.bbox)
            for ti in active:
                tr = tracks[ti]
                old = tr[-1]
                if old.frame == tf.frame or not _compatible_colors(colors[ti], c.colors):
                    continue
                # Keep low-confidence pixel tracks separate from candidates that
                # may support TAP/HOLD typing. UNKNOWN links remain UNKNOWN evidence.
                if (old.candidate.status == "UNKNOWN") != (c.status == "UNKNOWN"):
                    continue
                dt = tf.pts - old.pts
                if dt <= 0:
                    continue
                px, py = _predict(tr, tf.pts)
                ox, oy = _center(old.bbox)
                dx, dy = cx - px, cy - py
                distance = (dx * dx + dy * dy) ** 0.5
                if distance > min(cfg.max_center_error_px, cfg.max_speed_px_per_second * dt):
                    continue
                if abs(cx - px) > cfg.max_x_center_error_px:
                    continue
                if max(c.bbox[3], old.bbox[3]) / max(1, min(c.bbox[3], old.bbox[3])) > cfg.max_height_ratio:
                    continue
                # Prefer continuity while modestly penalizing lateral drift.
                edges.append((distance + abs(dx) * 0.35, ti, ci))
        edges.sort()
        # Cache the best alternative edge for each endpoint instead of rescanning
        # every edge for every match. This preserves the same ambiguity rule.
        by_track: dict[int, list[tuple[float, int]]] = {}
        by_candidate: dict[int, list[tuple[float, int]]] = {}
        for edge_id, (score, ti, ci) in enumerate(edges):
            by_track.setdefault(ti, []).append((score, edge_id))
            by_candidate.setdefault(ci, []).append((score, edge_id))
        for group in (*by_track.values(), *by_candidate.values()):
            group.sort()

        def best_alternative(group: list[tuple[float, int]], edge_id: int) -> float | None:
            if not group:
                return None
            if group[0][1] != edge_id:
                return group[0][0]
            return group[1][0] if len(group) > 1 else None

        used_tracks: set[int] = set()
        used_candidates: set[int] = set()
        for edge_id, (score, ti, ci) in enumerate(edges):
            if ti in used_tracks or ci in used_candidates:
                continue
            # A near-tie means identity is not unique. Leave the observation isolated.
            track_alt = best_alternative(by_track.get(ti, []), edge_id)
            candidate_alt = best_alternative(by_candidate.get(ci, []), edge_id)
            alternatives = [x for x in (track_alt, candidate_alt) if x is not None]
            if alternatives and min(alternatives) - score < cfg.ambiguity_margin:
                continue
            region_idx, c = candidates[ci]
            ref = f"frame_{tf.frame:06d}/region_{region_idx:02d}"
            evidence_status: EvidenceStatus = "UNKNOWN" if c.status == "UNKNOWN" else "OBSERVED"
            tracks[ti].append(TrackObservation(tf.frame, tf.pts, ref, c.bbox, evidence_status, c))
            used_tracks.add(ti)
            used_candidates.add(ci)
        for ci, (region_idx, c) in enumerate(candidates):
            if ci in used_candidates:
                continue
            serial += 1
            status: EvidenceStatus = "UNKNOWN" if c.status == "UNKNOWN" else ("AMBIGUOUS" if c.status == "AMBIGUOUS" else "OBSERVED")
            ref = f"frame_{tf.frame:06d}/region_{region_idx:02d}"
            tracks.append([TrackObservation(tf.frame, tf.pts, ref, c.bbox, status, c)])
            kinds.append(c.kind)
            colors.append(c.colors)
            active.append(len(tracks) - 1)
        active_tracks = active
    result: list[SceneTrack] = []
    for i, tr in enumerate(tracks):
        intervals: list[TrackInterval] = []
        for before, after in zip(tr, tr[1:]):
            if after.pts > before.pts and after.frame - before.frame > 1:
                gap_ms = (after.pts - before.pts) * 1000
                if before.status == "UNKNOWN" or after.status == "UNKNOWN":
                    intervals.append(TrackInterval(before.pts, after.pts, "UNKNOWN", before.candidate_ref, after.candidate_ref))
                elif gap_ms <= cfg.max_gap_ms:
                    intervals.append(TrackInterval(before.pts, after.pts, "INFERRED_OCCLUSION", before.candidate_ref, after.candidate_ref))
                else:
                    intervals.append(TrackInterval(before.pts, after.pts, "UNKNOWN", before.candidate_ref, after.candidate_ref))
        result.append(SceneTrack(f"track_{i+1:06d}", kinds[i], colors[i], tuple(tr), tuple(intervals)))
    return tuple(result)
