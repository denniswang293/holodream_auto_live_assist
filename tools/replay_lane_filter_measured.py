"""Latest-frame replay using measured per-frame inference wall time.

This mode is deliberately separate from fixed-latency algorithm A/B. It
models a live single-slot capture worker: while inference is busy, newly
acquired frames replace the pending frame and older pending frames are
dropped. Video decoding and output encoding are excluded from inference cost.
"""
from __future__ import annotations
import argparse
import csv
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.model import Frame,Geometry,KEYS  # noqa:E402
from tools.replay_lane_filter import make_state,read_index,poll_to,action_metrics  # noqa:E402


def indexed_frames(run_dir,limit=None):
    index=read_index(run_dir/"live_video_index.csv")
    cap=cv2.VideoCapture(str(run_dir/"live_source.mp4"))
    if not cap.isOpened():raise RuntimeError(f"could not open {run_dir/'live_source.mp4'}")
    seq=0
    try:
        while limit is None or seq<limit:
            ok,image=cap.read()
            if not ok:break
            row=index.get(seq)
            if row:
                yield seq,image,row
            seq+=1
    finally:cap.release()


def simulate_provider(run_dir,provider,arm_window,limit=None):
    index=read_index(run_dir/"live_video_index.csv")
    geometry=Geometry(ROOT/"config/geometry_live_assist.json")
    state=make_state(provider,Geometry(geometry.path),ROOT/"config/reference_timing.json",0.)
    iterator=iter(indexed_frames(run_dir,limit));current=next(iterator,None);pending_future=None
    if current is None:return state,{"decoded_frames":0,"processed_frames":0,"dropped_frames":0}
    first_acquired=float(current[2]["acquired_timestamp"])
    state["now"][0]=first_acquired;state["next_poll"]=first_acquired+.002
    decoded=0;processed=0;dropped=0;first_capture=float(current[2]["capture_timestamp"])
    while current is not None:
        seq,image,row=current;decoded=max(decoded,seq+1)
        captured=float(row["capture_timestamp"]);acquired=float(row["acquired_timestamp"])
        if acquired<captured:raise ValueError(f"acquired before capture at video_frame={seq}")
        focused=str(row.get("focused","True")).lower() in ("true","1")
        roi_valid=str(row.get("roi_valid","True")).lower() in ("true","1")
        start=max(state["now"][0],acquired)
        poll_to(state,start)
        state["now"][0]=start
        frame=Frame(seq,image,captured,acquired,focused,roi_valid,run_dir.name)
        wall_start=time.perf_counter();observation=state["engine"].observe(frame)
        after_observe=time.perf_counter()
        observe_ms=(after_observe-wall_start)*1000
        decision_at=start+(after_observe-wall_start)
        poll_to(state,decision_at,inclusive=False)
        info,decisions=state["engine"].decide(observation,processed_at=decision_at)
        after_decide=time.perf_counter()
        decision_ms=(after_decide-after_observe)*1000
        finish=decision_at+(after_decide-after_observe)
        poll_to(state,finish)
        compute_ms=observe_ms+decision_ms
        processed+=1
        state["summary"].append({"video_frame":seq,"source_frame":int(row.get("source_frame",seq)),
            "captured_at":captured,"acquired_at":acquired,"processed_at":finish,
            "processing_ms":compute_ms,"capture_age_ms":(finish-captured)*1000,
            "playing":info["playing"],"focused":focused,"roi_valid":roi_valid,
            "detection_count":info["detections"],"track_count":info["tracks"],
            "armed":info["armed"],"frame_drops_so_far":dropped})
        state["wall_ms"].append(compute_ms)
        profile=dict(observation.get("profile",{}))
        profile.update({"video_frame":seq,"source_frame":int(row.get("source_frame",seq)),
            "processing_ms":compute_ms,"observe_wall_ms":observe_ms,"decision_wall_ms":decision_ms,
            "capture_age_ms":(finish-captured)*1000})
        state["profile"].append(profile)
        for decision in decisions:
            state["decisions"].append({"provider":provider,"latency_ms":"MEASURED",
                "run_id":run_dir.name,"video_frame":seq,"physical_note_id":"UNKNOWN",**decision})
        relative=captured-first_capture
        if arm_window and not state["arm_triggered"] and relative>=arm_window[0] and info["playing"] and focused and roi_valid:
            state["scheduler"].toggle();state["arm_triggered"]=True
        if arm_window and not state["arm_ended"] and relative>arm_window[1]:
            state["scheduler"].disarm("simulated_arm_window_end");state["arm_ended"]=True

        # The single pending capture slot keeps only the most recently
        # acquired frame available when inference completes.
        latest=None
        if pending_future is not None and float(pending_future[2]["acquired_timestamp"])<=finish:
            latest=pending_future;pending_future=None
        while pending_future is None:
            nxt=next(iterator,None)
            if nxt is None:break
            nxt_acquired=float(nxt[2]["acquired_timestamp"])
            if nxt_acquired<=finish:
                if latest is not None:dropped+=1
                latest=nxt
            else:
                pending_future=nxt
        if latest is not None:
            current=latest
        elif pending_future is not None:
            current=pending_future;pending_future=None
        else:current=None
    final=(state["now"][0]+.04) if state["summary"] else 0.
    poll_to(state,final);state["scheduler"].disarm("replay_end")
    state["actions"]=[{"provider":provider,"latency_ms":"MEASURED","run_id":run_dir.name,**event}
                       for event in state["event_log"]]
    state["decoded_frames"]=decoded;state["dropped_frames"]=dropped
    return state,{"decoded_frames":decoded,"processed_frames":processed,"dropped_frames":dropped}


def write_rows(path,rows):
    if not rows:return
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");writer.writeheader();writer.writerows(rows)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir",type=Path,required=True)
    ap.add_argument("--out",type=Path,default=ROOT/"output/analysis_lane_filter_v84_rework/measured_realtime")
    ap.add_argument("--mode",choices=("compare","baseline","segmented"),default="compare")
    ap.add_argument("--simulated-arm-window",type=float,nargs=2,metavar=("START_S","END_S"),default=None)
    ap.add_argument("--reference-tolerance-ms",type=float,default=80.)
    ap.add_argument("--limit-frames",type=int)
    args=ap.parse_args();run_dir=args.run_dir.resolve();out=args.out.resolve()/run_dir.name;out.mkdir(parents=True,exist_ok=True)
    providers=("legacy","segmented") if args.mode=="compare" else (args.mode,)
    reference=[];ref_path=run_dir/"player_key_events.csv"
    if ref_path.exists():
        with ref_path.open(encoding="utf-8-sig",newline="") as f:reference=list(csv.DictReader(f))
    summaries=[];actions=[];decisions=[];profiles=[];aggregates=[];admission=[]
    for provider in providers:
        state,counts=simulate_provider(run_dir,provider,args.simulated_arm_window,args.limit_frames)
        summaries.extend({"provider":provider,**r} for r in state["summary"])
        actions.extend(state["actions"]);decisions.extend(state["decisions"])
        profiles.extend({"provider":provider,**r} for r in state["profile"])
        metric=action_metrics(state,reference,args.reference_tolerance_ms/1000)
        presses=[r for r in state["actions"] if r["event"]=="pressed"]
        accepts=[r for r in state["actions"] if r["event"]=="accepted"]
        aggregates.append({"provider":provider,**counts,"decision_rows":len(state["decisions"]),
            "compute_ms_mean":float(np.mean(state["wall_ms"])) if state["wall_ms"] else None,
            "compute_ms_p90":float(np.percentile(state["wall_ms"],90)) if state["wall_ms"] else None,
            "scheduler_accepts":len(accepts),"mock_pressed":len(presses),**metric})
        admission.append({"provider":provider,**counts,"admission_policy":"latest acquired frame at inference completion",
            "decode_and_render_in_compute_cost":False})
    write_rows(out/"frame_summary.csv",summaries);write_rows(out/"mock_actions.csv",actions)
    write_rows(out/"physical_note_decisions.csv",decisions);write_rows(out/"stage_profile_by_frame.csv",profiles)
    write_rows(out/"baseline_vs_candidate.csv",aggregates);write_rows(out/"frame_admission.csv",admission)
    (out/"replay_manifest.json").write_text(json.dumps({"run_id":run_dir.name,"mode":args.mode,
        "providers":providers,"latency_ms":"measured per frame; not fixed","simulated_arm_window_s":args.simulated_arm_window,
        "capture_acquired_timestamps_shared_source":True,"processing_clock":"measured observe+decide wall time; scheduler polling simulated separately",
        "frame_admission":"latest acquired frame replaces pending frame while inference is busy",
        "dropped_frame_counts_are_provider_specific":True,"decode_io_excluded_from_processing_cost":True,
        "video_encoding_included":False,"actuator":"in-memory MockActuator","OS_keyboard_injection":False,
        "future_frames_or_human_keys_in_decision_input":False,"geometry_config_sha256":Geometry(ROOT/"config/geometry_live_assist.json").sha256,
        "timing_calibration_sha256":__import__("hashlib").sha256((ROOT/"config/reference_timing.json").read_bytes()).hexdigest(),
        "partial":args.limit_frames is not None,"game_grade":"UNVERIFIED",
        "note":"Measured compute is host-dependent; offline video decode is excluded and actions remain mock only."},indent=2),encoding="utf-8")
    print(out)


if __name__=="__main__":main()
