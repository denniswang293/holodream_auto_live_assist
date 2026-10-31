"""Full-screen Windows Assist with an explicit manual input latch."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import ExitStack
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace

import numpy as np

from .calibration import load_calibration, geometry_hash
from .live_capture import AutoCapture, CaptureWorker, Region, normalization_transform
from .live_engine import LiveEngine, draw_live_overlay
from .live_input import TapScheduler
from .live_identity_trace import LiveIdentityTraceWriter
from .windows_runtime import DEFAULT_WINDOW_TITLE


EVENT_FIELDS = ["event_id", "track_id", "source_frame", "capture_timestamp", "processing_timestamp",
                "predicted_hit_time", "uncertainty_s", "key_candidates", "resolved_keys", "type", "appearance",
                "confidence_label", "abstain_reason", "gameplay_state", "eta_expired", "eta_abstain_reason", "geometry_status", "geometry_sha256", "resolution_basis",
                "predictor_mode", "eta_p10_s", "eta_p50_s", "eta_p90_s", "valid_crossing_mass", "particle_ess",
                "real_observation_count", "coast_ms", "physical_hit_time", "measurement_status",
                "physical_track_uid", "source_track_ids", "reidentified_from_id",
                "confirmed_note_type", "current_observation_type", "identity_state",
                "association_score", "measurement_quality", "note_uid",
                "simple_core_state", "simple_core_reason", "lane_span", "crossing_y",
                "revision", "particle_predicted_y", "particle_velocity_px_s", "simple_track_observations",
                "simple_track_status", "particle_rejection_streak", "particle_reinitializations"]
FRAME_FIELDS = ["frame", "capture_timestamp", "acquired_timestamp", "processing_timestamp", "timestamp_source",
                "process_begin", "process_end", "last_validated_capture", "scheduler_poll_at",
                "inflight_frame_age_ms", "inflight_processing_ms", "frame_age_expired",
                "gray_rejection_count", "detector_rejection_count",
                "gameplay_state", "focused", "roi_status", "frame_age_ms", "latency_ms", "processing_ms",
                "capture_fps", "processing_fps", "latency_p50_ms", "latency_p95_ms", "stale_total", "candidate_count",
                "tracked_count", "input_armed", "dropped_total", "video_frame", "acquire_queue_wait_ms",
                "normalization_ms", "state_detector_ms", "note_detector_ms", "tracker_matching_ms",
                "unknown_association_ms", "pf_prediction_update_ms", "decision_ms", "scheduler_update_ms",
                "simple_core_ms", "diagnostic_write_ms"]
ACTION_FIELDS = ["action", "reason", "timestamp", "event_id", "key", "scheduled_hit", "armed", "note_type", "lifecycle_state", "revision"]
DECISION_FIELDS = ["timestamp", "note_uid", "track_id", "lifecycle_state", "reason", "key",
                   "eta_s", "hit_at", "uncertainty_s", "first_possible_schedule_at",
                   "last_safe_schedule_at", "motion_reliable", "timing_reliable",
                   "timing_quality", "linear_eta_s", "linear_hit_at", "linear_quality",
                   "gates_json", "key_conflicts_json"]
SHADOW_FIELDS = ["capture_timestamp", "processing_timestamp", "note_uid", "track_id", "mode",
                 "status", "reason", "key", "hit_at", "timing_quality", "legacy_result",
                 "legacy_reason", "legacy_key", "legacy_hit_at", "input_sent"]
ETA_FIELDS = ["capture_timestamp", "processing_timestamp", "note_uid", "track_id",
              "last_observation_timestamp", "pf_eta_s", "pf_hit_at", "pf_uncertainty_s",
              "pf_eta_p10", "pf_eta_p50", "pf_eta_p90", "pf_crossing_mass", "linear_eta_s",
              "linear_hit_at", "linear_velocity_px_s", "linear_quality", "prediction_status",
              "linear_reason", "stale_observation", "legacy_planner_result", "legacy_planner_reason",
              "shadow_planner_result", "shadow_planner_reason", "scheduler_result",
              "scheduler_reason", "appearance"]
INTENT_FIELDS = ["event_id", "note_uid", "state", "reason", "timestamp", "key",
                 "predicted_hit_time", "uncertainty_s", "gameplay_state", "revision"]
class CsvLog:
    def __init__(self, path, fields):
        self.file = path.open("x", newline="", encoding="utf-8-sig")
        self.writer = csv.DictWriter(self.file, fieldnames=fields)
        self.writer.writeheader()
        self.lock = threading.Lock()

    def write(self, row):
        with self.lock:
            self.writer.writerow(row)
            self.file.flush()

    def close(self):
        self.file.close()


class RecordingIndexLog(CsvLog):
    def submit(self, name, rows, state):
        for row in rows:
            self.write(row)


def new_run_directory(requested):
    output_root = Path(requested)
    output_root.mkdir(parents=True, exist_ok=True)
    while True:
        run_dir = output_root / datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%S_%fZ")
        try:
            run_dir.mkdir(exist_ok=False)
            return run_dir
        except FileExistsError:
            # Avoid reusing a run directory even if two launches share a timestamp.
            time.sleep(0.00001)


def _summary(out, result):
    (out/"live_run.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    lines = ["# HoloDream Assist diagnostics", "", f"Stop: {result['stop_reason']}",
             f"Source: {result['source_kind']} | geometry: {result['geometry_status']} ({result['geometry_sha256']})", "",
             f"Input prediction target: y={result['input_trigger_y']:.1f}; physical track completion: y={result['tracking_completion_y']:.1f}.",
             f"Processed frames: {result['processed_frames']}; acquired/source frames: {result['acquired_frames']}",
             f"Capture FPS: {result['capture_fps']:.3f}; processing FPS: {result['wall_processing_fps']:.3f}",
             f"Latency P50/P95: {result['latency_p50_ms']:.3f}/{result['latency_p95_ms']:.3f} ms",
             f"Dropped frames: {result['dropped_frames']}; stale frames: {result['stale_frames']}",
             f"Events: {result['events']}; abstentions: {result['abstentions']}; key-downs: {result['sent_key_downs']} (Tap {result['sent_taps']}, Hold {result['sent_holds']})",
             f"Tap intent states: {result['simple_intent_states']}",
             f"Abstain reasons: {result['abstain_reasons']}", "",
             "Tap accuracy and real-game hit rate are UNVERIFIED; event counts are not accuracy metrics.",
             "The input latch starts OFF. Ctrl+Shift+Alt+Q plus modifier release is required to Arm.",
             "Esc/F12, stale frames, focus loss, invalid ROI or gameplay state disarm and release keys. Re-arming is manual.",
             "Hold uses the user-confirmed visible-tail rule; its accuracy is also UNVERIFIED.", "",
             f"Recording index: {result['recording_index']}; encoded frames: {result['recording_encoded_frames']}; dropped recording frames: {result['recording_dropped_frames']}.",
             "Latency stops at the decision stage and excludes overlay/encoding."]
    (out/"live_diagnostics.md").write_text("\n".join(lines)+"\n", encoding="utf-8")


def run(args):
    config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    if args.live_config.exists():
        live_document = json.loads(args.live_config.read_text(encoding="utf-8-sig"))
        config["live"] = {**config.get("live", {}), **live_document}
    config.setdefault("predictor", {})
    live_cfg = config.get("live", {})
    config["predictor"]["mode"] = "particle"
    geometry = load_calibration(args.geometry)
    max_age = live_cfg.get("max_frame_age_ms", 50)/1000
    worker = target = controls = None
    clock = time.perf_counter
    stopped = threading.Event()
    stop_reason = "stopped"
    recorder = None
    reasons = Counter()
    tap_funnel = Counter()
    input_actions = Counter()
    latencies = []
    last_info = None
    from .windows_runtime import WindowTarget, enable_dpi_awareness, modifiers_down
    enable_dpi_awareness()
    if not args.window_title:
        raise ValueError("Assist needs --window-title; use --list-windows to inspect titles")
    target = WindowTarget(args.window_title)
    target.client_region()  # Ensure the requested game window exists before capture starts.
    region = target.monitor_region()
    capture_fit = normalization_transform((region.width, region.height), geometry.reference_resolution)
    video_fps = live_cfg.get("capture_fps", 120)
    focus_check, modifier_check = target.focused, modifiers_down
    out = new_run_directory(args.out)
    identity_cfg = dict(config.get("diagnostics", {}).get("live_identity_trace", {}) or {})
    identity_trace = (LiveIdentityTraceWriter(out, out.name, identity_cfg)
                      if identity_cfg.get("enabled", False) else None)
    print(f"Assist | geometry {geometry.status} | predictor {config['predictor']['mode']} | output: {out}", flush=True)
    print("Ctrl+Shift+Alt+Q toggles assist only; Esc/F12 stops. Input starts OFF.", flush=True)
    print(f"Actual physical capture rectangle: {region.bounds} (entire game display)",flush=True)
    wall_started = time.perf_counter()
    with ExitStack() as stack:
        event_log = CsvLog(out/"live_events.csv", EVENT_FIELDS)
        frame_log = CsvLog(out/"live_frames.csv", FRAME_FIELDS)
        key_log = CsvLog(out/"live_key_actions.csv", ACTION_FIELDS)
        decision_log = CsvLog(out/"tap_decisions.csv", DECISION_FIELDS)
        shadow_log = CsvLog(out/"tap_planner_shadow.csv", SHADOW_FIELDS)
        eta_log = CsvLog(out/"tap_eta_comparison.csv", ETA_FIELDS)
        intent_log = CsvLog(out/"tap_intents.csv", INTENT_FIELDS)
        input_log = CsvLog(out/"input_actions.csv", ACTION_FIELDS)
        for log in (event_log, frame_log, key_log, decision_log, shadow_log, eta_log, intent_log, input_log):
            stack.callback(log.close)
        if identity_trace is not None:
            stack.callback(identity_trace.close)
        if args.record_overlay:
            from .live_async import EncoderWorker, VIDEO_INDEX_FIELDS
            from .live_profiling import StageProfiler
            index_log = RecordingIndexLog(out/'live_video_index.csv',VIDEO_INDEX_FIELDS)
            stack.callback(index_log.close)
            recorder = EncoderWorker(out,StageProfiler(),index_log,min(video_fps,60),True,
                                     overlay_filename='live_overlay.mp4',source_filename='live_source.mp4',
                                     index_filename='live_video_index.csv')
            stack.callback(recorder.close)
        from .windows_runtime import WindowsActuator
        actuator = WindowsActuator(input_mode=live_cfg.get('keyboard_input_mode','scan_code'))
        print(f"Keyboard input: {actuator.input_mode}",flush=True)
        engine_holder={}
        def log_action(row):
            key_log.write(row)
            input_log.write(row)
            input_actions[row.get("action", "unknown")] += 1
            if "engine" in engine_holder:
                engine_holder["engine"].record_scheduler_action(row)
            if row["action"] in ("armed","disarmed","arm_rejected","arm_requested",
                                  "arm_waiting_for_fresh_frame","arm_resumed_on_fresh_frame",
                                  "decision_wait","decision_resumed"):
                print(f"INPUT {row['action']}: {row['reason']}",flush=True)
            elif row['action']=='key_down':
                print(f"{row['note_type'].upper()} sent: {row['key']}",flush=True)
        scheduler = TapScheduler("assist", actuator, clock=clock, focus_check=focus_check,
                                 modifiers_check=modifier_check, on_log=log_action,
                                 max_age=max_age, duration=config.get("timing", {}).get("tap_duration_ms", 25)/1000,
                                 max_lateness=live_cfg.get("max_input_lateness_ms", 15)/1000,
                                 stale_context_pause_ms=live_cfg.get("stale_context_pause_ms", 200),
                                 max_hold_s=live_cfg.get('hold_visual',{}).get('max_hold_s',6.),
                                 max_uncertainty=live_cfg.get("speculative_taps",{}).get("max_uncertainty_s",.04)
                                     if live_cfg.get("speculative_taps",{}).get("enabled") else .04)
        stack.callback(scheduler.close)
        engine = LiveEngine(config, geometry, scheduler, clock,
                            identity_trace=identity_trace)
        engine_holder["engine"]=engine
        print(f"Particle-based Tap assist + visual Hold assist; keys: {','.join(k for k in config['key_map'] if k in engine.known_keys) or 'NONE; taps will abstain'}",flush=True)
        from .windows_runtime import GlobalControls
        def emergency_stop():
            stopped.set()
            scheduler.disarm("global_escape_or_f12")
        controls = GlobalControls(lambda: scheduler.toggle() if not stopped.is_set() else None,
                                  emergency_stop, True).start()
        stack.callback(controls.close)
        scheduler.start()
        worker = CaptureWorker(lambda: AutoCapture(region, args.backend), video_fps).start()
        stack.callback(worker.close)
        try:
            while not stopped.is_set():
                if recorder and recorder.error:
                    raise RuntimeError(f'Recording encoder failed: {recorder.error}')
                if scheduler.error:
                    raise RuntimeError(f"Input scheduler stopped: {scheduler.error}")
                if controls and controls.error:
                    raise RuntimeError(f"Global controls stopped: {controls.error}")
                packet = worker.buffer.take(.1)
                if packet is None:
                    if worker.error:
                        raise RuntimeError(str(worker.error))
                    if worker.buffer.closed:
                        break
                    continue
                dropped = worker.buffer.dropped
                try:
                    focused = target.focused()
                except ValueError:
                    focused = False
                roi_valid = True
                work, tracks, events, info = engine.process(packet, focused, roi_valid)
                info["capture_fps"] = worker.actual_fps
                for event in events:
                    event_log.write(event)
                    if event.get("simple_core_state") in {
                            "DETECTED", "CONFIRMED", "SCHEDULED", "PENDING", "FIRED",
                            "EXPIRED", "CANCELED", "NOT_SCHEDULED"}:
                        intent_log.write({
                            "event_id": event.get("event_id", ""),
                            "note_uid": event.get("note_uid", event.get("event_id", "")),
                            "state": event.get("simple_core_state", ""),
                            "reason": event.get("simple_core_reason", ""),
                            "timestamp": event.get("capture_timestamp", ""),
                            "key": event.get("resolved_keys", ""),
                            "predicted_hit_time": event.get("predicted_hit_time", ""),
                            "uncertainty_s": event.get("uncertainty_s", ""),
                            "gameplay_state": event.get("gameplay_state", ""),
                            "revision": event.get("revision", "")})
                        tap_funnel[event.get("simple_core_state", "unknown")] += 1
                    core_state=event.get("simple_core_state","")
                    if core_state:
                        if core_state=="SCHEDULED": reasons["selected_tap"] += 1
                        elif core_state in ("CANCELED","EXPIRED"):
                            reasons[event.get("simple_core_reason") or core_state.lower()] += 1
                    else:
                        reasons[event["abstain_reason"] or "selected_tap"] += 1
                for decision in engine.simple_core.drain_decisions():
                    decision_log.write(decision)
                for row in engine.simple_core.drain_shadow_rows():
                    shadow_log.write(row)
                for row in engine.simple_core.drain_eta_rows():
                    eta_log.write(row)
                image = draw_live_overlay(work, tracks, info, engine, dropped)
                info["dropped_total"] = dropped
                info["video_frame"] = ""
                if recorder:
                    job = SimpleNamespace(work=work,info=dict(info),event_ids='|'.join(e['event_id'] for e in events))
                    recorder.offer(job,image)
                frame_log.write(info)
                last_info = info
                latencies.append(info["latency_ms"])
                if engine.frames % 600 == 0:
                    print(f"{engine.frames} processed | armed {scheduler.armed} | sent {scheduler.sent} | events {engine.events} | abstain {engine.abstentions} | dropped {dropped}", flush=True)
                if args.max_frames and engine.frames >= args.max_frames:
                    stop_reason = "frame_limit"
                    break
            if stopped.is_set() and stop_reason == "stopped":
                stop_reason = "global_escape_or_f12"
        except KeyboardInterrupt:
            stop_reason = "keyboard_interrupt"
        except Exception as error:
            stop_reason = f"error: {error}"
            raise
        finally:
            # Disable immediately, before potentially slow encoder/camera close.
            stopped.set()
            scheduler.disarm("session_ended")
            if controls:
                controls.close()
            scheduler.close()
            if worker:
                worker.close()
            recording_error = None
            if recorder:
                try:
                    recorder.close()
                except Exception as error:
                    recording_error = error
                    stop_reason = f'error: {error}'
            wall_elapsed = time.perf_counter()-wall_started
            simple_states={state:sum(intent.state==state for intent in engine.simple_core.intents.intents.values())
                           for state in ("PENDING","FIRED","CANCELED","EXPIRED")}
            result = {"mode": "assist", "predictor_mode": config["predictor"]["mode"],
                      "tap_core": "simple_particle",
                      "simple_intent_states": simple_states,
                      "source_kind": "actual window capture",
                      "window_title": target.title if target else None,
                      "region": list(region.bounds) if region else None,
                      "normalization_transform": capture_fit.as_dict(),
                      "capture_backend": worker.backend_name,
                      "capture_fallback_reason": worker.fallback_reason,
                      "geometry_status": geometry.status, "geometry_sha256": geometry_hash(geometry.document),
                      "geometry_snapshot": geometry.document, "config": config,
                      "input_trigger_y": engine.trigger_y, "input_advance_px": engine.input_advance_px,
                      "tracking_completion_y": geometry.hit_y,
                      "hold_visual_enabled": engine.hold_enabled,
                      "judgment_time_model": {"status": engine.judgment_time.status,
                                              "samples": len(engine.judgment_time.samples),
                                              "min_samples": engine.judgment_time.min_samples},
                      "refactor_flags": {
                          "tap_deadline_amend": engine.simple_core.intents.amend_enabled,
                          "hold_tracker_v2": engine.hold_tracker_v2 is not None,
                          "judgment_calibration_v2": engine.judgment_time.enabled,
                      },
                      "geometry_cache": geometry.cache_info(),
                      "tap_rule": engine.tap_rule.metadata() if engine.tap_rule else None,
                      "processed_frames": engine.frames, "acquired_frames": worker.captured,
                      "dropped_frames": worker.buffer.dropped,
                      "stale_frames": engine.stale, "events": engine.events, "abstentions": engine.abstentions,
                      "abstain_reasons": dict(reasons), "sent_taps": scheduler.sent_taps,
                      "sent_holds": scheduler.sent_holds, "sent_key_downs": scheduler.sent,
                      "keyboard_backend": "Win32 SendInput",
                      "keyboard_input_mode": actuator.input_mode,
                      "input_armed_at_start": False, "recycled_track_ids": sorted(engine.recycled_ids),
                      "capture_fps": last_info["capture_fps"] if last_info else 0,
                      "wall_processing_fps": engine.frames/wall_elapsed if wall_elapsed else 0,
                      "latency_p50_ms": float(np.median(latencies)) if latencies else 0,
                      "latency_p95_ms": float(np.percentile(latencies,95)) if latencies else 0,
                      "stop_reason": stop_reason, "wall_elapsed_s": wall_elapsed,
                      "recording_async": recorder is not None,
                      "recording_encoded_frames": recorder.encoded if recorder else 0,
                      "recording_dropped_frames": recorder.slot.dropped if recorder else 0,
                      "recording_clean_source": recorder is not None,
                      "recording_nominal_fps": min(video_fps,60) if recorder else video_fps if args.record_overlay else None,
                      "recording_index": 'live_video_index.csv' if recorder else None,
                      "recording_error": str(recording_error) if recording_error else None,
                      "accuracy": "UNVERIFIED", "real_game_sessions_validated": 0}
            _summary(out, result)
            (out/"run_metrics.json").write_text(json.dumps({
                "metric_scope": "diagnostic_funnel; not game accuracy",
                "tap_lifecycle_transitions": dict(tap_funnel),
                "input_action_counts": dict(input_actions),
                "simple_intent_terminal_states": simple_states,
                "processed_frames": engine.frames,
                "acquired_frames": worker.captured,
                "capture_fps": result["capture_fps"],
                "processing_fps": result["wall_processing_fps"],
                "latency_p50_ms": result["latency_p50_ms"],
                "latency_p95_ms": result["latency_p95_ms"],
                "dropped_frames": result["dropped_frames"],
                "stale_frames": result["stale_frames"],
                "accuracy": "UNVERIFIED"
            }, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
            print(f"Saved {out}: {engine.frames} frames, {engine.events} events, {scheduler.sent_taps} taps, {scheduler.sent_holds} holds. Accuracy UNVERIFIED.", flush=True)
            if recording_error:
                raise RuntimeError(str(recording_error))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window-title",default=DEFAULT_WINDOW_TITLE,help="Game window title (default: %(default)s)")
    parser.add_argument("--list-windows", action="store_true")
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    parser.add_argument("--live-config", type=Path, default=Path("config/live_assist.json"))
    parser.add_argument("--geometry", type=Path, default=Path("config/geometry_live_assist.json"))
    parser.add_argument("--out", type=Path, default=Path("output/assist"))
    parser.add_argument("--backend", choices=("auto", "dxcam", "mss"), default="auto")
    parser.add_argument("--record-overlay", action="store_true",
                        help="Record overlay and clean source asynchronously")
    parser.add_argument("--max-frames", type=int)
    args = parser.parse_args()
    if args.max_frames is not None and args.max_frames <= 0:
        parser.error("--max-frames must be positive")
    try:
        if args.list_windows:
            from .windows_runtime import enable_dpi_awareness, list_windows
            enable_dpi_awareness()
            for hwnd, title in list_windows():
                print(f"{hwnd}: {title}")
            return
        run(args)
    except (ValueError, RuntimeError, OSError, ImportError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
