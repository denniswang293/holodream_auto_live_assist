"""Small, versioned synthetic Scene schema in native source pixel coordinates.

Coordinates are (x, y), with origin at the upper-left. A Scene has seven rail
segments (six lanes) and one judgment segment. Note keyframes are source PTS
seconds; evidence intervals bound rendering. UNKNOWN notes/keyframes are never
rendered as confirmed geometry. A HOLD is one note ID with connected head,
body, and tail extents; provenance is descriptive evidence metadata, not pixels.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

EvidenceStatus = Literal["OBSERVED", "INFERRED_OCCLUSION", "AMBIGUOUS", "UNKNOWN"]
NoteKind = Literal["TAP", "HOLD", "UNKNOWN"]


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class Segment:
    start: Point
    end: Point


@dataclass(frozen=True)
class Keyframe:
    pts: float
    x: float
    y: float
    width: float
    height: float
    status: EvidenceStatus = "OBSERVED"
    provenance: tuple[str, ...] = ()
    outline: tuple[Point, ...] = ()


@dataclass(frozen=True)
class SceneNote:
    scene_note_id: str
    kind: NoteKind
    keyframes: tuple[Keyframe, ...]
    evidence_interval: tuple[float, float]
    color: tuple[int, int, int] = (80, 210, 245)  # BGR
    head_fraction: float = 0.2  # HOLD head/tail cap fractions, body is connected between
    tail_fraction: float = 0.2
    lane_span: tuple[int, int] | None = None
    source_color: str = "UNKNOWN"
    track_status: str = "PROVISIONAL"
    kind_status: str = "UNKNOWN"
    confidence: float = 0.0
    head_status: EvidenceStatus = "UNKNOWN"
    body_status: EvidenceStatus = "UNKNOWN"
    tail_status: EvidenceStatus = "UNKNOWN"
    evidence_refs: tuple[str, ...] = ()
    inference_source: str = "SOURCE_OBSERVATION"

    def __post_init__(self) -> None:
        object.__setattr__(self, "keyframes", tuple(sorted(self.keyframes, key=lambda k: k.pts)))


@dataclass(frozen=True)
class Scene:
    width: int
    height: int
    rails: tuple[Segment, ...]
    judgment_line: Segment
    notes: tuple[SceneNote, ...] = ()
    version: str = "2.0"
    run_id: str = "synthetic"
    background: tuple[int, int, int] = (12, 14, 20)

    def __post_init__(self) -> None:
        # Hold geometry is drawn before concurrent Tap panels. Sort once per scene,
        # not once per rendered frame.
        object.__setattr__(self, "notes", tuple(sorted(self.notes, key=lambda n: n.kind == "TAP")))
