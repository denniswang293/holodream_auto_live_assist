from pathlib import Path

from tools.build_v788_visual_review import (
    REVIEW_FIELDS,
    add_parity_review_rows,
    html_page,
    normalize_review_rows,
    sample_index,
)
from tools.import_v788_review import merge, read_incoming


def _review(case_id="x"):
    return {field: "" for field in REVIEW_FIELDS} | {
        "case_id": case_id,
        "same_physical_note_verdict": "UNKNOWN",
        "visual_confidence": "UNKNOWN",
        "reviewer_status": "UNREVIEWED",
        "game_judgment": "UNKNOWN",
    }


def test_timestamp_window_uses_capture_timestamp_not_frame_division():
    index = [
        {"source_frame": "10", "capture_timestamp": "100.000", "source_video_frame": "0"},
        {"source_frame": "30", "capture_timestamp": "100.400", "source_video_frame": "1"},
        {"source_frame": "99", "capture_timestamp": "101.000", "source_video_frame": "2"},
    ]
    selected = sample_index(index, 100.4, 500, limit=20)
    assert [r["source_frame"] for r in selected] == ["10", "30"]


def test_parity_cases_are_added_without_changing_existing_rows():
    rows = [_review("nc-001")]
    divergence = [
        {"source_frame": "385", "target_candidate_id": "385:candidate:0"},
        {"source_frame": "546", "target_candidate_id": "546:candidate:11"},
    ]
    candidates = [
        {"source_frame": "385", "stage": "candidate_final", "candidate_id": "385:candidate:0", "appearance": "cyan_bar", "candidate_keys": "S"},
        {"source_frame": "546", "stage": "candidate_final", "candidate_id": "546:candidate:11", "appearance": "pink_candidate", "candidate_keys": "L"},
    ]
    result = add_parity_review_rows(rows, divergence, candidates)
    assert [r["case_id"] for r in result] == ["nc-001", "parity_385", "parity_546"]
    assert all(r["reviewer_status"] == "UNREVIEWED" for r in result)


def test_html_escapes_trace_text_and_is_offline():
    case = {
        "case_id": "x<script>alert(1)</script>",
        "evidence_status": "READY",
        "source_record": {"source_frame": "1", "capture_timestamp": "2"},
        "inference": {"review": _review("x<script>alert(1)</script>")},
        "media": {"frames": []},
    }
    page = html_page([case], REVIEW_FIELDS)
    assert "<script>alert(1)</script>" not in page
    assert "fetch(" not in page
    assert "physical_identity_review_completed.csv" in page
    assert "String.fromCharCode(10)" in page
    assert "function csvEscape(v){" in page


def test_review_schema_preserves_unknown_and_ambiguous():
    rows = normalize_review_rows([_review("unknown"), {**_review("amb"), "same_physical_note_verdict": "AMBIGUOUS"}])
    assert rows[0]["same_physical_note_verdict"] == "UNKNOWN"
    assert rows[1]["same_physical_note_verdict"] == "AMBIGUOUS"


def test_partial_review_merge_preserves_unsubmitted_cases(tmp_path):
    base = [_review("a"), _review("b")]
    incoming = [{**_review("a"), "same_physical_note_verdict": "SAME_PHYSICAL_NOTE", "visual_confidence": "HIGH", "reviewer_status": "REVIEWED"}]
    from tools.build_v788_visual_review import write_csv
    write_csv(tmp_path / "physical_identity_review_template.csv", base, REVIEW_FIELDS)
    write_csv(tmp_path / "incoming.csv", incoming, REVIEW_FIELDS)
    assert merge(tmp_path, tmp_path / "incoming.csv") == 0
    merged = normalize_review_rows(__import__('csv').DictReader((tmp_path / "physical_identity_review_completed.csv").open(encoding='utf-8')))
    assert merged[0]["reviewer_status"] == "REVIEWED"
    assert merged[1]["reviewer_status"] == "UNREVIEWED"


def test_headerless_legacy_review_csv_is_supported(tmp_path):
    row = _review("rescue_399_simple5")
    row["same_physical_note_verdict"] = "SAME_PHYSICAL_NOTE"
    row["visual_confidence"] = "HIGH"
    row["reviewer_status"] = "REVIEWED"
    path = tmp_path / "headerless.csv"
    path.write_text(",".join(row[field] for field in REVIEW_FIELDS) + "\n", encoding="utf-8")
    loaded = read_incoming(path)
    assert loaded[0]["case_id"] == "rescue_399_simple5"
