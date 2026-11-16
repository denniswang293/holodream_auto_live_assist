"""Summarize V8.5 early-candidate confirmation and replay commit timings."""
from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "output" / "analysis_v85_early_identity"

FIELDS = [
    "run_id", "color", "type_hint", "candidate_count",
    "exact_replay_uid_join_count", "confirmed_candidate_count", "rows_with_commit_at",
    "candidate_to_confirmation_seconds_p10", "candidate_to_confirmation_seconds_p50",
    "candidate_to_confirmation_seconds_p90", "candidate_to_confirmation_y_delta_p10",
    "candidate_to_confirmation_y_delta_p50", "candidate_to_confirmation_y_delta_p90",
    "candidate_to_first_commit_seconds_p10", "candidate_to_first_commit_seconds_p50",
    "candidate_to_first_commit_seconds_p90", "confirmed_to_first_commit_seconds_p10",
    "confirmed_to_first_commit_seconds_p50", "confirmed_to_first_commit_seconds_p90",
    "schedule_commit_spatial_delta_status", "ground_truth_status",
    "first_commit_timestamp_semantics",
]
SEMANTICS = (
    "minimum decision capture_timestamp among specified committed decision states; "
    "replay-log timestamp only"
)


def percentile(values: list[float], p: float) -> float | str:
    """Linear interpolation matching numpy.percentile's default method."""
    if not values:
        return ""
    ordered = sorted(values)
    position = (len(ordered) - 1) * p / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def numeric(row: dict[str, str], key: str) -> float | None:
    try:
        value = float(row[key])
        return value if math.isfinite(value) else None
    except (KeyError, TypeError, ValueError):
        return None


def differences(rows: list[dict[str, str]], end: str, start: str) -> list[float]:
    result = []
    for row in rows:
        a, b = numeric(row, end), numeric(row, start)
        if a is not None and b is not None:
            result.append(a - b)
    return result


def summarize(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row.get("run_id", ""), row.get("color", ""), row.get("type_hint", ""))].append(row)

    output = []
    for (run_id, color, type_hint), group in sorted(grouped.items()):
        confirmed = [row for row in group if row.get("confirmed_at", "").strip()]
        committed = [row for row in group if row.get("commit_at", "").strip()]
        exact_joins = sum(
            row.get("provider_local_replay_uid", "") not in ("", "UNJOINED", "NOT_REPLAYED")
            for row in group
        )
        metrics = [
            differences(confirmed, "confirmed_at", "first_candidate_at"),
            differences(confirmed, "confirmed_y", "birth_motion_y"),
            differences(committed, "commit_at", "first_candidate_at"),
            differences([row for row in committed if row in confirmed], "commit_at", "confirmed_at"),
        ]
        values: list[object] = [
            run_id, color, type_hint, len(group), exact_joins, len(confirmed), len(committed)
        ]
        for samples in metrics:
            values.extend(percentile(samples, p) for p in (10, 50, 90))
        values.extend([
            "NOT_AVAILABLE_IN_METRICS",
            "NOT_EVALUABLE_AUTOMATIC_TRACKS_ONLY",
            SEMANTICS,
        ])
        output.append(dict(zip(FIELDS, values)))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_DIR / "early_confirmation_metrics.csv")
    parser.add_argument("--output", type=Path, default=DEFAULT_DIR / "early_confirmation_stage_metrics.csv")
    args = parser.parse_args()

    with args.input.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    output = summarize(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(output)
    print(f"wrote {args.output} ({len(output)} groups)")


if __name__ == "__main__":
    main()
