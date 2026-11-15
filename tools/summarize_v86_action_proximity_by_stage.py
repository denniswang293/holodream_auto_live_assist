"""Summarize auxiliary cross-provider action proximity by Tracker-stage evidence."""
from __future__ import annotations
import argparse
import csv
from pathlib import Path


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--proximity",type=Path,required=True)
    ap.add_argument("--tracker-cases",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    def norm(value):return value.replace("\\","/")
    tracker={}
    with args.tracker_cases.open(encoding="utf-8-sig",newline="") as f:
        for row in csv.DictReader(f):tracker[(norm(row["attribution_file"]),row["case_id"])]=row
    # Keep named counters to avoid overloading one integer with several metrics.
    counts={}
    with args.proximity.open(encoding="utf-8-sig",newline="") as f:
        for row in csv.DictReader(f):
            key=(norm(row["attribution_file"]),row["case_id"])
            stage=tracker.get(key,{}).get("tracker_attribution_refinement","NOT_IN_TRACKER_TRACE")
            group=(row.get("candidate_provider",""),row.get("root_cause_stage",""),stage)
            item=counts.setdefault(group,{"cases":0,"same_key_within_tolerance":0,"any_key_within_tolerance":0})
            item["cases"]+=1
            item["same_key_within_tolerance"]+=bool(row.get("same_key_candidate_actions_within_tolerance"))
            item["any_key_within_tolerance"]+=bool(row.get("any_key_candidate_actions_within_tolerance"))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open("w",encoding="utf-8",newline="") as f:
        fields=["candidate_provider","root_cause_stage","tracker_attribution_refinement","cases",
            "same_key_within_tolerance","any_key_within_tolerance","physical_note_ground_truth"]
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for group,item in sorted(counts.items()):writer.writerow({
            "candidate_provider":group[0],"root_cause_stage":group[1],
            "tracker_attribution_refinement":group[2],**item,"physical_note_ground_truth":"UNKNOWN"})
    print(f"groups={len(counts)} out={args.out}")


if __name__=="__main__":main()
