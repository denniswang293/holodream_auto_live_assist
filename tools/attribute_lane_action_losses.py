"""Attribute Legacy Mock actions against Segmented candidates by visual track.

Provider UIDs are used only to gather each provider's own time series. Cross-
provider pairing uses same-frame geometry, lane/color, and vertical trajectory.
Ambiguous cases remain UNKNOWN. Evidence images are generated from source
frames and current-pixel masks, never from Legacy boxes as candidate masks.
"""
from __future__ import annotations
import argparse
import ast
import csv
import json
from collections import defaultdict,Counter
from pathlib import Path
import sys

import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.lane_segmentation import LanePixelSegmenter  # noqa:E402
from src.model import Geometry  # noqa:E402

TIMING_REASONS={"stale_observation","outside_motion_domain","stationary_or_implausible_motion",
    "crossing_in_past","outside_prediction_horizon","uncalibrated_visual_height",
    "motion_uncertainty","input_calibration_missing","prediction_late","outside_commit_horizon"}
ENGINE_GATES={"insufficient_motion_or_late_origin","hold_head_not_verified","late_hold_head_without_identity",
    "tap_face_not_visible","no_reliable_key_coverage","not_playing"}


def read_csv(path):
    with path.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))


def box(value):
    if not value:return None
    try:return tuple(float(v) for v in ast.literal_eval(value))
    except Exception:return None


def intersection(a,b):
    ax,ay,aw,ah=a;bx,by,bw,bh=b
    ix=max(0.,min(ax+aw,bx+bw)-max(ax,bx));iy=max(0.,min(ay+ah,by+bh)-max(ay,by))
    area=ix*iy
    return area,area/max(1.,aw*ah),area/max(1.,bw*bh)


def cross_score(legacy_rows,seg_frame_index,key):
    """Pair provider-local tracks using aligned visible position/motion."""
    best=None
    left={}
    for r in legacy_rows:
        capture=float(r.get("capture_timestamp",r.get("video_frame",0)))
        if abs(float(r.get("last_observation") or capture)-capture)>.001:continue
        b=box(r.get("bbox"));
        if not b:continue
        frame=int(r["video_frame"]);rect=(b[0]*.5,b[1],b[2]*.5,b[3])
        left[frame]=(r,rect)
    grouped=defaultdict(dict)
    for frame,(lr,lb) in left.items():
        for sr in seg_frame_index.get(frame,[]):
            capture=float(sr.get("capture_timestamp",sr.get("video_frame",0)))
            if abs(float(sr.get("last_observation") or capture)-capture)>.001:continue
            if key not in (sr.get("keys") or "").split("|"):continue
            raw=box(sr.get("bbox"))
            if not raw:continue
            sb=(raw[0]*.5,raw[1],raw[2]*.5,raw[3])
            grouped[sr["note_uid"]][frame]=(sr,sb)
    for uid,series in grouped.items():
        matches=[];distances=[];covers=[]
        for frame,(lr,lb) in left.items():
            sr_pair=series.get(frame)
            if not sr_pair:continue
            sr,sb=sr_pair
            if lr.get("color") not in (sr.get("color"),"neutral") and sr.get("color")!="neutral":continue
            _,cover,_=intersection(lb,sb)
            lx,ly,lw,lh=lb;sx,sy,sw,sh=sb
            dx=abs((lx+lw/2)-(sx+sw/2));dy=abs((ly+lh/2)-(sy+sh/2))
            if cover>=.35 or (dx<=max(18,lw*.35) and dy<=max(24,lh*.8)):
                matches.append(frame);distances.append(dx+dy);covers.append(cover)
        if not matches:continue
        score=(len(matches),float(np.mean(covers)),-float(np.mean(distances)))
        if best is None or score>best[0]:best=(score,uid,sorted(matches))
    return best


def nearest_same_frame(row,trace,geometry,key):
    target=box(row.get("bbox"));
    if not target:return None
    tx,ty,tw,th=target;target=(tx*.5,ty,tw*.5,th)
    candidates=[]
    for c in trace:
        if c.get("candidate_stage")!="segmentation_to_detector":continue
        cb=box(c.get("bbox"));
        if not cb:continue
        area,cover,_=intersection(target,cb)
        if area<=0:continue
        # Role keys may be absent for unknown components; same pixel color and
        # source-frame overlap still support a candidate match.
        key_match=key in (c.get("keys") or "").split("|")
        color_match=(row.get("color")==c.get("color") or c.get("role")=="unknown")
        role_priority={"tap_face":4,"hold_head":4,"hold_tail":3,"hold_body":2,
                       "effect_or_artifact":1,"unknown":0}.get(c.get("role"),0)
        score=(cover,role_priority,1 if color_match else 0,1 if key_match else 0,-cb[2]*cb[3])
        candidates.append((score,c))
    return max(candidates,key=lambda x:x[0])[1] if candidates else None


def classify_case(match,seg_row,component,seg_action,expected_key):
    if seg_action and seg_action.get("event")=="pressed":
        if seg_action.get("key")==expected_key:return "SEGMENTED_ACTION_PRESENT","HIGH","paired_mock_down_same_key"
        return "SEGMENTED_ACTION_WRONG_KEY","HIGH",f"mock_down_key={seg_action.get('key')}; expected_lane_key={expected_key}"
    if seg_action and seg_action.get("event")=="rejected":
        return "SCHEDULER_REJECTION","HIGH",seg_action.get("reason","")
    if match:
        _,uid,frames=match
        if seg_row:
            reason=seg_row.get("reason","")
            if reason in TIMING_REASONS:return "TIMING_GATE","HIGH" if len(frames)>=3 else "MEDIUM",reason
            if reason in ENGINE_GATES:return "ENGINE_ELIGIBILITY_GATE","HIGH" if len(frames)>=3 else "MEDIUM",reason
            if seg_row.get("state")=="SCHEDULED":return "UNRESOLVED_SCHEDULED_ACTION","MEDIUM",seg_row.get("reason",seg_row.get("state"))
            if str(seg_row.get("confirmed","False")).lower() not in ("true","1"):
                return "TRACK_CONFIRMATION","HIGH" if len(frames)>=3 else "MEDIUM",reason or "candidate_not_confirmed"
            return "UNRESOLVED_AFTER_TRACKING","MEDIUM",reason or "no_action_event_for_matched_track"
        return "TRACK_CONFIRMATION","MEDIUM","matched_spatial_track_has_no_decision_row"
    if component:
        role=component.get("role","");conversion=component.get("conversion","")
        if role=="hold_body" and conversion=="accepted":
            return "ADAPTER_BODY_CANNOT_SEED_NOTE","HIGH","body_is_preserved_but_tracker_requires_tap_or_hold_head"
        if role=="unknown":return "SEGMENTATION_UNKNOWN_ROLE","MEDIUM","overlapping_pixels_retained_as_unknown"
        if conversion.startswith("dropped_"):return "ADAPTER_CONVERSION_DROP","HIGH",component.get("reason",conversion)
        return "TRACK_INITIALIZATION","LOW","converted_candidate_without_matched_tracker_identity"
    return "UNKNOWN","LOW","no_spatially_matched_segmented_component_or_track"


def render_evidence(run_dir,frame_no,trace,legacy_note,component,geometry,out_dir,masker):
    path=out_dir/f"frame_{frame_no:06d}.png"
    if path.exists():return str(path)
    cap=cv2.VideoCapture(str(run_dir/"live_source.mp4"));cap.set(cv2.CAP_PROP_POS_FRAMES,frame_no);ok,source=cap.read();cap.release()
    if not ok:return ""
    rect=geometry.rectify(geometry.normalize(source));seg=masker.segment(rect,geometry,frame_index=frame_no)
    mask=np.zeros_like(rect);colors={"tap_face":(40,220,70),"hold_head":(0,220,255),
        "hold_body":(255,120,20),"hold_tail":(220,40,220),"effect_or_artifact":(40,80,255),"unknown":(170,170,170)}
    for name,color in colors.items():mask[seg.masks[name]>0]=color
    legacy_canvas=rect.copy()
    for c in trace:
        if c.get("provider")!="legacy" or c.get("candidate_stage")!="tracker_input" or int(c.get("video_frame",-1))!=frame_no:continue
        b=box(c.get("bbox"));
        if b:cv2.rectangle(legacy_canvas,(int(b[0]),int(b[1])),(int(b[0]+b[2]),int(b[1]+b[3])),(230,100,230),1)
    if legacy_note:
        b=box(legacy_note.get("bbox"));
        if b:cv2.rectangle(legacy_canvas,(int(b[0]*.5),int(b[1])),(int((b[0]+b[2])*.5),int(b[1]+b[3])),(0,255,255),2)
    seg_canvas=rect.copy()
    for c in trace:
        if c.get("provider")!="segmented" or c.get("candidate_stage")!="segmentation_to_detector" or int(c.get("video_frame",-1))!=frame_no:continue
        b=box(c.get("bbox"));
        if not b:continue
        color=colors.get(c.get("role"),(170,170,170))
        cv2.rectangle(seg_canvas,(int(b[0]),int(b[1])),(int(b[0]+b[2]),int(b[1]+b[3])),color,1)
    if component:
        b=box(component.get("bbox"));
        if b:cv2.rectangle(seg_canvas,(int(b[0]),int(b[1])),(int(b[0]+b[2]),int(b[1]+b[3])),(0,255,255),2)
    panels=[]
    for name,img in (("source + Legacy candidates",legacy_canvas),("current-pixel masks",mask),("Segmented component candidates",seg_canvas)):
        panel=img.copy();cv2.rectangle(panel,(0,0),(panel.shape[1],22),(0,0,0),-1)
        cv2.putText(panel,name,(5,16),cv2.FONT_HERSHEY_SIMPLEX,.42,(255,255,255),1,cv2.LINE_AA);panels.append(panel)
    out=np.concatenate(panels,axis=1);cv2.imwrite(str(path),out);return str(path)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir",type=Path,required=True)
    ap.add_argument("--replay-dir",type=Path,required=True)
    ap.add_argument("--out",type=Path,default=ROOT/"output/analysis_lane_filter_v84_rework")
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    actions=read_csv(args.replay_dir/"mock_actions.csv");decisions=read_csv(args.replay_dir/"physical_note_decisions.csv")
    trace=read_csv(args.replay_dir/"candidate_trace.csv")
    legacy_presses=[r for r in actions if r["provider"]=="legacy" and r["event"]=="pressed"]
    segmented_presses=[r for r in actions if r["provider"]=="segmented" and r["event"]=="pressed"]
    segmented_events=defaultdict(list)
    for event in actions:
        if event["provider"]=="segmented" and event.get("uid"):
            segmented_events[event["uid"]].append(event)
    rows_by_provider=defaultdict(lambda:defaultdict(list))
    for r in decisions:rows_by_provider[r["provider"]][r["note_uid"]].append(r)
    for group in rows_by_provider.values():
        for rr in group.values():rr.sort(key=lambda x:int(x["video_frame"]))
    seg_frame_index=defaultdict(list)
    for r in decisions:
        if r["provider"]=="segmented":seg_frame_index[int(r["video_frame"])].append(r)
    trace_by_frame=defaultdict(list)
    for r in trace:trace_by_frame[int(r["video_frame"])].append(r)
    evidence_dir=args.out/"action_loss_evidence_v4";evidence_dir.mkdir(exist_ok=True)
    geometry=Geometry(ROOT/"config/geometry_live_assist.json");masker=LanePixelSegmenter()
    output=[];counts=Counter()
    for n,event in enumerate(legacy_presses,1):
        uid=event["uid"];legacy_track=rows_by_provider["legacy"].get(uid,[])
        key=event["key"]
        segmented_tracks=list(rows_by_provider["segmented"].values())
        match=cross_score(legacy_track,seg_frame_index,key)
        match_uid=match[1] if match else "";matched_frames=match[2] if match else []
        cap_time=float(event.get("decision_capture_timestamp") or event["at"])
        legacy_row=min(legacy_track,key=lambda r:abs(float(r["capture_timestamp"])-cap_time)) if legacy_track else None
        seg_track=rows_by_provider["segmented"].get(match_uid,[]) if match_uid else []
        seg_row=min(seg_track,key=lambda r:abs(float(r["capture_timestamp"])-cap_time)) if seg_track else None
        frame_trace=trace_by_frame.get(int(legacy_row["video_frame"]),[]) if legacy_row else []
        component=nearest_same_frame(legacy_row,frame_trace,geometry,key) if legacy_row else None
        seg_track_events=segmented_events.get(match_uid,[]) if match_uid else []
        seg_action=next((r for r in seg_track_events if r.get("event") in ("pressed","rejected")),None)
        stage,confidence,reason=classify_case(match,seg_row,component,seg_action,key)
        paired=len(matched_frames)
        frame=int(legacy_row["video_frame"]) if legacy_row else -1
        evidence=render_evidence(args.run_dir,frame,frame_trace,legacy_row,component,geometry,evidence_dir,masker) if frame>=0 else ""
        counts[stage]+=1
        lbox=legacy_row.get("bbox","") if legacy_row else ""
        sbox=seg_row.get("bbox","") if seg_row else (str(component.get("bbox")) if component else "")
        output.append({"case_id":f"legacy_action_{n:04d}","legacy_action_uid_provider_local":uid,
            "legacy_key":key,"legacy_kind":legacy_row.get("kind",event.get("kind","")) if legacy_row else event.get("kind",""),
            "video_frame":frame,"source_frame":component.get("source_frame","") if component else "",
            "capture_timestamp":legacy_row.get("capture_timestamp",event.get("decision_capture_timestamp","")) if legacy_row else event.get("decision_capture_timestamp",""),
            "legacy_bbox_native":lbox,"legacy_tracker_uid_provider_local":uid,
            "legacy_tracker_confirmed":legacy_row.get("confirmed","") if legacy_row else "",
            "legacy_timing_reason":legacy_row.get("reason","") if legacy_row else "",
            "segmented_component_id":component.get("component_id","") if component else "",
            "segmented_component_role":component.get("role","") if component else "",
            "segmented_conversion":component.get("conversion","") if component else "",
            "segmented_component_bbox_rectified":component.get("bbox","") if component else "",
            "segmented_tracker_uid_provider_local":match_uid,
            "segmented_tracker_bbox_native":sbox,"segmented_tracker_confirmed":seg_row.get("confirmed","") if seg_row else "",
            "segmented_tracker_state":seg_row.get("state","") if seg_row else "",
            "segmented_timing_reason":seg_row.get("reason","") if seg_row else "",
            "trajectory_matched_frames":paired,"segmented_action_uid_provider_local":seg_action.get("uid","") if seg_action else "",
            "segmented_scheduler_outcome":seg_action.get("event","") if seg_action else "no_matched_scheduler_down_or_reject",
            "segmented_action_event":seg_action.get("event","") if seg_action else "",
            "segmented_action_key":seg_action.get("key","") if seg_action else "",
            "segmented_action_time":seg_action.get("injection_started_at",seg_action.get("at","")) if seg_action else "",
            "segmented_key_up":"yes" if any(e.get("event")=="released" for e in seg_track_events) else "no",
            "root_cause_stage":stage,"attribution_reason":reason,"evidence_confidence":confidence,
            "evidence_image":evidence,"interpretation":"provider UIDs are local labels only; physical match uses frame/position/key/color/downward track"})
    path=args.out/"action_loss_attribution.csv"
    with path.open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(output[0]));writer.writeheader();writer.writerows(output)
    summary=args.out/"action_loss_attribution_summary.csv"
    with summary.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["root_cause_stage","action_count","fraction_of_legacy_presses"]);w.writeheader()
        for stage,count in sorted(counts.items()):w.writerow({"root_cause_stage":stage,"action_count":count,"fraction_of_legacy_presses":count/max(1,len(output))})
    print(json.dumps({"legacy_presses":len(legacy_presses),"segmented_presses":len(segmented_presses),
        "output":str(path),"stage_counts":counts},default=dict))


if __name__=="__main__":main()
