"""Render source-indexed provisional windows around replay attribution failures.

All cross-provider selections are anchored to source video_frame/index rows.
Provider-local track IDs are deliberately not used to pair physical notes.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import gzip
import hashlib
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ANNOTATION_STATUS = "PROVISIONAL_VISUAL_AUDIT"
PHYSICAL_STATUS = "UNKNOWN"
WINDOW_SECONDS = 0.5
ASSIST_PREVIEW_FRAMES = ((294, "assist_preview_4_9s_frame_294"),
                         (360, "assist_preview_6_0s_frame_360"),
                         (894, "assist_preview_14_9s_frame_894"))


def read_csv(path: Path) -> list[dict[str, str]]:
    if path.is_file():
        handle_context = path.open(encoding="utf-8-sig", newline="")
    else:
        compressed_path = path.with_name(path.name + ".gz")
        if not compressed_path.is_file():
            return []
        handle_context = gzip.open(compressed_path, "rt", encoding="utf-8-sig", newline="")
    with handle_context as handle:
        return list(csv.DictReader(handle))


def as_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def frame_index(index_rows: list[dict[str, str]]) -> dict[int, dict[str, str]]:
    return {int(row["video_frame"]): row for row in index_rows if as_int(row.get("video_frame")) is not None}


def stage_bucket(row: dict[str, str]) -> tuple[str, str]:
    stage = row.get("root_cause_stage", "UNKNOWN") or "UNKNOWN"
    reason = row.get("attribution_reason", "") or row.get("candidate_timing_reason", "")
    normalized = stage.upper()
    reason_lower = reason.lower()
    if "TAP_VISIBILITY" in normalized or reason_lower == "confirmed_tap_observation_lost":
        return "tap_visibility_gate", stage
    if "TYPE_PENDING" in normalized or reason_lower == "type_pending":
        return "type_pending", stage
    if "TIMING_INSUFFICIENT_OBSERVATIONS" in normalized or reason_lower == "insufficient_observations":
        return "timing_insufficient", stage
    if "WRONG_KEY" in normalized:
        return "wrong_key", stage
    if "UNKNOWN" in normalized or "UNRESOLVED" in normalized:
        return "unknown_unresolved", stage
    slug = re.sub(r"[^a-z0-9]+", "_", normalized.lower()).strip("_") or "unknown"
    return f"terminal_{slug}", stage


def select_review_targets(attribution_rows: list[dict[str, str]],
                          profile_rows: list[dict[str, str]],
                          admission_rows: list[dict[str, str]],
                          index_rows: list[dict[str, str]],
                          provider: str = "v85", samples_per_bucket: int = 1) -> list[dict[str, Any]]:
    """Choose one indexed representative per available terminal bucket plus performance cases."""
    indexed = frame_index(index_rows)
    targets: dict[str, dict[str, Any]] = {}

    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in attribution_rows:
        frame = as_int(row.get("video_frame"))
        if frame is None or frame not in indexed:
            continue
        bucket, terminal = stage_bucket(row)
        groups[bucket].append({**row, "_bucket": bucket, "_terminal": terminal})
    if samples_per_bucket < 1:
        raise ValueError("samples_per_bucket must be at least 1")
    for bucket, rows in groups.items():
        rows.sort(key=lambda r: (as_int(r.get("video_frame")) or 0, r.get("case_id", "")))
        # Keep the deterministic first attribution row for each source frame.
        rows = list({as_int(row.get("video_frame")): row for row in reversed(rows)}.values())
        rows.sort(key=lambda r: (as_int(r.get("video_frame")) or 0, r.get("case_id", "")))
        count = min(samples_per_bucket, len(rows))
        positions = [0] if count == 1 else [round(i * (len(rows) - 1) / (count - 1)) for i in range(count)]
        for ordinal, pos in enumerate(positions, 1):
            row = rows[pos]
            frame = int(row["video_frame"])
            window_id = bucket if count == 1 else f"{bucket}_{ordinal:02d}"
            targets[window_id] = {
                "window_id": window_id, "category": bucket, "terminal_stage": row["_terminal"],
                "video_frame": frame, "case_id": row.get("case_id", ""),
                "legacy_key_context": row.get("legacy_key", ""),
                "legacy_tracker_uid_provider_local": row.get("legacy_tracker_uid_provider_local", ""),
                "candidate_tracker_uid_provider_local": row.get("candidate_tracker_uid_provider_local", ""),
                "candidate_provider": row.get("candidate_provider", provider),
                "reason": row.get("attribution_reason", "") or row.get("candidate_timing_reason", ""),
                "selection_basis": "source-indexed attribution cases stratified across category frame range" if count > 1 else "first source-indexed attribution example in category",
            }

    provider_profiles = [r for r in profile_rows if r.get("provider") == provider]
    if not provider_profiles:
        provider_profiles = profile_rows
    measured = []
    for row in provider_profiles:
        frame = as_int(row.get("video_frame"))
        cost = as_float(row.get("processing_ms"))
        if cost is None:
            cost = sum(as_float(row.get(k)) or 0.0 for k in ("observe_wall_ms", "decision_wall_ms"))
        if frame is not None and frame in indexed:
            measured.append((cost, frame, row))
    if measured:
        cost, frame, _ = max(measured, key=lambda item: (item[0], -item[1]))
        targets["slowest_processing_frame"] = {
            "window_id": "slowest_processing_frame", "category": "slowest_processing_frame",
            "terminal_stage": "MEASURED_PROCESSING_COST", "video_frame": frame,
            "reason": f"processing_ms={cost:.6f}",
            "selection_basis": "maximum measured processing_ms for selected provider",
        }

    decoded = max((as_int(r.get("decoded_frames")) or 0 for r in admission_rows
                   if r.get("provider") == provider), default=0)
    if decoded == 0:
        decoded = max((as_int(r.get("video_frame")) or -1 for r in profile_rows), default=-1) + 1
    processed = {as_int(r.get("video_frame")) for r in provider_profiles}
    processed.discard(None)
    first_drop = next((n for n in range(decoded) if n not in processed), None)
    if first_drop is not None and first_drop in indexed:
        targets["first_latest_frame_drop"] = {
            "window_id": "first_latest_frame_drop", "category": "first_latest_frame_drop",
            "terminal_stage": "FRAME_NOT_ADMITTED", "video_frame": first_drop,
            "reason": "first source video_frame absent from measured processed-frame profile",
            "selection_basis": "first sequence gap against decoded indexed frames",
        }
    return sorted(targets.values(), key=lambda r: (r["video_frame"], r["window_id"]))


def quick_target(fixed_dir: Path, index_rows: list[dict[str, str]]) -> dict[str, Any] | None:
    rows = read_csv(fixed_dir / "frame_summary.csv")
    candidates = sorted({as_int(r.get("video_frame")) for r in rows
                         if r.get("provider") == "v85" and as_int(r.get("video_frame")) is not None})
    if not candidates:
        trace = read_csv(fixed_dir / "candidate_trace.csv")
        candidates = sorted({as_int(r.get("video_frame")) for r in trace
                             if r.get("provider") == "v85" and as_int(r.get("video_frame")) is not None})
    indexed = frame_index(index_rows)
    candidates = [n for n in candidates if n in indexed]
    if not candidates:
        return None
    frame = candidates[len(candidates) // 2]
    return {"window_id": "quick_source_mask_preview", "category": "quick_source_mask_preview",
            "terminal_stage": "PARTIAL_QUICK_REPLAY", "video_frame": frame,
            "selection_basis": "middle indexed V85 frame available in limited quick replay"}


def safe_slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "case"


def nearest_frame(timestamp: float, timestamps: list[float]) -> int:
    pos = bisect.bisect_left(timestamps, timestamp)
    if pos <= 0:
        return 0
    if pos >= len(timestamps):
        return len(timestamps) - 1
    return pos if timestamps[pos] - timestamp < timestamp - timestamps[pos-1] else pos-1


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for row in rows for k in row)) or ["status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def uid_frame_evidence(uid: str, trace_rows: list[dict[str, str]],
                       decision_rows: list[dict[str, str]],
                       action_rows: list[dict[str, str]]) -> dict[str, str]:
    """Join one provider-local UID within one frame; absent evidence stays blank."""
    trace = next((r for r in trace_rows if uid and r.get("tracker_uid") == uid), {})
    decision = next((r for r in decision_rows if uid and r.get("note_uid") == uid), {})
    actions = [r for r in action_rows if uid and r.get("uid") == uid]
    def first(*values: Any) -> str:
        return next((str(value) for value in values if value not in (None, "")), "")
    return {
        "detection_role": trace.get("role", ""), "detection_kind": trace.get("kind", ""),
        "detection_color": trace.get("color", ""), "detection_bbox": trace.get("bbox", ""),
        "candidate_component_id": trace.get("component_id", ""),
        "confirmation": first(decision.get("confirmed"), trace.get("tracker_confirmed")),
        "identity": first(decision.get("identity_state"), trace.get("tracker_state")),
        "visibility": first(decision.get("visibility_state"), trace.get("visibility")),
        "reason": first(decision.get("reason"), trace.get("tracker_reason")),
        "timing": first(decision.get("press_at"), trace.get("scheduled_press")),
        "timing_reason": first(decision.get("timing_reason"), trace.get("timing_reason")),
        "crossing_at": first(decision.get("crossing_at"), trace.get("crossing_at")),
        "uncertainty": first(decision.get("uncertainty"), trace.get("uncertainty")),
        "press_key": "|".join(f"{r.get('event','')}:{r.get('key','')}" for r in actions),
        "down_up_events": "|".join(r.get("event", "") for r in actions),
    }


def source_provenance(run_dir: Path) -> dict[str, Any]:
    """Describe the immutable source/index pair used for frame mapping."""
    result: dict[str, Any] = {"run_id": run_dir.name, "run_dir": str(run_dir.resolve())}
    for name in ("live_source.mp4", "live_video_index.csv"):
        path = run_dir / name
        row: dict[str, Any] = {"path": str(path.resolve()), "available": path.is_file()}
        if path.is_file():
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
            row.update(sha256=digest.hexdigest(), size_bytes=path.stat().st_size)
        result[name] = row
    index_rows = read_csv(run_dir / "live_video_index.csv")
    result["index_row_count"] = len(index_rows)
    result["index_frame_key"] = "video_frame aligned to sequential decoded frame number"
    return result


def sequential_indexed_frames(run_dir: Path, indexed: dict[int, dict[str, str]],
                              max_frame: int):
    """Yield decoded frames in order with the matching video_frame index row."""
    cap = cv2.VideoCapture(str(run_dir / "live_source.mp4"))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open indexed source: {run_dir / 'live_source.mp4'}")
    decoded = 0
    try:
        while decoded <= max_frame:
            ok, image = cap.read()
            if not ok:
                break
            yield decoded, image, indexed.get(decoded)
            decoded += 1
    finally:
        cap.release()


def write_manifest(out_dir: Path, mode: str, run_dirs: list[Path], queue: list[dict[str, Any]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": ANNOTATION_STATUS,
        "annotation_status": ANNOTATION_STATUS,
        "physical_note_status": PHYSICAL_STATUS,
        "review_status": "UNKNOWN_PROVISIONAL",
        "mode": mode,
        "source_index_provenance": [source_provenance(path) for path in run_dirs],
        "frame_alignment": "Sequential VideoCapture.read order is keyed by video_frame; source_frame and capture_timestamp come from that exact index row.",
        "random_seek_used": False,
        "fps_used_as_event_truth": False,
        "cases": queue,
    }
    (out_dir / "review_manifest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def compose_preview(source: np.ndarray, detections: list[Any], provider: Any,
                    label: str) -> np.ndarray:
    from src.lane_filter import PREVIEW_COLORS, ROLE_MASK

    rect = provider.last_rect
    masks = provider.last_result.masks
    mask = np.zeros_like(rect)
    for role, channel in ROLE_MASK.items():
        mask[masks[channel] > 0] = PREVIEW_COLORS[role]
    overlay = cv2.addWeighted(rect, .68, mask, .72, 0)
    for detection in detections:
        x, y, w, h = detection.bbox
        color = PREVIEW_COLORS["HOLD_HEAD"] if detection.kind == "hold_head" else (
            PREVIEW_COLORS["TAP_FACE"] if detection.kind == "tap" else PREVIEW_COLORS["UNKNOWN"])
        cv2.rectangle(overlay, (x, y), (x+w-1, y+h-1), color, 1)
    width, height = 640, 360
    panels = []
    for title, image in (("SOURCE", source), ("RECTIFIED", rect), ("MASK", mask), ("V85 OVERLAY", overlay)):
        panel = cv2.resize(image, (width, height))
        cv2.rectangle(panel, (0, 0), (width, 24), (0, 0, 0), -1)
        cv2.putText(panel, title, (8, 17), cv2.FONT_HERSHEY_SIMPLEX, .48, (255, 255, 255), 1, cv2.LINE_AA)
        panels.append(panel)
    canvas = np.concatenate(panels, axis=1)
    cv2.rectangle(canvas, (0, height-27), (canvas.shape[1], height), (0, 0, 0), -1)
    cv2.putText(canvas, label, (8, height-8), cv2.FONT_HERSHEY_SIMPLEX, .40,
                (255, 255, 255), 1, cv2.LINE_AA)
    return canvas


def render_run_windows(run_dir: Path, cases: list[dict[str, Any]], out_dir: Path,
                       fixed_dir: Path, measured_dir: Path, quick: bool = False) -> list[dict[str, Any]]:
    from src.early_perception import EarlyPixelProvider
    from src.model import Geometry

    index_rows = read_csv(run_dir / "live_video_index.csv")
    indexed = frame_index(index_rows)
    sorted_index = sorted(index_rows, key=lambda r: int(r["video_frame"]))
    timestamps = [float(row["capture_timestamp"]) for row in sorted_index]
    candidate_trace = read_csv(fixed_dir / "candidate_trace.csv")
    decisions = read_csv(fixed_dir / "physical_note_decisions.csv")
    actions = read_csv(fixed_dir / "mock_actions.csv")
    profiles = read_csv(measured_dir / "stage_profile_by_frame.csv")
    profile_by_frame = {as_int(r.get("video_frame")): r for r in profiles
                        if r.get("provider") == "v85" and as_int(r.get("video_frame")) is not None}
    trace_by_frame: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in candidate_trace:
        if as_int(row.get("video_frame")) is not None:
            trace_by_frame[int(row["video_frame"])].append(row)
    decisions_by_frame: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in decisions:
        if as_int(row.get("video_frame")) is not None:
            decisions_by_frame[int(row["video_frame"])].append(row)
    action_by_frame: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in actions:
        timestamp = as_float(row.get("decision_capture_timestamp")) or as_float(row.get("at"))
        if timestamp is not None and timestamps:
            action_by_frame[int(sorted_index[nearest_frame(timestamp, timestamps)]["video_frame"])].append(row)

    case_states = {}
    frame_to_cases: dict[int, list[str]] = defaultdict(list)
    for case in cases:
        target = as_int(case.get("video_frame"))
        if target is None or target not in indexed:
            continue
        capture = float(indexed[target]["capture_timestamp"])
        low = capture if quick else capture - WINDOW_SECONDS
        high = capture if quick else capture + WINDOW_SECONDS
        selected = [r for r in sorted_index if low <= float(r["capture_timestamp"]) <= high]
        if not selected:
            continue
        key = str(case["window_id"])
        case_dir = out_dir / safe_slug(key)
        case_dir.mkdir(parents=True, exist_ok=True)
        state = {"case": case, "case_dir": case_dir, "target": target,
                 "target_capture": capture, "selected": selected,
                 "start": int(selected[0]["video_frame"]), "end": int(selected[-1]["video_frame"]),
                 "timeline": [], "writer": None, "preview_written": False}
        case_states[key] = state
        for row in selected:
            frame_to_cases[int(row["video_frame"])].append(key)

    if not case_states:
        return []
    max_frame = max(state["end"] for state in case_states.values())
    geometry = Geometry(ROOT / "config" / "geometry_live_assist.json")
    provider = EarlyPixelProvider(geometry)
    fps = 60.0
    queue: dict[str, dict[str, Any]] = {}
    try:
        for decoded, source, index_row in sequential_indexed_frames(run_dir, indexed, max_frame):
            selected_cases = frame_to_cases.get(decoded, [])
            if index_row and selected_cases:
                detections = provider.detect(geometry.normalize(source))
                timestamp = float(index_row["capture_timestamp"])
                for case_key in selected_cases:
                    state = case_states[case_key]
                    case = state["case"]
                    label = (f"{case_key} | frame={decoded} source={index_row.get('source_frame')} "
                             f"capture={timestamp:.6f} | {ANNOTATION_STATUS} | {PHYSICAL_STATUS}")
                    canvas = compose_preview(source, detections, provider, label)
                    frame_trace = trace_by_frame.get(decoded, [])
                    frame_actions = action_by_frame.get(decoded, [])
                    profile = profile_by_frame.get(decoded, {})
                    legacy_uid = case.get("legacy_tracker_uid_provider_local", "")
                    candidate_uid = case.get("candidate_tracker_uid_provider_local", "")
                    evidence = uid_frame_evidence(candidate_uid,
                                                  [r for r in frame_trace if r.get("provider") == case.get("candidate_provider", "v85")],
                                                  [r for r in decisions_by_frame.get(decoded, []) if r.get("provider") == case.get("candidate_provider", "v85")],
                                                  [r for r in frame_actions if r.get("provider") == case.get("candidate_provider", "v85")])
                    legacy_evidence = uid_frame_evidence(
                        legacy_uid,
                        [r for r in frame_trace if r.get("provider") == "legacy"],
                        [r for r in decisions_by_frame.get(decoded, []) if r.get("provider") == "legacy"],
                        [r for r in frame_actions if r.get("provider") == "legacy"])
                    state["timeline"].append({
                        "video_frame": decoded, "source_frame": index_row.get("source_frame", ""),
                        "capture_timestamp": timestamp,
                        "indexed_frame_decoded_sequentially": True,
                        "v85_trace_rows": len(frame_trace),
                        "v85_mock_events": "|".join(f"{r.get('event')}:{r.get('key','')}" for r in frame_actions),
                        "processing_ms": profile.get("processing_ms", ""),
                        "decision_wall_ms": profile.get("decision_wall_ms", ""),
                        "candidate_roles": "|".join(sorted({r.get("role", "") for r in frame_trace})),
                        "legacy_tracker_uid_provider_local": legacy_uid,
                        "candidate_tracker_uid_provider_local": candidate_uid,
                        **evidence,
                        **{f"legacy_{key}": value for key, value in legacy_evidence.items()},
                        "annotation_status": ANNOTATION_STATUS, "physical_note_status": PHYSICAL_STATUS,
                    })
                    if not quick:
                        if state["writer"] is None:
                            path = state["case_dir"] / "source_rectified_mask_overlay.mp4"
                            state["writer"] = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"),
                                                               fps, (canvas.shape[1], canvas.shape[0]))
                        state["writer"].write(canvas)
                    if decoded == state["target"] and not state["preview_written"]:
                        image_name = "quick_preview.png" if quick else "preview.png"
                        cv2.imwrite(str(state["case_dir"] / image_name), canvas)
                        state["preview_written"] = True
    finally:
        for state in case_states.values():
            if state["writer"] is not None:
                state["writer"].release()

    queue = []
    for case_key, state in case_states.items():
        case_dir: Path = state["case_dir"]
        timeline_path = case_dir / "timeline.csv"
        write_csv(timeline_path, state["timeline"])
        case = state["case"]
        target_row = indexed[state["target"]]
        video = case_dir / "source_rectified_mask_overlay.mp4"
        queue.append({
            "window_id": case_key, "run_id": run_dir.name,
            "category": case.get("category", "quick_source_mask_preview"),
            "terminal_stage": case.get("terminal_stage", ""),
            "case_id": case.get("case_id", ""), "reason": case.get("reason", ""),
            "legacy_tracker_uid_provider_local": case.get("legacy_tracker_uid_provider_local", ""),
            "candidate_tracker_uid_provider_local": case.get("candidate_tracker_uid_provider_local", ""),
            "candidate_provider": case.get("candidate_provider", "v85"),
            "target_video_frame": state["target"], "target_source_frame": target_row.get("source_frame", ""),
            "target_capture_timestamp": state["target_capture"],
            "window_start_video_frame": state["start"], "window_end_video_frame": state["end"],
            "render_status": "RENDERED" if state["preview_written"] else "SOURCE_FRAME_UNAVAILABLE",
            "annotation_status": ANNOTATION_STATUS, "physical_note_status": PHYSICAL_STATUS,
            "preview_image": str((case_dir / ("quick_preview.png" if quick else "preview.png")).relative_to(out_dir)) if state["preview_written"] else "",
            "review_video": str(video.relative_to(out_dir)) if video.is_file() else "",
            "timeline_csv": str(timeline_path.relative_to(out_dir)),
            "selection_basis": case.get("selection_basis", ""),
        })
    return queue


def write_event_summary(fixed_dir: Path, measured_dir: Path, run_dir: Path,
                        preview_row: dict[str, Any], out_dir: Path) -> None:
    events = read_csv(fixed_dir / "mock_actions.csv")
    counts = Counter((row.get("provider", ""), row.get("event", "")) for row in events)
    admission = read_csv(measured_dir / "frame_admission.csv")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "quick_event_summary.json").write_text(json.dumps({
        "status": "PARTIAL_QUICK_REPLAY_WITH_SOURCE_PREVIEW",
        "annotation_status": ANNOTATION_STATUS, "physical_note_status": PHYSICAL_STATUS,
        "run_id": run_dir.name,
        "preview_video_frame": preview_row.get("target_video_frame"),
        "preview_source_frame": preview_row.get("target_source_frame"),
        "preview_capture_timestamp": preview_row.get("target_capture_timestamp"),
        "event_counts_by_provider_and_type": {f"{provider}:{event}": count
                                                for (provider, event), count in sorted(counts.items())},
        "measured_frame_admission": admission,
        "mock_action_events_are_not_physical_note_ground_truth": True,
    }, indent=2), encoding="utf-8")


def run_quick(run_dir: Path, fixed_dir: Path, measured_dir: Path, out_dir: Path) -> None:
    index_rows = read_csv(run_dir / "live_video_index.csv")
    target = quick_target(fixed_dir, index_rows)
    if target is None:
        raise RuntimeError("quick replay contains no V85 source-indexed frame for preview")
    queue = render_run_windows(run_dir, [target], out_dir, fixed_dir, measured_dir, quick=True)
    if not queue:
        raise RuntimeError("quick source/mask preview could not be rendered")
    preview_path = out_dir / queue[0]["preview_image"]
    shutil.copyfile(preview_path, out_dir / "quick_preview.png")
    write_csv(out_dir / "review_queue.csv", queue)
    write_event_summary(fixed_dir, measured_dir, run_dir, queue[0], out_dir)
    write_manifest(out_dir, "quick_preview", [run_dir], queue)


def run_full(run_dir: Path, fixed_dir: Path, measured_dir: Path, attribution_csv: Path,
             out_dir: Path, assist_run_dir: Path | None = None, samples_per_bucket: int = 1) -> None:
    index_rows = read_csv(run_dir / "live_video_index.csv")
    attribution = read_csv(attribution_csv)
    profile = read_csv(measured_dir / "stage_profile_by_frame.csv")
    admission = read_csv(measured_dir / "frame_admission.csv")
    cases = select_review_targets(attribution, profile, admission, index_rows,
                                  samples_per_bucket=samples_per_bucket)
    assist_run = assist_run_dir if assist_run_dir and assist_run_dir.is_dir() else None
    assist_cases = []
    if assist_run is not None:
        assist_index = frame_index(read_csv(assist_run / "live_video_index.csv"))
        for frame, name in ASSIST_PREVIEW_FRAMES:
            if frame in assist_index:
                assist_cases.append({"window_id": name, "category": "required_assist_preview",
                                     "terminal_stage": "SOURCE_INDEXED_PREVIEW", "video_frame": frame,
                                     "selection_basis": "authoritative plan preview frame"})
    if assist_run is not None and assist_run.resolve() == run_dir.resolve():
        queue = render_run_windows(run_dir, cases + assist_cases, out_dir, fixed_dir, measured_dir)
    else:
        queue = render_run_windows(run_dir, cases, out_dir, fixed_dir, measured_dir)

    if assist_cases and assist_run is not None and assist_run.resolve() != run_dir.resolve():
        queue.extend(render_run_windows(assist_run, assist_cases, out_dir,
                                        Path("__no_primary_fixed_evidence__"),
                                        Path("__no_primary_measured_evidence__")))
    write_csv(out_dir / "review_queue.csv", queue)
    provenance_runs = [run_dir]
    if assist_run_dir is not None and assist_run_dir.is_dir() and assist_run_dir.resolve() != run_dir.resolve():
        provenance_runs.append(assist_run_dir)
    write_manifest(out_dir, "source_aligned_case_windows", provenance_runs, queue)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True, help="primary source/index run")
    parser.add_argument("--fixed-dir", type=Path, required=True, help="fixed replay directory for this run")
    parser.add_argument("--measured-dir", type=Path, required=True, help="measured replay directory for this run")
    parser.add_argument("--attribution-csv", type=Path, help="action attribution CSV (required for full mode)")
    parser.add_argument("--assist-run-dir", type=Path, help="optional Assist run for frames 294, 360, and 894")
    parser.add_argument("--samples-per-bucket", type=int, default=1,
                        help="distinct source-indexed attribution cases per category (default: 1)")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--quick-preview", action="store_true", help="one source/mask image plus event summary")
    args = parser.parse_args(argv)
    try:
        if args.quick_preview:
            run_quick(args.run_dir.resolve(), args.fixed_dir.resolve(), args.measured_dir.resolve(), args.out.resolve())
        else:
            if args.attribution_csv is None:
                parser.error("--attribution-csv is required outside --quick-preview")
            run_full(args.run_dir.resolve(), args.fixed_dir.resolve(), args.measured_dir.resolve(),
                     args.attribution_csv.resolve(), args.out.resolve(),
                     args.assist_run_dir.resolve() if args.assist_run_dir else None,
                     args.samples_per_bucket)
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
