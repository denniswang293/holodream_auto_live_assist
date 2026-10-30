"""Full-screen Windows Assist with an explicit manual input latch."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import ExitStack
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import queue
import threading
import time
from types import SimpleNamespace

import cv2
import numpy as np

from .calibration import load_calibration, geometry_hash
from .live_capture import AutoCapture, CaptureWorker, Region, normalization_transform
from .live_engine import LiveEngine, draw_live_overlay
from .live_input import TapScheduler
from .windows_runtime import DEFAULT_WINDOW_TITLE


EVENT_FIELDS = ["event_id", "track_id", "source_frame", "capture_timestamp", "processing_timestamp",
                "predicted_hit_time", "uncertainty_s", "key_candidates", "resolved_keys", "type", "appearance",
                "confidence_label", "abstain_reason", "gameplay_state", "eta_expired", "eta_abstain_reason", "geometry_status", "geometry_sha256", "resolution_basis",
                "predictor_mode", "eta_p10_s", "eta_p50_s", "eta_p90_s", "valid_crossing_mass", "particle_ess",
                "real_observation_count", "coast_ms", "physical_hit_time", "measurement_status",
                "physical_track_uid", "source_track_ids", "reidentified_from_id",
                "confirmed_note_type", "current_observation_type", "identity_state",
                "association_score", "measurement_quality", "note_uid",
                "simple_core_state", "simple_core_reason", "lane_span", "crossing_y"]
FRAME_FIELDS = ["frame", "capture_timestamp", "acquired_timestamp", "processing_timestamp", "timestamp_source",
                "gameplay_state", "focused", "roi_status", "frame_age_ms", "latency_ms", "processing_ms",
                "capture_fps", "processing_fps", "latency_p50_ms", "latency_p95_ms", "stale_total", "candidate_count",
                "tracked_count", "input_armed", "dropped_total", "video_frame", "acquire_queue_wait_ms",
                "normalization_ms", "state_detector_ms", "note_detector_ms", "tracker_matching_ms",
                "unknown_association_ms", "pf_prediction_update_ms", "decision_ms", "scheduler_update_ms",
                "simple_core_ms", "diagnostic_write_ms"]
ACTION_FIELDS = ["action", "reason", "timestamp", "event_id", "key", "scheduled_hit", "armed", "note_type"]
IDENTITY_FIELDS = ["physical_note_uid", "track_id", "timestamp", "from_state", "to_state",
                   "reason", "confirmed_note_type", "current_observation_type", "evidence_count",
                   "association_score", "innovation_y", "measurement_quality", "coast_ms",
                   "reliable_age_ms", "source_frame"]
ASSOCIATION_FIELDS = ["timestamp", "source_frame", "candidate_index", "track_id", "physical_note_uid",
                      "current_observation_type", "association_accepted", "final_reason", "association_score",
                      "accepted", "reason",
                      "predicted_y", "observed_y", "innovation_y", "sigma_y", "predicted_u", "innovation_u",
                      "sigma_u", "span_overlap", "span_width_ratio", "key_match", "measurement_quality", "coast_ms"]
HIT_ETA_FIELDS = ["physical_note_uid", "track_id", "source_track_ids", "source_frame", "capture_timestamp",
                  "confirmed_note_type", "current_observation_type", "identity_state", "particle_predicted_y",
                  "observed_y", "innovation_y", "association_score", "association_accepted", "measurement_quality",
                  "measurement_status", "eta_p10", "eta_p50", "eta_p90", "hit_at", "physical_hit_time",
                  "valid_crossing_mass", "particle_ess", "coast_ms", "original_selected_key", "original_hit_at",
                  "final_action", "final_reason", "last_reliable_tap_at", "tracker_status"]
SCHEDULER_TRACE_FIELDS = ["timestamp", "event_id", "track_id", "physical_note_uid", "source_track_ids",
                          "original_selected_key", "original_hit_at", "tracker_status", "current_type",
                          "confirmed_note_type", "identity_state", "measurement_status", "association_reason",
                          "first_failed_predicate", "all_failed_predicates"]
TAP_DECISION_FIELDS = ["timestamp", "source_frame", "event_id", "track_id", "physical_note_uid",
    "source_track_ids", "candidate_type", "confirmed_note_type", "identity_state", "track_status",
    "missed_frames", "appearance", "candidate_keys", "stable_keys", "selected_key",
    "particle_initialized", "particle_measurement_status", "particle_ess", "particle_ess_fraction",
    "particle_valid_crossing_mass", "particle_coast_ms", "particle_real_observation_count",
    "particle_measurement_age_ms", "particle_eta_usable", "particle_eta_reject_reason",
    "eta_p10", "eta_p50", "eta_p90", "predicted_hit_time", "hit_history_count",
    "hit_history_drift_ms", "decision_stage", "decision_result", "reject_reason", "is_retryable",
    "pending_intent_exists", "original_hit_at", "original_key", "arm_generation",
    "eventually_scheduled", "eventually_key_down", "eventually_canceled", "final_action",
    "final_reason", "reliable_candidate_appearance", "reliable_candidate_span",
    "current_candidate_span", "original_appearance", "original_span", "original_position_y",
    "current_position_y", "particle_predicted_position_y", "position_compatible",
    "span_compatible", "appearance_compatible", "identity_compatible",
    "competing_candidate_exists", "remaining_to_hit_ms"]
STAGE_FIELDS = ["frame", "capture_timestamp", "gameplay_state", "candidate_count", "tracked_count",
                "acquire_queue_wait_ms", "normalization_ms", "state_detector_ms", "note_detector_ms",
                "tracker_matching_ms", "unknown_association_ms", "pf_prediction_update_ms", "decision_ms",
                "scheduler_update_ms", "simple_core_ms",
                "diagnostic_write_ms", "event_csv_write_ms", "overlay_ms", "recording_offer_ms",
                "frame_csv_write_ms", "stage_csv_write_ms", "capture_to_acquire_ms", "processing_ms",
                "latency_ms", "capture_fps", "processing_fps", "encoder_queue_wait_ms"]


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


class AsyncCsvLog:
    """Bounded, nonblocking diagnostics writer; action logs remain synchronous."""
    def __init__(self,path,fields,*,max_queue=8192,batch_size=128):
        self.path=Path(path); self.fields=list(fields); self.queue=queue.Queue(maxsize=max_queue)
        self.batch_size=batch_size; self.file=self.path.open("x",newline="",encoding="utf-8-sig")
        self.writer=csv.DictWriter(self.file,fieldnames=self.fields); self.writer.writeheader()
        self.lock=threading.Lock(); self.dropped=0; self.schema_errors=0; self.rows_written=0
        self.last_error=""; self.closed=False
        self.thread=threading.Thread(target=self._run,name=f"csv-{self.path.stem}",daemon=True)
        self.thread.start()

    def write(self,row):
        extra=set(row)-set(self.fields)
        with self.lock:
            if extra:
                self.schema_errors+=1; self.dropped+=1
                self.last_error=f"extra_fields:{','.join(sorted(extra))}"
                return
            if self.closed:
                self.dropped+=1; self.last_error="write_after_close"; return
            try: self.queue.put_nowait(dict(row))
            except queue.Full:
                self.dropped+=1; self.last_error="diagnostic_queue_full"

    def _run(self):
        stopping=False
        while not stopping:
            item=self.queue.get(); batch=[]
            if item is None:
                self.queue.task_done(); stopping=True
            else:
                batch.append(item)
                while len(batch)<self.batch_size:
                    try: item=self.queue.get_nowait()
                    except queue.Empty: break
                    if item is None:
                        self.queue.task_done(); stopping=True; break
                    batch.append(item)
            if batch:
                try:
                    self.writer.writerows(batch); self.file.flush(); self.rows_written+=len(batch)
                except Exception as error:
                    with self.lock:
                        self.dropped+=len(batch)
                        self.last_error=f"writer_error:{type(error).__name__}:{error}"
            for _ in batch: self.queue.task_done()
        self.file.flush()

    def health(self):
        return {"file":self.path.name,"rows_written":self.rows_written,"dropped_rows":self.dropped,
                "schema_errors":self.schema_errors,"queue_remaining":self.queue.qsize(),
                "queue_capacity":self.queue.maxsize,"last_error":self.last_error}

    def close(self):
        if self.closed: return
        with self.lock: self.closed=True
        self.queue.put(None); self.thread.join(); self.file.close()


class RecordingIndexLog(CsvLog):
    def submit(self, name, rows, state):
        for row in rows:
            self.write(row)


def new_run_directory(requested):
    requested = Path(requested)
    if requested.exists() and any(requested.iterdir()):
        requested = requested / datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%S_%fZ")
    requested.mkdir(parents=True, exist_ok=False) if not requested.exists() else None
    return requested


def _summary(out, result):
    (out/"live_run.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    lines = ["# HoloDream Assist diagnostics", "", f"Stop: {result['stop_reason']}",
             f"Source: {result['source_kind']} | geometry: {result['geometry_status']} ({result['geometry_sha256']})", "",
             f"Input prediction target: y={result['input_trigger_y']:.1f}; physical track completion: y={result['tracking_completion_y']:.1f}.",
             f"Processed frames: {result['processed_frames']}; acquired/source frames: {result['acquired_frames']}",
             f"Frame/source FPS: {result['capture_fps']:.3f}; wall processing FPS: {result['wall_processing_fps']:.3f}",
             f"Acquisition-to-decision latency P50/P95: {result['latency_p50_ms']:.3f}/{result['latency_p95_ms']:.3f} ms",
             f"Dropped frames: {result['dropped_frames']}; stale frames: {result['stale_frames']}",
             f"Events: {result['events']}; abstentions: {result['abstentions']}; actual key-downs: {result['sent_key_downs']} (Tap {result['sent_taps']}, Hold {result['sent_holds']})",
             f"Abstain reasons: {result['abstain_reasons']}", "",
             "Accuracy / Tap precision / recall / key accuracy / signed timing error: UNVERIFIED.",
             "Live uses host perf_counter at capture start/end, not a verified GPU presentation timestamp.",
             "No confidence value is a correctness probability. The user-confirmed Assist Hold rule presses one start key for configured green/yellow paths and releases after that color's visible tail leaves the judgment row; this visual heuristic is unverified against game judgments. Other unknown candidates receive one Tap attempt.",
             "Key selection uses pinned manual singleton evidence or an explicit user-confirmed any-covered-key control profile; neither verifies recognition accuracy.",
             "Explicit range-rule Assist can commit an already-confirmed Tap across the measured judgment-bar occlusion for at most 100ms; fresh PLAYING/focus/ROI context remains mandatory.",
             "The input latch always starts OFF and requires an explicit user hotkey.",
             "Live assist requires Ctrl+Shift+Alt+Q, modifier release, fresh frames, game focus, PLAYING, and one eligible selected key.",
             "Esc/F12, stale capture, focus/ROI/game-state loss disarm and release keys; resuming does not re-arm.", "",
             "If only the previous decision expires while a fresh frame is being checked, key-down pauses until its validated result; the existing latch is retained, never re-armed automatically. See decision_wait/decision_resumed in live_key_actions.csv.", "",
             f"Recording index: {result['recording_index']}; async encoder: {result['recording_async']}; encoded: {result['recording_encoded_frames']}; unread recording frames replaced: {result['recording_dropped_frames']}.",
             "Live recordings pair clean live_source.mp4 and live_overlay.mp4 through live_video_index.csv. Nominal video FPS is not capture time.",
             "Latency statistics stop at the decision, excluding overlay/encoding. Live encoding has one bounded unread slot and does not wait in the CV loop.", "",
             "## Accuracy status", "",
             "No independent ground truth is available; runtime counts do not establish recognition accuracy.",
             "See the operator guide and live_key_actions.csv for Assist operation and diagnostics."]
    (out/"live_diagnostics.md").write_text("\n".join(lines)+"\n", encoding="utf-8")


def run(args):
    config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    if args.live_config.exists():
        live_document = json.loads(args.live_config.read_text(encoding="utf-8-sig"))
        config["live"] = {**config.get("live", {}), **live_document}
        if isinstance(live_document.get("predictor"), dict):
            config["predictor"] = {**config.get("predictor", {}), **live_document["predictor"]}
    config.setdefault("predictor", {})
    selected_predictor = getattr(args, "predictor", None)
    if selected_predictor:
        config["predictor"]["mode"] = selected_predictor
    config["predictor"].setdefault("mode", "particle")
    if config["predictor"]["mode"] not in ("particle", "legacy"):
        raise ValueError("predictor mode must be particle or legacy")
    live_cfg = config.get("live", {})
    if getattr(args, "tap_core", None):
        live_cfg["tap_core"] = args.tap_core
    live_cfg.setdefault("tap_core", "v6")
    geometry = load_calibration(args.geometry)
    max_age = live_cfg.get("max_frame_age_ms", 50)/1000
    worker = target = controls = None
    clock = time.perf_counter
    stopped = threading.Event()
    stop_reason = "stopped"
    recorder = None
    samples, reasons = {}, Counter()
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
    print(f"Assist | geometry {geometry.status} | predictor {config['predictor']['mode']} | output: {out}", flush=True)
    print("Ctrl+Shift+Alt+Q toggles assist only; Esc/F12 stops. Input starts OFF.", flush=True)
    print(f"Actual physical capture rectangle: {region.bounds} (entire game display)",flush=True)
    wall_started = time.perf_counter()
    with ExitStack() as stack:
        event_log = CsvLog(out/"live_events.csv", EVENT_FIELDS)
        frame_log = CsvLog(out/"live_frames.csv", FRAME_FIELDS)
        key_log = CsvLog(out/"live_key_actions.csv", ACTION_FIELDS)
        identity_log = AsyncCsvLog(out/"pf_identity_transitions.csv", IDENTITY_FIELDS)
        association_log = AsyncCsvLog(out/"pf_unknown_association_audit.csv", ASSOCIATION_FIELDS)
        eta_log = AsyncCsvLog(out/"pf_hit_eta_diagnostics.csv", HIT_ETA_FIELDS)
        scheduler_trace_log = AsyncCsvLog(out/"pf_identity_scheduler_trace.csv", SCHEDULER_TRACE_FIELDS)
        tap_decision_log = AsyncCsvLog(out/"tap_decision_trace.csv", TAP_DECISION_FIELDS)
        stage_log = CsvLog(out/"pf_stage_timing.csv", STAGE_FIELDS)
        diagnostic_logs=(identity_log,association_log,eta_log,scheduler_trace_log,tap_decision_log)
        for log in (event_log, frame_log, key_log, stage_log, *diagnostic_logs):
            stack.callback(log.close)
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
            if "engine" in engine_holder:
                engine_holder["engine"].record_scheduler_action(row)
            if row["action"] in ("armed","disarmed","arm_rejected","arm_requested"):
                print(f"INPUT {row['action']}: {row['reason']}",flush=True)
            elif row['action']=='key_down':
                print(f"{row['note_type'].upper()} sent: {row['key']}",flush=True)
        scheduler = TapScheduler("assist", actuator, clock=clock, focus_check=focus_check,
                                 modifiers_check=modifier_check, on_log=log_action,
                                 max_age=max_age, duration=config.get("timing", {}).get("tap_duration_ms", 25)/1000,
                                 max_lateness=live_cfg.get("max_input_lateness_ms", 15)/1000,
                                 max_hold_s=live_cfg.get('hold_visual',{}).get('max_hold_s',6.),
                                 max_uncertainty=live_cfg.get("speculative_taps",{}).get("max_uncertainty_s",.04)
                                     if live_cfg.get("speculative_taps",{}).get("enabled") else .04)
        stack.callback(scheduler.close)
        engine = LiveEngine(config, geometry, scheduler, clock)
        engine_holder["engine"]=engine
        def diagnostic_sink(name, row):
            {"identity_transition": identity_log, "unknown_association": association_log,
             "hit_eta": eta_log, "scheduler_trace": scheduler_trace_log,
             "tap_decision":tap_decision_log}[name].write(row)
        engine.diagnostic_sink = diagnostic_sink
        previous_stage_csv_ms=0.0
        label = ("Experimental Tap and visible-path Hold attempts" if engine.hold_enabled else
                 "Experimental unknown/uncertain candidate Tap attempts" if engine.speculative.get('enabled') else
                 "User-confirmed any-covered-key Tap rule" if engine.tap_rule else "Verified tap keys")
        print(f"{label}: {','.join(k for k in config['key_map'] if k in engine.known_keys) or 'NONE; automatic taps will abstain'}",flush=True)
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
                event_csv_started=time.perf_counter()
                for event in events:
                    event_log.write(event)
                    core_state=event.get("simple_core_state","")
                    if core_state:
                        if core_state=="SCHEDULED": reasons["selected_tap"] += 1
                        elif core_state in ("CANCELED","EXPIRED"):
                            reasons[event.get("simple_core_reason") or core_state.lower()] += 1
                    else:
                        reasons[event["abstain_reason"] or "selected_tap"] += 1
                event_csv_ms=(time.perf_counter()-event_csv_started)*1000
                overlay_started=time.perf_counter()
                image = draw_live_overlay(work, tracks, info, engine, dropped)
                overlay_ms=(time.perf_counter()-overlay_started)*1000
                info["dropped_total"] = dropped
                info["video_frame"] = ""
                recording_offer_ms=0.0
                if recorder:
                    job = SimpleNamespace(work=work,info=dict(info),event_ids='|'.join(e['event_id'] for e in events))
                    recording_started=time.perf_counter()
                    recorder.offer(job,image)
                    recording_offer_ms=(time.perf_counter()-recording_started)*1000
                frame_csv_started=time.perf_counter()
                frame_log.write(info)
                frame_csv_ms=(time.perf_counter()-frame_csv_started)*1000
                stage_row={"frame":info["frame"],"capture_timestamp":info["capture_timestamp"],
                    "gameplay_state":info["gameplay_state"],"candidate_count":info["candidate_count"],
                    "tracked_count":info["tracked_count"],"acquire_queue_wait_ms":info["acquire_queue_wait_ms"],
                    "normalization_ms":info["normalization_ms"],"state_detector_ms":info["state_detector_ms"],
                    "note_detector_ms":info["note_detector_ms"],"tracker_matching_ms":info["tracker_matching_ms"],
                    "unknown_association_ms":info["unknown_association_ms"],
                    "pf_prediction_update_ms":info["pf_prediction_update_ms"],"decision_ms":info["decision_ms"],
                    "scheduler_update_ms":info["scheduler_update_ms"],
                    "simple_core_ms":info.get("simple_core_ms",0.),
                    "diagnostic_write_ms":info["diagnostic_write_ms"],"event_csv_write_ms":event_csv_ms,
                    "overlay_ms":overlay_ms,"recording_offer_ms":recording_offer_ms,
                    "frame_csv_write_ms":frame_csv_ms,"stage_csv_write_ms":previous_stage_csv_ms,
                    "capture_to_acquire_ms":(packet.acquired_at-packet.captured_at)*1000,
                    "processing_ms":info["processing_ms"],"latency_ms":info["latency_ms"],
                    "capture_fps":info["capture_fps"],"processing_fps":info["processing_fps"],
                    "encoder_queue_wait_ms":""}
                stage_csv_started=time.perf_counter()
                stage_log.write(stage_row)
                previous_stage_csv_ms=(time.perf_counter()-stage_csv_started)*1000
                last_info = info
                latencies.append(info["latency_ms"])
                for name, condition in (
                    ("normal", any(e["type"] == "tap" and len(e["key_candidates"].split("|")) == 1 for e in events)),
                    ("ambiguous", any(e["abstain_reason"] == "ambiguous_or_unstable_keys" for e in events)),
                    ("special", any(e["type"] == "unknown" for e in events))):
                    if name not in samples and condition and all(s["source_frame"] != packet.sequence for s in samples.values()):
                        cv2.imwrite(str(out/f"sample_{name}.png"), image)
                        samples[name] = {"source_frame": packet.sequence, "capture_timestamp": packet.captured_at,
                                         "source": "LIVE", "file": f"sample_{name}.png"}
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
            for log in diagnostic_logs:
                log.close()
            diagnostic_health={log.path.name:log.health() for log in diagnostic_logs}
            (out/"pf_diagnostic_health.json").write_text(
                json.dumps(diagnostic_health,indent=2)+"\n",encoding="utf-8")
            wall_elapsed = time.perf_counter()-wall_started
            simple_states=({state:sum(intent.state==state for intent in engine.simple_core.intents.intents.values())
                            for state in ("PENDING","FIRED","CANCELED","EXPIRED")}
                           if engine.simple_core is not None else {})
            result = {"mode": "assist", "predictor_mode": config["predictor"]["mode"],
                      "tap_core": live_cfg.get("tap_core","v6"),
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
                      "dropout_grace_ms": engine.dropout_grace_s*1000,
                      "dropout_min_y": engine.dropout_min_y,
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
                      "samples": samples, "stop_reason": stop_reason, "wall_elapsed_s": wall_elapsed,
                      "recording_async": recorder is not None,
                      "recording_encoded_frames": recorder.encoded if recorder else 0,
                      "recording_dropped_frames": recorder.slot.dropped if recorder else 0,
                      "recording_clean_source": recorder is not None,
                      "recording_nominal_fps": min(video_fps,60) if recorder else video_fps if args.record_overlay else None,
                      "recording_index": 'live_video_index.csv' if recorder else None,
                      "recording_error": str(recording_error) if recording_error else None,
                      "diagnostic_health": diagnostic_health,
                      "accuracy": "UNVERIFIED", "real_game_sessions_validated": 0}
            _summary(out, result)
            print(f"Saved {out}: {engine.frames} frames, {engine.events} events, {scheduler.sent_taps} taps, {scheduler.sent_holds} holds. Accuracy UNVERIFIED.", flush=True)
            if recording_error:
                raise RuntimeError(str(recording_error))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window-title",default=DEFAULT_WINDOW_TITLE,help="Game window title (default: %(default)s)")
    parser.add_argument("--list-windows", action="store_true")
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    parser.add_argument("--live-config", type=Path, default=Path("config/live_assist_v5.json"))
    parser.add_argument("--geometry", type=Path, default=Path("config/geometry_live_assist.json"))
    parser.add_argument("--out", type=Path, default=Path("output/assist"))
    parser.add_argument("--backend", choices=("auto", "dxcam", "mss"), default="auto")
    parser.add_argument("--record-overlay", action="store_true",
                        help="Record overlay and clean source asynchronously")
    parser.add_argument("--predictor", choices=("particle", "legacy"),
                        help="Ordinary Tap ETA path (default: config predictor mode, particle)")
    parser.add_argument("--tap-core", choices=("v6", "simple"),
                        help="Ordinary Tap control path (default: config, v6)")
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
