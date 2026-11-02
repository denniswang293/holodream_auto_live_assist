"""Diagnose Tap SLOW without inventing game judgement truth.

The run's monotonic capture/action clocks are paired using the recorded video
index.  Grade/direction stay UNKNOWN unless an independent manual review is
provided; this tool never treats FIRED or key_down as a game result.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict, Counter
from pathlib import Path


def read_rows(path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def flt(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def percentile(values, q):
    values = sorted(value for value in values if value is not None and math.isfinite(value))
    if not values:
        return None
    pos = (len(values) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return values[lo]
    return values[lo] + (values[hi] - values[lo]) * (pos - lo)


def nearest_global(rows, timestamp):
    candidates = []
    for row in rows:
        capture = flt(row.get("capture_timestamp"))
        if capture is None:
            continue
        candidates.append((abs(capture - timestamp), row))
    return min(candidates, key=lambda item: item[0])[1] if candidates else {}


def analyze(run_dir: Path, video_path: Path | None = None):
    actions = read_rows(run_dir / "input_actions.csv")
    intents = read_rows(run_dir / "tap_intents.csv")
    global_rows = read_rows(run_dir / "global_tap_timing_shadow.csv")
    video = read_rows(run_dir / "live_video_index.csv")
    live_run = json.loads((run_dir / "live_run.json").read_text(encoding="utf-8-sig"))
    global_by_uid = defaultdict(list)
    for row in global_rows:
        global_by_uid[row.get("note_uid", "")].append(row)
    action_by_uid = defaultdict(list)
    for row in actions:
        if row.get("event_id"):
            action_by_uid[row["event_id"]].append(row)
    tap_uids = sorted({row.get("event_id", "") for row in actions
                       if row.get("action") == "key_down" and row.get("note_type") == "tap"})
    rows_out = []
    execution_residuals = []
    schedule_drift = []
    amend_counts = []
    for uid in tap_uids:
        uid_actions = action_by_uid[uid]
        scheduled = [row for row in uid_actions if row.get("action") == "scheduled"]
        amended = [row for row in uid_actions if row.get("action") == "amended"]
        downs = [row for row in uid_actions if row.get("action") == "key_down"]
        scheduled_at = flt(scheduled[0].get("timestamp")) if scheduled else None
        key_down_at = flt(downs[0].get("timestamp")) if downs else None
        final_deadline = flt(downs[0].get("scheduled_hit")) if downs else None
        first_deadline = flt(scheduled[0].get("scheduled_hit")) if scheduled else final_deadline
        if final_deadline is not None and key_down_at is not None:
            execution_residuals.append((key_down_at - final_deadline) * 1000)
        if first_deadline is not None and final_deadline is not None:
            schedule_drift.append((final_deadline - first_deadline) * 1000)
        amend_counts.append(len(amended))
        timed = [row for row in global_by_uid.get(uid, [])
                 if flt(row.get("press_at")) is not None or flt(row.get("hit_at")) is not None]
        timing = nearest_global(timed, key_down_at or scheduled_at or 0.0) if timed else {}
        capture = flt(timing.get("capture_timestamp"))
        frame = ""
        video_time = ""
        if capture is not None and video:
            mapped = min(video, key=lambda row: abs((flt(row.get("capture_timestamp")) or capture) - capture))
            frame = mapped.get("source_frame", mapped.get("video_frame", ""))
            first_capture = flt(video[0].get("capture_timestamp"))
            if first_capture is not None:
                video_time = capture - first_capture
        rows_out.append({
            "video_time": video_time,
            "frame_index": frame,
            "uid": uid,
            "note_type": "tap",
            "key": downs[0].get("key", "") if downs else (scheduled[0].get("key", "") if scheduled else ""),
            "grade": "UNKNOWN",
            "direction": "UNKNOWN",
            "confidence": "UNKNOWN_NO_MANUAL_GAME_LABEL",
            "physical_cross_at": timing.get("physical_cross_at", ""),
            "press_at": timing.get("press_at", timing.get("hit_at", "")),
            "scheduled_at": scheduled_at or "",
            "key_down_at": key_down_at or "",
            "observation_at": timing.get("observed_at", ""),
            "profile_age_ms": ((flt(timing.get("profile_age_s")) or 0.0) * 1000
                               if timing.get("profile_age_s") not in (None, "") else ""),
            "uncertainty_ms": ((flt(timing.get("uncertainty_s")) or 0.0) * 1000
                               if timing.get("uncertainty_s") not in (None, "") else ""),
            "amend_count": len(amended),
            "deadline_to_key_down_ms": ((key_down_at - final_deadline) * 1000
                                         if key_down_at is not None and final_deadline is not None else ""),
            "game_result": "UNKNOWN",
        })
    # These are manually reviewed overlay samples, not UID assignments.  The
    # labels are included only when the caller supplies the source video; the
    # UID remains UNKNOWN so a persistent overlay is never misbound to a Tap.
    visual_rows = []
    if video_path is not None and video_path.exists() and video:
        visual_labels = ((4.0, "PERFECT", "UNKNOWN"),
                         (12.0, "PERFECT", "UNKNOWN"),
                         (20.0, "GOOD", "SLOW"),
                         (30.0, "GOOD", "SLOW"),
                         (40.0, "PERFECT", "UNKNOWN"),
                         (60.0, "GREAT", "SLOW"),
                         (70.0, "GOOD", "SLOW"),
                         (80.0, "PERFECT", "UNKNOWN"))
        first_capture = flt(video[0].get("capture_timestamp"))
        for video_time, grade, direction in visual_labels:
            target = (first_capture + video_time) if first_capture is not None else None
            mapped = (min(video, key=lambda row: abs((flt(row.get("capture_timestamp")) or target) - target))
                      if target is not None else {})
            visual_rows.append({
                "video_time": video_time,
                "frame_index": mapped.get("source_frame", mapped.get("video_frame", "")),
                "uid": "UNKNOWN_VISUAL_FRAME",
                "note_type": "UNKNOWN",
                "key": "UNKNOWN",
                "grade": grade,
                "direction": direction,
                "confidence": "FRAME_OVERLAY_VISIBLE_UID_UNKNOWN",
                "physical_cross_at": "", "press_at": "", "scheduled_at": "",
                "key_down_at": "", "observation_at": "", "profile_age_ms": "",
                "uncertainty_ms": "", "amend_count": "",
                "deadline_to_key_down_ms": "",
                "game_result": "OBSERVED_FRAME_ONLY",
            })
        rows_out.extend(visual_rows)
    review_path = run_dir / "tap_judgment_review.csv"
    fields = ["video_time", "frame_index", "uid", "note_type", "key", "grade", "direction",
              "confidence", "physical_cross_at", "press_at", "scheduled_at", "key_down_at",
              "observation_at", "profile_age_ms", "uncertainty_ms", "amend_count",
              "deadline_to_key_down_ms", "game_result"]
    with review_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows_out)
    report_path = run_dir / "tap_slow_diagnosis.md"
    hold_downs = sum(row.get("action") == "key_down" and row.get("note_type") == "hold" for row in actions)
    tap_downs = len(tap_uids)
    video_pts = []
    for row in video:
        capture, source = flt(row.get("capture_timestamp")), flt(row.get("source_frame"))
        if capture is not None and source is not None:
            video_pts.append((source, capture))
    drift_residuals = []
    if len(video_pts) >= 2:
        (f0, t0), (f1, t1) = video_pts[0], video_pts[-1]
        fps = (f1 - f0) / (t1 - t0) if t1 > t0 else None
        if fps and fps > 0:
            for frame, capture in video_pts:
                drift_residuals.append((capture - t0) - (frame - f0) / fps)
    lines = ["# V7.14.3 Tap SLOW diagnosis", "",
             f"Run: `{run_dir}`", "",
             "Eight representative frame overlays were manually reviewed, but no per-UID manual labels were available. Frame-only grades are recorded with UID UNKNOWN; per-UID FAST/SLOW/PERFECT/GOOD/BAD/MISS remain **UNKNOWN**.",
             "This report separates scheduling/execution timing from game-side judgement.", "",
             "## Run counts", "",
             f"- Tap key_down rows: **{tap_downs}**",
             f"- Hold key_down rows (control): **{hold_downs}**",
             f"- Global READY ratio: **{live_run.get('global_timing_stats', {}).get('ready_ratio', 'UNKNOWN')}**",
             f"- Tap review rows with grade UNKNOWN: **{sum(row['grade'] == 'UNKNOWN' for row in rows_out if row['uid'] != 'UNKNOWN_VISUAL_FRAME')}**",
             f"- Manually reviewed visual overlay samples: **{len(visual_rows)}** (UID remains UNKNOWN)", "",
             "## Execution timing (not game input latency)", "",
             f"- final deadline → key_down P50/P90: **{percentile(execution_residuals, .5)} / {percentile(execution_residuals, .9)} ms**",
             f"- first → final deadline drift P50/P90: **{percentile(schedule_drift, .5)} / {percentile(schedule_drift, .9)} ms**",
             f"- amendment count P50/P90: **{percentile(amend_counts, .5)} / {percentile(amend_counts, .9)}**",
             f"- video-index capture/PTS residual P50/P90: **{percentile([abs(x) * 1000 for x in drift_residuals], .5)} / {percentile([abs(x) * 1000 for x in drift_residuals], .9)} ms**", "",
             "A positive deadline→key_down residual means the actuator woke after the scheduled deadline; it does not prove SLOW without a game label.", "",
             "## Required manual review", "",
             "Fill `tap_judgment_review.csv` only when the video frame, lane, note type, key and game grade can be aligned. Keep ambiguous rows UNKNOWN.",
             "Hold rows are not included in Tap grade ratios; use them only as a control for scheduler/input health.", "",
             f"Review CSV: `{review_path.name}`"]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"review_csv": str(review_path), "report": str(report_path),
            "tap_key_down": tap_downs, "hold_key_down": hold_downs,
            "execution_p50_ms": percentile(execution_residuals, .5),
            "execution_p90_ms": percentile(execution_residuals, .9),
            "game_grades": "UNKNOWN",
            "visual_frame_labels": len(visual_rows)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--video", type=Path)
    args = parser.parse_args()
    print(json.dumps(analyze(args.run_dir, args.video), indent=2))


if __name__ == "__main__":
    main()
