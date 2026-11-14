"""Causal V8.3 vs pixel-segmented replay through the same Engine and MockActuator."""
from __future__ import annotations
import argparse
import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.engine import Engine  # noqa:E402
from src.lane_filter import LaneFilter  # noqa:E402
from src.model import Detection, Frame, Geometry, KEYS  # noqa:E402
from src.perception import Perception  # noqa:E402
from src.scheduler import MockActuator, Scheduler  # noqa:E402


class SegmentedProvider:
    """Adapt pixel components to Detection for the unmodified shared Tracker."""
    def __init__(self, geometry):
        self.geometry=geometry;self.filter=LaneFilter(geometry)
        self.last_labels=None;self.last_path=None;self.last_result=None;self.frame_index=0
        self.last_profile={};self.conversion_trace=[]

    def detect(self, normalized_bgr):
        started=time.perf_counter()
        rect=self.geometry.rectify(normalized_bgr)
        rectify_ms=(time.perf_counter()-started)*1000
        segment_start=time.perf_counter()
        result=self.filter.segment_rectified(rect,frame_index=self.frame_index)
        segment_ms=(time.perf_counter()-segment_start)*1000
        self.last_result=result
        held=np.zeros(rect.shape[:2],np.uint8)
        for name in ("hold_head","hold_body","hold_tail"):
            held|=result.masks[name]
        self.last_path=held
        held_binary=held>0
        conversion_started=time.perf_counter()
        _,self.last_labels=cv2.connectedComponents((held>0).astype(np.uint8),8)
        out=[]
        trace=[]
        role_kind={"tap_face":"tap","hold_head":"hold_head","hold_body":"body","hold_tail":"hold_tail"}
        for component in result.components:
            kind=role_kind.get(component.role)
            if not kind:
                # UNKNOWN/effect components remain available in the perception
                # report but are never offered to the executable tracker.
                trace.append({"component_id":component.component_id,"role":component.role,
                    "conversion":"dropped_semantic_gate","bbox":component.bbox,"color":component.color,
                    "area":component.area,"reason":"role_not_executable"})
                continue
            x,y,w,h=component.bbox
            if w<1 or h<1:
                trace.append({"component_id":component.component_id,"role":component.role,
                    "conversion":"dropped_invalid_bbox","bbox":component.bbox,"color":component.color,
                    "area":component.area,"reason":"empty_bbox"})
                continue
            keys=tuple(key for i,key in enumerate(KEYS)
                       if min(x+w,(i+1)*self.geometry.lane_pixels)-max(x,i*self.geometry.lane_pixels)>=5)
            if not keys:
                trace.append({"component_id":component.component_id,"role":component.role,
                    "conversion":"dropped_no_lane_coverage","bbox":component.bbox,"color":component.color,
                    "area":component.area,"reason":"less_than_5_rectified_pixels_in_any_lane"})
                continue
            above=below=0.
            if kind in ("hold_head","body","hold_tail"):
                for step in range(4,85,4):
                    yy=y-step
                    if yy>=0 and np.count_nonzero(held_binary[yy,max(0,x):min(held_binary.shape[1],x+w)])>=max(2,.12*w):above=step
                    yy=y+h+step
                    if yy<held_binary.shape[0] and np.count_nonzero(held_binary[yy,max(0,x):min(held_binary.shape[1],x+w)])>=max(2,.12*w):below=step
            confidence=min(1.,component.area/max(1,w*h))
            out.append(Detection(tuple(map(int,component.bbox)),component.color,kind,keys,
                confidence,component.component_id,above,below,plane_width=self.geometry.plane_width))
            trace.append({"component_id":component.component_id,"role":component.role,
                "conversion":"accepted","bbox":component.bbox,"color":component.color,
                "area":component.area,"kind":kind,"keys":"|".join(keys),
                "above":above,"below":below,"confidence":confidence})
        self.conversion_trace=trace
        self.last_profile={**getattr(self.filter.segmenter,"last_profile",{}),
            "rectify_ms":rectify_ms,"segment_total_ms":segment_ms,
            "data_conversion_ms":(time.perf_counter()-conversion_started)*1000,
            "component_count":len(result.components),"converted_count":len(out),
            "dropped_component_count":len(result.components)-len(out)}
        self.frame_index+=1
        return out


def read_index(path):
    with path.open(encoding="utf-8-sig",newline="") as f:
        return {int(r["video_frame"]):r for r in csv.DictReader(f)}


def poll_to(state,target,*,inclusive=True):
    now,scheduler=state["now"],state["scheduler"]
    next_poll=state["next_poll"]
    boundary=target+1e-10 if inclusive else target-1e-10
    while next_poll<=boundary:
        now[0]=next_poll;scheduler.poll();next_poll+=.002
    state["next_poll"]=next_poll;now[0]=target


def make_state(provider,geometry,calibration,start_time):
    now=[start_time];actuator=MockActuator();event_log=[]
    scheduler=Scheduler(actuator,clock=lambda:now[0],focus_check=lambda:True,
                        modifiers_check=lambda:False,on_event=lambda event:event_log.append(dict(event)))
    engine=Engine(geometry,scheduler,calibration)
    if provider=="segmented":engine.perception=SegmentedProvider(geometry)
    return {"provider":provider,"now":now,"scheduler":scheduler,"actuator":actuator,"engine":engine,
            "next_poll":start_time+.002,"arm_triggered":False,"arm_ended":False,
            "actions":[],"event_log":event_log,"decisions":[],"summary":[],"candidate_trace":[],
            "wall_ms":[],"compute_wall_ms":[],"profile":[]}


def run_latency(run_dir,latency_s,arm_window,geometry,calibration,providers,limit_frames=None):
    index=read_index(run_dir/"live_video_index.csv")
    caps=cv2.VideoCapture(str(run_dir/"live_source.mp4"))
    if not caps.isOpened():raise RuntimeError(f"cannot open {run_dir/'live_source.mp4'}")
    states=[make_state(provider,Geometry(geometry.path),calibration,0.) for provider in providers]
    decoded=0;first_capture=None;last_capture=None
    while True:
        ok,frame=caps.read()
        if not ok or (limit_frames is not None and decoded>=limit_frames):break
        idx=index.get(decoded)
        if idx is None:decoded+=1;continue
        captured=float(idx["capture_timestamp"]);acquired=float(idx["acquired_timestamp"])
        if acquired<captured:raise ValueError(f"acquired before capture at video_frame={decoded}")
        if last_capture is not None and captured<=last_capture:raise ValueError("non-increasing capture timestamp")
        last_capture=captured
        if first_capture is None:
            first_capture=captured
            for s in states:s["now"][0]=captured;s["next_poll"]=captured+.002
        relative=captured-first_capture
        focused=str(idx.get("focused","True")).lower() in ("true","1")
        roi_valid=str(idx.get("roi_valid","True")).lower() in ("true","1")
        for s in states:
            process_time=acquired+latency_s
            # The acquired frame becomes in-flight before its configured
            # processing delay elapses. Let begin_frame publish that timestamp
            # before polling through the simulated processing interval.
            poll_to(s,acquired,inclusive=False)
            s["now"][0]=acquired
            frame_value=Frame(decoded,frame,captured,acquired,focused,roi_valid,run_dir.name)
            tick=time.perf_counter();observation=s["engine"].observe(frame_value)
            observe_end=time.perf_counter()
            poll_to(s,process_time)
            poll_end=time.perf_counter()
            info,decisions=s["engine"].decide(observation,processed_at=process_time)
            decide_end=time.perf_counter()
            compute_ms=((observe_end-tick)+(decide_end-poll_end))*1000
            wall_ms=(decide_end-tick)*1000
            poll_wall_ms=(poll_end-observe_end)*1000
            s["wall_ms"].append(wall_ms)
            s["compute_wall_ms"].append(compute_ms)
            profile=dict(observation.get("profile",{}))
            profile.update({"video_frame":decoded,"decision_wall_ms":(decide_end-poll_end)*1000,
                "compute_wall_ms":compute_ms,"scheduler_simulation_wall_ms":poll_wall_ms,
                "component_count":profile.get("component_count",len(observation["detections"])),
                "converted_count":profile.get("converted_count",len(observation["detections"])),
                "dropped_component_count":profile.get("dropped_component_count",0)})
            s["profile"].append(profile)
            perception=s["engine"].perception
            conversion_by_id={r.get("component_id"):r for r in getattr(perception,"conversion_trace",[])}
            decision_by_uid={r.get("note_uid"):r for r in decisions}
            for item in getattr(perception,"conversion_trace",[]):
                s["candidate_trace"].append({"provider":s["provider"],"video_frame":decoded,
                    "source_frame":int(idx.get("source_frame",decoded)),"capture_timestamp":captured,
                    "acquired_timestamp":acquired,"candidate_stage":"segmentation_to_detector",**item})
            for detection in observation["detections"]:
                cap=next((c for c in s["engine"].tracker.caps.values() if c.detection is detection),None)
                note=s["engine"].tracker.notes.get(cap.note_uid) if cap and cap.note_uid else None
                decision=decision_by_uid.get(note.uid,{}) if note else {}
                converted=conversion_by_id.get(detection.component,{})
                s["candidate_trace"].append({"provider":s["provider"],"video_frame":decoded,
                    "source_frame":int(idx.get("source_frame",decoded)),"capture_timestamp":captured,
                    "acquired_timestamp":acquired,"candidate_stage":"tracker_input",
                    "component_id":detection.component,"role":converted.get("role",detection.kind),
                    "kind":detection.kind,"color":detection.color,"bbox":detection.bbox,
                    "area":converted.get("area",""),"keys":"|".join(detection.keys),
                    "conversion":"accepted","tracker_uid":note.uid if note else "",
                    "tracker_confirmed":note.confirmed if note else False,
                    "tracker_kind":note.kind if note else "","tracker_state":note.state if note else "UNASSIGNED",
                    "tracker_reason":note.reason if note else "no_note_identity",
                    "timing_reason":decision.get("reason",""),"scheduled_press":decision.get("press_at",""),
                    "scheduler_pending":bool(note and note.uid in s["scheduler"].pending),
                    "mock_key_down":bool(note and note.uid in s["scheduler"].fired)})
            s["summary"].append({"video_frame":decoded,"source_frame":int(idx.get("source_frame",decoded)),
                "captured_at":captured,"acquired_at":acquired,"processed_at":process_time,
                "playing":info["playing"],"focused":focused,"roi_valid":roi_valid,
                "detection_count":info["detections"],"track_count":info["tracks"],
                "armed":info["armed"],"capture_age_ms":info["capture_age_ms"]})
            for row in decisions:
                s["decisions"].append({"provider":s["provider"],"latency_ms":latency_s*1000,
                    "run_id":run_dir.name,"video_frame":decoded,"physical_note_id":"UNKNOWN",**row})
            if arm_window and not s["arm_triggered"] and relative>=arm_window[0] and info["playing"] and focused and roi_valid:
                s["scheduler"].toggle();s["arm_triggered"]=True
            if arm_window and not s["arm_ended"] and relative>arm_window[1]:
                s["scheduler"].disarm("simulated_arm_window_end");s["arm_ended"]=True
        decoded+=1
    caps.release()
    for s in states:
        # Flush a final tap up / bounded Hold release without allowing future image evidence.
        final=(s["summary"][-1]["acquired_at"]+latency_s) if s["summary"] else 0.
        poll_to(s,final+.04)
        s["scheduler"].disarm("replay_end")
        for event in s["event_log"]:
            s["actions"].append({"provider":s["provider"],"latency_ms":latency_s*1000,
                "run_id":run_dir.name,**event})
    return states,decoded


def action_metrics(state,reference_events,tolerance_s):
    presses=[e for e in state["actions"] if e.get("event")=="pressed"]
    releases=[e for e in state["actions"] if e.get("event")=="released"]
    release_failures=[e for e in state["actions"] if e.get("event")=="key_up_error"]
    accepted=[e for e in state["actions"] if e.get("event")=="accepted"]
    start=state["summary"][0]["captured_at"] if state["summary"] else float("inf")
    end=state["summary"][-1]["captured_at"] if state["summary"] else float("-inf")
    session_downs=[e for e in reference_events if e.get("action")=="key_down"]
    downs=[e for e in session_downs if start<=float(e["timestamp"])<=end]
    unused=set(range(len(presses)));matched=[];unmatched=[]
    for ref in downs:
        t=float(ref["timestamp"]);key=ref["key"]
        choices=[(abs(float(presses[i]["injection_started_at"])-t),i) for i in unused if presses[i].get("key")==key]
        if choices and min(choices)[0]<=tolerance_s:
            error,i=min(choices);unused.remove(i);matched.append((float(presses[i]["injection_started_at"])-t)*1000)
        else:unmatched.append(ref)
    return {"mock_pressed":len(presses),"reference_key_downs":len(downs),"matched_reference_actions":len(matched),
        "unmatched_human_key_downs":len(unmatched),"wrong_key_or_extra_mock_presses":len(unused),
        "out_of_replay_window_human_key_downs":len(session_downs)-len(downs),
        "reference_denominator_start_timestamp":start,"reference_denominator_end_timestamp":end,
        "unique_mock_press_uids":len({e.get("uid") for e in presses}),
        "duplicate_mock_press_uids":len(presses)-len({e.get("uid") for e in presses}),
        "accepted_but_not_pressed_uids":len({e.get("uid") for e in accepted}-{e.get("uid") for e in presses}),
        "mock_key_up_events":len(releases),"mock_key_up_failures":len(release_failures),
        "presses_without_release_uid_count":len({e.get("uid") for e in presses}-{e.get("uid") for e in releases}),
        "illegal_mock_keys":sum(e.get("key") not in KEYS for e in presses),
        "reference_action_recall":len(matched)/len(downs) if downs else None,
        "signed_mock_minus_human_ms_p10":float(np.percentile(matched,10)) if matched else None,
        "signed_mock_minus_human_ms_p50":float(np.percentile(matched,50)) if matched else None,
        "signed_mock_minus_human_ms_p90":float(np.percentile(matched,90)) if matched else None,
        "reference_tolerance_ms":tolerance_s*1000,
        "interpretation":"posthoc key/time proximity only; not game-grade or physical-note match"}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir",type=Path,required=True)
    ap.add_argument("--out",type=Path,default=ROOT/"output/analysis_lane_filter_v84_rework")
    ap.add_argument("--mode",choices=("baseline","segmented","compare"),default="compare")
    ap.add_argument("--latency-ms",type=float,nargs="+",default=[8,14,18,25,40])
    ap.add_argument("--simulated-arm-window",type=float,nargs=2,metavar=("START_S","END_S"),default=None)
    ap.add_argument("--reference-tolerance-ms",type=float,default=80.)
    ap.add_argument("--limit-frames",type=int)
    args=ap.parse_args();run_dir=args.run_dir.resolve();out=args.out.resolve()/run_dir.name;out.mkdir(parents=True,exist_ok=True)
    requested=("legacy","segmented") if args.mode=="compare" else (("legacy",) if args.mode=="baseline" else ("segmented",))
    # `run_latency` always compares both providers; for a single-provider CLI mode
    # the unused provider's records are discarded from output.
    index=read_index(run_dir/"live_video_index.csv");reference=[]
    ref_path=run_dir/"player_key_events.csv"
    if ref_path.exists():
        with ref_path.open(encoding="utf-8-sig",newline="") as f:reference=list(csv.DictReader(f))
    all_actions=[];all_decisions=[];all_candidates=[];all_profiles=[]
    aggregate=[];frame_summaries=[];decoded_total=None
    for latency_ms in args.latency_ms:
        if not 0<=latency_ms<=200:ap.error("latency values must be between 0 and 200 ms")
        states,decoded=run_latency(run_dir,latency_ms/1000,args.simulated_arm_window,
            Geometry(ROOT/"config/geometry_live_assist.json"),ROOT/"config/reference_timing.json",requested,args.limit_frames)
        decoded_total=decoded
        for state in states:
            if state["provider"] not in requested:continue
            all_actions.extend(state["actions"]);all_decisions.extend(state["decisions"])
            all_candidates.extend({"latency_ms":latency_ms,**row} for row in state["candidate_trace"])
            all_profiles.extend({"provider":state["provider"],"latency_ms":latency_ms,**row} for row in state["profile"])
            frame_summaries.extend({"provider":state["provider"],"latency_ms":latency_ms,**r} for r in state["summary"])
            metrics=action_metrics(state,reference,args.reference_tolerance_ms/1000)
            events=[e for e in state["actions"] if e.get("event")=="rejected"]
            aggregate.append({"provider":state["provider"],"latency_ms":latency_ms,"decoded_frames":decoded,
                "decision_rows":len(state["decisions"]),"wall_ms_per_frame_mean":float(np.mean(state["wall_ms"])) if state["wall_ms"] else None,
                "wall_ms_per_frame_p90":float(np.percentile(state["wall_ms"],90)) if state["wall_ms"] else None,
                "simulated_deadline_rejections":sum(e.get("reason") in ("late","expired_while_stale") for e in events),**metrics})
    def write_rows(path,rows):
        if not rows:return
        fields=list(dict.fromkeys(k for r in rows for k in r))
        with path.open("w",encoding="utf-8",newline="") as f:w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
    write_rows(out/"mock_actions.csv",all_actions);write_rows(out/"physical_note_decisions.csv",all_decisions)
    write_rows(out/"candidate_trace.csv",all_candidates)
    write_rows(out/"stage_profile_by_frame.csv",all_profiles)
    write_rows(out/"frame_summary.csv",frame_summaries);write_rows(out/"baseline_vs_candidate.csv",aggregate)
    safety=[]
    for provider in requested:
        for latency in args.latency_ms:
            events=[e for e in all_actions if e.get("provider")==provider and float(e.get("latency_ms",-1))==float(latency)]
            downs=[e for e in events if e.get("event")=="pressed"]
            ups=[e for e in events if e.get("event")=="released"]
            down_uids=[e.get("uid") for e in downs];up_uids={e.get("uid") for e in ups}
            safety.append({"provider":provider,"latency_ms":latency,"mock_actuator":"in_memory",
                "pressed_events":len(downs),"released_events":len(ups),
                "duplicate_press_uids":len(down_uids)-len(set(down_uids)),
                "press_uids_without_release":len(set(down_uids)-up_uids),
                "key_up_failures":sum(e.get("event")=="key_up_error" for e in events),
                "illegal_keys":sum(e.get("key") not in KEYS for e in downs),
                "duplicate_down_same_uid":len(down_uids)-len(set(down_uids))})
    (out/"mock_safety_audit.json").write_text(json.dumps(safety,indent=2),encoding="utf-8")
    if ref_path.exists():
        # Reference events are read only after all provider decisions are made.
        with (out/"reference_actions_posthoc.csv").open("w",encoding="utf-8",newline="") as f:
            fields=list(reference[0]) if reference else ["timestamp","action","key"]
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(reference)
    manifest={"run_id":run_dir.name,"mode":args.mode,"providers":requested,"latency_ms":args.latency_ms,
        "simulated_arm_window_s":args.simulated_arm_window,"simulated_scheduler_poll_ms":2,
        "actuator":"src.scheduler.MockActuator (in-memory only)","OS_keyboard_injection":False,
        "frame_clock":"indexed capture/acquired timestamps; processed time=acquired+configured latency",
        "frame_admission":"all decoded/indexed frames admitted; no real-time latest-frame dropping in fixed-latency mode",
        "configured_latency_is_measured_compute":False,
        "geometry_config_sha256":Geometry(ROOT/"config/geometry_live_assist.json").sha256,
        "timing_calibration_sha256":__import__("hashlib").sha256((ROOT/"config/reference_timing.json").read_bytes()).hexdigest(),
        "stage_profile":"stage_profile_by_frame.csv excludes rendering/encoding; scheduler simulator polling is reported separately",
        "future_frames_or_human_keys_in_decision_input":False,"decoded_frames":decoded_total,
        "limit_frames":args.limit_frames,"partial":args.limit_frames is not None and decoded_total>=args.limit_frames,
        "reference_events":"posthoc only; key/time proximity is not game judgment",
        "game_grade":"UNVERIFIED","safety_note":"same Engine/Tracker/Timing/Scheduler used for both providers"}
    (out/"replay_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(out)


if __name__=="__main__":main()
