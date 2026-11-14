"""Compare manually polygon-labeled source frames with rectified pixel masks."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import sys
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.model import Geometry  # noqa:E402

ROLE_CHANNEL={"TAP_FACE":"tap_face","HOLD_HEAD":"hold_head","HOLD_BODY":"hold_body",
              "HOLD_TAIL":"hold_tail","EFFECT":"effect_or_artifact","UNKNOWN":"unknown"}


def scores(truth,pred):
    tp=int(np.count_nonzero(truth&pred));fp=int(np.count_nonzero(~truth&pred));fn=int(np.count_nonzero(truth&~pred))
    return {"tp":tp,"fp":fp,"fn":fn,"precision":tp/(tp+fp) if tp+fp else None,
            "recall":tp/(tp+fn) if tp+fn else None,"iou":tp/(tp+fp+fn) if tp+fp+fn else None}


def object_counts(truth_ids,role_ids,pred_mask):
    truth_instances=[truth_ids==ident for ident in role_ids]
    count,labels,stats,_=cv2.connectedComponentsWithStats(pred_mask.astype(np.uint8),8)
    # Keep one-pixel components in the object denominator.  A tiny artifact is
    # still a false object proposal; suppressing it here hides thin-line noise.
    predictions=[labels==i for i in range(1,count) if int(stats[i,cv2.CC_STAT_AREA])>=1]
    candidates=[]
    for ti,tmask in enumerate(truth_instances):
        for pi,pmask in enumerate(predictions):
            union=np.count_nonzero(tmask|pmask)
            iou=np.count_nonzero(tmask&pmask)/union if union else 0.
            if iou>=.5:candidates.append((iou,ti,pi))
    used_t=set();used_p=set()
    for _,ti,pi in sorted(candidates,reverse=True):
        if ti not in used_t and pi not in used_p:used_t.add(ti);used_p.add(pi)
    tp=len(used_t);fp=len(predictions)-tp;fn=len(truth_instances)-tp
    return {"object_tp":tp,"object_fp":fp,"object_fn":fn,
            "object_precision":tp/(tp+fp) if tp+fp else None,
            "object_recall":tp/(tp+fn) if tp+fn else None,
            "object_iou_threshold":.5}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--annotations",type=Path,required=True,help="directory containing reviewed frame_N_labels.json/.npy")
    ap.add_argument("--rendered-run",type=Path,required=True,help="run directory containing review_frames/*_masks.npz")
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    geometry=Geometry(ROOT/"config/geometry_live_assist.json")
    files=sorted(args.annotations.glob("frame_*_labels.json"))
    if not files:raise SystemExit("no reviewed annotation JSON files found; no metrics generated")
    rows=[];all_counts={role:{"tp":0,"fp":0,"fn":0,"object_tp":0,"object_fp":0,"object_fn":0} for role in ROLE_CHANNEL}
    owner_true=owner_total=0
    for path in files:
        ann=json.loads(path.read_text(encoding="utf-8"))
        if ann.get("review_status") not in ("REVIEWED","HUMAN_REVIEWED"):
            continue
        frame=int(ann["video_frame"]);truth_ids=np.load(path.with_suffix(".npy"))
        candidates=list(args.rendered_run.glob(f"review_frames/frame_{frame:06d}_*_masks.npz"))
        if len(candidates)!=1:raise FileNotFoundError(f"expected one candidate mask NPZ for frame {frame}; found {len(candidates)}")
        pred=np.load(candidates[0]);truth_rect=geometry.rectify(truth_ids)
        truth_rect=np.rint(truth_rect).astype(np.int32)
        class_ids={int(item["instance_id"].split("-")[-1]):item["class"] for item in ann["instances"]}
        for role,channel in ROLE_CHANNEL.items():
            role_ids=[i for i,c in class_ids.items() if c==role]
            truth=np.isin(truth_rect,role_ids)
            prediction=pred[channel]>0
            metric=scores(truth,prediction)
            objects=object_counts(truth_rect,role_ids,prediction)
            for key in ("tp","fp","fn"):all_counts[role][key]+=metric[key]
            for key in ("object_tp","object_fp","object_fn"):all_counts[role][key]+=objects[key]
            rows.append({"run_id":ann["run_id"],"video_frame":frame,"source_frame":ann["source_frame"],
                         "capture_timestamp":ann["capture_timestamp"],"physical_class":role,"channel":channel,**metric,**objects})
        for item in ann["instances"]:
            if item.get("class") in ("HOLD_HEAD","HOLD_TAIL") and item.get("head_tail_owner") not in (None,"UNKNOWN"):
                owner_total+=1
                # Owner topology metrics require instance-level candidate matching,
                # not merely a positive pixel overlap; keep a separate reported denominator.
                if item.get("candidate_owner_id")==item["head_tail_owner"]:owner_true+=1
    if not rows:raise SystemExit("annotation files exist but none are marked REVIEWED; no metrics generated")
    with (args.out/"pixel_metrics_by_frame.csv").open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    aggregate={}
    for role,c in all_counts.items():
        tp,fp,fn=c["tp"],c["fp"],c["fn"]
        aggregate[role]={**c,"precision":tp/(tp+fp) if tp+fp else None,
                         "recall":tp/(tp+fn) if tp+fn else None,"iou":tp/(tp+fp+fn) if tp+fp+fn else None,
                         "object_precision":c["object_tp"]/(c["object_tp"]+c["object_fp"]) if c["object_tp"]+c["object_fp"] else None,
                         "object_recall":c["object_tp"]/(c["object_tp"]+c["object_fn"]) if c["object_tp"]+c["object_fn"] else None}
    report={"reviewed_frames":len({r["video_frame"] for r in rows}),"per_class_pixel_metrics":aggregate,
            "hold_owner_accuracy":owner_true/owner_total if owner_total else "NOT_EVALUABLE_NO_MATCHED_OWNER_IDS",
            "owner_denominator":owner_total,"annotation_review_status":"reviewed_only",
            "warning":"A small selected-frame sample is not whole-run recall or generalization."}
    (args.out/"pixel_metrics.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(args.out)


if __name__=="__main__":main()
