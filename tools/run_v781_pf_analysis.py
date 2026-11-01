"""Produce the V7.8.1 PF-assisted continuity evidence package.

The package is safe to run after old recordings have been cleaned.  It writes
an explicit DATA_UNAVAILABLE/INSUFFICIENT_GROUND_TRUTH result when the source
run or video is absent; it never synthesizes UID or physical-note outcomes.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "output" / "run_20261031T201055_348946Z"
OUT = ROOT / "output" / "v781_pf_tracker_continuity"


def write_csv(path: Path, fields: list[str], rows: list[dict] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        wr = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        wr.writeheader()
        for row in rows or []:
            wr.writerow(row)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    required = [
        "live_source.mp4", "live_video_index.csv", "live_candidate_trace.csv",
        "live_association_attempts.csv", "live_track_identity.csv", "live_identity_trace_health.json",
        "live_events.csv", "tap_intents.csv", "tap_decisions.csv", "live_key_actions.csv",
    ]
    available = {name: (RUN / name).exists() for name in required}
    source_fallback = ROOT / "output" / "assist" / RUN.name / "live_source.mp4"
    overlay_fallback = ROOT / "output" / "assist" / RUN.name / "live_overlay.mp4"
    if not available["live_source.mp4"] and source_fallback.exists():
        available["live_source.mp4"] = True
    hashes = {}
    for name in required:
        path = RUN / name
        if path.exists():
            hashes[name] = sha256(path)
    if source_fallback.exists():
        hashes["live_source.mp4:fallback"] = sha256(source_fallback)
    manifest = {
        "plan": "V7.8.1_PF_ASSISTED_TRACK_CONTINUITY",
        "baseline_commit": "b748b5b29f6dc04c84b0934cb73b30e10ce3a03f",
        "run": str(RUN), "available_files": available, "sha256": hashes,
        "status": "DATA_UNAVAILABLE" if not all(available.values()) else "READY_FOR_REPLAY",
        "source_video": str(source_fallback if source_fallback.exists() else RUN / "live_source.mp4"),
        "overlay_video": str(overlay_fallback),
        "timestamp_policy": "capture_timestamp + source_frame via live_video_index; no frame/60 substitution",
        "physical_truth": "UNKNOWN",
        "note": "Previous cleanup removed the source run and recordings from the working tree; no raw replay was fabricated.",
    }
    (OUT / "evidence_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    timeout_fields = ["note_uid", "track_id", "first_lost_source_frame", "last_real_source_frame",
                      "reacquisition_count", "last_usable_prediction", "first_irreversible_deadline",
                      "classification", "confidence", "evidence", "counterevidence"]
    for name, fields in (("baseline_timeout_episode.csv", timeout_fields),
                         ("timeout_recovery_audit.csv", timeout_fields),
                         ("confirmed24_true_blockers.csv", timeout_fields),
                         ("physical_note_review_queue.csv", ["physical_note_id", "source_frame", "candidate_id", "track_id", "appearance", "status", "game_judgment"]),
                         ("reacquisition_case_table.csv", ["case_id", "old_uid", "candidate_id", "source_frame", "decision", "reason", "confidence"]),
                         ("false_attach_negative_controls.csv", ["case_id", "negative_control", "decision", "reason", "physical_truth"]),
                         ("confirmed24_ab.csv", ["note_uid", "baseline_status", "shadow_status", "reacquired", "scheduled", "game_judgment"]),
                         ("pf_reassociation_proposals.csv", ["source_frame", "capture_timestamp", "old_uid", "candidate_id", "decision", "reason", "input_sent"])):
        write_csv(OUT / name, fields)

    test = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT,
                          text=True, capture_output=True)
    (OUT / "pytest_v781.txt").write_text(test.stdout + test.stderr, encoding="utf-8")
    (OUT / "performance_safety_summary.json").write_text(json.dumps({
        "status": "NOT_MEASURED_SOURCE_UNAVAILABLE",
        "no_frame_drop_policy_change": True,
        "no_detector_scope_change": True,
        "pf_shadow_diagnostic_only": True,
    }, indent=2), encoding="utf-8")
    (OUT / "pf_tracker_shadow_ab.json").write_text(json.dumps({
        "status": "INSUFFICIENT_GROUND_TRUTH",
        "baseline": "Legacy tracker + Particle Filter active path",
        "shadow": "PF-assisted real-candidate proposal layer, default OFF",
        "source_replay": "DATA_UNAVAILABLE",
        "physical_note_denominator": "UNKNOWN",
        "active_enabled": False,
        "reason": "The V7.8 source run, trace CSVs and video were deleted during cleanup; no A/B or physical identity claim is made.",
    }, indent=2), encoding="utf-8")
    (OUT / "PF_TRACKER_AB_REPORT.md").write_text(
        "# V7.8.1 PF Tracker Shadow A/B\n\n"
        "Status: `INSUFFICIENT_GROUND_TRUTH` / `DATA_UNAVAILABLE`.\n\n"
        "The requested source run and recordings were removed during the previous project cleanup. "
        "The package therefore contains schemas and a runnable Shadow implementation, but no fabricated replay rows. "
        "No UID, physical note, reacquisition, or game judgment result is inferred.\n\n"
        "The Shadow layer is default OFF, requires a real candidate, preserves hard gates, cannot fire from coasting, "
        "and never mutates observations or sends input.\n", encoding="utf-8")
    (OUT / "V7_8_1_RESULT.md").write_text(
        "# HoloDream V7.8.1 Result\n\n"
        f"- Baseline source: `{RUN}`\n"
        f"- Data status: `{manifest['status']}`\n"
        "- PF-assisted reassociation: implemented as a bounded Shadow proposal layer; config default is `enabled=false`, `mode=shadow`.\n"
        "- Active Legacy Planner/PF path: unchanged.\n"
        "- Pure PF prediction cannot create a candidate, observation, UID, keydown or Hold action.\n"
        "- `FIRED`, `key_down` and software UID counts are not game accuracy.\n"
        "- Active promotion: **NO**; minimum two manually confirmed lost→reacquired physical notes are unavailable.\n\n"
        "## Code and rollback\n\n"
        "The rollback is `pf_assisted_reassociation.enabled=false` in `config.json`; no active path reads Shadow proposals.\n\n"
        "## Required evidence to continue\n\n"
        "Restore or provide one clean source run with `live_video_index.csv`, the three trace CSVs, lifecycle CSVs and "
        "source video. Then run the same tool and manually label at least two physical lost→reacquired cases plus ten negative controls.\n",
        encoding="utf-8")
    print(json.dumps({"output": str(OUT), "status": manifest["status"], "pytest_exit": test.returncode}, indent=2))


if __name__ == "__main__":
    main()
