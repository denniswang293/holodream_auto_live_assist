"""Build deterministic, explicitly provisional V2 cross-run review artifacts."""
from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

import cv2
import numpy as np

from tools.geometry_scene.review_samples import segment


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "output" / "geometry_scene_v2"


def read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main():
    runs = sorted(p for p in (BASE / "runs").iterdir() if p.is_dir())
    uncertain = []
    profile = []
    by_stage = {}
    for run in runs:
        run_id = run.name
        tracks = read_csv(run / "track_audit.csv")
        for t in tracks:
            if t["kind"].upper() == "UNKNOWN" or "AMBIGUOUS" in (t["kind_status"] + t["reason"]).upper():
                uncertain.append({"run_id": run_id, **t,
                                  "review_status": "AUTO_VISUAL_REVIEWED_PROVISIONAL",
                                  "truth_status": "UNKNOWN_NOT_HUMAN_REVIEWED"})
        stage_rows = read_csv(run / "profile_stages.csv")
        for s in stage_rows:
            row = {"run_id": run_id, **s}
            by_stage.setdefault(s["stage"], []).append(row)
    uncertain_fields = ["run_id", "scene_note_id", "kind", "kind_status", "reason", "confidence", "track_status", "source_color", "observations", "first_frame", "last_frame", "first_acquired_elapsed", "last_acquired_elapsed", "first_bbox", "last_bbox", "head_status", "body_status", "tail_status", "review_status", "truth_status"]
    write_csv(BASE / "uncertain_candidates.csv", uncertain_fields, uncertain)
    # Stage rows retain their original per-run sample counts. Aggregate columns are medians
    # over run-level stage statistics, never pooled sample-level estimates.
    fields = ["run_id", "stage", "samples", "mean_ms", "p50_ms", "p95_ms", "max_ms", "runs_in_median", "median_run_mean_ms", "median_run_p50_ms", "median_run_p95_ms", "median_run_max_ms", "sample_semantics"]
    for stage, rows in sorted(by_stage.items()):
        cols = ["mean_ms", "p50_ms", "p95_ms", "max_ms"]
        med = {c: statistics.median(float(x[c]) for x in rows) for c in cols}
        for r in rows:
            profile.append({**r, "runs_in_median": len(rows),
                            "median_run_mean_ms": med["mean_ms"], "median_run_p50_ms": med["p50_ms"],
                            "median_run_p95_ms": med["p95_ms"], "median_run_max_ms": med["max_ms"],
                            "sample_semantics": "per-frame stages: samples are frames; temporal_association_ms: samples is one whole-run association measurement" if r["stage"] == "temporal_association_ms" else "per-frame stage samples; medians aggregate per-run statistics"})
    write_csv(BASE / "processing_profile.csv", fields, profile)

    index = read_csv(BASE / "frame_index.csv")
    inventory = {r["run_id"]: r for r in read_csv(BASE / "inventory.csv")}
    summaries = {}
    for run in runs:
        run_id = run.name
        rows = [r for r in index if r["run_id"] == run_id]
        # Sort by source-frame number; select nearest rank at 5%, 50%, and 95%.
        rows.sort(key=lambda r: int(r["source_frame"]))
        picked = []
        for pct in (5, 50, 95):
            pos = round((len(rows) - 1) * pct / 100)
            picked.append((pct, rows[pos]))
        video = Path(inventory[run_id]["video"])
        out = run / "review_windows"
        out.mkdir(exist_ok=True)
        cap = cv2.VideoCapture(str(video))
        if not cap.isOpened():
            raise RuntimeError(f"cannot open {video}")
        queue = []
        try:
            for pct, row in picked:
                vf, sf = int(row["video_frame"]), int(row["source_frame"])
                cap.set(cv2.CAP_PROP_POS_FRAMES, vf)
                ok, frame = cap.read()
                status = "AUTO_VISUAL_REVIEWED_PROVISIONAL"
                count = 0
                boxes = ""
                if ok:
                    result = segment(frame)
                    count = len(result.candidates)
                    canvas = frame.copy()
                    for c in result.candidates:
                        x, y, w, h = c.bbox
                        label = f"{c.kind}/{c.status}/{'+'.join(c.colors)}"
                        color = (255, 0, 255) if "cyan" in c.colors else (0, 255, 255)
                        cv2.rectangle(canvas, (x, y), (x+w, y+h), color, 2)
                        cv2.putText(canvas, label, (x, max(12, y-3)), cv2.FONT_HERSHEY_SIMPLEX, .35, color, 1)
                        points = c.panel_outline if c.panel_outline else c.outline
                        if len(points) >= 3:
                            cv2.polylines(canvas, [np.asarray(points, np.int32)], True, color, 1, cv2.LINE_AA)
                    stem = f"{pct:02d}pct_source_{sf:06d}_video_{vf:06d}"
                    cv2.imwrite(str(out / f"source_frame_{stem}.png"), frame)
                    cv2.imwrite(str(out / f"candidate_mask_{stem}.png"), result.raw_mask)
                    cv2.imwrite(str(out / f"candidate_overlay_{stem}.png"), canvas)
                    boxes = ";".join(f"{c.bbox[0]},{c.bbox[1]},{c.bbox[2]},{c.bbox[3]},{c.kind},{c.status},{'+'.join(c.colors)}" for c in result.candidates)
                else:
                    status = "DECODE_FAILED"
                queue.append({"run_id": run_id, "percentile": pct, "source_frame": sf, "video_frame": vf,
                              "source_pts_seconds": row["source_pts_seconds"], "acquired_elapsed_seconds": row["acquired_elapsed_seconds"],
                              "status": status, "detections": count, "candidate_boxes": boxes,
                              "truth_status": "UNKNOWN_NOT_HUMAN_REVIEWED"})
        finally:
            cap.release()
        write_csv(out / "review_queue.csv", ["run_id", "percentile", "source_frame", "video_frame", "source_pts_seconds", "acquired_elapsed_seconds", "status", "detections", "candidate_boxes", "truth_status"], queue)
        summaries[run_id] = {"frames": len(rows), "review_samples": len(queue), "decode_failures": sum(r["status"] == "DECODE_FAILED" for r in queue)}
    print(json.dumps({"uncertain_candidate_rows": len(uncertain), "profile_rows": len(profile), "runs": summaries}, indent=2))


if __name__ == "__main__":
    main()
