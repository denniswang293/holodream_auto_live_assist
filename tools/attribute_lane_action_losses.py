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
import hashlib
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
    "motion_uncertainty","input_calibration_missing","prediction_late","outside_commit_horizon",
    "insufficient_observations"}
ENGINE_GATES={"insufficient_motion_or_late_origin","hold_head_not_verified","late_hold_head_without_identity",
    "tap_face_not_visible","no_reliable_key_coverage","not_playing"}
OBSERVABLE_STOP_STAGES={
    "confirmed_tap_observation_lost":"ENGINE_TAP_VISIBILITY_GATE",
    "type_pending":"ENGINE_TYPE_PENDING",
    "insufficient_observations":"TIMING_INSUFFICIENT_OBSERVATIONS",
}
# Auxiliary event-proximity diagnostic only. This is not a hit, recall, or
# scheduler timing threshold; it only limits report-tool event attribution.
ACTION_EVENT_PROXIMITY_WINDOW_SECONDS = 0.080


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


def native_box_to_rectified(bbox,geometry):
    """Invert the configured piecewise lane map, never approximate x by a scale."""
    if not bbox:return None
    x,y,w,h=bbox;bounds=np.asarray(geometry.boundaries(y+h/2),float)
    lanes=np.arange(7,dtype=float)*geometry.lane_pixels
    left=float(np.interp(x,bounds,lanes));right=float(np.interp(x+w,bounds,lanes))
    return left,float(y),max(0.,right-left),float(h)


def cross_score(legacy_rows,seg_frame_index,key):
    """Pair provider-local tracks using aligned visible position/motion."""
    ranked=cross_score_candidates(legacy_rows,seg_frame_index,key)
    if not ranked:return None
    if len(ranked)>1 and ranked[0][0]==ranked[1][0]:return None
    return ranked[0]


def cross_score_candidates(legacy_rows,seg_frame_index,key):
    """Return ranked cross-provider candidates, retaining exact-score ties."""
    left={}
    for r in legacy_rows:
        capture=float(r.get("capture_timestamp",r.get("video_frame",0)))
        if abs(float(r.get("last_observation") or capture)-capture)>.001:continue
        b=box(r.get("bbox"));
        if not b:continue
        # Engine decision rows from both providers use Geometry.native_bbox,
        # so compare their true native geometry directly.
        frame=int(r["video_frame"]);rect=b
        left[frame]=(r,rect)
    grouped=defaultdict(dict)
    for frame,(lr,lb) in left.items():
        for sr in seg_frame_index.get(frame,[]):
            capture=float(sr.get("capture_timestamp",sr.get("video_frame",0)))
            if abs(float(sr.get("last_observation") or capture)-capture)>.001:continue
            if key not in (sr.get("keys") or "").split("|"):continue
            raw=box(sr.get("bbox"))
            if not raw:continue
            # Provider Engine rows share native-frame coordinates.
            sb=raw
            grouped[sr["note_uid"]][frame]=(sr,sb)
    ranked=[]
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
        ranked.append((score,uid,sorted(matches)))
    return sorted(ranked,key=lambda item:item[0],reverse=True)


def linked_component(row,trace,provider,tracker_uid,frame):
    """Resolve a component only through same-provider/frame tracker-input UID evidence."""
    if not row or not tracker_uid:return None
    frame=int(frame)
    linked_ids={c.get("component_id") for c in trace
        if c.get("provider")==provider and c.get("candidate_stage")=="tracker_input"
        and int(c.get("video_frame",-1))==frame and c.get("tracker_uid")==tracker_uid
        and c.get("component_id")}
    if not linked_ids:return None
    return next((c for c in trace
        if c.get("provider")==provider and c.get("candidate_stage")=="segmentation_to_detector"
        and int(c.get("video_frame",-1))==frame and c.get("component_id") in linked_ids),None)


def nearest_same_frame(row,trace,geometry,key,provider=None):
    target=box(row.get("bbox"));
    if not target:return None
    target=native_box_to_rectified(target,geometry)
    candidates=[]
    for c in trace:
        if c.get("candidate_stage")!="segmentation_to_detector":continue
        if provider is not None and c.get("provider")!=provider:continue
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


def classify_case(match,seg_row,component,seg_action,expected_key,association_collision=None):
    if (association_collision
            and not (seg_action and seg_action.get("event")=="pressed"
                     and seg_action.get("key")==expected_key)):
        return ("ASSOCIATION_AMBIGUOUS","MEDIUM",
                "alternate_same_key_action_has_exact_frame_geometry_and_event_proximity; "
                "no_reassignment; alternate_uid="+association_collision["uid"])
    if seg_action and seg_action.get("event")=="pressed":
        if seg_action.get("key")==expected_key:return "SEGMENTED_ACTION_PRESENT","HIGH","paired_mock_down_same_key"
        if association_collision:
            return ("ASSOCIATION_AMBIGUOUS","MEDIUM",
                    "paired_uid_wrong_key; different_uid_same_key_action_has_exact_frame_geometry_and_event_proximity; "
                    "no_reassignment; alternate_uid="+association_collision["uid"])
        return "SEGMENTED_ACTION_WRONG_KEY","HIGH",f"mock_down_key={seg_action.get('key')}; expected_lane_key={expected_key}"
    if seg_action and seg_action.get("event")=="rejected":
        return "SCHEDULER_REJECTION","HIGH",seg_action.get("reason","")
    if match:
        _,uid,frames=match
        if seg_row:
            reason=seg_row.get("reason","")
            # Keep the terminal stage tied to the engine/timing reason. The
            # matched component role/conversion is emitted independently as
            # upstream evidence; neither that evidence nor the Legacy box is
            # treated as physical-note ground truth.
            if reason in OBSERVABLE_STOP_STAGES:
                return OBSERVABLE_STOP_STAGES[reason],"HIGH" if len(frames)>=3 else "MEDIUM",reason
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


def classify_at_reference_frame(match, exact_row, last_row, component, seg_action, expected_key, frame,
                                association_collision=None):
    """Classify from the target frame's evidence; never substitute a future row."""
    if seg_action:
        return classify_case(match, exact_row or last_row, component, seg_action, expected_key,
                             association_collision)
    if match and exact_row is not None:
        capture=float(exact_row.get("capture_timestamp") or exact_row.get("video_frame") or frame)
        observed=float(exact_row.get("last_observation") or capture)
        if not component or abs(observed-capture)>.001:
            return ("TRACK_ASSOCIATION_UNVERIFIED", "LOW",
                    "matched track has no fresh exact-frame tracker_uid-to-component link")
    if match and exact_row is None:
        last_frame = int(last_row["video_frame"]) if last_row else None
        if last_frame is None or last_frame < frame:
            return ("TRACK_NOT_ACTIVE_AT_REFERENCE_FRAME", "HIGH",
                    f"matched provider track has no decision at reference frame {frame}; "
                    f"last decision frame={last_frame}")
    return classify_case(match, exact_row, component, None, expected_key, association_collision)


def find_alternate_same_key_action(actions, rows_by_provider, provider, legacy_track,
                                   paired_uid, expected_key, reference_time,
                                   window=ACTION_EVENT_PROXIMITY_WINDOW_SECONDS):
    """Find a nonpaired same-key press supported by exact-frame native geometry.

    This is an ambiguity diagnostic only. It never changes the selected paired UID.
    """
    eligible = []
    for action in actions:
        uid = action.get("uid", "")
        if (action.get("provider") != provider or action.get("event") != "pressed"
                or not uid or uid == paired_uid or action.get("key") != expected_key):
            continue
        try:
            action_time = float(action.get("injection_started_at") or action.get("at"))
            decision_time = float(action.get("decision_capture_timestamp"))
        except (TypeError, ValueError):
            continue
        delta = action_time - reference_time
        if abs(delta) > window:
            continue

        candidate_rows = rows_by_provider[provider].get(uid, [])
        candidate_row = None
        for row in candidate_rows:
            try:
                capture_time = float(row.get("capture_timestamp", ""))
            except (TypeError, ValueError):
                continue
            if abs(capture_time - decision_time) <= .001:
                candidate_row = row
                break
        if candidate_row is None:
            continue
        frame = int(candidate_row["video_frame"])
        legacy_row = next((row for row in legacy_track
                           if int(row["video_frame"]) == frame), None)
        if legacy_row is None:
            continue
        try:
            candidate_capture = float(candidate_row.get("capture_timestamp", ""))
            candidate_observed = float(candidate_row.get("last_observation", ""))
            legacy_capture = float(legacy_row.get("capture_timestamp", ""))
            legacy_observed = float(legacy_row.get("last_observation", ""))
        except (TypeError, ValueError):
            continue
        if (abs(candidate_observed - candidate_capture) > .001
                or abs(legacy_observed - legacy_capture) > .001):
            continue
        candidate_box = box(candidate_row.get("bbox"))
        legacy_box = box(legacy_row.get("bbox"))
        if not candidate_box or not legacy_box:
            continue
        candidate_color = candidate_row.get("color", "")
        legacy_color = legacy_row.get("color", "")
        if not candidate_color or candidate_color == "neutral" or candidate_color != legacy_color:
            continue
        if candidate_row.get("key") != expected_key or expected_key not in (candidate_row.get("keys") or "").split("|"):
            continue
        area, _, _ = intersection(candidate_box, legacy_box)
        smaller_area = min(candidate_box[2] * candidate_box[3], legacy_box[2] * legacy_box[3])
        overlap = area / max(1., smaller_area)
        if overlap < .5:
            continue
        eligible.append({"uid": uid, "key": action.get("key", ""), "time": action_time,
                         "delta": delta, "frame": frame, "bbox": candidate_row.get("bbox", ""),
                         "color": candidate_color, "overlap": overlap})
    return max(eligible, key=lambda item: (item["overlap"], -abs(item["delta"])), default=None)


def classify_with_association_collision(match, exact_row, last_row, component, seg_action,
                                        expected_key, frame, association_collision=None):
    """Preserve the underlying diagnosis when a qualified alternate makes identity ambiguous."""
    base = classify_at_reference_frame(match, exact_row, last_row, component, seg_action,
                                       expected_key, frame)
    if not association_collision or (seg_action and seg_action.get("event") == "pressed"
                                     and seg_action.get("key") == expected_key):
        return (*base, "", "")
    reason = ("alternate_same_key_action_has_exact_frame_geometry_and_event_proximity; "
              "no_reassignment; alternate_uid=" + association_collision["uid"])
    return ("ASSOCIATION_AMBIGUOUS", "MEDIUM", reason, base[0], base[2])


def nearest_action_event(events, reference_time, window=ACTION_EVENT_PROXIMITY_WINDOW_SECONDS):
    """Return paired event plus nearest-event diagnostics (signed delta = event - reference)."""
    eligible=[e for e in events if e.get("event") in ("pressed","rejected")]
    if not eligible:
        return None, None, None, None, "NO_EVENT"
    def event_time(e):
        return float(e.get("injection_started_at") or e.get("at") or reference_time)
    nearest=min(eligible,key=lambda e:abs(event_time(e)-reference_time))
    signed=event_time(nearest)-reference_time
    absolute=abs(signed)
    if absolute <= window:
        return nearest, nearest, signed, absolute, "PAIRED_WITHIN_AUXILIARY_WINDOW"
    return None, nearest, signed, absolute, "NEAREST_EVENT_OUTSIDE_AUXILIARY_WINDOW"


def render_evidence(source,frame_no,trace,legacy_note,component,geometry,out_dir,masker,candidate_provider='segmented'):
    path=out_dir/f"frame_{frame_no:06d}.png"
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
        if b:
            rb=native_box_to_rectified(b,geometry)
            cv2.rectangle(legacy_canvas,(int(rb[0]),int(rb[1])),
                          (int(rb[0]+rb[2]),int(rb[1]+rb[3])),(0,255,255),2)
    seg_canvas=rect.copy()
    for c in trace:
        if c.get("provider")!=candidate_provider or c.get("candidate_stage")!="segmentation_to_detector" or int(c.get("video_frame",-1))!=frame_no:continue
        b=box(c.get("bbox"));
        if not b:continue
        color=colors.get(c.get("role"),(170,170,170))
        cv2.rectangle(seg_canvas,(int(b[0]),int(b[1])),(int(b[0]+b[2]),int(b[1]+b[3])),color,1)
    if component:
        b=box(component.get("bbox"));
        if b:cv2.rectangle(seg_canvas,(int(b[0]),int(b[1])),(int(b[0]+b[2]),int(b[1]+b[3])),(0,255,255),2)
    panels=[]
    for name,img in (("source + Legacy candidates",legacy_canvas),("current-pixel masks",mask),(f"{candidate_provider} component candidates",seg_canvas)):
        panel=img.copy();cv2.rectangle(panel,(0,0),(panel.shape[1],22),(0,0,0),-1)
        cv2.putText(panel,name,(5,16),cv2.FONT_HERSHEY_SIMPLEX,.42,(255,255,255),1,cv2.LINE_AA);panels.append(panel)
    out=np.concatenate(panels,axis=1);cv2.imwrite(str(path),out);return str(path)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir",type=Path,required=True)
    ap.add_argument("--replay-dir",type=Path,required=True)
    ap.add_argument("--out",type=Path,default=ROOT/"output/analysis_lane_filter_v84_rework")
    ap.add_argument('--candidate-provider',choices=('segmented','v85'),default='segmented')
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    actions=read_csv(args.replay_dir/"mock_actions.csv");decisions=read_csv(args.replay_dir/"physical_note_decisions.csv")
    trace=read_csv(args.replay_dir/"candidate_trace.csv")
    legacy_presses=[r for r in actions if r["provider"]=="legacy" and r["event"]=="pressed"]
    segmented_presses=[r for r in actions if r["provider"]==args.candidate_provider and r["event"]=="pressed"]
    candidate_events=defaultdict(list)
    for event in actions:
        if event["provider"]==args.candidate_provider and event.get("uid"):
            candidate_events[event["uid"]].append(event)
    rows_by_provider=defaultdict(lambda:defaultdict(list))
    for r in decisions:rows_by_provider[r["provider"]][r["note_uid"]].append(r)
    for group in rows_by_provider.values():
        for rr in group.values():rr.sort(key=lambda x:int(x["video_frame"]))
    seg_frame_index=defaultdict(list)
    for r in decisions:
        if r["provider"]==args.candidate_provider:seg_frame_index[int(r["video_frame"])].append(r)
    trace_by_frame=defaultdict(list)
    for r in trace:trace_by_frame[int(r["video_frame"])].append(r)
    index_rows=read_csv(args.run_dir/"live_video_index.csv")
    index_by_frame={int(r["video_frame"]):r for r in index_rows if r.get("video_frame","").isdigit()}
    evidence_dir=args.out/("action_loss_evidence_v85" if args.candidate_provider=='v85' else "action_loss_evidence_v4");evidence_dir.mkdir(exist_ok=True)
    geometry=Geometry(ROOT/"config/geometry_live_assist.json");masker=LanePixelSegmenter()
    output=[];counts=Counter();evidence_requests=defaultdict(list)
    for n,event in enumerate(legacy_presses,1):
        uid=event["uid"];legacy_track=rows_by_provider["legacy"].get(uid,[])
        key=event["key"]
        match_candidates=cross_score_candidates(legacy_track,seg_frame_index,key)
        match=(None if match_candidates and len(match_candidates)>1
               and match_candidates[0][0]==match_candidates[1][0]
               else (match_candidates[0] if match_candidates else None))
        match_uid=match[1] if match else "";matched_frames=match[2] if match else []
        cap_time=float(event.get("decision_capture_timestamp") or event["at"])
        legacy_row=min(legacy_track,key=lambda r:abs(float(r["capture_timestamp"])-cap_time)) if legacy_track else None
        seg_track=rows_by_provider[args.candidate_provider].get(match_uid,[]) if match_uid else []
        frame=int(legacy_row["video_frame"]) if legacy_row else -1
        seg_row=next((r for r in seg_track if int(r["video_frame"])==frame),None)
        last_seg_row=max((r for r in seg_track if int(r["video_frame"])<=frame),
                         key=lambda r:int(r["video_frame"]),default=None)
        frame_trace=trace_by_frame.get(frame,[]) if legacy_row else []
        spatial_component=nearest_same_frame(legacy_row,frame_trace,geometry,key,args.candidate_provider) if legacy_row else None
        component=linked_component(legacy_row,frame_trace,args.candidate_provider,match_uid,frame) if legacy_row and match_uid else None
        seg_track_events=candidate_events.get(match_uid,[]) if match_uid else []
        ref_action_time=float(event.get("injection_started_at") or event.get("at") or cap_time)
        seg_action,nearest_action,action_delta,action_abs_delta,action_pairing_status=nearest_action_event(
            seg_track_events,ref_action_time)
        association_collision=None
        if not (seg_action and seg_action.get("event")=="pressed"
                and seg_action.get("key")==key):
            association_collision=find_alternate_same_key_action(
                actions,rows_by_provider,args.candidate_provider,legacy_track,match_uid,key,ref_action_time)
        stage,confidence,reason,underlying_stage,underlying_reason=classify_with_association_collision(
            match,seg_row,last_seg_row,component,seg_action,key,frame,association_collision)
        if args.candidate_provider=='v85' and stage.startswith('SEGMENTED_'):
            stage='V85_'+stage[len('SEGMENTED_'):]
        paired=len(matched_frames)
        evidence=""
        counts[stage]+=1
        lbox=legacy_row.get("bbox","") if legacy_row else ""
        output.append({"case_id":f"legacy_action_{n:04d}","legacy_action_uid_provider_local":uid,
            "legacy_key":key,"legacy_kind":legacy_row.get("kind",event.get("kind","")) if legacy_row else event.get("kind",""),
            "video_frame":frame,"source_frame":index_by_frame.get(frame,{}).get("source_frame", ""),
            "capture_timestamp":legacy_row.get("capture_timestamp",event.get("decision_capture_timestamp","")) if legacy_row else event.get("decision_capture_timestamp",""),
            "legacy_bbox_native":lbox,"legacy_tracker_uid_provider_local":uid,
            "legacy_tracker_confirmed":legacy_row.get("confirmed","") if legacy_row else "",
            "legacy_timing_reason":legacy_row.get("reason","") if legacy_row else "",
            "candidate_provider":args.candidate_provider,
            "candidate_component_id":component.get("component_id","") if component else "",
            "candidate_component_role":component.get("role","") if component else "",
            "candidate_conversion":component.get("conversion","") if component else "",
            "candidate_component_bbox_rectified":component.get("bbox","") if component else "",
            "candidate_component_link_evidence":"provider+video_frame+tracker_uid" if component else "",
            "spatial_detection_component_id":spatial_component.get("component_id","") if spatial_component else "",
            "spatial_detection_role":spatial_component.get("role","") if spatial_component else "",
            "spatial_detection_conversion":spatial_component.get("conversion","") if spatial_component else "",
            "spatial_detection_tracker_assignment":"unassigned_or_unverified" if spatial_component else "",
            "candidate_track_pairing_ambiguous":"yes" if not match and len(match_candidates)>1 and match_candidates[0][0]==match_candidates[1][0] else "no",
            "candidate_track_pairing_candidates":"|".join(c[1] for c in match_candidates if c[0]==match_candidates[0][0]) if match_candidates and len(match_candidates)>1 and match_candidates[0][0]==match_candidates[1][0] else "",
            "candidate_tracker_uid_provider_local":match_uid,
            "candidate_tracker_bbox_native":seg_row.get("bbox","") if seg_row else "",
            "candidate_tracker_key_at_reference":seg_row.get("key","") if seg_row else "",
            "candidate_tracker_press_at_reference":seg_row.get("press_at","") if seg_row else "",
            "candidate_tracker_release_at_reference":seg_row.get("release_at","") if seg_row else "",
            "candidate_tracker_state":seg_row.get("state","") if seg_row else "",
            "candidate_timing_reason":seg_row.get("reason","") if seg_row else "",
            "candidate_track_active_at_reference_frame":"yes" if seg_row else "no" if match else "",
            "candidate_track_last_decision_frame":last_seg_row.get("video_frame","") if last_seg_row else "",
            "candidate_track_last_observation":last_seg_row.get("last_observation","") if last_seg_row else "",
            "candidate_track_last_state":last_seg_row.get("state","") if last_seg_row else "",
            "candidate_track_last_reason":last_seg_row.get("reason","") if last_seg_row else "",
            "trajectory_matched_frames":paired,"candidate_action_uid_provider_local":seg_action.get("uid","") if seg_action else "",
            "candidate_scheduler_outcome":seg_action.get("event","") if seg_action else "no_matched_scheduler_down_or_reject",
            "candidate_action_event":seg_action.get("event","") if seg_action else "",
            "candidate_action_key":seg_action.get("key","") if seg_action else "",
            "candidate_action_time":seg_action.get("injection_started_at",seg_action.get("at","")) if seg_action else "",
            "candidate_action_pairing_status":action_pairing_status,
            "candidate_action_proximity_window_seconds":ACTION_EVENT_PROXIMITY_WINDOW_SECONDS,
            "candidate_action_nearest_uid_provider_local":nearest_action.get("uid","") if nearest_action else "",
            "candidate_action_nearest_event":nearest_action.get("event","") if nearest_action else "",
            "candidate_action_nearest_key":nearest_action.get("key","") if nearest_action else "",
            "candidate_action_nearest_time":nearest_action.get("injection_started_at",nearest_action.get("at","")) if nearest_action else "",
            "candidate_action_nearest_signed_delta_seconds":action_delta if action_delta is not None else "",
            "candidate_action_nearest_absolute_delta_seconds":action_abs_delta if action_abs_delta is not None else "",
            "candidate_action_association_status":(
                "ALTERNATE_SAME_KEY_EXACT_FRAME_GEOMETRY" if association_collision else
                "PAIRED_UID_WRONG_KEY_NO_QUALIFIED_ALTERNATE" if seg_action and seg_action.get("event")=="pressed" and seg_action.get("key")!=key else
                "PAIRED_UID_ACTION" if seg_action else "NO_PAIRED_ACTION"),
            "candidate_alternate_action_uid_provider_local":association_collision["uid"] if association_collision else "",
            "candidate_alternate_action_key":association_collision["key"] if association_collision else "",
            "candidate_alternate_action_time":association_collision["time"] if association_collision else "",
            "candidate_alternate_action_delta_seconds":association_collision["delta"] if association_collision else "",
            "candidate_alternate_decision_video_frame":association_collision["frame"] if association_collision else "",
            "candidate_alternate_bbox_native":association_collision["bbox"] if association_collision else "",
            "candidate_alternate_color":association_collision["color"] if association_collision else "",
            "candidate_alternate_overlap_fraction_smaller_box":association_collision["overlap"] if association_collision else "",
            "underlying_root_cause_stage":underlying_stage,
            "underlying_attribution_reason":underlying_reason,
            "candidate_key_up":"yes" if any(e.get("event")=="released" for e in seg_track_events) else "no",
            "root_cause_stage":stage,"attribution_reason":reason,"evidence_confidence":confidence,
            "evidence_image":evidence,"interpretation":"provider UIDs are local labels only; physical match uses frame/position/key/color/downward track"})
        if frame>=0 and frame in index_by_frame:
            evidence_requests[frame].append((len(output)-1,frame_trace,legacy_row,component))
    # Decode the immutable source sequentially so each indexed video_frame is
    # paired with the same decoded frame used by replay/case-window evidence.
    source_path=args.run_dir/"live_source.mp4"
    cap=cv2.VideoCapture(str(source_path))
    if not cap.isOpened():raise RuntimeError(f"cannot open indexed source: {source_path}")
    try:
        decoded=0;last_frame=max(evidence_requests,default=-1)
        while decoded<=last_frame:
            ok,source=cap.read()
            if not ok:break
            if decoded in evidence_requests and decoded in index_by_frame:
                for row_index,frame_trace,legacy_note,component in evidence_requests[decoded]:
                    output[row_index]["evidence_image"]=render_evidence(
                        source,decoded,frame_trace,legacy_note,component,geometry,evidence_dir,masker,
                        args.candidate_provider)
            decoded+=1
    finally:
        cap.release()
    if any(not row.get("evidence_image") for row in output):
        raise RuntimeError("one or more indexed attribution evidence frames could not be decoded/rendered")
    path=args.out/"action_loss_attribution.csv"
    with path.open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(output[0]));writer.writeheader();writer.writerows(output)
    summary=args.out/"action_loss_attribution_summary.csv"
    with summary.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["root_cause_stage","action_count","fraction_of_legacy_presses"]);w.writeheader()
        for stage,count in sorted(counts.items()):w.writerow({"root_cause_stage":stage,"action_count":count,"fraction_of_legacy_presses":count/max(1,len(output))})
    def sha256(path):
        digest=hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda:handle.read(1024*1024),b""):digest.update(block)
        return digest.hexdigest()
    manifest={"status":"PROVISIONAL_VISUAL_AUDIT","physical_note_status":"UNKNOWN",
        "run_id":args.run_dir.name,"candidate_provider":args.candidate_provider,
        "source_video_sha256":sha256(source_path),
        "source_index_sha256":sha256(args.run_dir/"live_video_index.csv"),
        "frame_alignment":"sequential decode order keyed by video_frame and live_video_index.csv",
        "random_seek_used":False,"attribution_rows":len(output),
        "stage_counts":dict(counts),
            "cross_provider_identity":"same-frame geometry, lane/key, color, and motion trajectory; exact component linkage requires provider+video_frame+tracker_uid trace evidence; provider-local UIDs only query each provider's own rows"}
    (args.out/"attribution_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps({"legacy_presses":len(legacy_presses),"candidate_presses":len(segmented_presses),
        "output":str(path),"stage_counts":counts},default=dict))


if __name__=="__main__":main()
