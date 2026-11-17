from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.geometry_rebuild_v1.geometry import Geometry, Rail


# These slope bins are broad grouping neighborhoods around modes observed in
# source-frame Hough segments. Intercepts and final slopes are fitted only from
# the development split; holdout runs are used solely for residual reporting.
SLOPE_NEIGHBORHOODS = np.asarray([-.84, -.56, -.28, 0.0, .28, .56, .84])


def run_ids(input_root: Path) -> list[str]:
    return sorted(p.name for p in input_root.glob("run_*") if (p / "live_source.mp4").is_file())


def sampled_frames(path: Path, count: int = 8):
    cap = cv2.VideoCapture(str(path))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if not cap.isOpened() or n <= 0:
        cap.release()
        raise RuntimeError(f"cannot read source: {path}")
    indices = sorted(set(np.linspace(max(30, n * .04), min(n - 30, n * .96), count, dtype=int).tolist()))
    for index in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = cap.read()
        if ok:
            yield int(index), frame
    cap.release()


def hough_segments(frame: np.ndarray) -> list[tuple[int, int, int, int]]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 65, 180)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 720, threshold=95,
                            minLineLength=160, maxLineGap=24)
    return [] if lines is None else [tuple(map(int, row)) for row in lines[:, 0, :]]


def _robust_center(values: list[float]) -> float:
    if not values:
        raise ValueError("insufficient source-supported rail segments")
    vals = np.asarray(values, dtype=np.float64)
    med = float(np.median(vals))
    mad = float(np.median(np.abs(vals - med)))
    keep = np.abs(vals - med) <= max(3.5 * mad, .025)
    return float(np.median(vals[keep]))


def fit_geometry(input_root: Path, dev_runs: list[str], width: int = 1280,
                 height: int = 720) -> tuple[Geometry, dict]:
    rail_slopes: list[list[float]] = [[] for _ in range(7)]
    rail_intercepts: list[list[float]] = [[] for _ in range(7)]
    per_run: dict[str, list[list[tuple[float, float]]]] = {}
    horizontal_y: list[float] = []

    for run_id in dev_runs:
        buckets: list[list[tuple[float, float]]] = [[] for _ in range(7)]
        for _, frame in sampled_frames(input_root / run_id / "live_source.mp4"):
            if frame.shape[1] != width or frame.shape[0] != height:
                raise ValueError(f"mixed source dimensions in {run_id}: {frame.shape[1]}x{frame.shape[0]}")
            for x1, y1, x2, y2 in hough_segments(frame):
                dx, dy = x2 - x1, y2 - y1
                if abs(dy) >= 110 and abs(dx / dy) <= 1.05:
                    slope = dx / dy
                    k = int(np.argmin(np.abs(SLOPE_NEIGHBORHOODS - slope)))
                    if abs(SLOPE_NEIGHBORHOODS[k] - slope) <= .055:
                        intercept = x1 - slope * y1
                        x560 = intercept + slope * 560
                        # Perspective rails intersect the observed play field
                        # as a compact ordered fan, not the HUD margins.
                        if 50 <= x560 <= width - 50 and 500 <= intercept <= 800:
                            buckets[k].append((float(slope), float(intercept)))
                            rail_slopes[k].append(float(slope))
                            rail_intercepts[k].append(float(intercept))

                if abs(dy) <= 8 and abs(dx) >= 600 and 450 <= y1 <= 630 and 450 <= y2 <= 630:
                    horizontal_y.append((y1 + y2) / 2)
        per_run[run_id] = buckets

    rails = tuple(Rail(_robust_center(rail_slopes[k]), _robust_center(rail_intercepts[k]))
                  for k in range(7))
    if any(a.x(560) >= b.x(560) for a, b in zip(rails, rails[1:])):
        raise ValueError("source-fitted rail lines are not ordered")
    if not horizontal_y:
        raise ValueError("no persistent source horizontal judgment-band edges found")
    ys = np.asarray(horizontal_y)
    # The source exposes two long, persistent edges around the hit band.
    upper = float(np.median(ys[ys < 580])) if np.any(ys < 580) else float(np.percentile(ys, 25))
    lower = float(np.median(ys[ys >= 580])) if np.any(ys >= 580) else float(np.percentile(ys, 75))
    judgment_y = (upper + lower) / 2
    geometry = Geometry(width, height, rails, judgment_y, (upper, lower), tuple(dev_runs))

    report = {"calibration_split": {"development_runs": dev_runs, "holdout_runs_not_used_for_fit": []},
              "hough_segment_counts_by_boundary": [len(x) for x in rail_slopes],
              "judgment_edge_observations": len(horizontal_y),
              "judgment_edge_y_medians": [upper, lower],
              "development_rail_fit": [
                  {"boundary": i, "slope_median": r.slope_dx_per_dy,
                   "x_y0_median": r.x_at_top,
                   "source_x_at_y560": r.x(560),
                   "slope_mad": float(np.median(np.abs(np.asarray(rail_slopes[i]) - r.slope_dx_per_dy))),
                   "intercept_mad_px": float(np.median(np.abs(np.asarray(rail_intercepts[i]) - r.x_at_top)))}
                  for i, r in enumerate(rails)],
              "per_development_run_segment_counts": {
                  run: [len(x) for x in buckets] for run, buckets in per_run.items()},
              "geometry": geometry.to_dict()}
    return geometry, report


def assess_holdout(input_root: Path, holdout_runs: list[str], geometry: Geometry) -> dict:
    rows = []
    for run_id in holdout_runs:
        errors: list[list[float]] = [[] for _ in range(7)]
        for _, frame in sampled_frames(input_root / run_id / "live_source.mp4"):
            for x1, y1, x2, y2 in hough_segments(frame):
                dx, dy = x2 - x1, y2 - y1
                if abs(dy) < 110 or abs(dx / dy) > 1.05:
                    continue
                slope = dx / dy
                k = int(np.argmin(np.abs(SLOPE_NEIGHBORHOODS - slope)))
                if abs(SLOPE_NEIGHBORHOODS[k] - slope) > .055:
                    continue
                intercept = x1 - slope * y1
                for y in (32, 190, 325, 560):
                    x = intercept + slope * y
                    predicted = geometry.rails[k].x(y)
                    if abs(x - predicted) <= 12:
                        errors[k].append(abs(x - predicted))
        rows.append({"run_id": run_id,
                     "boundary_inlier_counts": [len(x) for x in errors],
                     "boundary_median_abs_error_px": [float(np.median(x)) if x else None for x in errors],
                     "boundary_p95_abs_error_px": [float(np.percentile(x, 95)) if x else None for x in errors],
                     "holdout_used_for_fitting": False})
    return {"holdout_results": rows}


def render_overlay(frame: np.ndarray, geometry: Geometry, alpha: float = .62) -> np.ndarray:
    layer = frame.copy()
    ys = np.arange(0, min(geometry.judgment_y + 50, geometry.height - 1), 3)
    colors = [(50, 180, 255)] * 7
    for idx, rail in enumerate(geometry.rails):
        pts = np.asarray([[round(rail.x(float(y))), int(y)] for y in ys], dtype=np.int32)
        cv2.polylines(layer, [pts], False, colors[idx], 2, cv2.LINE_AA)
    left, right = geometry.rails[0].x(geometry.judgment_y), geometry.rails[-1].x(geometry.judgment_y)
    cv2.line(layer, (round(left), round(geometry.judgment_y)),
             (round(right), round(geometry.judgment_y)), (255, 240, 40), 3, cv2.LINE_AA)
    return cv2.addWeighted(frame, alpha, layer, 1 - alpha, 0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, default=Path("output/recording"))
    parser.add_argument("--out", type=Path, default=Path("output/geometry_video_v1/fresh_20261117"))
    args = parser.parse_args()
    input_root = args.input_root.resolve(strict=True)
    out = args.out.resolve()
    if out.exists() and (out / "calibration_geometry.json").exists():
        raise SystemExit("refusing to overwrite existing fresh calibration")
    ids = run_ids(input_root)
    if len(ids) < 4:
        raise SystemExit("need at least four runs to keep an independent holdout")
    split = int(len(ids) * .75)
    dev, holdout = ids[:split], ids[split:]
    geometry, report = fit_geometry(input_root, dev)
    report["holdout_results"] = assess_holdout(input_root, holdout, geometry)["holdout_results"]
    report["calibration_split"]["holdout_runs_not_used_for_fit"] = holdout
    out.mkdir(parents=True, exist_ok=True)
    config_path = out / "calibration_geometry.json"
    metrics_path = out / "geometry_calibration_metrics.json"
    for path in (config_path, metrics_path):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")
    config_path.write_text(json.dumps(geometry.to_dict(), indent=2), encoding="utf-8")
    metrics_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    review = out / "geometry_alignment_review"
    review.mkdir(exist_ok=True)
    for run_id in (dev[0], dev[-1], holdout[0], holdout[-1]):
        for frame_index in (32, 190, 325, 560):
            cap = cv2.VideoCapture(str(input_root / run_id / "live_source.mp4"))
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = cap.read(); cap.release()
            if not ok:
                continue
            overlay = render_overlay(frame, geometry)
            canvas = np.hstack((frame, overlay))
            cv2.imwrite(str(review / f"{run_id}_f{frame_index:06d}_source_overlay.png"), canvas)
    print(json.dumps({"status": geometry.to_dict()["status"], "development_runs": dev,
                      "holdout_runs": holdout, "judgment_band": geometry.to_dict()["judgment_band"],
                      "rails_y560": [round(r.x(560), 2) for r in geometry.rails],
                      "config": str(config_path), "metrics": str(metrics_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
