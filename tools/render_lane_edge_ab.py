"""Render a source-aligned edge-Tap segmentation comparison.

The pre-change side reconstructs the recorded iteration-0047 outer-ROI behavior
from the exact iteration-0048 change description. The archived source file hash
is unavailable, so this is explicitly a reconstructed parent, not an exact
historical binary/source snapshot.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
import types
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.model import Geometry  # noqa: E402
from src.lane_filter import MASK_CHANNELS, PREVIEW_COLORS, ROLE_MASK  # noqa: E402
from tools.render_lane_filter_window import index_row, read_index, sha256, validate_range  # noqa: E402

SOURCE = ROOT / "src/lane_segmentation.py"
OLD_WINDOW_BLOCK = """        for lane_index in range(6):
            center=(lane_index+.5)*geometry.lane_pixels
"""
OLD_WINDOW_RECONSTRUCTION = """        for lane_index in range(6):
            # Iteration 0047 omitted outer centered ROIs that crossed the image edge.
            if lane_index in (0, 5):
                continue
            center=(lane_index+.5)*geometry.lane_pixels
"""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def reconstructed_parent_class(source_text: str):
    if source_text.count(OLD_WINDOW_BLOCK) != 1:
        raise ValueError("expected one outer-ROI construction block; refusing reconstruction")
    module = types.ModuleType("v86_reconstructed_iteration_0047_segmentation")
    sys.modules[module.__name__] = module
    exec(compile(source_text.replace(OLD_WINDOW_BLOCK, OLD_WINDOW_RECONSTRUCTION, 1),
                 "v86_reconstructed_iteration_0047_segmentation.py", "exec"), module.__dict__)
    return module.LanePixelSegmenter


def mask_preview(rectified: np.ndarray, masks: dict[str, np.ndarray]) -> np.ndarray:
    preview = np.zeros_like(rectified)
    for role, channel in ROLE_MASK.items():
        preview[masks[channel] > 0] = PREVIEW_COLORS[role]
    return preview


def stamp(image: np.ndarray, title: str, frame: int, source_frame: int, captured: str) -> np.ndarray:
    cv2.rectangle(image, (0, 0), (image.shape[1], 42), (18, 18, 18), -1)
    cv2.putText(image, title, (7, 16), cv2.FONT_HERSHEY_SIMPLEX, .42,
                (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(image, f"v={frame} s={source_frame} t={float(captured):.3f}",
                (7, 34), cv2.FONT_HERSHEY_SIMPLEX, .35, (220, 220, 220), 1, cv2.LINE_AA)
    return image


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--start", type=int, default=361)
    ap.add_argument("--end", type=int, default=385)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    validate_range(args.start, args.end)
    run = args.run_dir.resolve()
    out = args.out.resolve()
    if out.exists():
        raise SystemExit(f"refusing to overwrite existing output: {out}")
    video = run / "live_source.mp4"
    index_path = run / "live_video_index.csv"
    index = read_index(index_path)
    for frame_id in range(args.start, args.end + 1):
        index_row(index, frame_id)

    source_text = SOURCE.read_text(encoding="utf-8-sig")
    current_source_hash = sha256(SOURCE)
    parent_segmenter_type = reconstructed_parent_class(source_text)
    geometry = Geometry(ROOT / "config/geometry_live_assist.json")
    current_segmenter_type = __import__("src.lane_segmentation", fromlist=["LanePixelSegmenter"]).LanePixelSegmenter
    before_segmenter = parent_segmenter_type()
    after_segmenter = current_segmenter_type()

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise SystemExit(f"cannot open {video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
    out.mkdir(parents=True)
    panel_width = geometry.width + geometry.plane_width * 3
    writer = cv2.VideoWriter(str(out / "edge_recovery_ab.mp4"),
                             cv2.VideoWriter_fourcc(*"mp4v"), fps,
                             (panel_width, geometry.height))
    if not writer.isOpened():
        cap.release()
        raise SystemExit("cannot open output video writer")

    rows: list[dict[str, object]] = []
    mask_frames: list[np.ndarray] = []
    before_373: dict[str, object] | None = None
    after_373: dict[str, object] | None = None
    archived = cv2.imread(str(ROOT / "output/analysis_v86_autoloop/iteration_0040/action_attribution_segmented/action_loss_evidence_v4/frame_000373.png"))
    if archived is None or archived.shape[1] < geometry.plane_width * 2:
        raise SystemExit("archived frame-373 pre-change mask evidence is unavailable")
    archived_mask_panel = archived[:, geometry.plane_width:geometry.plane_width * 2]

    decoded = 0
    render_ms: list[float] = []
    try:
        while decoded <= args.end:
            ok, raw = cap.read()
            if not ok:
                raise ValueError(f"source ended before video_frame={decoded}")
            if args.start <= decoded <= args.end:
                row = index_row(index, decoded)
                source_frame = int(row["source_frame"])
                normalize_start = time.perf_counter()
                normalized = geometry.normalize(raw)
                rectify_start = time.perf_counter()
                rectified = geometry.rectify(normalized)
                rectify_ms = (time.perf_counter() - rectify_start) * 1000
                normalize_ms = (rectify_start - normalize_start) * 1000

                before_start = time.perf_counter()
                before_result = before_segmenter.segment(rectified, geometry, frame_index=decoded)
                before_ms = (time.perf_counter() - before_start) * 1000
                after_start = time.perf_counter()
                after_result = after_segmenter.segment(rectified, geometry, frame_index=decoded)
                after_ms = (time.perf_counter() - after_start) * 1000

                before_mask = mask_preview(rectified, before_result.masks)
                after_mask = mask_preview(rectified, after_result.masks)
                panels = [normalized, rectified.copy(), before_mask, after_mask]
                names = ["SOURCE", "RECTIFIED", "PARENT MASK*", "CURRENT MASK"]
                panels = [stamp(panel, name, decoded, source_frame, row["capture_timestamp"])
                          for panel, name in zip(panels, names)]
                render_start = time.perf_counter()
                writer.write(np.concatenate(panels, axis=1))
                render_ms.append((time.perf_counter() - render_start) * 1000)

                before_cyan = [c for c in before_result.components
                               if c.role == "tap_face" and c.color == "cyan"]
                after_cyan = [c for c in after_result.components
                              if c.role == "tap_face" and c.color == "cyan"]
                row_data = {
                    "video_frame": decoded,
                    "source_frame": source_frame,
                    "capture_timestamp": row["capture_timestamp"],
                    "acquired_timestamp": row["acquired_timestamp"],
                    "normalize_ms": f"{normalize_ms:.3f}",
                    "rectify_ms": f"{rectify_ms:.3f}",
                    "reconstructed_parent_segmentation_ms": f"{before_ms:.3f}",
                    "current_segmentation_ms": f"{after_ms:.3f}",
                    "reconstructed_cyan_tap_boxes": "|".join(str(c.bbox) for c in before_cyan),
                    "current_cyan_tap_boxes": "|".join(str(c.bbox) for c in after_cyan),
                    "reconstructed_tap_pixels": int(np.count_nonzero(before_result["tap_face"])),
                    "current_tap_pixels": int(np.count_nonzero(after_result["tap_face"])),
                }
                rows.append(row_data)
                mask_frames.append(np.stack([before_result.masks[k] for k in MASK_CHANNELS] +
                                            [after_result.masks[k] for k in MASK_CHANNELS]))
                if decoded == 373:
                    old_edge_faces = [c for c in before_cyan if c.bbox[0] <= 2 or c.bbox[0] + c.bbox[2] >= geometry.plane_width - 4]
                    new_edge_faces = [c for c in after_cyan if c.bbox[0] <= 2 or c.bbox[0] + c.bbox[2] >= geometry.plane_width - 4]
                    if old_edge_faces or len(new_edge_faces) != 2:
                        raise AssertionError(f"frame-373 regression check failed: old={len(old_edge_faces)} new={len(new_edge_faces)}")
                    mismatch = np.any(before_mask != archived_mask_panel, axis=2)
                    before_373 = {
                        "reconstructed_edge_cyan_tap_faces": len(old_edge_faces),
                        "reconstructed_cyan_tap_pixels": int(np.count_nonzero(before_result["tap_face"])),
                        "preview_pixel_mismatches_vs_archived_iteration_0040_panel": int(mismatch.sum()),
                        "archived_panel_pixels": int(mismatch.size),
                    }
                    after_373 = {
                        "current_edge_cyan_tap_faces": len(new_edge_faces),
                        "current_edge_cyan_tap_boxes": [list(c.bbox) for c in new_edge_faces],
                        "current_edge_cyan_tap_pixels": [c.area for c in new_edge_faces],
                        "bridge_tap_pixels": int(np.count_nonzero(after_result["tap_face"][286:317, 120:238])),
                    }
            decoded += 1
    finally:
        cap.release()
        writer.release()

    if len(rows) != args.end - args.start + 1 or before_373 is None or after_373 is None:
        raise AssertionError("requested source window or frame-373 audit was incomplete")
    with (out / "timeline.csv").open("w", newline="", encoding="utf-8") as f:
        writer_csv = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer_csv.writeheader()
        writer_csv.writerows(rows)
    np.savez_compressed(out / "semantic_masks_ab.npz",
                        video_frames=np.arange(args.start, args.end + 1),
                        source_frames=np.asarray([int(r["source_frame"]) for r in rows]),
                        channel_names=np.asarray(MASK_CHANNELS), masks=np.stack(mask_frames))

    manifest = {
        "status": "PROVISIONAL_RECONSTRUCTED_PARENT_AB; NOT_EXACT_ARCHIVED_SOURCE",
        "run_id": run.name,
        "video_frame_window": {"start_inclusive": args.start, "end_inclusive": args.end, "count": len(rows)},
        "source_video_sha256": sha256(video),
        "index_sha256": sha256(index_path),
        "geometry_sha256": geometry.sha256,
        "geometry_status": geometry.status,
        "sequential_decode_start": 0,
        "sequential_decoded_through": decoded - 1,
        "index_rows_verified": len(rows),
        "index_mapping_verified": all(int(index_row(index, int(r["video_frame"]))["source_frame"]) == int(r["source_frame"]) for r in rows),
        "current_segmenter_source_sha256": current_source_hash,
        "reconstructed_parent": {
            "basis": "iteration_0048 report: iteration_0047 omitted lane-centered ROIs extending beyond the image; iteration_0048 added explicit full-width edge tiles",
            "transformation": "skip lane indices 0 and 5 during centered-window construction; leave all other current code byte-for-byte equal",
            "exact_historical_source_available": False,
            "frame_373_comparison_to_archived_iteration_0040": before_373,
        },
        "frame_373_current": after_373,
        "timing_ms": {
            "normalize_mean": float(np.mean([float(r["normalize_ms"]) for r in rows])),
            "rectify_mean": float(np.mean([float(r["rectify_ms"]) for r in rows])),
            "reconstructed_parent_segmentation_mean": float(np.mean([float(r["reconstructed_parent_segmentation_ms"]) for r in rows])),
            "current_segmentation_mean": float(np.mean([float(r["current_segmentation_ms"]) for r in rows])),
            "video_write_only_mean": float(np.mean(render_ms)),
            "note": "Video rendering is outside the segmentation timings; write-only excludes panel composition.",
        },
        "artifacts": {},
    }
    for p in sorted(out.iterdir()):
        if p.is_file():
            manifest["artifacts"][p.name] = {"sha256": sha256(p), "bytes": p.stat().st_size}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
