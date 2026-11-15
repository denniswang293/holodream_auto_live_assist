"""Summarize exact-frame Tracker evidence for each Legacy-action attribution."""
from __future__ import annotations
import argparse
import csv
import json
from collections import Counter,defaultdict
from pathlib import Path


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--attribution",type=Path,nargs="+",required=True)
    ap.add_argument("--trace",type=Path,required=True,
                    help="spatially filtered output from filter_v86_tracker_trace.py")
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    cases={}
    for path in args.attribution:
        with path.open(encoding="utf-8-sig",newline="") as f:
            for row in csv.DictReader(f):
                key=(str(path),row.get("case_id",""))
                row["_attribution_file"]=str(path)
                cases[key]=row
    edge_reasons=defaultdict(Counter);edge_status=defaultdict(Counter);matched_track_status=defaultdict(Counter)
    outcomes=defaultdict(Counter);component_outcome=defaultdict(dict);matched_track_edges=defaultdict(Counter)
    target_component_edges=defaultdict(Counter);target_component_target_track_edges=defaultdict(Counter)
    with args.trace.open(encoding="utf-8-sig",newline="") as f:
        for row in csv.DictReader(f):
            key=(row.get("attribution_file",""),row.get("case_id",""))
            case=cases.get(key)
            if not case:continue
            if row.get("trace_type")=="association_edge":
                edge_reasons[key][row.get("edge_reason","")]+=1
                edge_status[key][row.get("assignment_status","")]+=1
                uid=case.get("candidate_tracker_uid_provider_local","")
                if uid and row.get("prior_note_uid")==uid:
                    matched_track_edges[key][row.get("edge_reason","")]+=1
                    matched_track_status[key][row.get("assignment_status","")]+=1
                target_ids={case.get("candidate_component_id", ""),case.get("spatial_detection_component_id", "")}-{"",None}
                if row.get("component_id","") in target_ids:
                    target_component_edges[key][row.get("edge_reason","")+"|"+row.get("assignment_status","")]+=1
                    if uid and row.get("prior_note_uid")==uid:
                        target_component_target_track_edges[key][row.get("edge_reason","")+"|"+row.get("assignment_status","")]+=1
            elif row.get("trace_type")=="detection_outcome":
                outcome=row.get("outcome","")
                outcomes[key][outcome]+=1
                ids={case.get("candidate_component_id","") ,case.get("spatial_detection_component_id","")}
                if row.get("component_id","") in ids-{"",None}:
                    component_outcome[key][row.get("component_id","")]=(outcome,row.get("cap_uid",""),
                        row.get("note_uid",""),row.get("confirmed",""),row.get("bbox",""))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    fields=["attribution_file","case_id","candidate_provider","video_frame","legacy_key","legacy_kind",
        "legacy_bbox_native","root_cause_stage","evidence_confidence","candidate_component_id",
        "candidate_component_role","candidate_conversion","candidate_component_bbox_rectified",
        "spatial_detection_component_id","spatial_detection_role","spatial_detection_conversion",
        "candidate_tracker_uid_provider_local","candidate_tracker_bbox_native","candidate_track_last_observation",
        "candidate_track_last_decision_frame","candidate_track_last_reason","candidate_track_last_state",
        "target_component_outcome","target_component_cap_uid","target_component_note_uid","target_component_confirmed",
        "exact_candidate_track_edge_reasons","all_nearby_edge_reasons","nearby_assignment_status_counts",
        "exact_candidate_track_assignment_status_counts",
        "target_component_edge_reason_and_assignment",
        "target_component_candidate_track_edge_reason_and_assignment",
        "nearby_detection_outcome_counts","tracker_attribution_refinement","physical_note_ground_truth"]
    with args.out.open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for key,row in cases.items():
            target=component_outcome.get(key,{})
            uid=row.get("candidate_tracker_uid_provider_local","")
            exact=matched_track_edges.get(key,Counter())
            target_rows=target.get(row.get("spatial_detection_component_id","") or row.get("candidate_component_id",""),())
            refinement="UNRESOLVED"
            target_edges=target_component_edges.get(key,Counter())
            target_track_edges=target_component_target_track_edges.get(key,Counter())
            if target_track_edges:
                statuses="|".join(target_track_edges)
                if "|selected" in statuses:refinement="EXACT_COMPONENT_MATCHED_CANDIDATE_TRACK"
                elif "|ambiguous_detection" in statuses:refinement="EXACT_COMPONENT_AMBIGUOUS_FOR_CANDIDATE_TRACK"
                elif "|lost_global_assignment_competition" in statuses:refinement="EXACT_COMPONENT_LOST_CANDIDATE_TRACK_ASSIGNMENT"
                elif "|cost_at_or_above_unmatched" in statuses:refinement="EXACT_COMPONENT_CANDIDATE_TRACK_COST_TOO_HIGH"
                else:refinement="EXACT_COMPONENT_CANDIDATE_TRACK_HARD_GATE_REJECTED"
            elif target_edges:
                statuses="|".join(target_edges)
                if "|selected" in statuses:refinement="EXACT_COMPONENT_MATCHED_EXISTING_TRACK"
                elif "|ambiguous_detection" in statuses:refinement="EXACT_COMPONENT_ASSOCIATION_AMBIGUOUS"
                elif "|lost_global_assignment_competition" in statuses:refinement="EXACT_COMPONENT_LOST_GLOBAL_ASSIGNMENT"
                elif "|cost_at_or_above_unmatched" in statuses:refinement="EXACT_COMPONENT_COST_AT_OR_ABOVE_UNMATCHED"
                else:refinement="EXACT_COMPONENT_HARD_GATE_REJECTED"
            elif row.get("spatial_detection_component_id") and row.get("spatial_detection_conversion") not in ("accepted", ""):
                refinement="SPATIAL_COMPONENT_DROPPED_BEFORE_TRACKER_INPUT"
            elif target_rows and target_rows[0]=="matched_existing_cap":
                if uid and target_rows[2]==uid:refinement="SPATIAL_COMPONENT_MATCHED_CANDIDATE_TRACK"
                else:refinement="SPATIAL_COMPONENT_ASSIGNED_OTHER_NOTE_UID_PHYSICAL_LINK_UNVERIFIED"
            elif target_rows and target_rows[0]=="born_new_cap":
                refinement="SPATIAL_COMPONENT_BORN_NEW_CAP_PHYSICAL_LINK_UNVERIFIED"
            elif target_rows and target_rows[0]=="ambiguous_unassigned":
                refinement="SPATIAL_COMPONENT_AMBIGUOUS_UNASSIGNED"
            elif exact:
                refinement="NEARBY_TRACK_EDGES_RECORDED_TARGET_COMPONENT_UNLINKED"
            else:
                try:
                    gap=float(row.get("capture_timestamp",""))-float(row.get("candidate_track_last_observation",""))
                except (ValueError,TypeError):gap=None
                if uid and gap is not None and gap>.24:
                    refinement="TRACK_OUTSIDE_240MS_ASSOCIATION_WINDOW"
            writer.writerow({"attribution_file":key[0],"case_id":key[1],
                "candidate_provider":row.get("candidate_provider",""),"video_frame":row.get("video_frame",""),
                "legacy_key":row.get("legacy_key",""),"legacy_kind":row.get("legacy_kind",""),
                "legacy_bbox_native":row.get("legacy_bbox_native",""),
                "root_cause_stage":row.get("root_cause_stage",""),"evidence_confidence":row.get("evidence_confidence",""),
                "candidate_component_id":row.get("candidate_component_id",""),
                "candidate_component_role":row.get("candidate_component_role",""),
                "candidate_conversion":row.get("candidate_conversion",""),
                "candidate_component_bbox_rectified":row.get("candidate_component_bbox_rectified",""),
                "spatial_detection_role":row.get("spatial_detection_role",""),
                "spatial_detection_conversion":row.get("spatial_detection_conversion",""),
                "candidate_tracker_uid_provider_local":uid,
                "candidate_tracker_bbox_native":row.get("candidate_tracker_bbox_native",""),
                "candidate_track_last_observation":row.get("candidate_track_last_observation",""),
                "candidate_track_last_decision_frame":row.get("candidate_track_last_decision_frame",""),
                "candidate_track_last_reason":row.get("candidate_track_last_reason",""),
                "candidate_track_last_state":row.get("candidate_track_last_state",""),
                "spatial_detection_component_id":row.get("spatial_detection_component_id",""),
                "target_component_outcome":target_rows[0] if target_rows else "",
                "target_component_cap_uid":target_rows[1] if target_rows else "",
                "target_component_note_uid":target_rows[2] if target_rows else "",
                "target_component_confirmed":target_rows[3] if target_rows else "",
                "exact_candidate_track_edge_reasons":";".join(f"{k}:{v}" for k,v in sorted(exact.items())),
                "all_nearby_edge_reasons":";".join(f"{k}:{v}" for k,v in sorted(edge_reasons[key].items())),
                "nearby_assignment_status_counts":";".join(f"{k}:{v}" for k,v in sorted(edge_status[key].items())),
                "exact_candidate_track_assignment_status_counts":";".join(f"{k}:{v}" for k,v in sorted(matched_track_status[key].items())),
                "target_component_edge_reason_and_assignment":";".join(f"{k}:{v}" for k,v in sorted(target_edges.items())),
                "target_component_candidate_track_edge_reason_and_assignment":";".join(f"{k}:{v}" for k,v in sorted(target_track_edges.items())),
                "nearby_detection_outcome_counts":";".join(f"{k}:{v}" for k,v in sorted(outcomes[key].items())),
                "tracker_attribution_refinement":refinement,"physical_note_ground_truth":"UNKNOWN"})
    print(f"cases={len(cases)} out={args.out}")


if __name__=="__main__":main()
