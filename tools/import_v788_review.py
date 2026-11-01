"""Merge a partial human review CSV into the V7.8.8 review package.

The merge is conservative: only existing case IDs are updated.  Cases not
present in the supplied file retain their existing UNREVIEWED/UNKNOWN values.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_v788_visual_review import REVIEW_FIELDS, normalize_review_rows, read_csv, write_csv


def read_incoming(path: Path) -> list[dict[str, str]]:
    """Read normal CSV and the legacy headerless V7.8.x export format."""
    rows = read_csv(path)
    if rows and "case_id" in rows[0]:
        return rows
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        raw = list(csv.reader(fh))
    if raw and raw[0] and raw[0][0] == "case_id":
        raw = raw[1:]
    return [dict(zip(REVIEW_FIELDS, row)) for row in raw if any(row)]


def merge(review_dir: Path, incoming_path: Path) -> int:
    template_path = review_dir / "physical_identity_review_template.csv"
    completed_path = review_dir / "physical_identity_review_completed.csv"
    base_path = completed_path if completed_path.exists() else template_path
    base = normalize_review_rows(read_csv(base_path))
    incoming = normalize_review_rows(read_incoming(incoming_path))
    by_id = {row["case_id"]: row for row in base}
    accepted = 0
    rejected_ids = []
    for row in incoming:
        if row["case_id"] not in by_id:
            rejected_ids.append(row["case_id"])
            continue
        # Only review fields are copied. Source identity/evidence fields remain
        # those generated from the run and cannot be changed by a reviewer CSV.
        target = by_id[row["case_id"]]
        for field in ("same_physical_note_verdict", "visual_confidence", "reviewer_status", "reviewer_notes", "game_judgment"):
            target[field] = row.get(field, target.get(field, ""))
        accepted += 1
    merged = list(by_id.values())
    write_csv(completed_path, merged, REVIEW_FIELDS)
    report = {"incoming": str(incoming_path), "base": str(base_path), "accepted_rows": accepted, "incoming_rows": len(incoming), "unmatched_case_ids": rejected_ids, "merged_case_count": len(merged), "missing_from_incoming": [row["case_id"] for row in merged if row["case_id"] not in {r["case_id"] for r in incoming}], "policy": "Only matching case IDs updated; absent cases remain UNREVIEWED/UNKNOWN."}
    (review_dir / "review_import_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not rejected_ids else 2


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-dir", default="output/v788_visual_identity_review")
    parser.add_argument("--incoming", required=True)
    args = parser.parse_args()
    raise SystemExit(merge(Path(args.review_dir).expanduser().resolve(), Path(args.incoming).expanduser().resolve()))


if __name__ == "__main__":
    main()
