"""V7.5.5 offline detector/tracker association instrumentation.

The tool is read-only with respect to live input.  It replays a clean source
video using capture timestamps from live_video_index.csv and writes bounded
detector/tracker traces for diagnosis.  It never changes planner gates or
sends keyboard input.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import platform
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import cv2

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.detector import detect
from src.geometry import CalibratedGeometry
from src.simple_tracker import SimpleTracker, is_simple_tap


def load_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    if not fields:
        fields = ["status"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def json_cell(value):
    if isinstance(value, (tuple, list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return value


def config_particle_seed(config: dict) -> int:
    return int(config.get("predictor", {}).get("particle", {}).get("deterministic_seed", 20261030))


def load_index(path: Path):
    rows = load_csv(path)
    by_video = {}
    alignment = []
    previous_ts = None
    for row in rows:
        video = int(row["source_video_frame"])
        source = int(row["source_frame"])
        timestamp = row.get("capture_timestamp", "")
        problems = []
        if not timestamp:
            problems.append("timestamp_missing")
        else:
            timestamp_value = float(timestamp)
            if previous_ts is not None and timestamp_value <= previous_ts:
                problems.append("timestamp_non_increasing")
            previous_ts = timestamp_value
        if video in by_video:
            problems.append("duplicate_source_video_frame")
        by_video[video] = row
        alignment.append({
            "video_frame": row.get("video_frame", ""),
            "source_frame": source,
            "source_video_frame": video,
            "capture_timestamp": timestamp,
            "processing_timestamp": row.get("processing_timestamp", ""),
            "gameplay_state": row.get("gameplay_state", ""),
            "timestamp_missing": "timestamp_missing" in problems,
            "timestamp_non_increasing": "timestamp_non_increasing" in problems,
            "mapping_status": "OK" if not problems else "|".join(problems),
        })
    return rows, by_video, alignment


def replay(source: Path, index_rows: list[dict], index_by_video: dict,
           config: dict, geometry: CalibratedGeometry, *, trace_enabled: bool):
    detector_cfg = {
        **config["detector"],
        "reference_resolution": config["reference_resolution"],
        "association_diagnostics": {
            **dict(config["detector"].get("association_diagnostics", {}) or {}),
            "enabled": trace_enabled,
        },
    }
    tracker_cfg = {
        **config.get("tracker", {}),
        "completion_y": geometry.hit_y,
        "max_eta_s": config.get("events", {}).get("max_eta_s", .45),
    }
    particle_cfg = dict(config.get("predictor", {}).get("particle", {}))
    input_advance = float(config.get("live", {}).get("input_advance_px", 30))
    tracker = SimpleTracker(tracker_cfg, particle_cfg, hit_y=geometry.hit_y - input_advance)
    cap = cv2.VideoCapture(str(source))
    candidate_rows, pair_rows, track_rows = [], [], []
    candidate_signatures, track_signatures = [], []
    frame_count = 0
    detector_trace_dropped = 0
    tracker_trace_dropped = 0
    previous_capture = None
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_count not in index_by_video:
            raise RuntimeError(f"missing timestamp mapping for source_video_frame={frame_count}")
        idx = index_by_video[frame_count]
        capture_ts = float(idx["capture_timestamp"])
        processing_ts = float(idx.get("processing_timestamp") or capture_ts)
        if previous_capture is not None and capture_ts <= previous_capture:
            raise RuntimeError(f"non-increasing capture timestamp at source_video_frame={frame_count}")
        capture_gap_ms = (capture_ts - previous_capture) * 1000 if previous_capture is not None else ""
        previous_capture = capture_ts
        diagnostics = {}
        candidates = detect(frame, geometry, config["key_map"], detector_cfg,
                            diagnostics, frame_index=frame_count)
        playing = idx.get("gameplay_state") == "PLAYING"
        trace = {"max_rows": int(detector_cfg["association_diagnostics"].get("max_pair_rows", 10000))} if trace_enabled else None
        tracks = tracker.update([c for c in candidates if is_simple_tap(c)], capture_ts,
                                playing=playing, trace=trace, frame_index=frame_count,
                                capture_gap_ms=capture_gap_ms)
        for row in diagnostics.get("candidate_trace", []):
            row = dict(row)
            row.update({"source_frame": idx["source_frame"], "source_video_frame": frame_count,
                        "capture_timestamp": capture_ts, "processing_timestamp": processing_ts,
                        "raw_bbox": json_cell(row.get("raw_bbox")),
                        "core_bbox": json_cell(row.get("core_bbox")),
                        "path_bbox": json_cell(row.get("path_bbox"))})
            candidate_rows.append(row)
        detector_trace_dropped += int(diagnostics.get("candidate_trace_dropped_rows", 0) or 0)
        if trace is not None:
            tracker_trace_dropped += int(trace.get("dropped_rows", 0) or 0)
            for bucket, target in (("pair_rows", pair_rows), ("track_rows", track_rows)):
                for row in trace.get(bucket, []):
                    row = {k: json_cell(v) for k, v in row.items()}
                    row.update({"source_frame": idx["source_frame"], "source_video_frame": frame_count,
                                "capture_timestamp": capture_ts, "processing_timestamp": processing_ts})
                    target.append(row)
        candidate_signatures.append([(c.bbox, c.appearance, c.note_type,
                                      tuple(c.candidate_keys)) for c in candidates])
        track_signatures.append([(t.track_id, t.status, t.candidate.bbox,
                                  tuple(t.stable_keys), t.observations, t.missed) for t in tracks])
        frame_count += 1
    cap.release()
    return {
        "candidate_rows": candidate_rows, "pair_rows": pair_rows, "track_rows": track_rows,
        "candidate_signatures": candidate_signatures, "track_signatures": track_signatures,
        "frames": frame_count, "detector_trace_dropped": detector_trace_dropped,
        "tracker_trace_dropped": tracker_trace_dropped,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config.json")
    parser.add_argument("--geometry", type=Path, default=REPO_ROOT / "config/geometry_live_assist.json")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "output/assist/v755_tracker_association")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    cfg = json.loads(args.config.read_text(encoding="utf-8-sig"))
    geometry = CalibratedGeometry(json.loads(args.geometry.read_text(encoding="utf-8-sig")))
    index_rows, index_by_video, alignment = load_index(args.run / "live_video_index.csv")
    if any(r["mapping_status"] != "OK" for r in alignment):
        raise RuntimeError("timestamp mapping has missing/duplicate/non-increasing rows; fail-fast")
    write_csv(args.out / "frame_alignment_audit.csv", alignment)
    traced = replay(args.source, index_rows, index_by_video, cfg, geometry, trace_enabled=True)
    off = replay(args.source, index_rows, index_by_video, cfg, geometry, trace_enabled=False)
    write_csv(args.out / "detector_candidate_audit.csv", traced["candidate_rows"])
    write_csv(args.out / "association_audit.csv", traced["pair_rows"])
    write_csv(args.out / "tracker_frame_state.csv", traced["track_rows"])

    # Existing lifecycle rows are retained only as a best-effort case index;
    # replay track IDs are not asserted to equal live UIDs.
    live_events = load_csv(args.run / "live_events.csv")
    live_intents = load_csv(args.run / "tap_intents.csv")
    live_decisions = load_csv(args.run / "tap_decisions.csv")
    live_shadow = load_csv(args.run / "tap_planner_shadow.csv")
    by_uid = defaultdict(list)
    by_intent = defaultdict(list)
    by_decision = defaultdict(list)
    by_shadow = defaultdict(list)
    for r in live_events: by_uid[r["note_uid"]].append(r)
    for r in live_intents: by_intent[r["note_uid"]].append(r)
    for r in live_decisions: by_decision[r["note_uid"]].append(r)
    for r in live_shadow: by_shadow[r["note_uid"]].append(r)
    rank = {"NOT_SCHEDULED": 0, "DETECTED": 1, "CONFIRMED": 2, "PENDING": 3,
            "SCHEDULED": 4, "FIRED": 5, "EXPIRED": 5}
    root_cases = []
    for uid, rows in by_uid.items():
        intents = by_intent[uid]
        if not intents:
            continue
        max_state = max(intents, key=lambda r: rank.get(r["state"], -1))["state"]
        fired = any(r["state"] == "FIRED" for r in intents)
        if fired:
            continue
        first, last = rows[0], rows[-1]
        if max_state == "DETECTED":
            classification = "UNKNOWN_confirmation_or_current_loss"
        elif max_state == "CONFIRMED":
            classification = "confirmed_but_not_current" if any(r["reason"] == "track_not_current_confirmed" for r in by_decision[uid]) else "planner_or_pf_gate"
        else:
            classification = "UNKNOWN"
        root_cases.append({"note_uid": uid, "live_track_id": first.get("track_id", ""),
            "evidence_frame_start": first.get("source_frame", ""), "evidence_frame_end": last.get("source_frame", ""),
            "capture_timestamp_start": first.get("capture_timestamp", ""), "capture_timestamp_end": last.get("capture_timestamp", ""),
            "appearance": first.get("appearance", ""), "candidate_keys": first.get("key_candidates", ""),
            "max_live_state": max_state, "classification": classification,
            "replay_track_id": "UNMATCHED", "candidate_id": "UNMATCHED",
            "matching_confidence": "UNKNOWN", "trace_reference": "no reliable UID mapping",
            "terminal_reason": last.get("simple_core_reason", "") or "UNKNOWN",
            "truth_status": "UNKNOWN"})
    write_csv(args.out / "tracker_root_cause_cases.csv", root_cases)

    shadow_cases = []
    for uid, rows in by_shadow.items():
        disagreement = next((r for r in rows if r["status"] == "schedule" and r["legacy_result"] == "rejected"), None)
        if disagreement is None: continue
        ev = by_uid[uid][0]
        states = {r["state"] for r in by_intent[uid]}
        shadow_cases.append({"note_uid": uid, "representative_frame": ev.get("source_frame", ""),
            "capture_timestamp": ev.get("capture_timestamp", ""), "appearance": ev.get("appearance", ""),
            "candidate_keys": ev.get("key_candidates", ""), "legacy_reason": disagreement.get("legacy_reason", ""),
            "shadow_reason": disagreement.get("reason", ""), "shadow_key": disagreement.get("key", ""),
            "shadow_hit_at": disagreement.get("hit_at", ""), "final_states": "|".join(sorted(states)),
            "final_fired": "FIRED" in states, "truth_status": "UNKNOWN", "review_status": "UNREVIEWED"})
    write_csv(args.out / "shadow_paired_review.csv", shadow_cases)

    # Deadline review keeps the expired case and high-amendment Tap UIDs.
    actions = load_csv(args.run / "live_key_actions.csv")
    grouped = defaultdict(list)
    for row in actions:
        if row.get("event_id") and row.get("note_type") == "tap" and row.get("action") in ("scheduled", "amended"):
            grouped[row["event_id"]].append(row)
    deadline_rows = []
    for uid, rows in grouped.items():
        rows = sorted(rows, key=lambda r: float(r["timestamp"]))
        if len(rows) <= 3 and uid != "cdaf4ddbea12:simple:1000129": continue
        vals = [float(r["scheduled_hit"]) for r in rows]
        deadline_rows.append({"note_uid": uid, "amendment_count": len(rows) - 1,
            "first_schedule_timestamp": rows[0]["timestamp"], "final_deadline": vals[-1],
            "signed_drift_ms": (vals[-1] - vals[0]) * 1000,
            "range_ms": (max(vals) - min(vals)) * 1000,
            "expired_case": uid == "cdaf4ddbea12:simple:1000129",
            "truth_status": "UNKNOWN"})
    write_csv(args.out / "deadline_case_review.csv", deadline_rows)

    crop_dir = args.out / "case_crops"
    crop_dir.mkdir(parents=True, exist_ok=True)
    crop_frames = {257: "shadow_1000004", 615: "shadow_1000059", 923: "shadow_1000139",
                   935: "shadow_1000140", 963: "shadow_1000143", 401: "pink_1000005", 957: "expired_1000129"}
    cap = cv2.VideoCapture(str(args.source)); frame_no = 0
    wanted = set(crop_frames)
    while wanted:
        ok, frame = cap.read()
        if not ok: break
        if frame_no in wanted:
            cv2.imwrite(str(crop_dir / f"{crop_frames[frame_no]}_frame_{frame_no}.jpg"), frame)
            wanted.remove(frame_no)
        frame_no += 1
    cap.release()

    detector_diff = sum(a != b for a, b in zip(traced["candidate_signatures"], off["candidate_signatures"]))
    tracker_diff = sum(a != b for a, b in zip(traced["track_signatures"], off["track_signatures"]))
    trace_quality = {
        "source_frames": traced["frames"], "index_rows": len(index_rows),
        "timestamp_coverage": len(index_by_video) / max(1, traced["frames"]),
        "timestamp_fallback_rows": 0, "detector_trace_rows": len(traced["candidate_rows"]),
        "association_pair_rows": len(traced["pair_rows"]), "tracker_state_rows": len(traced["track_rows"]),
        "diagnostic_dropped_rows": traced["detector_trace_dropped"] + traced["tracker_trace_dropped"],
        "uid_mapping_status": "UNMATCHED_without explicit cross-run identity",
        "limitations": ["candidate-level trace is replay evidence, not game truth", "live UID mapping is UNKNOWN"]}
    (args.out / "trace_quality_summary.json").write_text(json.dumps(trace_quality, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ab = {"trace_enabled_default": False, "detector_signature_diff_frames": detector_diff,
          "tracker_signature_diff_frames": tracker_diff, "decision_changes": "UNKNOWN (replay has no live scheduler)",
          "candidate_order_unchanged": detector_diff == 0, "tracker_state_unchanged": tracker_diff == 0,
          "legacy_input_path_changed": False, "shadow_active": False, "truth_status": "UNKNOWN"}
    (args.out / "diagnostic_off_on_ab.json").write_text(json.dumps(ab, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {"commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "source": str(args.source), "source_sha256": sha256(args.source),
        "index": str(args.run / "live_video_index.csv"), "index_sha256": sha256(args.run / "live_video_index.csv"),
        "config_sha256": sha256(args.config), "geometry_sha256": sha256(args.geometry),
        "python": sys.version, "platform": platform.platform(), "opencv": cv2.__version__,
        "random_seed": config_particle_seed(cfg),
        "timestamp_basis": "source_video_frame -> capture_timestamp; fail-fast on missing/non-increasing",
        "trace_enabled_default": False, "command": "py tools/replay_tracker_association_v755.py --run ... --source ..."}
    (args.out / "v755_replay_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"frames": traced["frames"], "candidate_trace_rows": len(traced["candidate_rows"]),
                      "pair_rows": len(traced["pair_rows"]), "track_rows": len(traced["track_rows"]),
                      "detector_diff_frames": detector_diff, "tracker_diff_frames": tracker_diff,
                      "out": str(args.out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
