"""Replay one recorded Assist source video through LiveEngine with MockActuator only."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from types import SimpleNamespace
import time

import cv2

from src.geometry import CalibratedGeometry
from src.live_capture import CapturedFrame
from src.live_engine import LiveEngine,draw_live_overlay
from src.live_input import MockActuator, TapScheduler
from src.live import TAP_DECISION_FIELDS


STAGE_FIELDS=["frame","capture_timestamp","gameplay_state","candidate_count","tracked_count",
 "acquire_queue_wait_ms","normalization_ms","state_detector_ms","note_detector_ms","tracker_matching_ms",
 "unknown_association_ms","pf_prediction_update_ms","decision_ms","scheduler_update_ms","diagnostic_write_ms","overlay_ms",
 "processing_ms","latency_ms","capture_fps","processing_fps","encoder_queue_wait_ms"]


class ReplayClock:
    def __init__(self):
        self.value=0.0; self.focused=True
    def reset(self,value,focused):
        """Use the run's recorded decision timestamp, independent of replay speed."""
        self.value=float(value); self.focused=focused
    def advance(self,value):
        self.value=max(self.value,float(value))
    @property
    def now(self): return self()
    def __call__(self): return self.value


def read_csv(path):
    with path.open(newline="",encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def write_csv(path,rows,fields):
    with path.open("w",newline="",encoding="utf-8-sig") as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("run_dir",type=Path)
    args=parser.parse_args()
    run_dir=args.run_dir.resolve()
    run=json.loads((run_dir/"live_run.json").read_text(encoding="utf-8-sig"))
    source=run_dir/"live_source.mp4"
    if not source.exists(): raise SystemExit("live_source.mp4 is missing")
    indexes=read_csv(run_dir/"live_video_index.csv")
    original_frames={int(row["frame"]):row for row in read_csv(run_dir/"live_frames.csv")}
    config=run["config"]
    geometry=CalibratedGeometry(run["geometry_snapshot"])
    clock=ReplayClock()
    actuator=MockActuator()
    action_rows=[]
    engine_holder={}
    def log_action(row):
        action_rows.append(row)
        if "engine" in engine_holder:
            engine_holder["engine"].record_scheduler_action(row)
    live=config.get("live",{})
    scheduler=TapScheduler("assist",actuator,clock=lambda:clock.now,
        focus_check=lambda:clock.focused,modifiers_check=lambda:False,
        on_log=log_action,max_age=live.get("max_frame_age_ms",60)/1000,
        max_lateness=live.get("max_input_lateness_ms",15)/1000,
        duration=config.get("timing",{}).get("tap_duration_ms",25)/1000,
        max_hold_s=live.get("hold_visual",{}).get("max_hold_s",6.0),
        max_uncertainty=live.get("speculative_taps",{}).get("max_uncertainty_s",.04)
            if live.get("speculative_taps",{}).get("enabled") else .04)
    engine=LiveEngine(config,geometry,scheduler,clock=lambda:clock.now)
    engine_holder["engine"]=engine
    trace_rows=[]
    engine.diagnostic_sink=lambda name,row: trace_rows.append((name,row))
    session=next((row["event_id"].rsplit(":",1)[0] for row in read_csv(run_dir/"live_events.csv")
                  if row.get("event_id")),"mockreplay")
    engine.session_id=session
    current_state="UNCERTAIN"
    engine.gate.update=lambda image:current_state
    arm_generation=0
    capture=cv2.VideoCapture(str(source))
    if not capture.isOpened(): raise SystemExit("Unable to open live_source.mp4")
    stages=[]; replay_events=[]; video_frame=0; started=time.perf_counter()
    try:
        for index in indexes:
            ok,image=capture.read()
            if not ok: break
            seq=int(index["source_frame"])
            original=original_frames.get(seq,{})
            timestamp=float(index["capture_timestamp"])
            acquired=float(original.get("acquired_timestamp") or index["processing_timestamp"])
            processed=float(original.get("processing_timestamp") or index["processing_timestamp"])
            focused=original.get("focused","False").lower()=="true"
            clock.reset(processed,focused)
            current_state=index.get("gameplay_state",original.get("gameplay_state","UNCERTAIN"))
            should_arm=original.get("input_armed","False").lower()=="true"
            if should_arm and not scheduler.armed:
                scheduler.armed=True; arm_generation+=1; scheduler.arm_generation=arm_generation
            elif not should_arm and scheduler.armed:
                scheduler.disarm("recorded_input_disabled")
            roi_valid=original.get("roi_status") not in ("BLOCKED","STALE")
            frame=CapturedFrame(seq,image,timestamp,acquired,"recorded_capture_index")
            process_wall_started=time.perf_counter()
            work,tracks,events,info=engine.process(frame,clock.focused,roi_valid)
            process_wall_ms=(time.perf_counter()-process_wall_started)*1000
            replay_events.extend(events)
            overlay_started=time.perf_counter()
            draw_live_overlay(work,tracks,info,engine,int(original.get("dropped_total",0) or 0))
            overlay_ms=(time.perf_counter()-overlay_started)*1000
            stages.append({"frame":seq,"capture_timestamp":timestamp,"gameplay_state":info["gameplay_state"],
                "candidate_count":info["candidate_count"],"tracked_count":info["tracked_count"],
                "acquire_queue_wait_ms":info["acquire_queue_wait_ms"],
                "normalization_ms":info["normalization_ms"],"state_detector_ms":info["state_detector_ms"],
                "note_detector_ms":info["note_detector_ms"],"tracker_matching_ms":info["tracker_matching_ms"],
                "unknown_association_ms":info["unknown_association_ms"],
                "pf_prediction_update_ms":info["pf_prediction_update_ms"],"decision_ms":info["decision_ms"],
                "scheduler_update_ms":info["scheduler_update_ms"],
                "diagnostic_write_ms":info["diagnostic_write_ms"],"overlay_ms":overlay_ms,
                "processing_ms":process_wall_ms,"latency_ms":info["latency_ms"],
                "capture_fps":info["capture_fps"],"processing_fps":info["processing_fps"],
                "encoder_queue_wait_ms":index.get("encoder_queue_wait_ms","")})
            video_frame+=1
    finally:
        capture.release(); scheduler.close()
    write_csv(run_dir/"pf_mock_replay_actions.csv",action_rows,
        ["action","reason","timestamp","event_id","key","scheduled_hit","armed","note_type"])
    write_csv(run_dir/"tap_decision_trace.csv",
        [row for name,row in trace_rows if name=="tap_decision"],TAP_DECISION_FIELDS)
    write_csv(run_dir/"pf_mock_replay_events.csv",replay_events,
        list(replay_events[0].keys()) if replay_events else ["event_id","track_id","source_frame"])
    write_csv(run_dir/"pf_stage_timing.csv",stages,STAGE_FIELDS)
    original_events=read_csv(run_dir/"live_events.csv")
    original_actions=read_csv(run_dir/"live_key_actions.csv")
    def downs(rows):
        out={}
        for row in rows:
            if row.get("action")=="key_down":out.setdefault(row.get("event_id",""),[]).append(row)
        return out
    actual_downs=downs(original_actions); mock_downs=downs(action_rows)
    original_map={row.get("event_id"):row for row in original_events if row.get("event_id")}
    replay_map={row.get("event_id"):row for row in replay_events if row.get("event_id")}
    compare=[]
    for eid in sorted(set(original_map)|set(replay_map)):
        old=original_map.get(eid,{}); new=replay_map.get(eid,{})
        same=(bool(old) and bool(new) and str(old.get("source_frame"))==str(new.get("source_frame")) and
              old.get("physical_track_uid")==new.get("physical_track_uid"))
        compare.append({"event_id":eid,"original_uid":old.get("physical_track_uid","UNKNOWN"),
            "replay_uid":new.get("physical_track_uid","UNKNOWN"),"original_key_downs":len(actual_downs.get(eid,[])),
            "mock_key_downs":len(mock_downs.get(eid,[])),
            "original_keys":"|".join(r.get("key","") for r in actual_downs.get(eid,[])),
            "mock_keys":"|".join(r.get("key","") for r in mock_downs.get(eid,[])),
            "comparison":"COMPARABLE_SAME_EVENT_UID_SOURCE_FRAME" if same else "NOT_COMPARABLE_TRACK_OR_EVENT_MAPPING"})
    write_csv(run_dir/"pf_before_after_comparison.csv",compare,
        ["event_id","original_uid","replay_uid","original_key_downs","mock_key_downs",
         "original_keys","mock_keys","comparison"])
    summary={"source_video":source.name,"indexed_frames":len(indexes),"replayed_frames":video_frame,
        "replay_events":len(replay_events),"actual_key_down_ids":len(actual_downs),
        "mock_key_down_ids":len(mock_downs),"same_event_identity_rows":sum(
            row["comparison"].startswith("COMPARABLE") for row in compare),
        "not_comparable_rows":sum(row["comparison"].startswith("NOT_COMPARABLE") for row in compare),
        "mock_calls":len(actuator.calls),"wall_seconds":time.perf_counter()-started,
        "real_game_accuracy":"UNVERIFIED"}
    (run_dir/"pf_mock_replay_summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,indent=2))


if __name__=="__main__":main()
