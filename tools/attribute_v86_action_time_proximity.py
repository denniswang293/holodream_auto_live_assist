"""Add posthoc cross-provider key/time proximity to action-loss cases.

This is an auxiliary replay diagnostic only. It does not assign physical-note
identity and is not a game-hit or note-recall metric.
"""
from __future__ import annotations
import argparse
import csv
from collections import defaultdict
from pathlib import Path


def read_rows(path):
    with path.open(encoding="utf-8-sig",newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--attribution",type=Path,nargs="+",required=True)
    ap.add_argument("--actions",type=Path,required=True)
    ap.add_argument("--tolerance-ms",type=float,default=80.)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    if args.tolerance_ms<0:ap.error("tolerance-ms must be non-negative")
    actions=read_rows(args.actions);legacy={};candidate=defaultdict(list)
    for row in actions:
        if row.get("event")!="pressed":continue
        try:t=float(row["injection_started_at"])
        except (KeyError,ValueError,TypeError):continue
        if row.get("provider")=="legacy":legacy[row.get("uid","")]=(t,row)
        else:candidate[row.get("provider","")].append((t,row))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    fields=["attribution_file","case_id","candidate_provider","video_frame","legacy_action_uid_provider_local",
        "legacy_key","root_cause_stage","attribution_reason","evidence_confidence","legacy_mock_press_at","candidate_tracker_uid_provider_local",
        "candidate_action_uid_provider_local","candidate_exact_uid_action_at","same_key_candidate_actions_within_tolerance",
        "any_key_candidate_actions_within_tolerance","nearest_same_key_delta_ms","tolerance_ms",
        "diagnostic_interpretation","physical_note_ground_truth"]
    with args.out.open("w",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for path in args.attribution:
            for row in read_rows(path):
                provider=row.get("candidate_provider","")
                uid=row.get("legacy_action_uid_provider_local","")
                legacy_entry=legacy.get(uid)
                t0,legacy_event=legacy_entry if legacy_entry else (None,{})
                nearby=[]
                if t0 is not None:
                    nearby=[(t,event) for t,event in candidate.get(provider,())
                        if abs(t-t0)<=args.tolerance_ms/1000]
                same_key=[(t,event) for t,event in nearby if event.get("key")==row.get("legacy_key")]
                exact_uid=row.get("candidate_action_uid_provider_local","")
                exact=next((t for t,event in candidate.get(provider,()) if exact_uid and event.get("uid")==exact_uid),None)
                nearest=min((abs(t-t0)*1000 for t,_ in same_key),default=None) if t0 is not None else None
                writer.writerow({"attribution_file":str(path),"case_id":row.get("case_id",""),
                    "candidate_provider":provider,"video_frame":row.get("video_frame",""),
                    "legacy_action_uid_provider_local":uid,"legacy_key":row.get("legacy_key",""),
                    "root_cause_stage":row.get("root_cause_stage",""),"attribution_reason":row.get("attribution_reason",""),
                    "evidence_confidence":row.get("evidence_confidence",""),
                    "legacy_mock_press_at":t0 if t0 is not None else "",
                    "candidate_tracker_uid_provider_local":row.get("candidate_tracker_uid_provider_local",""),
                    "candidate_action_uid_provider_local":exact_uid,
                    "candidate_exact_uid_action_at":exact if exact is not None else "",
                    "same_key_candidate_actions_within_tolerance":";".join(
                        f"{event.get('uid','')}@{t:.9f}" for t,event in same_key),
                    "any_key_candidate_actions_within_tolerance":";".join(
                        f"{event.get('key','')}:{event.get('uid','')}@{t:.9f}" for t,event in nearby),
                    "nearest_same_key_delta_ms":nearest if nearest is not None else "",
                    "tolerance_ms":args.tolerance_ms,
                    "diagnostic_interpretation":"posthoc cross-provider key/time proximity only; no physical identity, game-hit, or note-recall claim",
                    "physical_note_ground_truth":"UNKNOWN"})
    print(f"cases={sum(1 for path in args.attribution for _ in read_rows(path))} out={args.out}")


if __name__=="__main__":main()
