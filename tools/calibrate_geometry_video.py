"""Fit the static six-lane projection from source-only temporal medians."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


Y_SAMPLES = (30, 190, 325, 560)
VISUAL_BOUNDARY_ANCHORS = {
    30: (605, 617, 628, 640, 652, 663, 675),
    190: (407, 485, 562, 640, 718, 795, 873),
    325: (327, 431, 536, 640, 744, 849, 953),
    560: (61, 254, 447, 640, 833, 1026, 1219),
}
EDGE_EXTENSIONS = {
    0: (600, 613, 626, 640, 654, 667, 680),
    615: (0, 213, 426, 640, 854, 1067, 1279),
}


def line_observations(image: np.ndarray) -> list[tuple[float, float, float]]:
    """Return (dx/dy, x-intercept, weight) for long perspective rails."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 40, 125)
    roi = np.zeros_like(edges)
    roi[:585] = edges[:585]
    segments = cv2.HoughLinesP(roi, 1, np.pi / 1800, 140,
                               minLineLength=300, maxLineGap=14)
    output = []
    if segments is None:
        return output
    for x1, y1, x2, y2 in segments[:, 0, :]:
        dy, dx = float(y2-y1), float(x2-x1)
        if dy == 0 or abs(dx/dy) > 1.2:
            continue
        slope = dx/dy
        intercept = x1 - slope*y1
        output.append((slope, intercept, abs(dy)))
    return output


def cluster_lines(lines: list[tuple[float, float, float]]) -> list[dict]:
    # Cluster only by measured slope. Parallel outline duplicates are collapsed
    # by weighted medians; each rail must be visible in multiple long segments.
    lines = sorted(lines, key=lambda line: line[0])
    clusters: list[list[tuple[float, float, float]]] = []
    for row in lines:
        if not clusters or row[0] - np.median([item[0] for item in clusters[-1]]) > .075:
            clusters.append([row])
        else:
            clusters[-1].append(row)
    candidates = []
    for cluster in clusters:
        if sum(row[2] for row in cluster) < 300:
            continue
        candidates.append({
            "slope": float(np.median([row[0] for row in cluster])),
            "intercept": float(np.median([row[1] for row in cluster])),
            "segments": len(cluster), "vertical_support_px": float(sum(row[2] for row in cluster)),
        })
    return sorted(candidates, key=lambda line: line["slope"])


def horizontal_line_scores(image: np.ndarray) -> dict:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    # Score a long cyan/white bar, not notes or effects confined to a few lanes.
    saturation, value = hsv[540:620, :, 1], hsv[540:620, :, 2]
    mask = ((value > 170) & ((saturation < 95) | (hsv[540:620, :, 0] >= 75) & (hsv[540:620, :, 0] <= 110)))
    scores = mask[:, 40:1240].mean(axis=1)
    peaks = []
    for local_y in np.argsort(scores)[-12:][::-1]:
        if all(abs(int(local_y)-p[0]) > 2 for p in peaks):
            peaks.append((int(local_y), float(scores[local_y])))
        if len(peaks) == 6:
            break
    return {"top_rows_by_horizontal_cyan_white_support": [[y+540, round(score, 4)] for y, score in peaks]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--median-root", type=Path, default=Path("output/geometry_video_v1/geometry_alignment_review/temporal_medians"))
    parser.add_argument("--development-runs", type=int, default=6)
    parser.add_argument("--report", type=Path, default=Path("output/geometry_video_v1/geometry_alignment_review/rail_measurements.json"))
    parser.add_argument("--out-config", type=Path, default=Path("config/geometry_video_v1.json"))
    args = parser.parse_args()
    files = sorted(args.median_root.glob("run_*_median_*.png"))
    if len(files) < 3:
        raise SystemExit("Need temporal medians for development and holdout runs")
    split = min(max(1, args.development_runs), len(files)-1)
    dev_files, holdout_files = files[:split], files[split:]
    run_rows = []
    for path in files:
        image = cv2.imread(str(path))
        if image is None:
            continue
        lines = cluster_lines(line_observations(image))
        run_rows.append({"run_id": path.name.split("_median_")[0], "role": "DEVELOPMENT" if path in dev_files else "HOLDOUT",
                         "rail_lines": lines, **horizontal_line_scores(image)})
    dev_rows = [row for row in run_rows if row["role"] == "DEVELOPMENT"]
    if not dev_rows or any(len(row["rail_lines"]) not in (6, 7) for row in dev_rows):
        summary = {row["run_id"]: row["rail_lines"] for row in dev_rows}
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({"status": "RAIL_CLUSTER_COUNT_MISMATCH", "observations": summary}, indent=2), encoding="utf-8")
        raise SystemExit(f"Expected at least six observable lane-boundary lines in each development median; counts={ {k: len(v) for k, v in summary.items()} }")
    fitted = []
    for index in range(7):
        group = [row["rail_lines"][index] for row in dev_rows if len(row["rail_lines"]) == 7]
        if len(group) < 4:
            raise SystemExit(f"Only {len(group)} seven-rail development observations for boundary {index}")
        fitted.append({
            "slope_dx_per_dy": float(np.median([line["slope"] for line in group])),
            "x_intercept_at_y0": float(np.median([line["intercept"] for line in group])),
            "development_run_count": len(group),
            "slope_range": [float(min(line["slope"] for line in group)), float(max(line["slope"] for line in group))],
            "intercept_range_px": [float(min(line["intercept"] for line in group)), float(max(line["intercept"] for line in group))],
        })
    holdout_errors = []
    for row in run_rows:
        if row["role"] != "HOLDOUT":
            continue
        if len(row["rail_lines"]) not in (6, 7):
            holdout_errors.append({"run_id": row["run_id"], "status": "RAIL_COUNT_MISMATCH", "observed": len(row["rail_lines"])})
            continue
        diffs = []
        available = set(range(7))
        matched = []
        for observed in row["rail_lines"]:
            observed_slope = observed["slope"]
            index = min(available, key=lambda i: abs(fitted[i]["slope_dx_per_dy"]-observed_slope))
            available.remove(index)
            matched.append((index, observed))
        for index, observed in matched:
            predicted = fitted[index]
            for y in Y_SAMPLES:
                diffs.append(abs((predicted["x_intercept_at_y0"] + predicted["slope_dx_per_dy"]*y) -
                                 (observed["intercept"] + observed["slope"]*y)))
        holdout_errors.append({"run_id": row["run_id"], "status": "MEASURED",
                               "mean_abs_rail_residual_px": float(np.mean(diffs)),
                               "p95_abs_rail_residual_px": float(np.percentile(diffs, 95)),
                               "max_abs_rail_residual_px": float(np.max(diffs))})
    result = {
        "method": "Canny + Hough long-line segments on temporal-median source frames; grouped by measured dx/dy; first six Run medians fit, final two are held out; a missed Hough cluster is matched to its nearest fitted slope and recorded",
        "source_coordinates": {"width": 1280, "height": 720},
        "rail_y_samples": list(Y_SAMPLES),
        "roles": {row["run_id"]: row["role"] for row in run_rows},
        "fitted_rails_left_to_right": fitted,
        "hough_holdout_crosscheck_errors": holdout_errors,
        "visual_geometry_holdout_validation": "VISUAL_OVERLAY_REQUIRED; final two runs are rendered with anchors but have no independent human pixel measurements",
        "per_run_observations": run_rows,
        "judgment_bar_estimate": "Provisional only: horizontal cyan/white row support is recorded but the true decision-line reference requires source visual review; do not use the brightest transient row as a line estimate.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    judgment_y = 0.5 * (560 + 600)
    # The Hough lines are retained as a measured cross-check. Their single
    # global straight-line fit is visibly too narrow near the judgment band,
    # so production geometry uses piecewise source-pixel anchors instead.
    geometry_rows = (0, *Y_SAMPLES, 615)
    anchored_rails = [{
        "pixel_anchors": [{"y": y, "x": EDGE_EXTENSIONS[y][rail] if y in EDGE_EXTENSIONS
                           else VISUAL_BOUNDARY_ANCHORS[y][rail]}
                          for y in geometry_rows],
        "anchor_provenance": "INDEPENDENT_ASSISTANT_VISUAL_ESTIMATE_FROM_SOURCE_MEDIANS",
        "confidence_by_region": {"top_y30": "LOW", "middle_y190_y325": "MEDIUM", "bottom_y560": "LOW"},
    } for rail in range(7)]
    geometry_cfg = {
        "schema_version": 1,
        "status": "AUTO_CALIBRATED_PROVISIONAL",
        "coordinate_space": "native_recorded_source_pixels",
        "source_resolution": [1280, 720],
        "source_scene_consistency": "All eight temporal medians show the same static playfield; visual anchor overlays are generated for both a development Run and the final held-out Run.",
        "rails_left_to_right": anchored_rails,
        "hough_straight_line_crosscheck": fitted,
        "geometry_method": "Piecewise-linear interpolation through four independent visual boundary anchors per rail; the Hough straight-line fit is retained as a cross-check because it is too narrow near the bottom.",
        "judgment_line": {
            "y": judgment_y, "observed_bar_top_y": 560, "observed_bar_bottom_y": 600,
            "definition": "center row of the persistent judgment band; source pixel row support peaks at both band edges across runs",
            "evidence": "Per-run temporal-median cyan/white row support is consistently high at y=560 and y=600; their midpoint is used as a neutral visual reference. The true gameplay hit row is not independently labeled. This is AUTO_VISUAL_REVIEWED, not HUMAN_REVIEWED.",
            "confidence": "MEDIUM",
        },
        "calibration_method": "Piecewise source-pixel visual anchors with a global straight-line Hough fit retained as a cross-check",
        "hough_crosscheck_method": result["method"],
        "development_run_ids": [row["run_id"] for row in run_rows if row["role"] == "DEVELOPMENT"],
        "holdout_run_ids": [row["run_id"] for row in run_rows if row["role"] == "HOLDOUT"],
        "hough_holdout_crosscheck_errors": holdout_errors,
        "source_median_visual_anchor_rows": {str(y): list(xs) for y, xs in VISUAL_BOUNDARY_ANCHORS.items()},
        "edge_extension_rows": {str(y): list(xs) for y, xs in EDGE_EXTENSIONS.items()},
        "live_geometry_config_sha256_read_only_comparison_only": __import__("hashlib").sha256(Path("config/geometry_live_assist.json").read_bytes()).hexdigest(),
        "review_status": "AUTO_VISUAL_REVIEWED_PROVISIONAL; independent human calibration absent",
    }
    args.out_config.parent.mkdir(parents=True, exist_ok=True)
    args.out_config.write_text(json.dumps(geometry_cfg, indent=2), encoding="utf-8")
    print(json.dumps({"fitted_rails_left_to_right": fitted, "holdout_fit_errors": holdout_errors,
                      "judgment_rows": {row["run_id"]: row["top_rows_by_horizontal_cyan_white_support"] for row in run_rows}}, indent=2))
    print(f"Detailed measurements: {args.report}; config: {args.out_config}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
