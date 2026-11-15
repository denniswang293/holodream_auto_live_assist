"""Build a bounded tracker-diagnostic frame list from attribution CSVs."""
from __future__ import annotations
import argparse
import csv
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attribution",type=Path,nargs="+",required=True)
    parser.add_argument("--radius",type=int,default=3,
                        help="include this many source frames before and after each target frame")
    parser.add_argument("--frame-count",type=int,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--provider",help="keep attribution rows whose candidate_provider matches")
    parser.add_argument("--root-stage",help="keep attribution rows with this root_cause_stage")
    parser.add_argument("--spatial-role",help="keep rows with this spatial_detection_role")
    parser.add_argument("--spatial-conversion",help="keep rows with this spatial_detection_conversion")
    args=parser.parse_args()
    if args.radius<0 or args.frame_count<=0:parser.error("radius must be >=0 and frame-count must be >0")
    frames=set()
    cases=0
    for path in args.attribution:
        with path.open(encoding="utf-8-sig",newline="") as stream:
            for row in csv.DictReader(stream):
                if args.provider and row.get("candidate_provider")!=args.provider:continue
                if args.root_stage and row.get("root_cause_stage")!=args.root_stage:continue
                if args.spatial_role and row.get("spatial_detection_role")!=args.spatial_role:continue
                if args.spatial_conversion and row.get("spatial_detection_conversion")!=args.spatial_conversion:continue
                try:frame=int(row["video_frame"])
                except (KeyError,TypeError,ValueError):continue
                cases+=1
                frames.update(range(max(0,frame-args.radius),min(args.frame_count,frame+args.radius+1)))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text("# Derived from attribution target frames; radius={} frames; source_cases={}\n".format(args.radius,cases)+
        "".join(f"{frame}\n" for frame in sorted(frames)),encoding="utf-8")
    print(f"target_cases={cases} trace_frames={len(frames)} out={args.out}")


if __name__=="__main__":main()
