"""Run deterministic legacy/particle MockActuator replays on a paired live recording."""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
import statistics
import time

import cv2
import numpy as np

from src.geometry import CalibratedGeometry
from src.live_capture import CapturedFrame
from src.live_engine import LiveEngine
from src.live_input import MockActuator, TapScheduler


def read_rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_rows(path, rows):
    rows = list(rows)
    fields = list(rows[0]) if rows else ["status"]
    with Path(path).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class ReplayClock:
    def __init__(self): self.now = 0.
    def __call__(self): return self.now


def quantile(values, q):
    return float(np.percentile(values, q)) if values else 0.


def replay(run_dir: Path, out: Path, mode: str, count: int, root_config: dict,
           live_config: dict, geometry: CalibratedGeometry):
    index = read_rows(run_dir / "live_video_index.csv")
    cap = cv2.VideoCapture(str(run_dir / "live_source.mp4"))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open {run_dir / 'live_source.mp4'}")
    config = json.loads(json.dumps(root_config))
    config["live"] = {**config.get("live", {}), **live_config}
    config.setdefault("predictor", {})["mode"] = mode
    if mode == "particle":
        config["predictor"].setdefault("particle", {})["count"] = count
    clock = ReplayClock()
    actions = []
    actuator = MockActuator()
    scheduler = TapScheduler("assist", actuator, clock=clock,
                             focus_check=lambda: True, modifiers_check=lambda: False,
                             on_log=actions.append,
                             max_age=config["live"].get("max_frame_age_ms", 60) / 1000,
                             max_lateness=config["live"].get("max_input_lateness_ms", 15) / 1000)
    engine = LiveEngine(config, geometry, scheduler, clock=clock)
    state_for_frame = {int(r["source_video_frame"]): r for r in index}
    engine.gate.update = lambda _frame: current_state[0]
    current_state = ["NOT_PLAYING"]
    frame_rows, event_rows, cpu_ms, processing_ms = [], [], [], []
    stage_ms = defaultdict(list)
    frame_n = 0
    start_wall = time.perf_counter()
    try:
        while True:
            ok, image = cap.read()
            if not ok: break
            row = state_for_frame.get(frame_n)
            frame_n += 1
            if row is None:
                continue
            source_frame = int(row["source_frame"])
            captured = float(row["capture_timestamp"])
            processed = float(row["processing_timestamp"])
            current_state[0] = row["gameplay_state"]
            focused = current_state[0] != "FOCUS_LOST"
            clock.now = max(processed, captured)
            begin = time.perf_counter()
            _, tracks, events, info = engine.process(
                CapturedFrame(source_frame, image, captured, processed, "recorded_capture_timestamp"),
                focused=focused, roi_valid=True)
            cpu_ms.append((time.perf_counter() - begin) * 1000)
            processing_ms.append((time.perf_counter() - begin) * 1000)
            for stage, seconds in engine.stage_times.items():
                stage_ms[stage].append(seconds * 1000)
            event_rows.extend({**e, "replay_mode": mode, "particle_count": count if mode == "particle" else ""}
                              for e in events)
            for tr in tracks:
                p = tr.prediction
                if p.predictor_mode != "particle": continue
                frame_rows.append({
                    "run_mode": mode, "track_id": tr.track_id, "source_frame": source_frame,
                    "physical_track_uid": tr.physical_note_uid,
                    "source_track_ids": "|".join(map(str, tr.source_track_ids)),
                    "reidentified_from_id": tr.reidentified_from_id if tr.reidentified_from_id is not None else "",
                    "captured_at": captured, "measurement_used": p.measurement_status == "USED" or p.measurement_status == "INITIALIZED",
                    "measurement_status": p.measurement_status, "measured_y": tr.history[-1][1] if tr.history else "",
                    "pf_y": p.fitted_y if p.fitted_y is not None else "",
                    "pf_velocity": p.velocity if p.velocity is not None else "",
                    "particle_count": p.ess and count or count, "ess": p.ess if p.ess is not None else "",
                    "real_observation_count": p.real_observation_count or "", "coast_ms": p.coast_ms,
                    "eta_p10_ms": p.eta_p10 * 1000 if p.eta_p10 is not None else "",
                    "eta_p50_ms": p.eta_p50 * 1000 if p.eta_p50 is not None else "",
                    "eta_p90_ms": p.eta_p90 * 1000 if p.eta_p90 is not None else "",
                    "trigger_hit_at": p.hit_time if p.hit_time is not None else "",
                    "physical_hit_at": p.physical_hit_time if p.physical_hit_time is not None else "",
                    "valid_crossing_mass": p.valid_crossing_mass if p.valid_crossing_mass is not None else "",
                    "prediction_reason": p.reason,
                })
            # This opt-in arm is confined to MockActuator and the offline replay.
            # It models the user's manual arm only while indexed focus/PLAYING are valid.
            if focused and current_state[0] == "PLAYING" and not scheduler.armed:
                scheduler.update_context(captured, "PLAYING", True, True)
                scheduler.toggle()
                scheduler.poll()
            if frame_n < len(index):
                next_t = float(index[frame_n]["capture_timestamp"])
                while clock.now < next_t:
                    clock.now = min(clock.now + .002, next_t)
                    scheduler.poll()
    finally:
        cap.release()
        scheduler.disarm("replay_finished")
        scheduler.close()
    elapsed = time.perf_counter() - start_wall
    run_json = json.loads((run_dir / "live_run.json").read_text(encoding="utf-8-sig")) if (run_dir / "live_run.json").exists() else {}
    return {
        "mode": mode, "particle_count": count if mode == "particle" else None,
        "frames": frame_n, "replay_wall_s": elapsed, "replay_fps": frame_n / elapsed if elapsed else 0,
        "cv_processing_p50_ms": quantile(processing_ms, 50), "cv_processing_p95_ms": quantile(processing_ms, 95),
        "replay_cpu_call_p50_ms": quantile(cpu_ms, 50), "replay_cpu_call_p95_ms": quantile(cpu_ms, 95),
        "measured_engine_stages_ms": {stage: {"p50": quantile(values, 50), "p95": quantile(values, 95)}
                                       for stage, values in stage_ms.items()},
        "approx_particle_arrays_bytes_per_track": 5 * 8 * count if mode == "particle" else 0,
        "frame_rows": frame_rows, "event_rows": event_rows, "actions": actions,
        "mock_key_downs": sum(a[0] == "down" for a in actuator.calls),
        "mock_calls": actuator.calls,
        "recorded_live_drops": run_json.get("dropped_frames", "UNAVAILABLE"),
        "recorded_live_processed_fps": run_json.get("wall_processing_fps", "UNAVAILABLE"),
        "recorded_live_latency_p95_ms": run_json.get("latency_p95_ms", "UNAVAILABLE"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True,
                        help="Assist run containing live_source.mp4, live_video_index.csv and live_run.json")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    parser.add_argument("--live-config", type=Path, default=Path("config/live_assist_v5.json"))
    parser.add_argument("--geometry", type=Path, default=Path("config/geometry_live_assist.json"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    root_config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    live_config = json.loads(args.live_config.read_text(encoding="utf-8-sig"))
    geometry = CalibratedGeometry(json.loads(args.geometry.read_text(encoding="utf-8-sig")))
    results = []
    aggregate_frames, aggregate_events, aggregate_actions = [], [], []
    for mode, count in (("legacy", 0), ("particle", 64), ("particle", 128), ("particle", 256)):
        result = replay(args.run_dir, args.out, mode, count, root_config, live_config, geometry)
        aggregate_frames.extend(result.pop("frame_rows"))
        aggregate_events.extend(result.pop("event_rows"))
        aggregate_actions.extend({**a, "replay_mode": mode, "particle_count": count or ""}
                                 for a in result.pop("actions"))
        result.pop("mock_calls")
        results.append(result)
    write_rows(args.out / "particle_filter_frames.csv", aggregate_frames)
    write_rows(args.out / "particle_filter_events.csv", aggregate_events)
    event_index = {(r["replay_mode"], str(r["particle_count"] or ""), r["event_id"]): r for r in aggregate_events}
    action_rows = []
    for action in aggregate_actions:
        event = event_index.get((action["replay_mode"], str(action["particle_count"] or ""), action["event_id"]))
        action_rows.append({**action,
            "predictor_mode": event["predictor_mode"] if event else action["replay_mode"],
            "physical_track_uid": event["physical_track_uid"] if event else "",
            "pf_trigger_hit_at": event["predicted_hit_time"] if event else "",
            "frozen_hit_at": action.get("scheduled_hit", ""),
            "identity_parent": event["reidentified_from_id"] if event else "",
            "identity_evidence": "pf_gated_tracker_handoff" if event and event["reidentified_from_id"] else "tracker_id_only"})
    write_rows(args.out / "particle_filter_actions.csv", action_rows)
    # A tracker ID is an alignment aid only, not independently verified physical-note identity.
    legacy = {(int(r["track_id"]), int(r["source_frame"])): r for r in aggregate_events if r["replay_mode"] == "legacy"}
    comparisons = []
    for row in aggregate_events:
        if row["replay_mode"] != "particle": continue
        old = legacy.get((int(row["track_id"]), int(row["source_frame"])))
        comparisons.append({"track_id": row["track_id"], "source_frame": row["source_frame"],
                            "particle_count": row["particle_count"], "legacy_hit_at": old["predicted_hit_time"] if old else "",
                            "particle_hit_at": row["predicted_hit_time"], "legacy_abstain": old["abstain_reason"] if old else "",
                            "particle_abstain": row["abstain_reason"],
                            "ground_truth_crossing_at": "Unknown", "accuracy_status": "UNVERIFIED",
                            "alignment_status": "same_tracker_id_and_first_seen_frame" if old else "no_exact_legacy_match"})
    write_rows(args.out / "particle_filter_comparison.csv", comparisons)
    (args.out / "particle_filter_benchmark.json").write_text(json.dumps({
        "source_run": str(args.run_dir), "source_video": str(args.run_dir / "live_source.mp4"),
        "same_decoded_frames_and_capture_timestamps": True,
        "source_video_index_rows": len(read_rows(args.run_dir / "live_video_index.csv")),
        "results": results,
        "bytes_per_active_particle_filter_state_approx": 5 * 8,
        "accuracy": "UNVERIFIED: no independently annotated physical-note crossing times",
        "mock_arm_note": "Arm latch was simulated only with MockActuator during indexed PLAYING/focused frames.",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
