"""Causal, deterministic replay of indexed recordings through the live core."""
from __future__ import annotations

import csv
import json
import math
import time
from collections import Counter
from pathlib import Path

from .engine import Engine
from .model import Frame as EngineFrame, Geometry
from .recordings import Recording
from .scheduler import MockActuator, Scheduler


def _quantiles(values):
    values = sorted(float(v) for v in values if math.isfinite(float(v)))
    if not values:
        return {"count": 0, "p10": None, "p50": None, "p90": None, "p95": None, "p99": None, "max": None}
    def at(q):
        return values[round((len(values) - 1) * q)]
    return {"count": len(values), "p10": at(.1), "p50": at(.5), "p90": at(.9), "p95": at(.95),
            "p99": at(.99), "max": values[-1]}


def replay_session(recording, *, out_dir=None, geometry=None, geometry_path="config/geometry_live_assist.json",
                   calibration_path="config/reference_timing.json", cpu_ms=18., poll_ms=2., engine_factory=Engine):
    """Replay one Recording (or compatible fake) and return rows plus summary.

    Acquisition timestamps drive scheduling; each frame is admitted only when
    processing is idle, with a one-frame latest slot while busy. No human input
    events are read. The actuator is always in-memory.
    """
    if cpu_ms < 0 or poll_ms <= 0:
        raise ValueError("cpu_ms must be nonnegative and poll_ms positive")
    if geometry is None:
        geometry = Geometry(geometry_path, plane_width=360)
    cal_path = Path(calibration_path)
    calibration = cal_path if cal_path.is_file() else None
    run_id = getattr(recording, "run_id", Path(getattr(recording, "path", "recording")).name)
    start_timestamp=float(getattr(recording,'session',{}).get('start_timestamp',0.) or 0.)
    if not math.isfinite(start_timestamp):raise ValueError('Invalid recording clock origin')
    clock = [start_timestamp]
    def now(): return clock[0]
    actuator = MockActuator()
    focus_state = [True, True]
    events = []
    scheduler_ref = {}
    current_frame = {"captured": "", "source": ""}
    source_by_capture = {}
    scheduled = {}
    def record_event(event):
        event = dict(event)
        uid = str(event.get("uid", ""))
        sched = scheduler_ref.get("scheduler")
        valid_capture = sched.context[0] if sched and sched.context[0] is not None else current_frame["captured"]
        event["capture_timestamp"] = valid_capture
        event["source_frame"] = source_by_capture.get(valid_capture, current_frame["source"])
        action = None
        if sched and uid:
            action = next((a for a in list(sched.pending.values()) + list(sched.held.values())
                           if a.uid == uid), None)
        if action:
            scheduled[uid] = action
        action = action or scheduled.get(uid)
        event["scheduled_hit"] = event.get("scheduled_press", action.press_at if action else "")
        event["note_type"] = action.kind if action else event.get("kind", "")
        events.append(event)
    scheduler = Scheduler(actuator, clock=now,
                          focus_check=lambda: focus_state[0] and focus_state[1],
                          on_event=record_event)
    scheduler_ref["scheduler"] = scheduler
    engine = engine_factory(geometry, scheduler, calibration)
    frame_rows, decision_rows, action_rows = [], [], []
    track_hist = {}
    latencies, cpu_observed, observe_wall_ms, decide_wall_ms = [], [], [], []
    observe_reported_ms, decode_ms = [], []
    arm_attempted = False
    sequence = 0
    indexed_frames = 0
    overwritten_frames = 0
    step = poll_ms / 1000.

    def poll_until(target):
        while clock[0] + 1e-12 < target:
            clock[0] = min(target, clock[0] + step)
            scheduler.poll()

    def begin_process(rec_frame):
        nonlocal arm_attempted, sequence
        start = max(clock[0], rec_frame.acquired_timestamp)
        poll_until(start)
        clock[0] = start
        index_row = getattr(rec_frame, "index_row", {}) or {}
        def flag(name, default=True):
            value = getattr(rec_frame, name, None)
            if value is None:
                value = index_row.get(name, default)
            return str(value).strip().lower() not in {"0", "false", "no", "off", ""} if isinstance(value, str) else bool(value)
        focused, roi_valid = flag("focused"), flag("roi_valid")
        focus_state[:] = [focused, roi_valid]
        frame = EngineFrame(sequence=rec_frame.source_frame if rec_frame.source_frame is not None else rec_frame.video_frame,
                            image=rec_frame.image, captured_at=rec_frame.capture_timestamp,
                            acquired_at=rec_frame.acquired_timestamp, focused=focused, roi_valid=roi_valid,
                            run_id=rec_frame.run_id)
        sequence += 1
        current_frame["captured"] = frame.captured_at
        current_frame["source"] = frame.sequence
        source_by_capture[frame.captured_at] = frame.sequence
        observe_started = time.perf_counter()
        obs = engine.observe(frame)
        observe_wall_ms.append((time.perf_counter() - observe_started) * 1000.)
        observe_reported_ms.append(float(obs.get("cpu_ms", 0.)))
        finish = start + cpu_ms / 1000.
        return (rec_frame, frame, obs, finish)

    def finish_process(state):
        nonlocal arm_attempted
        rec_frame, frame, obs, finish = state
        poll_until(finish)
        clock[0] = finish
        decide_started = time.perf_counter()
        info, decisions = engine.decide(obs, processed_at=finish)
        decide_wall_ms.append((time.perf_counter() - decide_started) * 1000.)
        info["simulated_cpu_ms"] = cpu_ms
        frame_rows.append(info)
        latencies.append((finish - rec_frame.capture_timestamp) * 1000.)
        for row in decisions:
            row = dict(row, run_id=run_id, source_frame=frame.sequence)
            decision_rows.append(row)
            uid = str(row.get("note_uid", ""))
            hist = track_hist.setdefault(uid, {"run_id": run_id, "event_id": uid, "note_type": row.get("kind", ""),
                                               "color": row.get("color", ""), "key": row.get("key", ""),
                                               "key_candidates": row.get("keys", ""), "samples": []})
            hist["key"] = row.get("key", hist["key"])
            current = engine.tracker.notes.get(uid)
            if current and current.head and current.head[-1][0] == frame.captured_at:
                t, _, lo, hi = current.head[-1][:4]
                bbox = row.get("bbox", "")
                leading_y = (float(bbox[1]) + float(bbox[3])) if isinstance(bbox, (list, tuple)) else current.head[-1][1]
                hist["samples"].append({"capture_timestamp": t, "source_frame": frame.sequence, "y": leading_y,
                                         "span": [lo, hi], "bbox": bbox})
        if not arm_attempted and obs.get("playing") and frame.focused and frame.roi_valid:
            arm_attempted = True
            scheduler.toggle()
            scheduler.poll()
        scheduler.poll()

    # We stream decoded frames. A queued frame is overwritten on every arrival
    # during simulated processing, exactly like a one-slot capture mailbox.
    active = None
    latest = None
    iterator = iter(recording.iter_frames())
    while True:
        decode_start = time.perf_counter()
        try:
            rec_frame = next(iterator)
        except StopIteration:
            break
        decode_ms.append((time.perf_counter() - decode_start) * 1000.)
        indexed_frames += 1
        acquired = rec_frame.acquired_timestamp
        while active is not None and active[3] <= acquired + 1e-12:
            finish_process(active)
            active = None
            if latest is not None:
                queued, latest = latest, None
                active = begin_process(queued)
        if active is None:
            active = begin_process(rec_frame)
        else:
            if latest is not None:
                overwritten_frames += 1
            latest = rec_frame

    # Drain a final latest slot if present and poll through the final action tail.
    while active is not None:
        finish_process(active)
        active = None
        if latest is not None:
            queued, latest = latest, None
            active = begin_process(queued)
    if frame_rows:
        poll_until(clock[0] + .25)
    scheduler.disarm("replay_end")
    for ev in events:
        uid = str(ev.get("uid", ""))
        event = ev.get("event", "")
        action_name = {"pressed": "key_down", "released": "key_up"}.get(event, event)
        action_rows.append({"run_id": run_id, "event_id": uid or f"{run_id}:system:{len(action_rows)+1}",
                            "event_sequence": ev.get("event_sequence", ""),
                            "action": action_name, "key": ev.get("key", ""),
                            "capture_timestamp": ev.get("capture_timestamp", ""),
                            "source_frame": ev.get("source_frame", ""),
                            "timestamp": ev.get("at", ""), "reason": ev.get("reason", ""),
                            "scheduled_hit": ev.get("scheduled_hit", ""),
                            "note_type": ev.get("note_type", ""), "note_uid": uid,
                            "track_uid": uid})
        action_rows[-1]['canonical_uid']=ev.get('canonical_uid','')
    tracks = []
    for hist in track_hist.values():
        if not hist["samples"]:
            continue
        tracks.append({"run_id": run_id, "note_uid": hist["event_id"], "tracker": "rebuild",
                       "track_id": hist["event_id"], "kind": hist["note_type"],
                       "color": hist["color"], "key_candidates": hist["key_candidates"],
                       "first_observed": hist["samples"][0]["capture_timestamp"],
                       "last_observed": hist["samples"][-1]["capture_timestamp"],
                       "history": json.dumps(hist["samples"], separators=(",", ":"))})
    normal_releases = {"tap_end", "tail_release", "observed_tail_crossing"}
    safety_releases = Counter(ev.get("reason", "") for ev in events
                              if ev.get("event") == "released" and ev.get("reason")
                              and ev.get("reason") not in normal_releases)
    actuator_downs = sum(kind == "down" for kind, _ in actuator.calls)
    actuator_ups = sum(kind == "up" for kind, _ in actuator.calls)
    summary = {"run_id": run_id, "frames_processed": len(frame_rows), "decision_rows": len(decision_rows),
               "indexed_frames": indexed_frames, "dropped_frames": indexed_frames-len(frame_rows),
               "latest_slot_overwrites": overwritten_frames,
               "simulated_cpu_ms_per_frame": cpu_ms, "poll_ms": poll_ms,
               "cpu_observed_ms": _quantiles([a + b for a, b in zip(observe_wall_ms, decide_wall_ms)]),
               "observe_wall_ms": _quantiles(observe_wall_ms), "decide_wall_ms": _quantiles(decide_wall_ms),
               "observe_reported_cpu_ms": _quantiles(observe_reported_ms),
               "decode_wall_ms": _quantiles(decode_ms),
               "cpu_observed_excluding_decode_ms": _quantiles([a + b for a, b in zip(observe_wall_ms, decide_wall_ms)]),
               "simulation_latency_ms": _quantiles(latencies),
               "timing_calibration": str(cal_path) if calibration else None,
               "input_calibration_enabled": calibration is not None,
               "missing_calibration_reason": "config/reference_timing.json unavailable; scheduler input predictions disabled" if calibration is None else "",
               "scheduler_events": len(action_rows), "scheduler_actions": len(action_rows),
               "actual_actuator_key_downs": actuator_downs,
               "actual_actuator_key_ups": actuator_ups,
               "safety_release_reasons": dict(safety_releases), "game_accuracy": "UNVERIFIED",
               "manual_arm_attempted": arm_attempted}
    result = {"simulated_actions": action_rows, "track_summary": tracks,
              "frame_decisions": decision_rows, "frame_summary": frame_rows, "summary": summary}
    if out_dir is not None:
        write_replay(result, out_dir)
    return result


def _write_csv(path, rows, fields):
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def write_replay(result, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    _write_csv(out / "simulated_actions.csv", result["simulated_actions"],
               ["run_id", "event_id", "event_sequence", "action", "key", "capture_timestamp", "source_frame", "timestamp", "reason", "scheduled_hit", "note_type", "note_uid", "track_uid","canonical_uid"])
    _write_csv(out / "track_summary.csv", result["track_summary"],
               ["run_id", "note_uid", "tracker", "track_id", "kind", "color", "key_candidates", "first_observed", "last_observed", "history"])
    _write_csv(out / "frame_decisions.csv", result["frame_decisions"],
               ["run_id", "source_frame", "sequence", "capture_timestamp", "note_uid", "kind", "color", "bbox", "keys", "state", "reason", "key", "crossing_at", "press_at", "release_at", "uncertainty", "tail_uid", "tail_observations",
                "tail_last_observation","tail_bbox","tail_y","tail_prediction_reason","tail_crossing_at","tail_uncertainty","release_update_reason","aliases","detection_kind","detection_color","detection_component","origin_y","full_head_observations","tail_detection_kind","tail_detection_color","tail_terminal_owner","last_full_tap_at","tail_last_kind"])
    (out / "replay_summary.json").write_text(json.dumps(result["summary"], indent=2), encoding="utf-8")
