"""Offline, shadow-only geometry/ETA audit for one Assist run.

This tool deliberately does not change the active planner or scheduler.  It
uses recorded bbox observations to compare top/center/bottom anchors and
nearby judgment-line hypotheses.  Game grades remain UNKNOWN unless a human
has supplied a one-to-one label in the existing review CSV.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
from pathlib import Path
from collections import defaultdict, Counter


ANCHORS = ("top", "center", "bottom")
Y_OFFSETS = (-20.0, -15.0, -10.0, -5.0, 0.0, 5.0, 10.0, 15.0, 20.0)
LEADS_MS = (0.0, 30.0, 50.0, 60.0, 70.0)
GRADE_FIELDS = [
    "video_time", "frame_index", "uid", "lane", "key", "note_type", "grade",
    "direction", "confidence", "association_reason", "visual_anchor", "source_frame",
    "source_video_frame",
]


def _f(value, default=None):
    try:
        value = float(value)
        return value if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def _i(value, default=None):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _bool(value):
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _read(path):
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        rd = csv.DictReader(fh)
        return list(rd), list(rd.fieldnames or [])


def _bbox(value):
    try:
        raw = json.loads(value) if isinstance(value, str) else value
        if len(raw) != 4:
            return None
        vals = tuple(float(v) for v in raw)
        if not all(math.isfinite(v) for v in vals) or vals[2] <= 0 or vals[3] <= 0:
            return None
        return vals
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _nearest(sorted_times, rows, timestamp):
    if not sorted_times or timestamp is None:
        return None
    pos = bisect.bisect_left(sorted_times, timestamp)
    choices = []
    if pos < len(rows):
        choices.append(rows[pos])
    if pos:
        choices.append(rows[pos - 1])
    return min(choices, key=lambda row: abs(_f(row.get("capture_timestamp"), 0.0) - timestamp))


def _crossing(observations, target):
    """Return first visual crossing using only observations up to that crossing."""
    if len(observations) < 2:
        return None, "INSUFFICIENT_OBSERVATIONS"
    for (t0, y0), (t1, y1) in zip(observations, observations[1:]):
        if t1 <= t0:
            continue
        if y0 <= target <= y1 and y1 > y0:
            ratio = (target - y0) / (y1 - y0)
            return t0 + ratio * (t1 - t0), "INTERPOLATED"
    # A short, bounded extrapolation is useful for a visible note that was
    # recorded immediately before the line.  It is explicitly labelled and
    # never treated as an observed game event.
    t0, y0 = observations[-2]
    t1, y1 = observations[-1]
    if t1 > t0 and y1 > y0 and y1 <= target and target - y1 <= 80.0:
        velocity = (y1 - y0) / (t1 - t0)
        if velocity > 0:
            return t1 + (target - y1) / velocity, "BOUNDED_EXTRAPOLATION"
    return None, "NO_CROSSING_IN_VISIBLE_TRACK"


def _write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        wr.writeheader()
        wr.writerows(rows)


def _extract_review_frames(video, index_rows, keydowns, out_dir):
    """Create ±300 ms frame probes when OpenCV and a source video exist."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if not video or not video.exists() or not index_rows:
        return [], "UNAVAILABLE"
    try:
        import cv2  # optional dependency for diagnostics only
    except ImportError:
        return [], "OPENCV_UNAVAILABLE"
    times = [_f(r.get("capture_timestamp")) for r in index_rows]
    valid = [(t, r) for t, r in zip(times, index_rows) if t is not None]
    if not valid:
        return [], "NO_CAPTURE_TIMESTAMPS"
    times = [t for t, _ in valid]
    rows = [r for _, r in valid]
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        return [], "VIDEO_OPEN_FAILED"
    probes = []
    seen = set()
    try:
        for action in keydowns:
            ts = _f(action.get("timestamp"))
            if ts is None:
                continue
            for offset in (-0.3, 0.0, 0.3):
                target = ts + offset
                row = _nearest(times, rows, target)
                if not row:
                    continue
                vf = _i(row.get("video_frame"))
                if vf is None or vf in seen:
                    continue
                seen.add(vf)
                cap.set(cv2.CAP_PROP_POS_FRAMES, vf)
                ok, frame = cap.read()
                if not ok:
                    continue
                uid = action.get("event_id") or "unknown"
                name = f"{len(probes):04d}_{uid.replace(':', '_')}_offset_{offset:+.1f}s_frame_{vf}.png"
                path = out_dir / name
                cv2.imwrite(str(path), frame)
                probes.append({"uid": uid, "offset_s": offset, "frame_index": vf,
                               "source_frame": row.get("source_frame", ""),
                               "capture_timestamp": row.get("capture_timestamp", ""),
                               "path": str(path)})
    finally:
        cap.release()
    return probes, "OK"


def analyze(run_dir: Path, video: Path | None = None):
    run_dir = run_dir.resolve()
    run = {}
    run_path = run_dir / "live_run.json"
    if run_path.exists():
        run = json.loads(run_path.read_text(encoding="utf-8-sig"))
    track_rows, _ = _read(run_dir / "live_track_identity.csv")
    if not track_rows:
        track_rows, _ = _read(run_dir / "live_candidate_trace.csv")
    global_rows, _ = _read(run_dir / "global_tap_timing_shadow.csv")
    intent_rows, _ = _read(run_dir / "tap_intents.csv")
    action_rows, _ = _read(run_dir / "input_actions.csv")
    index_rows, _ = _read(run_dir / "live_video_index.csv")

    geometry = run.get("geometry_snapshot") or {}
    hit_y = _f(run.get("tracking_completion_y"), 325.5)
    input_y = _f(run.get("input_trigger_y"), hit_y)
    lead_ms = _f((run.get("tap_timing_calibration") or {}).get("input_lead_ms"), 0.0)
    timing_source = (run.get("tap_timing_calibration") or {}).get("timing_source", "UNKNOWN")
    config = run.get("config") or {}
    actual_label = (((config.get("live") or {}).get("global_tap_timing") or {}).get("ab_label")
                    or ((config.get("live") or {}).get("diagnostics") or {}).get("timing_ab_label")
                    or "UNKNOWN")

    video_rows = sorted(index_rows, key=lambda row: _f(row.get("capture_timestamp"), math.inf))
    video_times = [_f(row.get("capture_timestamp")) for row in video_rows]
    start_time = next((t for t in video_times if t is not None), None)

    by_uid = defaultdict(list)
    for row in track_rows:
        uid = row.get("note_uid") or row.get("track_uid") or ""
        box = _bbox(row.get("bbox"))
        timestamp = _f(row.get("capture_timestamp"))
        if not uid or box is None or timestamp is None:
            continue
        if track_rows and "real_observation_this_frame" in row and not _bool(row.get("real_observation_this_frame")):
            continue
        x, y, w, h = box
        by_uid[uid].append({"t": timestamp, "top": y, "center": y + h / 2,
                            "bottom": y + h, "height": h, "row": row})
    for values in by_uid.values():
        values.sort(key=lambda item: item["t"])

    global_by_uid = defaultdict(list)
    for row in global_rows:
        uid = row.get("note_uid", "")
        if uid:
            global_by_uid[uid].append(row)
    intents_by_uid = defaultdict(list)
    for row in intent_rows:
        uid = row.get("note_uid") or row.get("event_id") or ""
        if uid:
            intents_by_uid[uid].append(row)
    tap_downs = defaultdict(list)
    action_history = defaultdict(list)
    for row in action_rows:
        if row.get("event_id") and row.get("action") in {"scheduled", "amended", "key_down"}:
            action_history[row.get("event_id")].append(row)
        if row.get("action") == "key_down" and row.get("note_type") == "tap":
            tap_downs[row.get("event_id", "")].append(row)

    per_uid = []
    hypotheses = []
    for uid, values in sorted(by_uid.items()):
        if len(values) < 2:
            continue
        heights = [v["height"] for v in values]
        bbox_reliability = ("RELIABLE" if len(values) >= 3 and all(h > 0 for h in heights)
                            else "UNRELIABLE_BBOX")
        first = values[0]["row"]
        appearance = first.get("appearance", "")
        lane = first.get("stable_keys", "")
        gvals = global_by_uid.get(uid, [])
        available = [r for r in gvals if r.get("eta_status") == "AVAILABLE"]
        last_model = available[-1] if available else (gvals[-1] if gvals else {})
        ivals = intents_by_uid.get(uid, [])
        scheduled = [r for r in ivals if r.get("state") in {"SCHEDULED", "PENDING", "FIRED"}]
        history = action_history.get(uid, [])
        amendments = [r for r in history if r.get("action") == "amended"]
        actions = tap_downs.get(uid, [])
        keydown = actions[-1] if actions else {}
        deadline_actions = [r for r in history if r.get("scheduled_hit")]
        first_deadline = (deadline_actions[0].get("scheduled_hit", "")
                          if deadline_actions else next((r.get("predicted_hit_time") for r in scheduled
                                                         if r.get("predicted_hit_time")), ""))
        final_deadline = (deadline_actions[-1].get("scheduled_hit", "") if deadline_actions
                          else (scheduled[-1].get("predicted_hit_time", "") if scheduled else ""))
        if keydown.get("scheduled_hit"):
            final_deadline = keydown.get("scheduled_hit")
        top_obs = [(v["t"], v["top"]) for v in values]
        center_obs = [(v["t"], v["center"]) for v in values]
        bottom_obs = [(v["t"], v["bottom"]) for v in values]
        crossings = {anchor: _crossing(obs, hit_y) for anchor, obs in
                     (("top", top_obs), ("center", center_obs), ("bottom", bottom_obs))}
        keydown_time = _f(keydown.get("timestamp"))
        nearest_index = _nearest(video_times, video_rows, keydown_time) if keydown_time is not None else None
        per_uid.append({
            "uid": uid, "track_uid": first.get("track_uid", ""), "track_id": first.get("track_id", ""),
            "lane": lane, "appearance": appearance, "note_type": "tap" if actions else first.get("confirmed_note_type", ""),
            "observation_count": len(values), "first_capture_timestamp": values[0]["t"],
            "last_capture_timestamp": values[-1]["t"], "first_bbox": first.get("bbox", ""),
            "last_bbox": values[-1]["row"].get("bbox", ""), "bbox_height_min": min(heights),
            "bbox_height_max": max(heights), "bbox_reliability": bbox_reliability,
            "profile_age_s": last_model.get("profile_age_s", ""),
            "profile_segment_count": last_model.get("profile_segment_count", ""),
            "velocity_px_s": last_model.get("velocity_px_s", ""),
            "uncertainty_s": last_model.get("uncertainty_s", ""),
            "speed_epoch": last_model.get("speed_epoch", ""),
            "model_status": last_model.get("model_status", ""),
            "model_reason": last_model.get("model_reason", ""),
            "eta_status": last_model.get("eta_status", ""),
            "eta_reason": last_model.get("eta_reason", ""),
            "planner_status": last_model.get("planner_status", ""),
            "planner_reason": last_model.get("planner_reason", ""),
            "planner_key": last_model.get("planner_key", ""),
            "observed_at": last_model.get("observed_at", ""),
            "physical_hit_y": hit_y, "geometry_source": "live_run.tracking_completion_y",
            "timing_source": timing_source, "input_lead_ms": lead_ms,
            "physical_cross_at": last_model.get("physical_cross_at", ""),
            "press_at": last_model.get("press_at", ""), "first_deadline": first_deadline,
            "final_deadline": final_deadline, "amend_count": len(amendments),
            "key_down_at": keydown.get("timestamp", ""), "key_down_key": keydown.get("key", ""),
            "key_down_frame": nearest_index.get("video_frame", "") if nearest_index else "",
            "visual_crossing_center": crossings["center"][0] or "",
            "visual_crossing_status": crossings["center"][1],
            "game_grade": "UNKNOWN", "grade_confidence": "NEEDS_GROUND_TRUTH",
        })
        for anchor, observations in (("top", top_obs), ("center", center_obs), ("bottom", bottom_obs)):
            for delta in Y_OFFSETS:
                target = hit_y + delta
                cross, cross_status = _crossing(observations, target)
                for candidate_lead in LEADS_MS:
                    press = cross - candidate_lead / 1000.0 if cross is not None else None
                    error_ms = (keydown_time - press) * 1000.0 if press is not None and keydown_time is not None else None
                    hypotheses.append({
                        "uid": uid, "lane": lane, "appearance": appearance,
                        "anchor": anchor, "target_y": target, "y_offset_px": delta,
                        "lead_ms": candidate_lead, "crossing_at": cross or "",
                        "crossing_status": cross_status, "press_at": press or "",
                        "recorded_key_down_at": keydown_time or "", "press_error_ms": error_ms or "",
                        "bbox_reliability": bbox_reliability, "source": "offline_shadow_only",
                        "game_truth": "UNKNOWN",
                    })

    # Build a non-destructive grade sheet.  Existing human grades, if any, are
    # copied through; machine-created rows explicitly require review.
    grade_path = run_dir / "tap_game_grade_review.csv"
    old_grades, old_fields = _read(grade_path) if grade_path.exists() else ([], [])
    old_by_uid = {r.get("uid", ""): r for r in old_grades}
    grade_rows = []
    for uid, actions in sorted(tap_downs.items()):
        for action in actions:
            ts = _f(action.get("timestamp"))
            idx = _nearest(video_times, video_rows, ts) if ts is not None else None
            old = old_by_uid.get(uid, {})
            grade_rows.append({
                "video_time": (ts - start_time) if ts is not None and start_time is not None else "",
                "frame_index": idx.get("video_frame", "") if idx else "", "uid": uid,
                "lane": next((r["lane"] for r in per_uid if r["uid"] == uid), ""),
                "key": action.get("key", ""), "note_type": "tap",
                "grade": old.get("grade", "UNKNOWN") or "UNKNOWN",
                "direction": old.get("direction", "UNKNOWN") or "UNKNOWN",
                "confidence": old.get("confidence", "NEEDS_GROUND_TRUTH") or "NEEDS_GROUND_TRUTH",
                "association_reason": old.get("association_reason", "key_down_to_UID_only; no_game_truth") or "key_down_to_UID_only; no_game_truth",
                "visual_anchor": old.get("visual_anchor", "UNKNOWN") or "UNKNOWN",
                "source_frame": idx.get("source_frame", "") if idx else "",
                "source_video_frame": idx.get("source_video_frame", "") if idx else "",
            })
    generated_uids = {row["uid"] for row in grade_rows}
    # Preserve manual rows that do not belong to a currently observed key-down
    # instead of silently deleting a reviewer's work on a rerun.
    grade_rows.extend(row for row in old_grades if row.get("uid", "") not in generated_uids)
    _write_csv(grade_path, grade_rows, GRADE_FIELDS)
    probes, probe_status = _extract_review_frames(video, video_rows,
                                                   [a for rows in tap_downs.values() for a in rows],
                                                   run_dir / "tap_geometry_review_frames")
    if probes:
        _write_csv(run_dir / "tap_geometry_review_frame_index.csv", probes,
                   ["uid", "offset_s", "frame_index", "source_frame", "capture_timestamp", "path"])

    per_uid_fields = list(per_uid[0].keys()) if per_uid else ["uid"]
    hypothesis_fields = list(hypotheses[0].keys()) if hypotheses else ["uid"]
    _write_csv(run_dir / "tap_geometry_eta_per_uid.csv", per_uid, per_uid_fields)
    _write_csv(run_dir / "tap_geometry_eta_hypotheses.csv", hypotheses, hypothesis_fields)

    status_counts = Counter(row["crossing_status"] for row in hypotheses)
    grades = Counter(row["grade"] for row in grade_rows)
    reason_uid = defaultdict(set)
    for row in global_rows:
        uid = row.get("note_uid", "")
        if not uid:
            continue
        reason = row.get("eta_reason") or row.get("planner_reason") or "UNKNOWN"
        reason_uid[reason].add(uid)
    amendment_rows = [r for r in action_rows if r.get("action") == "amended"]
    amend_deltas = []
    for row in amendment_rows:
        uid = row.get("event_id", "")
        previous = [r for r in action_rows if r.get("event_id") == uid and r.get("action") in {"scheduled", "amended"}
                    and _f(r.get("timestamp"), -math.inf) < _f(row.get("timestamp"), math.inf)]
        if previous:
            old = _f(previous[-1].get("scheduled_hit"))
            new = _f(row.get("scheduled_hit"))
            if old is not None and new is not None:
                amend_deltas.append((new - old) * 1000.0)
    keyed_offsets = []
    for row in per_uid:
        keydown = _f(row.get("key_down_at"))
        deadline = _f(row.get("final_deadline"))
        if keydown is not None and deadline is not None:
            keyed_offsets.append((keydown - deadline) * 1000.0)
    report = [
        "# V7.14.6 Tap Geometry / ETA Shadow Report", "",
        f"Run: `{run_dir}`", f"Source video: `{video if video else 'UNAVAILABLE'}`",
        "", "## Scope and safety",
        "This is an offline shadow replay. It does not change the active geometry, input lead, Planner, Scheduler, Hold path, or safety gates.",
        "FIRED/key_down/event counts are not game hit truth; grades remain UNKNOWN unless a one-to-one manual label is supplied.",
        "", "## Runtime facts (SUPPORTED)",
        f"- Runtime physical hit y: **{hit_y:.3f}**; input trigger y: **{input_y:.3f}**; input advance: **{hit_y-input_y:.3f}px**.",
        f"- Timing source: `{timing_source}`; actual input lead from run: **{lead_ms:.3f} ms**.",
        f"- Recorded config label: `{actual_label}`. The numeric run value is authoritative; labels are diagnostic metadata.",
        f"- Geometry snapshot status: `{geometry.get('status', 'UNAVAILABLE')}`; geometry SHA: `{run.get('geometry_sha256', 'UNKNOWN')}`.",
        "- The legacy `config.json.playfield.hit_y` is not assumed to be the Live Assist physical target; Live Assist uses the loaded calibration geometry and records it in `tracking_completion_y`.",
        "", "## Visual replay",
        f"- Track UIDs with usable real bbox observations: **{len(per_uid)}**; hypotheses: **{len(hypotheses)}**.",
        f"- Crossing statuses: `{dict(status_counts)}`.",
        f"- Tap key-down rows reviewed: **{len(grade_rows)}**; grade distribution: `{dict(grades)}`.",
        f"- Per-UID model/planner reason coverage: `{dict(sorted((k, len(v)) for k, v in reason_uid.items()))}`.",
        f"- Deadline amendments: **{len(amendment_rows)}** actions over **{len({r.get('event_id') for r in amendment_rows})}** event IDs; amendment delta samples: **{len(amend_deltas)}**.",
        f"- `key_down - final_deadline` is an execution offset only: n={len(keyed_offsets)}, median={sorted(keyed_offsets)[len(keyed_offsets)//2] if keyed_offsets else 'UNKNOWN'} ms.",
        f"- Frame probe extraction: `{probe_status}`; probes written: **{len(probes)}**.",
        "- Anchor comparisons are only geometric timing proxies. A bbox can be clipped or altered by effects; such rows are marked `UNRELIABLE_BBOX`.",
        "", "## Candidate hypotheses",
        "Top, center and bottom are evaluated independently. Each anchor's own coordinate is used for both crossing and velocity-free interpolation; no center-distance/bottom-position mixing is performed.",
        "The y offsets and lead values are shadow hypotheses, not an active A/B result. No best anchor or hit line is selected without one-to-one game labels.",
        "", "## Evidence classification",
        "- **SUPPORTED:** the run used the physical calibrated target recorded above and a 60 ms numeric lead; the old `lead-10ms` label was inconsistent and is corrected for future runs in memory.",
        "- **POSSIBLE:** a fixed anchor or target offset may explain SLOW; the current files provide visual crossings and key-down timing but no per-note game grade.",
        "- **UNRESOLVED:** whether top, center or bottom matches the game's judgment anchor; whether the 60 ms improvement is input latency, geometry offset, or song/timing variation.",
        "- **NOT_SUPPORTED:** treating key-down/FIRED, overlay text, or candidate counts as PERFECT/HIT accuracy.",
        "", "## Missing evidence / next single operation",
        "Manually label the generated `tap_game_grade_review.csv` rows using the adjacent ±300 ms images, retaining UNKNOWN when UID/lane/type/key/grade is not one-to-one. Then run this tool again; only the labelled subset can rank anchor or y hypotheses.",
    ]
    (run_dir / "tap_geometry_eta_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return {"uids": len(per_uid), "hypotheses": len(hypotheses), "grades": dict(grades),
            "frame_probes": len(probes), "probe_status": probe_status, "label": actual_label}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--video", type=Path, default=None,
                        help="Optional source video; otherwise use live_source.mp4 under run-dir if present")
    args = parser.parse_args()
    video = args.video or (args.run_dir / "live_source.mp4")
    if not video.exists():
        video = None
    result = analyze(args.run_dir, video)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
