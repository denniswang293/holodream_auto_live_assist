import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def int_value(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def float_value(value):
    try:
        result = float(value)
        return result if result == result and abs(result) != float("inf") else None
    except (TypeError, ValueError):
        return None


def csv_stats(path, frame_col, source_col, timestamp_cols):
    csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
    result = {"rows": 0, "missing_video_frame_rows": 0, "video_frame_gaps": 0,
              "source_frame_gaps": 0, "timestamp_reversals": 0,
              "acquired_before_capture_rows": 0, "capture_to_acquired_ms": [],
              "missing_timestamp_rows": {},
              "timestamp_columns": {}, "focused_true_rows": 0, "focused_false_rows": 0,
              "armed_true_rows": 0, "armed_false_rows": 0}
    prev_video, prev_source = {}, {}
    previous_times = {}
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        result["columns"] = reader.fieldnames or []
        available = [name for name in timestamp_cols if name in (reader.fieldnames or [])]
        result["timestamp_columns"] = {name: {"first": None, "last": None, "reversals": 0}
                                       for name in available}
        result["missing_timestamp_rows"] = {name: 0 for name in available}
        for row in reader:
            result["rows"] += 1
            video = int_value(row.get(frame_col))
            source = int_value(row.get(source_col)) if source_col else None
            if video is None:
                result["missing_video_frame_rows"] += 1
            elif prev_video.get("value") is not None and video > prev_video["value"] + 1:
                result["video_frame_gaps"] += video - prev_video["value"] - 1
            if video is not None:
                prev_video["value"] = video
            if source is not None:
                if prev_source.get("value") is not None and source > prev_source["value"] + 1:
                    result["source_frame_gaps"] += source - prev_source["value"] - 1
                prev_source["value"] = source
            for name in available:
                val = float_value(row.get(name))
                if val is None:
                    result["missing_timestamp_rows"][name] += 1
                    continue
                item = result["timestamp_columns"][name]
                if item["first"] is None:
                    item["first"] = val
                item["last"] = val
                if name in previous_times and val < previous_times[name]:
                    item["reversals"] += 1
                    result["timestamp_reversals"] += 1
                previous_times[name] = val
            captured = float_value(row.get("capture_timestamp", row.get("captured_at")))
            acquired = float_value(row.get("acquired_timestamp", row.get("acquired_at")))
            if captured is not None and acquired is not None:
                delta = (acquired - captured) * 1000
                result["capture_to_acquired_ms"].append(delta)
                if delta < 0:
                    result["acquired_before_capture_rows"] += 1
            focused = str(row.get("focused", "")).strip().lower()
            result["focused_true_rows"] += focused in ("true", "1", "yes")
            result["focused_false_rows"] += focused in ("false", "0", "no")
            info = row.get("info_json")
            if info:
                try:
                    state = json.loads(info)
                    armed = state.get("armed")
                    if armed is True:
                        result["armed_true_rows"] += 1
                    elif armed is False:
                        result["armed_false_rows"] += 1
                    if not focused and state.get("focused") is True:
                        result["focused_true_rows"] += 1
                    elif not focused and state.get("focused") is False:
                        result["focused_false_rows"] += 1
                except (json.JSONDecodeError, TypeError):
                    pass
    return result


def event_stats(path, event_column):
    if not path.exists():
        return {"present": False, "rows": 0, "event_counts": {}}
    counts = {}
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            event = row.get(event_column, "")
            counts[event] = counts.get(event, 0) + 1
    return {"present": True, "rows": sum(counts.values()), "event_counts": counts}


def video_stats(path):
    if not path.exists():
        return {"present": False}
    try:
        import cv2
        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            capture.release()
            return {"present": True, "opened": False}
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        declared = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        decoded = 0
        while True:
            ok, _ = capture.read()
            if not ok:
                break
            decoded += 1
        capture.release()
        return {"present": True, "opened": True, "width": width, "height": height,
                "declared_frames": declared, "decoded_frames": decoded}
    except Exception as exc:
        return {"present": True, "opened": False, "error": type(exc).__name__}


def audit_run(run_dir, kind, cached_video=None):
    is_assist = kind == "assist"
    index_path = run_dir / "live_video_index.csv"
    video_path = run_dir / "live_source.mp4"
    idx = csv_stats(index_path, "video_frame", "source_frame",
                    ["capture_timestamp", "acquired_timestamp"])
    player_events = event_stats(run_dir / "player_key_events.csv", "action") if not is_assist else None
    markers = event_stats(run_dir / "markers.csv", "kind")
    video = cached_video if cached_video is not None else video_stats(video_path)
    session_path = run_dir / "session.json"
    try:
        session = json.loads(session_path.read_text(encoding="utf-8-sig")) if session_path.exists() else {}
    except (OSError, json.JSONDecodeError):
        session = {}
    frames = csv_stats(run_dir / "frames.csv", "encoded_frame", "source_frame",
                       ["captured_at", "acquired_at"]) if is_assist else None
    actions = csv_stats(run_dir / "actions.csv", "", "", []) if is_assist else None
    notes = csv_stats(run_dir / "note_decisions.csv", "", "", []) if is_assist else None
    reasons = []
    if not video.get("present"):
        status = "UNUSABLE"
        reasons.append("missing live_source.mp4")
    elif not video.get("opened") or video.get("decoded_frames", 0) == 0:
        status = "UNUSABLE"
        reasons.append("video could not be decoded")
    elif not idx:
        status = "UNUSABLE"
        reasons.append("missing live_video_index.csv")
    elif idx["rows"] == 0:
        status = "UNUSABLE"
        reasons.append("index has no data rows")
    else:
        status = "USABLE"
        if idx["missing_video_frame_rows"]:
            reasons.append(f"{idx['missing_video_frame_rows']} index rows lack video_frame")
        if idx["video_frame_gaps"]:
            reasons.append(f"{idx['video_frame_gaps']} encoded-frame gaps")
        if idx["source_frame_gaps"]:
            reasons.append(f"{idx['source_frame_gaps']} source-frame gaps")
        if idx["timestamp_reversals"]:
            reasons.append(f"{idx['timestamp_reversals']} timestamp reversals")
        if idx["acquired_before_capture_rows"]:
            reasons.append(f"{idx['acquired_before_capture_rows']} rows acquired before capture")
        missing_times = sum(idx["missing_timestamp_rows"].values())
        if missing_times:
            reasons.append(f"{missing_times} missing capture/acquired timestamps")
        if video.get("decoded_frames") != idx["rows"]:
            reasons.append(f"decoded video/index row mismatch ({video.get('decoded_frames')}/{idx['rows']})")
        if reasons:
            status = "PARTIAL"
    return {
        "run": run_dir.name, "kind": kind, "status": status,
        "reasons": "; ".join(reasons) if reasons else "none",
        "video": video, "index": idx, "timestamp_source": session.get("timestamp_source", "not recorded"),
        "nominal_fps_is_playback_only": bool(session.get("nominal_video_fps")),
        "session_complete": session.get("complete"),
        "session_capture_dropped_frames": session.get("capture_dropped_frames"),
        "session_captured_frames": session.get("captured_frames"),
        "session_processed_frames": session.get("processed_frames"),
        "video_integrity_verified": session.get("video_integrity_verified"),
        "session_automatic_input": session.get("automatic_input"),
        "session_judgment_accuracy": session.get("game_judgment_accuracy"),
        "index_capture_to_acquired_ms_p50": __import__("statistics").median(idx["capture_to_acquired_ms"]) if idx and idx["capture_to_acquired_ms"] else None,
        "index_capture_to_acquired_ms_p90": __import__("numpy").percentile(idx["capture_to_acquired_ms"], 90).item() if idx and idx["capture_to_acquired_ms"] else None,
        "player_key_event_rows": player_events["rows"] if player_events else None,
        "player_key_event_counts": player_events["event_counts"] if player_events else None,
        "marker_file_present": markers["present"], "marker_rows": markers["rows"], "marker_counts": markers["event_counts"],
        # Prefer the indexed frame stream. frames.csv repeats the same focus
        # state for Assist runs and must not double-count it.
        "focused_true_rows": ((idx or {}).get("focused_true_rows", 0) or (frames or {}).get("focused_true_rows", 0)),
        "focused_false_rows": ((idx or {}).get("focused_false_rows", 0) or (frames or {}).get("focused_false_rows", 0)),
        "armed_true_rows": (frames or {}).get("armed_true_rows", 0),
        "armed_false_rows": (frames or {}).get("armed_false_rows", 0),
        "frames_csv": frames, "actions_csv": actions, "note_decisions_csv": notes,
    }


def main():
    parser = argparse.ArgumentParser(description="Read-only audit of recording and Assist datasets")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--reuse-video-inventory", action="store_true",
                         help="reuse decoded width/height/frame counts in an existing dataset_audit.csv")
    args = parser.parse_args()
    root = args.root.resolve()
    out = (args.out or root / "output/analysis_lane_filter_v84").resolve()
    out.mkdir(parents=True, exist_ok=True)
    cached = {}
    if args.reuse_video_inventory:
        cache_path = out / "dataset_audit.csv"
        if not cache_path.is_file():
            parser.error("--reuse-video-inventory requires an existing dataset_audit.csv")
        with cache_path.open("r", encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                cached[row["run"]] = {"present": True, "opened": True,
                    "width": int_value(row.get("video_width")), "height": int_value(row.get("video_height")),
                    "decoded_frames": int_value(row.get("decoded_video_frames")),
                    "declared_frames": int_value(row.get("decoded_video_frames"))}
    runs = []
    for kind in ("recording", "assist"):
        parent = root / "output" / kind
        if parent.exists():
            for run_dir in sorted(parent.glob("run_*")):
                if run_dir.is_dir():
                    runs.append(audit_run(run_dir, kind, cached.get(run_dir.name)))
    fields = ["run", "kind", "status", "reasons", "video_width", "video_height",
              "decoded_video_frames", "indexed_rows", "missing_video_frame_rows", "encoded_frame_gaps",
              "source_frame_gaps", "timestamp_reversals", "missing_capture_timestamps", "missing_acquired_timestamps",
              "timestamp_source", "nominal_fps_is_playback_only",
              "focused_true_rows", "focused_false_rows", "armed_true_rows", "armed_false_rows",
              "index_capture_to_acquired_ms_p50", "index_capture_to_acquired_ms_p90",
              "session_capture_dropped_frames", "session_captured_frames", "session_processed_frames",
              "player_key_event_rows", "marker_file_present", "marker_rows", "session_automatic_input", "session_judgment_accuracy",
              "session_complete", "video_integrity_verified"]
    with (out / "dataset_audit.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for r in runs:
            v, i = r["video"], r["index"] or {}
            writer.writerow({"run": r["run"], "kind": r["kind"], "status": r["status"], "reasons": r["reasons"],
                "video_width": v.get("width", ""), "video_height": v.get("height", ""),
                "decoded_video_frames": v.get("decoded_frames", ""), "indexed_rows": i.get("rows", ""),
                "missing_video_frame_rows": i.get("missing_video_frame_rows", ""),
                "encoded_frame_gaps": i.get("video_frame_gaps", ""), "source_frame_gaps": i.get("source_frame_gaps", ""),
                "timestamp_reversals": i.get("timestamp_reversals", ""), "timestamp_source": r["timestamp_source"],
                "missing_capture_timestamps": (i.get("missing_timestamp_rows") or {}).get("capture_timestamp", ""),
                "missing_acquired_timestamps": (i.get("missing_timestamp_rows") or {}).get("acquired_timestamp", ""),
                "nominal_fps_is_playback_only": r["nominal_fps_is_playback_only"],
                "focused_true_rows": r["focused_true_rows"], "focused_false_rows": r["focused_false_rows"],
                "armed_true_rows": r["armed_true_rows"], "armed_false_rows": r["armed_false_rows"],
                "index_capture_to_acquired_ms_p50": r["index_capture_to_acquired_ms_p50"],
                "index_capture_to_acquired_ms_p90": r["index_capture_to_acquired_ms_p90"],
                "session_capture_dropped_frames": r["session_capture_dropped_frames"],
                "session_captured_frames": r["session_captured_frames"],
                "session_processed_frames": r["session_processed_frames"],
                "player_key_event_rows": r["player_key_event_rows"], "marker_rows": r["marker_rows"],
                "marker_file_present": r["marker_file_present"],
                "session_automatic_input": r["session_automatic_input"],
                "session_judgment_accuracy": r["session_judgment_accuracy"],
                "session_complete": r["session_complete"], "video_integrity_verified": r["video_integrity_verified"]})
    # lane_filter.py is introduced by this experiment, so it is not part of
    # the V8.3 baseline code hash set.
    code_hashes = {str(p.relative_to(root)): sha256(p) for p in sorted((root / "src").glob("*.py"))
                   if p.name != "lane_filter.py"}
    configs = {str(p.relative_to(root)): sha256(p) for p in sorted((root / "config").glob("*.json"))}
    try:
        import cv2
        cv2_version = cv2.__version__
    except Exception as exc:
        cv2_version = f"unavailable ({type(exc).__name__})"
    try:
        pytest_version = importlib.metadata.version("pytest")
    except importlib.metadata.PackageNotFoundError:
        pytest_version = "not installed"
    baseline = {
        "python_version": sys.version,
        "platform": platform.platform(),
        "opencv_version": cv2_version,
        "pytest_version": pytest_version,
        "baseline_pytest": {"command": "python -m pytest -q", "result": "no tests collected", "exit_code": 5,
                            "source": "provided pre-audit baseline"},
        "code_sha256": code_hashes,
        "excluded_experiment_files": ["src/lane_filter.py", "tools/render_lane_filter.py"],
        "config_sha256": configs,
        "audit_script_sha256": sha256(Path(__file__).resolve()),
        "decoded_video_inventory_reused": args.reuse_video_inventory,
        "run_counts": {s: sum(r["status"] == s for r in runs) for s in ("USABLE", "PARTIAL", "UNUSABLE")},
        "run_timing_audit": {r["run"]: {"capture_to_acquired_ms_p50": r["index_capture_to_acquired_ms_p50"],
            "capture_to_acquired_ms_p90": r["index_capture_to_acquired_ms_p90"],
            "capture_source_frame_gaps": (r["index"] or {}).get("source_frame_gaps"),
            "missing_timestamps": (r["index"] or {}).get("missing_timestamp_rows"),
            "acquired_before_capture_rows": (r["index"] or {}).get("acquired_before_capture_rows"),
            "player_key_event_rows": r["player_key_event_rows"], "player_key_event_counts": r["player_key_event_counts"],
            "markers": r["marker_counts"], "session_capture_dropped_frames": r["session_capture_dropped_frames"]} for r in runs},
        "total_runs": len(runs),
    }
    (out / "baseline_environment.json").write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"runs": len(runs), "counts": baseline["run_counts"], "out": str(out)}, indent=2))


if __name__ == "__main__":
    main()


