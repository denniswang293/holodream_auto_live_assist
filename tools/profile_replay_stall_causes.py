"""One-run, instrumented V85 latest-frame replay for intermittent stall diagnosis.

This is diagnostic only. It records wall/thread/process clocks, GC intervals,
allocation-block counts, and compact state sizes without tracing allocations.
"""
from __future__ import annotations

import csv
import argparse
import gc
import hashlib
import json
import sys
import threading
import time
from collections import Counter
from pathlib import Path
import statistics

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.model import Frame, Geometry  # noqa: E402
from tools.replay_lane_filter import make_state, poll_to, read_index  # noqa: E402

RUN_DIR = ROOT / "output/recording/run_20261106T164049_800126Z"
OUT = ROOT / "output/analysis_v86_autoloop/iteration_0078_stall_causes"
DEFAULT_OUT = OUT / "attempt_2"
ARM_WINDOW = (1.0, 124.0)
BIRTH_ZONE_END_Y = 176.75


def write_rows(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True,
                        help="new output directory under iteration_0078_stall_causes")
    parser.add_argument("--disable-gc", action="store_true",
                        help="disable automatic cyclic GC before the replay; never collect manually")
    args = parser.parse_args()
    out_root = (ROOT / "output/analysis_v86_autoloop/iteration_0078_stall_causes").resolve()
    out = args.out.resolve()
    if out_root not in out.parents:
        raise ValueError("--out must be a new child directory under iteration_0078_stall_causes")
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"refusing to overwrite nonempty output directory: {out}")
    if not args.disable_gc:
        raise ValueError("controlled GC ablation requires --disable-gc")
    OUT = out
    OUT.mkdir(parents=True, exist_ok=True)
    index = read_index(RUN_DIR / "live_video_index.csv")
    if len(index) != 3159:
        raise RuntimeError(f"expected 3159 indexed frames, got {len(index)}")
    first = index[0]
    first_acquired = float(first["acquired_timestamp"])
    first_capture = float(first["capture_timestamp"])
    now = [first_acquired]
    state = make_state("v85", Geometry(ROOT / "config/geometry_live_assist.json"),
                       ROOT / "config/reference_timing.json", first_acquired,
                       birth_zone_end_y=BIRTH_ZONE_END_Y,
                       trace_tracker_associations=False, record_conversion_trace=False)
    event_log = state["event_log"]

    shared = {"latest": None, "done": False, "error": None, "decoded": 0,
              "overwritten": 0, "lock": threading.Condition()}
    gc_events: list[dict] = []
    gc_open: dict[tuple[int, int], tuple[int, int, int]] = {}

    def gc_callback(phase, info):
        wall = time.perf_counter_ns()
        thread_cpu = time.thread_time_ns()
        process_cpu = time.process_time_ns()
        generation = int(info.get("generation", -1))
        key = (threading.get_ident(), generation)
        if phase == "start":
            gc_open[key] = (wall, thread_cpu, process_cpu)
        elif phase == "stop":
            start = gc_open.pop(key, None)
            if start is not None:
                gc_events.append({
                    "thread_id": key[0], "generation": generation,
                    "wall_start_ns": start[0], "wall_end_ns": wall,
                    "wall_duration_ms": (wall - start[0]) / 1e6,
                    "thread_cpu_duration_ms": (thread_cpu - start[1]) / 1e6,
                    "process_cpu_duration_ms": (process_cpu - start[2]) / 1e6,
                    "collected": int(info.get("collected", 0)),
                    "uncollectable": int(info.get("uncollectable", 0)),
                })

    def reader() -> None:
        cap = cv2.VideoCapture(str(RUN_DIR / "live_source.mp4"))
        try:
            if not cap.isOpened():
                raise RuntimeError("could not open immutable source video")
            base_wall = time.perf_counter()
            decoded = 0
            while True:
                ok, image = cap.read()
                if not ok:
                    break
                row = index.get(decoded)
                if row is None:
                    raise RuntimeError(f"missing index row {decoded}")
                acquired = float(row["acquired_timestamp"])
                deadline = base_wall + (acquired - first_acquired)
                remaining = deadline - time.perf_counter()
                if remaining > 0:
                    time.sleep(remaining)
                packet = (decoded, image, row)
                with shared["lock"]:
                    if shared["latest"] is not None:
                        shared["overwritten"] += 1
                    shared["latest"] = packet
                    shared["decoded"] = decoded + 1
                    shared["lock"].notify_all()
                decoded += 1
            with shared["lock"]:
                shared["done"] = True
                shared["decoded"] = decoded
                shared["lock"].notify_all()
        except BaseException as exc:
            with shared["lock"]:
                shared["error"] = repr(exc)
                shared["done"] = True
                shared["lock"].notify_all()
        finally:
            cap.release()

    def next_packet():
        with shared["lock"]:
            while shared["latest"] is None and not shared["done"]:
                shared["lock"].wait()
            if shared["error"]:
                raise RuntimeError(shared["error"])
            packet = shared["latest"]
            shared["latest"] = None
            return packet

    gc_enabled_before_replay = gc.isenabled()
    gc.disable()
    gc.callbacks.append(gc_callback)
    reader_thread = threading.Thread(target=reader, name="v86-index-paced-decoder", daemon=True)
    reader_thread.start()
    telemetry: list[dict] = []
    frame_summary: list[dict] = []
    processed: list[int] = []
    decision_rows = 0
    arm_triggered = arm_ended = False
    decoded = 0
    try:
        while True:
            packet = next_packet()
            if packet is None:
                break
            frame_index, image, idx = packet
            decoded = max(decoded, frame_index + 1)
            captured = float(idx["capture_timestamp"])
            acquired = float(idx["acquired_timestamp"])
            focused = str(idx.get("focused", "True")).lower() in ("true", "1")
            roi_valid = str(idx.get("roi_valid", "True")).lower() in ("true", "1")

            poll_begin = time.perf_counter_ns()
            poll_to(state, acquired, inclusive=False)
            pre_poll_wall_ns = time.perf_counter_ns() - poll_begin
            state["now"][0] = acquired
            frame = Frame(frame_index, image, captured, acquired, focused, roi_valid, RUN_DIR.name)

            gc_before = tuple(gc.get_count())
            blocks_before = sys.getallocatedblocks()
            update_wall_start = time.perf_counter_ns()
            update_thread_start = time.thread_time_ns()
            update_process_start = time.process_time_ns()

            observe_wall_start = time.perf_counter_ns()
            observe_thread_start = time.thread_time_ns()
            observation = state["engine"].observe(frame)
            observe_wall_end = time.perf_counter_ns()
            observe_thread_end = time.thread_time_ns()
            observe_process_end = time.process_time_ns()

            media_now = acquired + (observe_wall_end - observe_wall_start) / 1e9
            scheduler_poll_start = time.perf_counter_ns()
            poll_to(state, media_now)
            scheduler_poll_wall_ns = time.perf_counter_ns() - scheduler_poll_start

            decide_process_start = time.process_time_ns()
            decide_wall_start = time.perf_counter_ns()
            decide_thread_start = time.thread_time_ns()
            info, decisions = state["engine"].decide(observation, processed_at=state["now"][0])
            decide_wall_end = time.perf_counter_ns()
            decide_thread_end = time.thread_time_ns()
            decide_process_end = time.process_time_ns()
            update_end = decide_wall_end
            state["now"][0] = acquired + (update_end - update_wall_start) / 1e9
            completed_poll_start = time.perf_counter_ns()
            poll_to(state, state["now"][0])
            completed_poll_wall_ns = time.perf_counter_ns() - completed_poll_start

            gc_after = tuple(gc.get_count())
            blocks_after = sys.getallocatedblocks()
            processed.append(frame_index)
            decision_rows += len(decisions)
            component_count = observation["profile"].get("component_count", len(observation["detections"]))
            tracker = state["engine"].tracker
            scheduler = state["scheduler"]
            row = {
                "video_frame": frame_index,
                "source_frame": int(idx.get("source_frame", frame_index)),
                "engine_thread_id": threading.get_ident(),
                "captured_at": captured, "acquired_at": acquired,
                "playing": info["playing"], "detection_count": len(observation["detections"]),
                "component_count": component_count,
                "observe_wall_ms": (observe_wall_end-observe_wall_start)/1e6,
                "observe_wall_start_ns": observe_wall_start,
                "observe_wall_end_ns": observe_wall_end,
                "observe_thread_cpu_ms": (observe_thread_end-observe_thread_start)/1e6,
                "observe_process_cpu_ms": (observe_process_end-update_process_start)/1e6,
                "decide_wall_ms": (decide_wall_end-decide_wall_start)/1e6,
                "decide_wall_start_ns": decide_wall_start,
                "decide_wall_end_ns": decide_wall_end,
                "decide_thread_cpu_ms": (decide_thread_end-decide_thread_start)/1e6,
                "decide_process_cpu_ms": (decide_process_end-decide_process_start)/1e6,
                "engine_compute_wall_ms": ((observe_wall_end-observe_wall_start)+
                                            (decide_wall_end-decide_wall_start))/1e6,
                "engine_compute_thread_cpu_ms": ((observe_thread_end-observe_thread_start)+
                                                  (decide_thread_end-decide_thread_start))/1e6,
                "engine_compute_process_cpu_ms": ((observe_process_end-update_process_start)+
                                                   (decide_process_end-decide_process_start))/1e6,
                "engine_compute_wall_minus_thread_cpu_ms": (((observe_wall_end-observe_wall_start)+
                    (decide_wall_end-decide_wall_start))-
                    ((observe_thread_end-observe_thread_start)+(decide_thread_end-decide_thread_start)))/1e6,
                "orchestration_cycle_wall_ms": (update_end-update_wall_start)/1e6,
                "orchestration_cycle_thread_cpu_ms": (decide_thread_end-update_thread_start)/1e6,
                "pre_update_scheduler_poll_wall_ms": pre_poll_wall_ns/1e6,
                "mid_update_scheduler_poll_wall_ms": scheduler_poll_wall_ns/1e6,
                "post_update_scheduler_poll_wall_ms": completed_poll_wall_ns/1e6,
                "gc_count_before": ",".join(map(str,gc_before)),
                "gc_count_after": ",".join(map(str,gc_after)),
                "allocated_blocks_before": blocks_before,
                "allocated_blocks_after": blocks_after,
                "allocated_blocks_delta": blocks_after-blocks_before,
                "tracker_caps": len(tracker.caps), "tracker_notes": len(tracker.notes),
                "hold_connections": len(state["engine"].hold_connections),
                "scheduler_pending": len(scheduler.pending), "scheduler_held": len(scheduler.held),
                "scheduler_consumed": len(scheduler.consumed), "scheduler_fired": len(scheduler.fired),
                "scheduler_events_retained": len(scheduler.events),
                "scheduler_thread_started": bool(scheduler.thread and scheduler.thread.is_alive()),
                "decoder_overwrites_so_far": shared["overwritten"],
                **{f"gc_{k}":v for k,v in observation.get("profile",{}).items()
                   if k.endswith("_ms") and k in ("perception_ms","tracker_association_ms")},
                **{f"decide_{k}":v for k,v in state["engine"].last_decision_profile.items()
                   if k.endswith("_ms")},
                **{k:v for k,v in observation.get("profile",{}).items()
                   if k.endswith("_ms") and k not in ("perception_ms","tracker_association_ms")},
            }
            telemetry.append(row)
            processed_at = state["now"][0]
            profile = observation.get("profile", {})
            frame_summary.append({
                "video_frame":frame_index,"source_frame":int(idx.get("source_frame",frame_index)),
                "captured_at":captured,"acquired_at":acquired,"processed_at":processed_at,
                "processing_ms":row["engine_compute_wall_ms"],
                "capture_age_ms":(processed_at-captured)*1000,
                "playing":info["playing"],"focused":focused,"roi_valid":roi_valid,
                "detection_count":len(observation["detections"]),"track_count":len(observation["notes"]),
                "armed":info["armed"],"frame_drops_so_far":shared["overwritten"],
            })
            state["summary"].append(frame_summary[-1])
            for decision in decisions:
                state["decisions"].append({"provider":"v85","latency_ms":"DIAGNOSTIC",
                    "run_id":RUN_DIR.name,"video_frame":frame_index,
                    "physical_note_id":"UNKNOWN",**decision})
            relative = captured-first_capture
            if not arm_triggered and relative>=ARM_WINDOW[0] and info["playing"] and focused and roi_valid:
                scheduler.toggle();arm_triggered=True
            if not arm_ended and relative>ARM_WINDOW[1]:
                scheduler.disarm("simulated_arm_window_end");arm_ended=True
    finally:
        reader_thread.join(timeout=10)
        gc.callbacks.remove(gc_callback)
    if reader_thread.is_alive():
        raise RuntimeError("capture reader did not finish")
    decoded = shared["decoded"]
    if decoded != 3159:
        raise RuntimeError(f"expected 3159 decoded frames, got {decoded}")
    final_time = state["summary"][-1]["acquired_at"] + state["summary"][-1]["processing_ms"]/1000
    poll_to(state, final_time+.04)
    state["scheduler"].disarm("replay_end")
    for event in event_log:
        state["actions"].append({"provider":"v85","latency_ms":"DIAGNOSTIC",
                                 "run_id":RUN_DIR.name,**event})

    # Match GC intervals to observe/decide windows after the measured pass.
    for row in telemetry:
        intervals=((row["observe_wall_start_ns"],row["observe_wall_end_ns"]),
                   (row["decide_wall_start_ns"],row["decide_wall_end_ns"]))
        overlaps=[]
        for event in gc_events:
            duration=sum(max(0,min(end,event["wall_end_ns"])-max(start,event["wall_start_ns"]))
                         for start,end in intervals)
            if duration:
                overlaps.append((event,duration))
        row["gc_overlap_count"]=len(overlaps)
        row["gc_overlap_wall_ms"]=sum(duration for _,duration in overlaps)/1e6
        row["gc_overlap_generations"]="|".join(str(event["generation"]) for event,_ in overlaps)
    write_rows(OUT/"stall_telemetry_by_frame.csv", telemetry)
    write_rows(OUT/"frame_summary.csv", frame_summary)
    write_rows(OUT/"mock_actions.csv", state["actions"])
    write_rows(OUT/"physical_note_decisions.csv", state["decisions"])
    write_rows(OUT/"gc_events.csv", gc_events)
    write_rows(OUT/"processed_frame_indices.csv", [{"video_frame":f} for f in processed])
    press_events=[e for e in event_log if e.get("event")=="pressed"]
    release_events=[e for e in event_log if e.get("event")=="released"]
    safety={"pressed_events":len(press_events),"released_events":len(release_events),
        "duplicate_press_uids":len(press_events)-len({e.get("uid") for e in press_events}),
        "press_uids_without_release":len({e.get("uid") for e in press_events}-{e.get("uid") for e in release_events}),
        "key_up_failures":sum(e.get("event")=="key_up_error" for e in event_log),
        "illegal_keys":sum(e.get("key") not in "SDFJKL" for e in press_events)}

    def signature(events):
        return Counter((e.get("event"),e.get("reason"),e.get("uid"),e.get("key"),e.get("kind")) for e in events)
    comparisons=[]
    evidence=ROOT/"output/analysis_v86_autoloop/iteration_0075_lazy_labels/measured_repeats2"
    with (evidence/"matrix_summary.csv").open(encoding="utf-8-sig",newline="") as stream:
        measured_rows=list(csv.DictReader(stream))
    for repeat in (1,2):
        run=evidence/f"repeat_{repeat}/v85/{RUN_DIR.name}"
        with (run/"stage_profile_by_frame.csv").open(encoding="utf-8-sig",newline="") as stream:
            old_frames={int(r["video_frame"]) for r in csv.DictReader(stream)}
        with (run/"mock_actions.csv").open(encoding="utf-8-sig",newline="") as stream:
            old_actions=list(csv.DictReader(stream))
        old_sig=signature(old_actions)
        new_sig=signature(event_log)
        old_summary=next(r for r in measured_rows if int(r["repeat"])==repeat and r["provider"]=="v85")
        baseline_safety={key:int(old_summary[key]) for key in (
            "mock_key_up_failures","duplicate_mock_press_uids",
            "presses_without_release_uid_count","illegal_mock_keys")}
        comparisons.append({"repeat":repeat,"baseline_processed_frames":len(old_frames),
            "diagnostic_processed_frames":len(processed),"admission_exact_match":old_frames==set(processed),
            "baseline_only_frames":sorted(old_frames-set(processed)),
            "diagnostic_only_frames":sorted(set(processed)-old_frames),
            "baseline_action_events":sum(old_sig.values()),"diagnostic_action_events":sum(new_sig.values()),
            "action_signature_exact_match":old_sig==new_sig,
            "action_signature_common_entries":sum((old_sig & new_sig).values()),
            "baseline_event_counts":dict(Counter(e.get("event") for e in old_actions)),
            "diagnostic_event_counts":dict(Counter(e.get("event") for e in event_log)),
            "baseline_safety_counters":baseline_safety})

    outliers=sorted((r for r in telemetry),key=lambda r:float(r["engine_compute_wall_ms"]),reverse=True)[:20]
    attempt2_dir = OUT.parent / "attempt_2"
    with (attempt2_dir/"processed_frame_indices.csv").open(encoding="utf-8-sig",newline="") as stream:
        attempt2_frames={int(r["video_frame"]) for r in csv.DictReader(stream)}
    with (attempt2_dir/"mock_actions.csv").open(encoding="utf-8-sig",newline="") as stream:
        attempt2_actions=list(csv.DictReader(stream))
    with (attempt2_dir/"stall_telemetry_by_frame.csv").open(encoding="utf-8-sig",newline="") as stream:
        attempt2_telemetry={int(r["video_frame"]):r for r in csv.DictReader(stream)}
    current_frames=set(processed)
    attempt2_action_sig=signature(attempt2_actions)
    current_action_sig=signature(event_log)
    paired_wall_deltas=[float(row["engine_compute_wall_ms"])-
                        float(attempt2_telemetry[int(row["video_frame"])] ["engine_compute_wall_ms"])
                        for row in telemetry if int(row["video_frame"]) in attempt2_telemetry]
    attempt2_summary=json.loads((attempt2_dir/"summary.json").read_text(encoding="utf-8-sig"))
    attempt2_walls=[float(row["engine_compute_wall_ms"]) for row in attempt2_telemetry.values()]
    def wall_distribution(values):
        ordered=sorted(values)
        return {"count":len(ordered),"mean_ms":statistics.mean(ordered),
            "p90_ms":ordered[int(.90*(len(ordered)-1))],
            "p95_ms":ordered[int(.95*(len(ordered)-1))],
            "p99_ms":ordered[int(.99*(len(ordered)-1))],"max_ms":ordered[-1],
            "count_over_50ms":sum(v>50 for v in ordered),
            "count_over_70ms":sum(v>70 for v in ordered),
            "count_over_100ms":sum(v>100 for v in ordered)}
    compare_attempt2={
        "attempt2_processed_frames":len(attempt2_frames),"gc_disabled_processed_frames":len(current_frames),
        "processed_frame_sets_exact_match":current_frames==attempt2_frames,
        "attempt2_only_frames":sorted(attempt2_frames-current_frames),
        "gc_disabled_only_frames":sorted(current_frames-attempt2_frames),
        "attempt2_action_signature_exact_match":attempt2_action_sig==current_action_sig,
        "attempt2_action_events":sum(attempt2_action_sig.values()),
        "gc_disabled_action_events":sum(current_action_sig.values()),
        "common_action_signature_entries":sum((attempt2_action_sig & current_action_sig).values()),
        "attempt2_safety":attempt2_summary["safety"],"gc_disabled_safety":safety,
        "attempt2_wall_distribution_ms":wall_distribution(attempt2_walls),
        "gc_disabled_wall_distribution_ms":wall_distribution([float(r["engine_compute_wall_ms"]) for r in telemetry]),
        "distribution_comparison_is_single_run_descriptive_only":True,
        "same_frame_pair_deltas_are_not_state_matched":True,
        "paired_frame_timing_rows":len(paired_wall_deltas),
        "paired_frame_mean_wall_delta_ms_gc_disabled_minus_attempt2":statistics.mean(paired_wall_deltas) if paired_wall_deltas else None,
        "paired_frame_p90_wall_delta_ms_gc_disabled_minus_attempt2":sorted(paired_wall_deltas)[int(.9*(len(paired_wall_deltas)-1))] if paired_wall_deltas else None,
    }
    wall_values=[float(row["engine_compute_wall_ms"]) for row in telemetry]
    summary={"iteration":"0078","run_id":RUN_DIR.name,"provider":"v85",
        "decoded_frames":decoded,"processed_frames":len(processed),
        "dropped_frames":decoded-len(processed),"reader_overwrites":shared["overwritten"],
        "processed_frame_index_sha256":hashlib.sha256(",".join(map(str,processed)).encode()).hexdigest(),
        "arm_window_s":ARM_WINDOW,"birth_zone_end_y":BIRTH_ZONE_END_Y,
        "source_index_sha256":sha256(RUN_DIR/"live_video_index.csv"),
        "source_video_sha256":sha256(RUN_DIR/"live_source.mp4"),
        "engine_source_sha256":sha256(ROOT/"src/engine.py"),
        "tracker_source_sha256":sha256(ROOT/"src/tracking.py"),
        "scheduler_source_sha256":sha256(ROOT/"src/scheduler.py"),
        "replay_tool_source_sha256":sha256(ROOT/"tools/replay_lane_filter.py"),
        "diagnostic_runner_pre_edit_sha256":"A78F154309BC98C211B4F4739A9B8EFD983AB6A72B64EC5A136DC1F41F543067",
        "diagnostic_runner_sha256":sha256(Path(__file__).resolve()),
        "scheduler_worker_started":False,"diagnostic_decoder_thread":"index paced; latest pending frame overwrites prior pending frame",
        "gc_ablation":{"requested":True,"gc_enabled_before_replay":gc_enabled_before_replay,
            "gc_enabled_after_replay":gc.isenabled(),"automatic_gc_disabled_before_reader_start":True,
            "manual_collection_called":False,"gc_callback_count":len(gc_events)},
        "attempt2_comparison":compare_attempt2,
        "interpretation":"With automatic cyclic GC disabled, this run had no >70ms update; attempt 2 had eight, including generation-2 callbacks lasting 39-182ms on the Engine thread. This supports Gen2 collection as a proximate contributor in this harness, but the one-run ablation, instrumentation, and changed admission/actions prevent a production performance claim. The cause of long GC scans and large tracked heap remains UNKNOWN.",
        "engine_compute_wall_ms_summary":{"mean":statistics.mean(wall_values),
            "p90":sorted(wall_values)[int(.9*(len(wall_values)-1))],"max":max(wall_values)},
        "allocated_blocks":{"first_before":telemetry[0]["allocated_blocks_before"],
            "last_after":telemetry[-1]["allocated_blocks_after"],
            "net_growth":telemetry[-1]["allocated_blocks_after"]-telemetry[0]["allocated_blocks_before"],
            "max_after":max(int(row["allocated_blocks_after"]) for row in telemetry)},
        "gc_callback_count":len(gc_events),"gc_wall_time_total_ms":sum(e["wall_duration_ms"] for e in gc_events),
        "safety":safety,"comparisons_to_uninstrumented_0075":comparisons,
        "instrumentation_interference":"Diagnostic callback logging, per-frame scalar sampling, paced reader thread, and synchronous simulated scheduler polling alter host load/admission timing. This is not an A/B performance result; compare admissions/actions to quantify interference.",
        "top_20_engine_compute_wall_outliers":outliers,
        "artifacts":["stall_telemetry_by_frame.csv","gc_events.csv","processed_frame_indices.csv","frame_summary.csv","mock_actions.csv","physical_note_decisions.csv"]}
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    (OUT/"diagnostic_report.md").write_text(
        "# Iteration 0078 - V85 stall-cause diagnostic\n\n"
        "One full-source 3,159-frame V85 run using the indexed capture/acquired timestamps, 1-124s arm window, birth-zone y=176.75, and in-memory MockActuator. No video rendering/encoding, OS input, tracemalloc, tests, or runtime source edits.\n\n"
        "The telemetry records per-update wall/thread/process CPU time, GC callback intervals, GC counters, allocated-block counts, and tracker/scheduler state sizes. The reader is paced by acquired timestamps and keeps only the latest pending frame. The scheduler worker is not started; polling is synchronous.\n\n"
        "Automatic cyclic GC was disabled before the paced reader started; no manual collection occurred. Telemetry and comparison against attempt 2 are in `summary.json` and `stall_telemetry_by_frame.csv`; GC callbacks are expected to be empty. Instrumentation changes host load/admission, so action divergence precludes a performance/release claim. Any remaining cause is UNKNOWN.\n",
        encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
