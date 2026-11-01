"""Read-only aggregation of the V7.8.8 human identity review CSV."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_v788_visual_review import REVIEW_FIELDS, normalize_review_rows, read_csv, write_csv  # noqa: E402


def summarize(review_dir: Path, review_csv: Path | None, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    source = review_csv or (review_dir / "physical_identity_review_completed.csv")
    if not source.exists():
        source = review_dir / "physical_identity_review_template.csv"
    rows = normalize_review_rows(read_csv(source)) if source.exists() else []
    by_id = {r.get("case_id", ""): r for r in rows}
    rescue = [r for r in rows if r.get("case_id", "").startswith("rescue_")]
    negatives = [r for r in rows if r.get("case_id", "").startswith("nc-")]
    parity = [r for r in rows if r.get("case_id", "").startswith("parity_")]
    reviewed = [r for r in rows if r.get("reviewer_status") == "REVIEWED"]
    verified_rescue = [r for r in rescue if r.get("reviewer_status") == "REVIEWED" and r.get("same_physical_note_verdict") == "SAME_PHYSICAL_NOTE" and r.get("visual_confidence") in {"HIGH", "MEDIUM"}]
    rejected = [r for r in rows if r.get("same_physical_note_verdict") in {"DIFFERENT_PHYSICAL_NOTE", "NOT_A_REAL_NOTE", "AMBIGUOUS"}]
    false_attach = [r for r in rescue if r.get("reviewer_status") == "REVIEWED" and r.get("same_physical_note_verdict") == "DIFFERENT_PHYSICAL_NOTE"]
    unknown = [r for r in rows if r.get("same_physical_note_verdict") in {"UNKNOWN", "UNREVIEWED"} or r.get("reviewer_status") != "REVIEWED"]
    software_stable = {"rescue_399_simple5": "STABLE", "rescue_525_simple12": "STABLE", "rescue_408_simple5": "UNSTABLE"}
    verified_controls = [r for r in negatives if r.get("reviewer_status") == "REVIEWED" and r.get("same_physical_note_verdict") in {"DIFFERENT_PHYSICAL_NOTE", "NOT_A_REAL_NOTE"} and r.get("visual_confidence") in {"HIGH", "MEDIUM"}]
    parity_path = review_dir / ".." / "v787_parity_identity" / "baseline_parity_semantic.json"
    if not parity_path.exists():
        parity_path = ROOT / "output" / "v787_parity_identity" / "baseline_parity_semantic.json"
    try:
        parity_data = json.loads(parity_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        parity_data = {"semantic_assignment_parity": "UNKNOWN", "extra_edges": "UNKNOWN", "missing_edges": "UNKNOWN"}
    parity_status = parity_data.get("semantic_assignment_parity", "UNKNOWN")
    summary = {
        "source_csv": str(source), "case_count": len(rows),
        "manual_review_complete": len(rows) >= 30 and not unknown,
        "row_counts": {"all": len(rows), "rescue": len(rescue), "negative_controls": len(negatives), "parity": len(parity), "reviewed": len(reviewed), "unreviewed_or_unknown": len(unknown)},
        "original_legacy_recovered": {"count": 0, "status": "SOFTWARE_TRACE_SEPARATE_FROM_PHYSICAL_IDENTITY"},
        "shadow_proposals": {"count": 3, "status": "SOFTWARE_TRACE_SEPARATE_FROM_PHYSICAL_IDENTITY"},
        "simulated_stable_recoveries": {"count": 2, "cases": [k for k, v in software_stable.items() if v == "STABLE"]},
        "physically_verified_incremental_recovery": len(verified_rescue),
        "false_attach_verified": len(false_attach),
        "negative_controls_verified": len(verified_controls),
        "unknown_identity_cases": len(unknown),
        "parity_status": parity_status,
        "game_accuracy": "UNKNOWN",
        "active_enabled": False,
        "decision": "BLOCK_ACTIVE" if false_attach else "SHADOW_ONLY_NEEDS_REVIEW",
    }
    (out_dir / "human_review_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(out_dir / "verified_rescue_cases.csv", verified_rescue, REVIEW_FIELDS)
    write_csv(out_dir / "rejected_or_ambiguous_cases.csv", rejected, REVIEW_FIELDS)
    lines = ["# V7.8.8 Decision Report", "", f"Review source: `{source}`", "", "## Human review", "", f"- Cases: **{len(rows)}** (rescue={len(rescue)}, negative controls={len(negatives)}, parity={len(parity)}).", f"- `manual_review_complete`: **{summary['manual_review_complete']}**.", f"- Physically verified incremental rescue: **{len(verified_rescue)}**.", f"- False attach verified: **{len(false_attach)}**.", f"- Negative controls verified: **{len(verified_controls)}**.", "- Unreviewed/unknown cases are not treated as successes or failures.", "", "## Software A/B (not physical truth)", "", "- Legacy and Shadow results remain separate; Shadow produced three simulated rescue transitions, two stable and one unstable.", "- `FIRED`, key_down, UID continuity and replay recovery are not game judgments.", "", "## Parity", "", f"- Semantic replay parity: **{parity_status}**; recorded 1654 unique edges vs replay 1656 (extra=2, missing=0).", "- 0 extra/0 missing is required for PASS. Frame 385 and 546 remain trace-semantic audit cases; no replay edge was deleted.", "", "## Gate", "", f"**{summary['decision']}**", "", "- PF Active remains OFF; Legacy remains the real input path.", "- Game accuracy: **UNKNOWN** (no direct game judgment source).", "- No detector, tracker, planner, scheduler, Hold or safety gate was modified by this aggregation.", "- Full pytest result: see `pytest_v788.txt`.", ""]
    (out_dir / "V7_8_8_DECISION_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-dir", default=str(ROOT / "output" / "v788_visual_identity_review"))
    parser.add_argument("--review-csv")
    parser.add_argument("--out-dir")
    args = parser.parse_args()
    review_dir = Path(args.review_dir).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else review_dir
    raise SystemExit(summarize(review_dir, Path(args.review_csv).expanduser().resolve() if args.review_csv else None, out_dir))


if __name__ == "__main__":
    main()
