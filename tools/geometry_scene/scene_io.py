"""Versioned JSON serialization for renderer-only Scene documents."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .scene import Keyframe, Point, Scene, SceneNote, Segment


def scene_to_dict(scene: Scene) -> dict[str, Any]:
    return {
        "schema_version": scene.version,
        "run_id": scene.run_id,
        "coordinate_space": "source_native_pixels",
        "width": scene.width,
        "height": scene.height,
        "background_bgr": list(scene.background),
        "rails": [{"start": [r.start.x, r.start.y], "end": [r.end.x, r.end.y]} for r in scene.rails],
        "judgment_line": {"start": [scene.judgment_line.start.x, scene.judgment_line.start.y],
                          "end": [scene.judgment_line.end.x, scene.judgment_line.end.y]},
        "notes": [{
            "scene_note_id": n.scene_note_id, "kind": n.kind,
            "evidence_interval_pts": list(n.evidence_interval), "color_bgr": list(n.color),
            "head_fraction": n.head_fraction, "tail_fraction": n.tail_fraction,
            "lane_span": list(n.lane_span) if n.lane_span is not None else None,
            "source_color": n.source_color, "track_status": n.track_status,
            "kind_status": n.kind_status, "confidence": n.confidence,
            "head_status": n.head_status, "body_status": n.body_status, "tail_status": n.tail_status,
            "evidence_refs": list(n.evidence_refs), "inference_source": n.inference_source,
            "keyframes": [{"pts": k.pts, "x": k.x, "y": k.y, "width": k.width, "height": k.height,
                           "status": k.status, "provenance": list(k.provenance),
                           "outline": [[p.x, p.y] for p in k.outline]} for k in n.keyframes],
        } for n in scene.notes],
    }


def scene_from_dict(data: dict[str, Any]) -> Scene:
    if data.get("schema_version") != "2.0":
        raise ValueError(f"unsupported scene schema: {data.get('schema_version')!r}")
    rails = tuple(Segment(Point(*r["start"]), Point(*r["end"])) for r in data["rails"])
    j = data["judgment_line"]
    notes = tuple(SceneNote(
        n["scene_note_id"], n["kind"],
        tuple(Keyframe(k["pts"], k["x"], k["y"], k["width"], k["height"],
                       k.get("status", "OBSERVED"), tuple(k.get("provenance", ())),
                       tuple(Point(*p) for p in k.get("outline", ()))) for k in n["keyframes"]),
        tuple(n["evidence_interval_pts"]), tuple(n.get("color_bgr", (80, 210, 245))),
        n.get("head_fraction", 0.2), n.get("tail_fraction", 0.2),
        tuple(n["lane_span"]) if n.get("lane_span") is not None else None,
        n.get("source_color", "UNKNOWN"), n.get("track_status", "PROVISIONAL"),
        n.get("kind_status", "UNKNOWN"), n.get("confidence", 0.0),
        n.get("head_status", "UNKNOWN"), n.get("body_status", "UNKNOWN"),
        n.get("tail_status", "UNKNOWN"), tuple(n.get("evidence_refs", ())),
        n.get("inference_source", "SOURCE_OBSERVATION"),
    ) for n in data.get("notes", []))
    return Scene(data["width"], data["height"], rails,
                 Segment(Point(*j["start"]), Point(*j["end"])), notes,
                 data["schema_version"], data.get("run_id", "unknown"),
                 tuple(data.get("background_bgr", (12, 14, 20))))


def load_scene(path: Path) -> Scene:
    return scene_from_dict(json.loads(path.read_text(encoding="utf-8")))


def save_scene(scene: Scene, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(scene_to_dict(scene), indent=2), encoding="utf-8")
