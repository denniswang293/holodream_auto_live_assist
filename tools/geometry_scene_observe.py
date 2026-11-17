"""Source observation and scene reconstruction; never writes Live inputs."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import time
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np

from tools.geometry_scene.association import AssociationConfig, TimedFrame, associate_frames
from tools.geometry_scene.scene import Keyframe, Point, Scene, SceneNote, Segment
from tools.geometry_scene.scene_io import save_scene
from tools.geometry_scene.segmentation import HSVBand, PixelCandidate, SegmentationConfig, segment_frame


RAILS_TOP = (590, 607, 624, 641, 658, 675, 692)
RAILS_BOTTOM = (60, 253, 446, 639, 832, 1025, 1218)
BOARD_POLYGON = ((590, 20), (693, 20), (1220, 560), (60, 560))


def percentile(values: list[float], q: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=np.float64), q)) if values else 0.0


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stage_summary(samples: dict[str, list[float]]) -> list[dict[str, float | int | str]]:
    rows = []
    for name, values in samples.items():
        rows.append({"stage": name, "samples": len(values),
                     "mean_ms": statistics.fmean(values) if values else 0.0,
                     "p50_ms": percentile(values, 50), "p95_ms": percentile(values, 95),
                     "max_ms": max(values, default=0.0)})
    return rows


def compact_candidate(c: PixelCandidate) -> PixelCandidate:
    return replace(c, mask=np.empty((0, 0), dtype=np.uint8))


def classify_track(track) -> tuple[str, str, float, str]:
    obs = track.observations
    if len(obs) < 3:
        return "UNKNOWN", "INSUFFICIENT_TEMPORAL_SUPPORT", 0.0, "TOO_FEW_OBSERVATIONS"
    if all(o.candidate.status == "UNKNOWN" for o in obs):
        return "UNKNOWN", "LOW_CONFIDENCE_PIXEL_TRACK", 0.0, "UNKNOWN_STATUS_EVIDENCE_PATH"
    colors = set(track.colors)
    if len(colors) != 1:
        return "UNKNOWN", "COLOR_OWNERSHIP_AMBIGUOUS", 0.0, "MULTIPLE_COLOR_FAMILIES"
    times = [o.pts for o in obs]
    ys = [o.bbox[1] + o.bbox[3] / 2 for o in obs]
    dt = times[-1] - times[0]
    displacement = ys[-1] - ys[0]
    velocities = [(b-a)/(tb-ta) for a,b,ta,tb in zip(ys,ys[1:],times,times[1:]) if tb > ta]
    if dt <= 0 or displacement < 8 or not velocities:
        return "UNKNOWN", "MOTION_NOT_CONFIRMED", 0.0, "NO_COHERENT_DOWNWARD_TRAJECTORY"
    if (sum(v < -80 for v in velocities) / len(velocities) > 0.08 or
            sum(v > 900 for v in velocities) / len(velocities) > 0.05):
        return "UNKNOWN", "MOTION_OUTLIER", 0.0, "TRAJECTORY_SPEED_OUTLIER"
    if any(any(token in ref for token in ("MERGED_OR_OCCLUDED_REGION", "CONNECTED_COLOR_OVERLAP", "OWNERSHIP_UNRESOLVED"))
           for o in obs for ref in o.candidate.provenance):
        return "UNKNOWN", "OWNERSHIP_AMBIGUOUS", 0.0, "MERGED_OR_OCCLUDED_EVIDENCE"
    # Tap hypothesis requires repeated compact, high-solidity panel geometry and
    # observed downward motion. Hue alone never promotes an object to TAP.
    if track.colors == ("cyan",):
        compact = []
        for o in obs:
            c = o.candidate
            if len(c.panel_outline) != 4:
                continue
            p0, p1, _, p3 = c.panel_outline
            pw = ((p1[0]-p0[0])**2 + (p1[1]-p0[1])**2)**0.5
            ph = ((p3[0]-p0[0])**2 + (p3[1]-p0[1])**2)**0.5
            if (2.5 <= pw / max(1.0, ph) <= 14 and 40 <= pw <= 280 and 6 <= ph <= 48
                    and c.solidity >= 0.90 and c.panel_fill_ratio >= 0.90
                    and c.panel_profile_cv <= 0.06 and len(c.outline) <= 30
                    and c.component_area <= 18_000):
                compact.append(o)
        if len(compact) >= max(3, int(0.8 * len(obs))):
            return "TAP", "PROVISIONAL_MORPHOLOGY_AND_TEMPORAL_MOTION", 0.78, "COMPACT_PANEL_TRACK"
    if track.colors == ("green",):
        linked = [o for o in obs if o.candidate.body_link_evidence and o.bbox[3] >= 60]
        if len(linked) >= max(3, int(0.8 * len(obs))):
            return "HOLD", "PROVISIONAL_CONNECTED_BODY_AND_TEMPORAL_MOTION", 0.72, "CONNECTED_BODY_TRACK"
    return "UNKNOWN", "TYPE_UNRESOLVED", 0.0, "TRACK_DOES_NOT_MEET_TYPED_RULES"


def lane_span_for_bbox(bbox: tuple[int, int, int, int]) -> tuple[int, int] | None:
    x, y, w, h = bbox
    yc = min(560.0, max(20.0, y + h / 2))
    f = (yc - 20.0) / 540.0
    rails = [a + f * (b - a) for a, b in zip(RAILS_TOP, RAILS_BOTTOM)]
    left, right = x, x + w
    lanes = [i for i in range(6) if right >= rails[i] and left <= rails[i + 1]]
    return (min(lanes), max(lanes)) if lanes and len(lanes) <= 2 else None


def process_run(video: Path, index_path: Path, frame_index_path: Path, run_out: Path, run_id: str) -> dict:
    run_out.mkdir(parents=True, exist_ok=True)
    with frame_index_path.open("r", encoding="utf-8-sig", newline="") as f:
        source_index = [r for r in csv.DictReader(f) if r["run_id"] == run_id]
    if not source_index:
        raise ValueError(f"empty frame index for {run_id}")
    acquired0 = float(source_index[0]["acquired_timestamp"])
    cfg = SegmentationConfig(
        cyan=(HSVBand((85, 80, 180), (112, 255, 255)),),
        green=(HSVBand((38, 80, 75), (84, 255, 255)),),
        calibration_polygon=BOARD_POLYGON, min_area=180, min_panel_width=30,
        min_panel_height=6, body_min_vertical_ratio=1.25,
    )
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"cannot decode video: {video}")
    frame_records: list[TimedFrame] = []
    timings: dict[str, list[float]] = {k: [] for k in (
        "decode_ms", "normalize_rectify_ms", "hsv_ms", "mask_segmentation_ms",
        "connected_components_ms", "candidate_extraction_ms", "data_conversion_ms")}
    observation_path = run_out / "source_observations.jsonl"
    decoded = 0
    try:
        with observation_path.open("w", encoding="utf-8") as out:
            while True:
                tdec = time.perf_counter()
                ok, frame = cap.read()
                decode_ms = (time.perf_counter() - tdec) * 1000
                if not ok:
                    break
                if decoded >= len(source_index):
                    raise ValueError(f"video has more frames than index for {run_id}")
                timings["decode_ms"].append(decode_ms)
                timings["normalize_rectify_ms"].append(0.0)  # Native source coordinates are retained unchanged.
                rec = source_index[decoded]
                pts = float(rec["acquired_timestamp"]) - acquired0
                tseg = time.perf_counter()
                found = segment_frame(frame, cfg)
                for key in ("hsv_ms", "mask_ms", "connected_components_ms", "candidate_extraction_ms"):
                    target = "mask_segmentation_ms" if key == "mask_ms" else key
                    timings[target].append(found.stage_ms.get(key, 0.0))
                tconv = time.perf_counter()
                converted = []
                for ridx, candidate in enumerate(found.candidates):
                    x, y, w, h = candidate.bbox
                    converted.append({
                        "evidence_ref": f"frame_{decoded:06d}/region_{ridx:02d}",
                        "bbox": [x, y, w, h], "outline": [list(p) for p in candidate.outline],
                        "panel_outline": [list(p) for p in candidate.panel_outline],
                        "panel_fill_ratio": candidate.panel_fill_ratio,
                        "panel_profile_cv": candidate.panel_profile_cv,
                        "component_area": candidate.component_area, "solidity": candidate.solidity,
                        "colors": list(candidate.colors), "kind_hypothesis": candidate.kind,
                        "status": candidate.status, "body_link_evidence": candidate.body_link_evidence,
                        "provenance": list(candidate.provenance),
                    })
                row = {"run_id": run_id, "video_frame": decoded, "source_frame": int(rec["source_frame"]),
                       "source_pts_seconds": float(rec["source_pts_seconds"]),
                       "capture_timestamp": float(rec["capture_timestamp"]),
                       "acquired_timestamp": float(rec["acquired_timestamp"]),
                       "acquired_elapsed_seconds": pts, "regions": converted}
                out.write(json.dumps(row, separators=(",", ":")) + "\n")
                timings["data_conversion_ms"].append((time.perf_counter() - tconv) * 1000)
                compact_obs = tuple(compact_candidate(c) for c in found.candidates)
                frame_records.append(TimedFrame(decoded, pts,
                    type(found)(found.width, found.height, compact_obs, np.empty((0, 0), dtype=np.uint8), found.stage_ms)))
                decoded += 1
    finally:
        cap.release()
    if decoded != len(source_index):
        raise ValueError(f"decoded/index mismatch {decoded}/{len(source_index)} for {run_id}")
    ta = time.perf_counter()
    tracks = associate_frames(frame_records, AssociationConfig(max_gap_ms=120))
    association_ms = (time.perf_counter() - ta) * 1000
    scene_notes = []
    track_rows = []
    for track in tracks:
        kind, kind_status, confidence, reason = classify_track(track)
        obs = track.observations
        if not obs:
            continue
        keyframes = []
        for o in obs:
            c = o.candidate
            points = c.panel_outline if kind == "TAP" and len(c.panel_outline) >= 3 else c.outline
            outline = tuple(Point(float(x), float(y)) for x, y in points)
            bx, by, bw, bh = o.bbox
            if kind == "TAP" and points:
                bx, by = min(x for x, _ in points), min(y for _, y in points)
                bw, bh = max(x for x, _ in points) - bx + 1, max(y for _, y in points) - by + 1
            keyframe_status = "UNKNOWN" if o.status == "UNKNOWN" else "OBSERVED"
            keyframes.append(Keyframe(o.pts, float(bx), float(by),
                                      float(bw), float(bh), keyframe_status,
                                      (o.candidate_ref, *c.provenance), outline))
        colors = sorted({color for o in obs for color in o.candidate.colors})
        lane_spans = {lane_span_for_bbox(o.bbox) for o in obs}
        lane = next(iter(lane_spans)) if len(lane_spans) == 1 else None
        interval = (obs[0].pts, obs[-1].pts)
        color = (255, 190, 60) if kind == "TAP" else (45, 220, 80) if kind == "HOLD" else (100, 120, 150)
        scene_notes.append(SceneNote(
            track.track_id, kind, tuple(keyframes), interval, color, lane_span=lane,
            source_color="+".join(colors) if colors else "UNKNOWN",
            track_status="AUTO_VISUAL_REVIEWED_PROVISIONAL" if len(obs) >= 3 else "SINGLE_FRAME_OR_SHORT_TRACK",
            kind_status=kind_status, confidence=confidence,
            head_status="OBSERVED" if kind == "TAP" else "UNKNOWN",
            body_status="OBSERVED" if kind == "HOLD" else "UNKNOWN",
            tail_status="UNKNOWN", evidence_refs=tuple(o.candidate_ref for o in obs),
            inference_source=reason))
        track_rows.append({"scene_note_id": track.track_id, "kind": kind,
                           "kind_status": kind_status, "reason": reason, "confidence": confidence,
                           "track_status": scene_notes[-1].track_status, "source_color": "+".join(colors),
                           "observations": len(obs), "first_frame": obs[0].frame, "last_frame": obs[-1].frame,
                           "first_acquired_elapsed": obs[0].pts, "last_acquired_elapsed": obs[-1].pts,
                           "first_bbox": obs[0].bbox, "last_bbox": obs[-1].bbox,
                           "head_status": scene_notes[-1].head_status, "body_status": scene_notes[-1].body_status,
                           "tail_status": scene_notes[-1].tail_status})
    timings["temporal_association_ms"] = [association_ms]
    profile = stage_summary(timings)
    with (run_out / "profile_stages.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(profile[0])); writer.writeheader(); writer.writerows(profile)
    with (run_out / "track_audit.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fields = list(track_rows[0]) if track_rows else ["scene_note_id", "kind", "kind_status", "reason", "confidence", "track_status", "source_color", "observations", "first_frame", "last_frame", "first_acquired_elapsed", "last_acquired_elapsed", "first_bbox", "last_bbox", "head_status", "body_status", "tail_status"]
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(track_rows)
    rails = tuple(Segment(Point(x0, 20), Point(x1, 560)) for x0, x1 in zip(RAILS_TOP, RAILS_BOTTOM))
    scene = Scene(1280, 720, rails, Segment(Point(60, 560), Point(1220, 560)),
                  tuple(scene_notes), "2.0", run_id)
    save_scene(scene, run_out / "scene.json")
    source_digest = file_sha256(video)
    summary = {"run_id": run_id, "source_video_sha256": source_digest,
               "source_index_sha256": file_sha256(index_path),
               "source_frame_count": decoded, "scene_track_count": len(scene_notes),
               "typed_tap_tracks": sum(n.kind == "TAP" for n in scene_notes),
               "typed_hold_tracks": sum(n.kind == "HOLD" for n in scene_notes),
               "unknown_tracks": sum(n.kind == "UNKNOWN" for n in scene_notes),
               "scene_timebase": "acquired_timestamp_relative_to_first_index_row",
               "calibration_status": "AUTO_VISUAL_ESTIMATE_REVIEW_REQUIRED",
               "track_identity_status": "OFFLINE_VISUAL_PROVISIONAL_NOT_GROUND_TRUTH",
               "processing_profile": profile}
    (run_out / "reconstruction_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recording-root", type=Path, default=Path("output/recording"))
    parser.add_argument("--frame-index", type=Path, default=Path("output/geometry_scene_v2/frame_index.csv"))
    parser.add_argument("--inventory", type=Path, default=Path("output/geometry_scene_v2/inventory.csv"))
    parser.add_argument("--out", type=Path, default=Path("output/geometry_scene_v2/runs"))
    parser.add_argument("--run-id", action="append")
    args = parser.parse_args()
    inv = list(csv.DictReader(args.inventory.open(encoding="utf-8-sig", newline="")))
    summaries = []
    for row in inv:
        run_id = row["run_id"]
        if args.run_id and run_id not in args.run_id:
            continue
        video = args.recording_root / run_id / row["video_name"]
        index = video.parent / "live_video_index.csv"
        print(f"Observing {run_id} ({row['decoded_frames']} frames)...", flush=True)
        summaries.append(process_run(video, index, args.frame_index, args.out / run_id, run_id))
        print(json.dumps(summaries[-1], ensure_ascii=False), flush=True)
    if not summaries:
        raise SystemExit("no matching run IDs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
