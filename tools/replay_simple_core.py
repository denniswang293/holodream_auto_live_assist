"""Run matched V6/PF and Simple Core/Linear-or-PF Mock replays.

No Windows actuator is constructed by this tool. Outputs are written under a
separate directory so the recorded live evidence remains untouched.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import statistics
import time

import cv2

from src.geometry import CalibratedGeometry
from src.live import ACTION_FIELDS, EVENT_FIELDS, FRAME_FIELDS
from src.live_capture import CapturedFrame
from src.live_engine import LiveEngine, draw_live_overlay
from src.live_input import MockActuator, TapScheduler


class ReplayClock:
    def __init__(self):
        self.value = 0.
        self.focused = True

    def __call__(self):
        return self.value

    def reset(self, value, focused):
        self.value, self.focused = float(value), bool(focused)


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows, fields):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def percentile(values, p):
    if not values:
        return 0.
    return float(sorted(values)[min(len(values)-1, round((len(values)-1)*p))])


def run_mode(source_dir: Path, output_dir: Path, *, name: str, tap_core: str, predictor: str):
    run = json.loads((source_dir / "live_run.json").read_text(encoding="utf-8-sig"))
    indexes = read_csv(source_dir / "live_video_index.csv")
    original_frames = {int(row["frame"]): row for row in read_csv(source_dir / "live_frames.csv")}
    config = json.loads(json.dumps(run["config"]))
    config.setdefault("live", {})["tap_core"] = tap_core
    config.setdefault("predictor", {})["mode"] = predictor
    geometry = CalibratedGeometry(run["geometry_snapshot"])
    clock, actuator = ReplayClock(), MockActuator()
    action_rows, event_rows, frame_rows, stage_rows = [], [], [], []
    scheduler = TapScheduler("assist", actuator, clock=clock,
        focus_check=lambda: clock.focused, modifiers_check=lambda: False,
        on_log=action_rows.append,
        max_age=config.get("live", {}).get("max_frame_age_ms", 60)/1000,
        max_lateness=config.get("live", {}).get("max_input_lateness_ms", 15)/1000,
        duration=config.get("timing", {}).get("tap_duration_ms", 25)/1000,
        max_hold_s=config.get("live", {}).get("hold_visual", {}).get("max_hold_s", 6.),
        max_uncertainty=config.get("live", {}).get("speculative_taps", {}).get("max_uncertainty_s", .04)
            if config.get("live", {}).get("speculative_taps", {}).get("enabled") else .04)
    engine = LiveEngine(config, geometry, scheduler, clock=clock)
    engine.session_id = "simple-core-ab"
    if engine.simple_core is not None:
        engine.simple_core.session_id = engine.session_id
    scheduler.on_log = lambda row: (action_rows.append(dict(row)), engine.record_scheduler_action(row))
    state = "UNCERTAIN"
    engine.gate.update = lambda image: state
    source = source_dir / "live_source.mp4"
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise RuntimeError(f"Unable to open source recording: {source}")
    output_dir.mkdir(parents=True, exist_ok=True)
    wall_process_ms, wall_overlay_ms = [], []
    began = time.perf_counter()
    frames_read = 0
    arm_generation = 0
    try:
        for index in indexes:
            ok, image = capture.read()
            if not ok:
                break
            seq = int(index["source_frame"])
            recorded = original_frames.get(seq, {})
            captured = float(index["capture_timestamp"])
            acquired = float(recorded.get("acquired_timestamp") or index["processing_timestamp"])
            processed = float(recorded.get("processing_timestamp") or index["processing_timestamp"])
            focused = str(recorded.get("focused", "False")).lower() == "true"
            clock.reset(processed, focused)
            state = index.get("gameplay_state", recorded.get("gameplay_state", "UNCERTAIN"))
            should_arm = str(recorded.get("input_armed", "False")).lower() == "true"
            if should_arm and not scheduler.armed:
                scheduler.armed = True
                scheduler.arm_generation = arm_generation = arm_generation + 1
            elif not should_arm and scheduler.armed:
                scheduler.disarm("recorded_input_disabled")
            roi_valid = recorded.get("roi_status") not in ("BLOCKED", "STALE")
            packet = CapturedFrame(seq, image, captured, acquired, "recorded_capture_index")
            start = time.perf_counter()
            work, tracks, events, info = engine.process(packet, clock.focused, roi_valid)
            process_ms = (time.perf_counter() - start) * 1000
            event_rows.extend(events)
            overlay_start = time.perf_counter()
            draw_live_overlay(work, tracks, info, engine, int(recorded.get("dropped_total", 0) or 0))
            overlay_ms = (time.perf_counter() - overlay_start) * 1000
            wall_process_ms.append(process_ms)
            wall_overlay_ms.append(overlay_ms)
            frame_rows.append({**info, "video_frame": frames_read})
            stage_rows.append({
                "frame": seq, "capture_timestamp": captured, "gameplay_state": info["gameplay_state"],
                "candidate_count": info["candidate_count"], "tracked_count": info["tracked_count"],
                "normalization_ms": info["normalization_ms"], "state_detector_ms": info["state_detector_ms"],
                "note_detector_ms": info["note_detector_ms"], "tracker_matching_ms": info["tracker_matching_ms"],
                "unknown_association_ms": info["unknown_association_ms"],
                "pf_prediction_update_ms": info["pf_prediction_update_ms"],
                "simple_core_ms": info.get("simple_core_ms", 0.),
                "decision_ms": info["decision_ms"], "scheduler_update_ms": info["scheduler_update_ms"],
                "diagnostic_write_ms": info["diagnostic_write_ms"], "overlay_ms": overlay_ms,
                "processing_wall_ms": process_ms, "latency_ms": info["latency_ms"],
                "acquire_queue_wait_ms": (acquired-captured)*1000,
                "recorded_capture_fps": recorded.get("capture_fps", ""),
                "recorded_processing_fps": recorded.get("processing_fps", "")})
            frames_read += 1
    finally:
        capture.release()
        scheduler.close()

    write_csv(output_dir / "live_events.csv", event_rows,
              list(dict.fromkeys([*EVENT_FIELDS, *(key for row in event_rows for key in row)])))
    write_csv(output_dir / "live_key_actions.csv", action_rows, ACTION_FIELDS)
    write_csv(output_dir / "live_frames.csv", frame_rows,
              list(dict.fromkeys([*FRAME_FIELDS, *(key for row in frame_rows for key in row)])))
    perf_fields = ["frame", "capture_timestamp", "gameplay_state", "candidate_count", "tracked_count",
        "normalization_ms", "state_detector_ms", "note_detector_ms", "tracker_matching_ms",
        "unknown_association_ms", "pf_prediction_update_ms", "simple_core_ms", "decision_ms",
        "scheduler_update_ms", "diagnostic_write_ms", "overlay_ms", "processing_wall_ms",
        "latency_ms", "acquire_queue_wait_ms", "recorded_capture_fps", "recorded_processing_fps"]
    write_csv(output_dir / "stage_timing.csv", stage_rows, perf_fields)
    downs = [row for row in action_rows if row.get("action") == "key_down"]
    schedules = [row for row in action_rows if row.get("action") == "scheduled"]
    cancels = [row for row in action_rows if row.get("action") in ("canceled", "abstain")]
    summary = {
        "mode": name, "tap_core": tap_core, "predictor": predictor,
        "source": str(source), "source_index_frames": len(indexes), "replayed_frames": frames_read,
        "candidate_observations": sum(int(row.get("candidate_count") or 0) for row in frame_rows),
        "schedule_actions": len(schedules), "unique_scheduled_ids": len({r.get("event_id") for r in schedules}),
        "key_downs": len(downs), "tap_key_downs": sum(r.get("note_type") == "tap" for r in downs),
        "hold_key_downs": sum(r.get("note_type") == "hold" for r in downs),
        "canceled_or_abstained": len(cancels), "duplicate_key_downs_same_id": max(0, len(downs)-len({r.get("event_id") for r in downs})),
        "wall_processing_fps": frames_read/(sum(wall_process_ms)/1000) if sum(wall_process_ms) else 0.,
        "process_wall_p50_ms": percentile(wall_process_ms,.50),
        "process_wall_p95_ms": percentile(wall_process_ms,.95),
        "overlay_p95_ms": percentile(wall_overlay_ms,.95),
        "replay_processing_p95_ms": percentile(wall_process_ms,.95),
        "latency_recorded_p95_ms": percentile([float(r.get("latency_ms") or 0) for r in frame_rows],.95),
        "recognition_accuracy": "UNVERIFIED", "timing_error": "UNVERIFIED",
        "real_sendinput_calls": 0}
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2)+"\n", encoding="utf-8")
    return summary, event_rows, action_rows, stage_rows


def audit_duplicates(results, root):
    rows = []
    for name, (_summary, events, actions, _stages) in results.items():
        scheduled = [r for r in events if r.get("simple_core_state") == "SCHEDULED"]
        for i, a in enumerate(scheduled):
            try:
                a0, a1 = map(float, str(a.get("lane_span", "")).split(":"))
                ah = float(a.get("predicted_hit_time"))
            except (ValueError, TypeError):
                continue
            for b in scheduled[i+1:]:
                try:
                    b0, b1 = map(float, str(b.get("lane_span", "")).split(":"))
                    bh = float(b.get("predicted_hit_time"))
                except (ValueError, TypeError):
                    continue
                overlap = max(0., min(a1,b1)-max(a0,b0)) / max(1e-9,min(a1-a0,b1-b0))
                if abs(ah-bh) < .035 and overlap >= .90:
                    ta = float(a.get("capture_timestamp") or 0.)
                    tb = float(b.get("capture_timestamp") or 0.)
                    ya = float(a.get("crossing_y") or 0.)
                    yb = float(b.get("crossing_y") or 0.)
                    rows.append({"mode":name,"note_uid_a":a.get("note_uid"),"note_uid_b":b.get("note_uid"),
                        "source_frame_a":a.get("source_frame"),"source_frame_b":b.get("source_frame"),
                        "capture_gap_s":abs(tb-ta),"vertical_gap_px":abs(yb-ya),
                        "eta_gap_s":abs(bh-ah),
                        "key_a":a.get("resolved_keys"),"key_b":b.get("resolved_keys"),
                        "appearance_a":a.get("appearance"),"appearance_b":b.get("appearance"),
                        "span_a":a.get("lane_span"),"span_b":b.get("lane_span"),
                        "hit_at_a":ah,"hit_at_b":bh,"span_overlap_fraction":overlap,
                        "audit":"REVIEW_POSSIBLE_DUPLICATE_NOT_PHYSICAL_GROUND_TRUTH"})
        down_by_id = {}
        for action in actions:
            if action.get("action") == "key_down":
                down_by_id.setdefault(action.get("event_id"), []).append(action)
        for uid, downs in down_by_id.items():
            if len(downs) > 1:
                rows.append({"mode":name,"note_uid_a":uid,"note_uid_b":uid,
                    "key_a":"|".join(r.get("key","") for r in downs),
                    "audit":"DUPLICATE_KEY_DOWN_SAME_INTENT"})
    write_csv(root / "simple_core_duplicate_note_audit.csv", rows,
        ["mode","note_uid_a","note_uid_b","source_frame_a","source_frame_b",
         "capture_gap_s","vertical_gap_px","eta_gap_s","key_a","key_b",
         "appearance_a","appearance_b","span_a","span_b","hit_at_a","hit_at_b",
         "span_overlap_fraction","audit"])


def audit_cancellations(results, root):
    audits = []
    for name, (_summary, events, actions, _stages) in results.items():
        event_by_id = {row.get("event_id"): row for row in events if row.get("event_id")}
        for action in actions:
            if action.get("action") in ("canceled", "abstain"):
                event = event_by_id.get(action.get("event_id"), {})
                audits.append({"mode":name,"event_id":action.get("event_id"),
                    "source_frame":event.get("source_frame"),"candidate_lanes":event.get("key_candidates"),
                    "lane_span":event.get("lane_span"),"key":action.get("key"),
                    "scheduled_hit":action.get("scheduled_hit"),"action":action.get("action"),
                    "reason":action.get("reason"),"classification":"ACTION_STAGE_ONLY_PHYSICAL_NOTE_UNKNOWN"})
        for row in events:
            if row.get("simple_core_state") in ("CANCELED", "EXPIRED"):
                audits.append({"mode":name,"event_id":row.get("event_id"),
                    "source_frame":row.get("source_frame"),"candidate_lanes":row.get("key_candidates"),
                    "lane_span":row.get("lane_span"),"key":row.get("resolved_keys"),
                    "scheduled_hit":row.get("predicted_hit_time"),"action":row.get("simple_core_state"),
                    "reason":row.get("simple_core_reason"),"classification":"CORE_LIFECYCLE_PHYSICAL_NOTE_UNKNOWN"})
    write_csv(root / "simple_core_cancel_audit.csv", audits,
        ["mode","event_id","source_frame","candidate_lanes","lane_span","key","scheduled_hit",
         "action","reason","classification"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path,
        nargs="?", default=Path("output/run_20261030T132141_738544Z"))
    parser.add_argument("--out", type=Path, default=Path("output/v7_simple_core_ab"))
    args = parser.parse_args()
    source_dir = args.run_dir.resolve()
    root = args.out.resolve()
    if not (source_dir / "live_source.mp4").exists() or not (source_dir / "live_video_index.csv").exists():
        raise SystemExit("Source MP4 or live_video_index.csv is missing; no replay data was changed.")
    modes = [("A_v6_particle", "v6", "particle"),
             ("B_simple_linear", "simple", "legacy"),
             ("C_simple_particle", "simple", "particle")]
    results = {}
    for name, core, predictor in modes:
        print(f"Replay {name}: core={core}, predictor={predictor}", flush=True)
        result = run_mode(source_dir, root / name, name=name,
                          tap_core=core, predictor=predictor)
        results[name] = result
        print(json.dumps(result[0], indent=2), flush=True)
    write_csv(root / "simple_core_ab_comparison.csv", [r[0] for r in results.values()],
        ["mode","tap_core","predictor","source_index_frames","replayed_frames","candidate_observations",
         "schedule_actions","unique_scheduled_ids","key_downs","tap_key_downs","hold_key_downs",
         "canceled_or_abstained","duplicate_key_downs_same_id","wall_processing_fps",
         "process_wall_p50_ms","process_wall_p95_ms","overlay_p95_ms","replay_processing_p95_ms",
         "latency_recorded_p95_ms","recognition_accuracy","timing_error","real_sendinput_calls"])
    audit_cancellations(results, root)
    perf_rows = []
    for name, (_summary, _events, _actions, stages) in results.items():
        for column in ("normalization_ms","state_detector_ms","note_detector_ms","tracker_matching_ms",
                       "unknown_association_ms","pf_prediction_update_ms","simple_core_ms","decision_ms",
                       "scheduler_update_ms","diagnostic_write_ms","overlay_ms","processing_wall_ms",
                       "acquire_queue_wait_ms"):
            values = [float(row.get(column) or 0) for row in stages]
            perf_rows.append({"mode":name,"stage":column,"samples":len(values),
                "mean_ms":statistics.fmean(values) if values else 0.,
                "p50_ms":percentile(values,.50),"p95_ms":percentile(values,.95),
                "max_ms":max(values,default=0.)})
    write_csv(root / "simple_core_performance.csv", perf_rows,
        ["mode","stage","samples","mean_ms","p50_ms","p95_ms","max_ms"])
    audit_duplicates(results, root)
    baseline = json.loads((source_dir / "live_run.json").read_text(encoding="utf-8-sig"))
    report = ["# Simple Assist Core A/B/C Mock replay", "",
        f"Source: `{source_dir}` / `{baseline.get('recording_index')}`.",
        "All replay runs used MockActuator; no physical keyboard input was sent.",
        "Candidate/action counts are not game accuracy. Physical-note and judgment truth were not manually labeled.", "",
        "## Recorded V6 live baseline", "",
        f"Frames acquired/processed/dropped: {baseline.get('acquired_frames')}/{baseline.get('processed_frames')}/{baseline.get('dropped_frames')}; ",
        f"FPS: {baseline.get('wall_processing_fps')}; latency P95: {baseline.get('latency_p95_ms')} ms; ",
        f"key-downs: {baseline.get('sent_key_downs')} (Tap {baseline.get('sent_taps')}, Hold {baseline.get('sent_holds')}).",
        "Recorded recognition accuracy remains UNVERIFIED.", "", "## Mock comparison", "",
        "See `simple_core_ab_comparison.csv`, `simple_core_performance.csv`, `simple_core_duplicate_note_audit.csv`, and `simple_core_cancel_audit.csv`.",
        "ETA error and physical-note duplicate status remain UNVERIFIED without independent crossing-time and note annotations.", ""]
    (root / "cleanup_validation_report.md").write_text("\n".join(report), encoding="utf-8")
    print(f"Wrote matched replay outputs under {root}", flush=True)


if __name__ == "__main__":
    main()
