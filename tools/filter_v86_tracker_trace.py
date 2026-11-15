"""Reduce the opt-in tracker trace to source-frame action-loss neighborhoods."""
from __future__ import annotations
import argparse
import csv
import json
import sys
from collections import Counter,defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.model import Geometry


def bbox(value):
    try:
        parsed=json.loads(value.replace("(","[").replace(")","]")) if isinstance(value,str) else value
        return tuple(float(v) for v in parsed[:4])
    except (ValueError,TypeError,IndexError):return None


def rectified_x(geometry,native_x,y):
    boundaries=geometry.boundaries(y)
    return float(__import__("numpy").interp(native_x,boundaries,
        __import__("numpy").linspace(0,geometry.plane_width,7)))


def near(box,target,geometry,margin_x,margin_y):
    if box is None:return False
    x,y,w,h=box
    tx,ty,tw,th=target["native_bbox"]
    cy=ty+th/2
    target_left=rectified_x(geometry,tx,cy)
    target_right=rectified_x(geometry,tx+tw,cy)
    cx=x+w/2
    return (target_left-margin_x <= cx <= target_right+margin_x and
            ty-margin_y <= y+h/2 <= ty+th+margin_y)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trace",type=Path,required=True)
    ap.add_argument("--attribution",type=Path,nargs="+",required=True)
    ap.add_argument("--geometry",type=Path,default=Path("config/geometry_live_assist.json"))
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--margin-x",type=float,default=24.)
    ap.add_argument("--margin-y",type=float,default=64.)
    args=ap.parse_args();geometry=Geometry(args.geometry)
    targets=defaultdict(list)
    for path in args.attribution:
        with path.open(encoding="utf-8-sig",newline="") as f:
            for row in csv.DictReader(f):
                box=bbox(row.get("legacy_bbox_native"))
                if box is None:continue
                key=(row.get("candidate_provider", ""),int(row["video_frame"]))
                targets[key].append({"case_id":row.get("case_id",""),"attribution_file":str(path),
                    "reference_stage":row.get("root_cause_stage",""),"reference_reason":row.get("attribution_reason",""),
                    "reference_confidence":row.get("evidence_confidence",""),"native_bbox":box,
                    "legacy_key":row.get("legacy_key",""),"legacy_kind":row.get("legacy_kind","")})
    args.out.parent.mkdir(parents=True,exist_ok=True)
    counts=Counter();provider_map={"segmented":"segmented","v85":"v85"}
    with args.trace.open(encoding="utf-8-sig",newline="") as src, args.out.open("w",encoding="utf-8",newline="") as dst:
        reader=csv.DictReader(src)
        writer=None
        for row in reader:
            provider=row.get("provider","")
            attribution_provider=provider_map.get(provider)
            if not attribution_provider:continue
            key=(attribution_provider,int(row.get("video_frame",-1)))
            cases=targets.get(key,())
            if not cases:continue
            detbox=bbox(row.get("detection_bbox") or row.get("bbox"))
            capbox=bbox(row.get("prior_bbox"))
            for case in cases:
                if not (near(detbox,case,geometry,args.margin_x,args.margin_y) or
                        near(capbox,case,geometry,args.margin_x,args.margin_y)):
                    continue
                output={**case,"provider":provider,**row}
                if writer is None:
                    writer=csv.DictWriter(dst,fieldnames=list(output),extrasaction="ignore")
                    writer.writeheader()
                writer.writerow(output)
                counts[(provider,row.get("trace_type",""),row.get("edge_reason","") or row.get("outcome",""))]+=1
    summary={"trace_source":str(args.trace),"attribution_sources":[str(p) for p in args.attribution],
        "trace_output":str(args.out),"rows_by_provider_trace_reason":{
            "|".join(k):v for k,v in sorted(counts.items())},"physical_note_ground_truth":"UNKNOWN",
        "interpretation":"Spatially filtered diagnostics only; this does not establish physical-note identity or truth."}
    args.out.with_name(args.out.stem+"_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(f"rows={sum(counts.values())} output={args.out}")


if __name__=="__main__":main()
