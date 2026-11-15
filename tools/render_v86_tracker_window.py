"""Render a sequential source/mask contact sheet for a tracked ambiguity."""
from __future__ import annotations
import argparse
import ast
import csv
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.early_perception import EarlyPixelProvider
from src.model import Geometry


def sha(path):
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):digest.update(chunk)
    return digest.hexdigest()


def read_index(path):
    with path.open(encoding="utf-8-sig",newline="") as f:
        return {int(row["video_frame"]):row for row in csv.DictReader(f)}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir",type=Path,required=True)
    ap.add_argument("--candidate-trace",type=Path,required=True)
    ap.add_argument("--target-frame",type=int,required=True)
    ap.add_argument("--radius",type=int,default=4)
    ap.add_argument("--uids",nargs="+",default=["note:100","note:137"])
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--roi",type=int,nargs=4,default=(180,200,360,360),metavar=("X1","Y1","X2","Y2"))
    args=ap.parse_args()
    if args.radius<0 or args.radius>4:ap.error("radius must be between 0 and 4 for the 3x3 contact sheet")
    run_dir=args.run_dir.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    start=max(0,args.target_frame-args.radius);end=args.target_frame+args.radius
    target_rows={}
    with args.candidate_trace.open(encoding="utf-8-sig",newline="") as f:
        for row in csv.DictReader(f):
            if row.get("provider")!="v85" or row.get("candidate_stage")!="tracker_input":continue
            frame=int(row.get("video_frame",-1))
            if start<=frame<=end and row.get("tracker_uid") in args.uids:
                target_rows.setdefault(frame,[]).append(row)
    index=read_index(run_dir/"live_video_index.csv")
    geometry=Geometry(ROOT/"config/geometry_live_assist.json",plane_width=360)
    provider=EarlyPixelProvider(geometry,birth_zone_end_y=176.75)
    video=run_dir/"live_source.mp4";cap=cv2.VideoCapture(str(video))
    if not cap.isOpened():raise RuntimeError(f"cannot open {video}")
    frames=[];timeline=[];decoded=0
    colors={uid:tuple(int(v) for v in color) for uid,color in zip(args.uids,((255,80,40),(40,220,255)))}
    while decoded<=end:
        ok,image=cap.read()
        if not ok:break
        if decoded>=start:
            idx=index.get(decoded)
            if idx is None:raise ValueError(f"video frame {decoded} missing from live_video_index.csv")
            normalized=geometry.normalize(image)
            provider.detect(normalized)
            rect=provider.last_rect.copy();mask=np.zeros_like(rect)
            role_colors={"tap_face":(45,220,70),"hold_head":(0,220,255),"hold_body":(255,120,20),
                "hold_tail":(220,40,220),"unknown":(150,150,150),"effect_or_artifact":(0,0,255),
                "judgment_line":(255,255,0)}
            for role,color in role_colors.items():mask[provider.last_result.masks[role]>0]=color
            x1,y1,x2,y2=args.roi
            rect_crop=rect[y1:y2,x1:x2].copy();mask_crop=mask[y1:y2,x1:x2].copy()
            labels=[]
            for row in target_rows.get(decoded,[]):
                try:x,y,w,h=ast.literal_eval(row["bbox"])
                except (ValueError,SyntaxError,KeyError):continue
                uid=row["tracker_uid"];color=colors.get(uid,(255,255,255))
                p1=(max(0,x-x1),max(0,y-y1));p2=(min(x2-x1,x+w-x1),min(y2-y1,y+h-y1))
                cv2.rectangle(rect_crop,p1,p2,color,2)
                cv2.rectangle(mask_crop,p1,p2,color,1)
                labels.append(f"{uid} c{row.get('component_id')} {row.get('role')}/{row.get('kind')} {row.get('tracker_reason')}")
            scale=2
            rect_crop=cv2.resize(rect_crop,None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST)
            mask_crop=cv2.resize(mask_crop,None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST)
            pane_w,pane_h=rect_crop.shape[1],rect_crop.shape[0]
            tile=np.zeros((pane_h+58,pane_w*2,3),np.uint8)
            tile[58:58+pane_h,:pane_w]=rect_crop;tile[58:58+pane_h,pane_w:]=mask_crop
            rel=float(idx["capture_timestamp"])-float(index[min(index)]["capture_timestamp"])
            cv2.putText(tile,f"video_frame={decoded} source_frame={idx.get('source_frame',decoded)} t={rel:.3f}s",
                (5,22),cv2.FONT_HERSHEY_SIMPLEX,.48,(255,255,255),1,cv2.LINE_AA)
            cv2.putText(tile,"rectified source crop",(5,47),cv2.FONT_HERSHEY_SIMPLEX,.42,(255,255,255),1,cv2.LINE_AA)
            cv2.putText(tile,"current-frame role masks",(pane_w+5,47),cv2.FONT_HERSHEY_SIMPLEX,.42,(255,255,255),1,cv2.LINE_AA)
            status=" | ".join(labels) if labels else "target UID has no current tracker-input row"
            cv2.putText(tile,status[:125],(5,pane_h+53),cv2.FONT_HERSHEY_SIMPLEX,.36,(220,220,220),1,cv2.LINE_AA)
            frames.append(tile)
            timeline.append({"video_frame":decoded,"source_frame":idx.get("source_frame",decoded),
                "capture_timestamp":idx["capture_timestamp"],"acquired_timestamp":idx["acquired_timestamp"],
                "candidate_uids_observed":"|".join(row["tracker_uid"] for row in target_rows.get(decoded,[])),
                "candidate_rows":";".join(f"{row.get('tracker_uid')}:{row.get('component_id')}:{row.get('bbox')}:{row.get('role')}:{row.get('tracker_reason')}" for row in target_rows.get(decoded,[]))})
        decoded+=1
    cap.release()
    if not frames:raise RuntimeError("target window contains no decodable source frames")
    blank=np.zeros_like(frames[0]);frames.extend([blank]*(9-len(frames)))
    grid=np.vstack([np.hstack(frames[row:row+3]) for row in range(0,9,3)])
    image_path=out/"contact_sheet.png"
    if not cv2.imwrite(str(image_path),grid):raise RuntimeError(f"failed to write {image_path}")
    with (out/"timeline.csv").open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(timeline[0]));writer.writeheader();writer.writerows(timeline)
    manifest={"target_frame":args.target_frame,"frame_range":[start,min(end,decoded-1)],"frames_rendered":len(timeline),
        "uids":args.uids,"roi_rectified_pixels":args.roi,"source_video_sha256":sha(video),
        "source_index_sha256":sha(run_dir/"live_video_index.csv"),"candidate_trace_sha256":sha(args.candidate_trace),
        "decode":"sequential from frame 0; no random seek","labels":"PROVISIONAL_VISUAL_AUDIT; physical identity UNKNOWN",
        "outputs":[image_path.name,"timeline.csv"]}
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(out)


if __name__=="__main__":main()
