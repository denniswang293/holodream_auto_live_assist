import csv
import json

from tools.run_v789_uid_mapping_audit import namespace_audit, parity_audit


def review(case_id, frame, candidate):
    return {
        "case_id": case_id, "source_frame": frame, "candidate_id": candidate,
        "same_physical_note_verdict": "SAME_PHYSICAL_NOTE", "visual_confidence": "HIGH",
        "reviewer_status": "REVIEWED", "game_judgment": "UNKNOWN",
    }


def test_cross_namespace_same_candidate_stays_ambiguous(tmp_path):
    namespace_audit(
        [review("rescue_408_simple5", "408", "408:candidate:0")],
        [{"case_id": "rescue_408_simple5", "old_uid": "simple:5", "software_stability": "UNSTABLE"}],
        {"408:candidate:0": [{"track_uid": "simple:1000004", "note_uid": "live-note"}]},
        {},
        tmp_path,
    )
    rows = list(csv.DictReader((tmp_path / "namespace_uid_mapping.csv").open(encoding="utf-8-sig")))
    assert rows[0]["mapping_class"] == "AMBIGUOUS_NAMESPACE_MAPPING"
    assert rows[0]["live_track_uids"] == "simple:1000004"
    ownership = list(csv.DictReader((tmp_path / "candidate_ownership_audit.csv").open(encoding="utf-8-sig")))
    assert ownership[0]["double_owned_same_namespace"] == "False"


def test_parity_audit_keeps_extra_edges_visible(tmp_path):
    v787 = tmp_path / "v787"; run = tmp_path / "run"; v787.mkdir(); run.mkdir()
    (v787 / "baseline_parity_semantic.json").write_text(json.dumps({"recorded_unique_edges": 1, "replay_unique_edges": 2, "extra_edges": 1, "missing_edges": 0}), encoding="utf-8")
    (run / "live_association_attempts.csv").write_text("candidate_id,source_frame\n", encoding="utf-8")
    (run / "live_candidate_trace.csv").write_text("candidate_id,source_frame,stage\n385:candidate:0,385,candidate_final\n546:candidate:11,546,candidate_final\n", encoding="utf-8")
    parity_audit(v787, run, tmp_path)
    data = json.loads((tmp_path / "assignment_parity_after.json").read_text(encoding="utf-8"))
    assert data["status"] == "PARTIAL_SOURCE_INSUFFICIENT"
    rows = list(csv.DictReader((tmp_path / "assignment_parity_diff.csv").open(encoding="utf-8-sig")))
    assert rows[0]["earliest_divergence"] == "candidate_final_present_without_live_assignment_trace"
