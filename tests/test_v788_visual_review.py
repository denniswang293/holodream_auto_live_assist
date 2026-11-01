from pathlib import Path

from tools.build_v788_visual_review import (
    REVIEW_FIELDS,
    add_parity_review_rows,
    html_page,
    normalize_review_rows,
    sample_index,
)


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


def test_review_schema_preserves_unknown_and_ambiguous():
    rows = normalize_review_rows([_review("unknown"), {**_review("amb"), "same_physical_note_verdict": "AMBIGUOUS"}])
    assert rows[0]["same_physical_note_verdict"] == "UNKNOWN"
    assert rows[1]["same_physical_note_verdict"] == "AMBIGUOUS"
