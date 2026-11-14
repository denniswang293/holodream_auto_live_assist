"""Small OpenCV polygon annotator for source-provenance review frames.

Left-click polygon vertices, press a class key to commit the polygon, `z` to
undo, `s` to save, and `n`/`p` to move between source crops.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import cv2
import numpy as np

CLASSES = {"t": "TAP_FACE", "h": "HOLD_HEAD", "b": "HOLD_BODY",
           "e": "HOLD_TAIL", "x": "EFFECT", "u": "UNKNOWN", "g": "BACKGROUND"}
COLORS = {"TAP_FACE": (50, 220, 50), "HOLD_HEAD": (0, 220, 255),
          "HOLD_BODY": (255, 120, 20), "HOLD_TAIL": (220, 60, 220),
          "EFFECT": (80, 80, 255), "UNKNOWN": (180, 180, 180),
          "BACKGROUND": (70, 70, 70)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--frames", type=Path, required=True, help="directory with case_manifest.csv and *_source.png")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader((args.frames / "case_manifest.csv").open(encoding="utf-8-sig", newline="")))
    rows = [r for r in rows if r.get("status") == "EXTRACTED"]
    states = {i: [] for i in range(len(rows))}; active: list[tuple[int, int]] = []
    pos = 0

    def mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN: active.append((x, y))

    win = "Lane mask labels: click points; t/h/b/e/x/u/g commit; z undo; s save; n/p frame"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL); cv2.setMouseCallback(win, mouse)
    while rows:
        row = rows[pos]; frame_no = int(row["video_frame"]); sec = row["requested_preview_s"]
        source = cv2.imread(str(args.frames / f"frame_{frame_no:06d}_{float(sec):.1f}s_source.png"))
        if source is None: raise FileNotFoundError(f"missing source image for frame {frame_no}")
        display = source.copy()
        for cls, poly in states[pos]:
            pts = np.asarray(poly, np.int32)
            cv2.polylines(display, [pts], True, COLORS[cls], 2)
            cv2.putText(display, cls, tuple(pts[0]), cv2.FONT_HERSHEY_SIMPLEX, .45, COLORS[cls], 1)
        if len(active) > 1: cv2.polylines(display, [np.asarray(active, np.int32)], False, (255, 255, 255), 1)
        cv2.putText(display, f"{pos+1}/{len(rows)} frame={frame_no} capture={row['capture_timestamp']} polygons={len(states[pos])}",
                    (4, 18), cv2.FONT_HERSHEY_SIMPLEX, .42, (255, 255, 255), 1)
        cv2.imshow(win, display); key = cv2.waitKey(30) & 0xFF
        if key == 255: continue
        if chr(key) in CLASSES:
            if len(active) >= 3:
                states[pos].append((CLASSES[chr(key)], [list(p) for p in active]))
            active.clear()
        elif key == ord("z"):
            if active: active.clear()
            elif states[pos]: states[pos].pop()
        elif key == ord("s"):
            mask = np.zeros(source.shape[:2], np.uint8); payload=[]
            for index, (cls, poly) in enumerate(states[pos], 1):
                cv2.fillPoly(mask, [np.asarray(poly, np.int32)], index)
                payload.append({"instance_id": f"label-{index}", "class": cls,
                                "polygon_xy": poly, "head_tail_owner": "UNKNOWN",
                                "physical_note_id": "UNKNOWN", "review_status": "DRAFT_REVIEW_REQUIRED"})
            np.save(args.out / f"frame_{frame_no:06d}_labels.npy", mask)
            (args.out / f"frame_{frame_no:06d}_labels.json").write_text(json.dumps({
                "run_id": "run_20261109T143554_007912Z", "source_frame": int(row["source_frame"]),
                "video_frame": frame_no, "capture_timestamp": float(row["capture_timestamp"]),
                "acquired_timestamp": float(row["acquired_timestamp"]), "split": "development",
                "coordinate_space": "source_frame_pixels", "review_status": "DRAFT_REVIEW_REQUIRED",
                "instances": payload}, indent=2), encoding="utf-8")
        elif key == ord("n"): pos = (pos + 1) % len(rows); active.clear()
        elif key == ord("p"): pos = (pos - 1) % len(rows); active.clear()
        elif key == 27: break
    cv2.destroyAllWindows()


if __name__ == "__main__": main()
