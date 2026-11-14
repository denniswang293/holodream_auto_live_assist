"""Extract source-provenance review frames by encoded preview playback time."""
from __future__ import annotations
import argparse
import csv
from pathlib import Path

import cv2

CASE_NOTES = {
    4.9: ("hold_ribbon", "Green curved ribbon visible; endpoint ownership requires review."),
    6.0: ("hold_ribbon", "Green ribbon body visible; head/tail extent requires review."),
    13.2: ("multi_note_effect", "Multiple note-like shapes and judgment effects; separate positives from effects."),
    14.9: ("curved_multi_hold", "Curved overlapping ribbon-like shapes; owner separation is uncertain."),
    16.9: ("mixed_notes_effect", "Mixed colored note-like shapes and a miss effect; label only visible evidence."),
}


def read_index(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {int(r["video_frame"]): r for r in csv.DictReader(f)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--legacy-preview", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--seconds", type=float, nargs="+", default=[4.9, 6.0, 13.2, 14.9, 16.9])
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    src_path = a.run_dir / "live_source.mp4"
    idx = read_index(a.run_dir / "live_video_index.csv")
    src = cv2.VideoCapture(str(src_path)); prev = cv2.VideoCapture(str(a.legacy_preview))
    if not src.isOpened() or not prev.isOpened():
        raise SystemExit("could not open source or legacy preview")
    preview_fps = prev.get(cv2.CAP_PROP_FPS) or 60.0
    source_count = int(src.get(cv2.CAP_PROP_FRAME_COUNT))
    rows=[]
    for sec in a.seconds:
        video_frame = int(round(sec * preview_fps))
        if video_frame >= source_count or video_frame not in idx:
            rows.append({"requested_preview_s": sec, "video_frame": video_frame,
                         "status": "OUT_OF_RANGE_OR_NO_INDEX"})
            continue
        src.set(cv2.CAP_PROP_POS_FRAMES, video_frame); ok0, original = src.read()
        prev.set(cv2.CAP_PROP_POS_FRAMES, video_frame); ok1, legacy = prev.read()
        if not (ok0 and ok1):
            rows.append({"requested_preview_s": sec, "video_frame": video_frame, "status": "DECODE_FAILED"})
            continue
        key=f"frame_{video_frame:06d}_{sec:.1f}s"
        cv2.imwrite(str(a.out / f"{key}_source.png"), original)
        cv2.imwrite(str(a.out / f"{key}_legacy_preview.png"), legacy)
        row=idx[video_frame]
        case_type, visual_note = CASE_NOTES.get(sec, ("additional_review", "Requires source-frame review."))
        rows.append({"requested_preview_s": sec, "preview_fps": preview_fps,
            "video_frame": video_frame, "source_frame": row.get("source_frame"),
            "capture_timestamp": row.get("capture_timestamp"),
            "acquired_timestamp": row.get("acquired_timestamp"),
            "focused": row.get("focused"), "roi_valid": row.get("roi_valid"),
            "source_width": original.shape[1], "source_height": original.shape[0],
            "case_type": case_type, "visual_note_not_ground_truth": visual_note,
            "annotation_status": "NOT_HUMAN_REVIEWED", "split": "UNASSIGNED",
            "status": "EXTRACTED"})
    src.release(); prev.release()
    with (a.out / "case_manifest.csv").open("w", encoding="utf-8", newline="") as f:
        fields=sorted({k for r in rows for k in r})
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


if __name__ == "__main__": main()
