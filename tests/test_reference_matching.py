import pytest
import csv
from pathlib import Path

from src.evaluation import match_reference


def note(note_id, key="S", crossing=1.0, kind="tap", tail_crossing=None):
    lane_ids = ["SDFJKL".index(k) for k in key.split("|") if k in "SDFJKL"]
    lo, hi = (min(lane_ids) / 6, (max(lane_ids) + 1) / 6) if lane_ids else (0, 1 / 6)
    head = [
        {"t": crossing - .2, "leading_edge_y": 300.0, "span_lo": lo, "span_hi": hi, "source_frame": 10},
        {"t": crossing, "leading_edge_y": 325.5, "span_lo": lo, "span_hi": hi, "source_frame": 20},
        {"t": crossing + .2, "leading_edge_y": 351.0, "span_lo": lo, "span_hi": hi, "source_frame": 30},
    ]
    tail = []
    if tail_crossing is not None:
        tail = [
            {"t": tail_crossing - .2, "trailing_edge_y": 300.0, "span_lo": lo, "span_hi": hi, "source_frame": 100},
            {"t": tail_crossing, "trailing_edge_y": 325.5, "span_lo": lo, "span_hi": hi, "source_frame": 110},
            {"t": tail_crossing + .2, "trailing_edge_y": 351.0, "span_lo": lo, "span_hi": hi, "source_frame": 120},
        ]
    return {"run_id": "r", "physical_note_id": note_id, "kind": kind, "keys": key,
            "head_samples_json": head, "tail_samples_json": tail,
            "visual_crossing_timestamp": crossing, "crossing_status": "OBSERVED",
            "tail_crossing_timestamp": tail_crossing, "first_frame": 10, "last_frame": 30}


def action(action_id, key="S", down=1.0, up=1.1):
    return {"run_id": "r", "action_id": action_id, "key": key,
            "down_timestamp": down, "up_timestamp": up, "duration_s": up - down,
            "status": "complete"}


def test_simultaneous_two_heads_match_distinct_actions():
    rows = match_reference([note("nS", "S"), note("nD", "D")],
                           [action("aS", "S"), action("aD", "D")])
    pairs = {(r["physical_note_id"], r["action_id"]) for r in rows if r["record_type"] == "MATCH"}
    assert pairs == {("nS", "aS"), ("nD", "aD")}


def test_one_wide_head_cannot_consume_two_actions():
    rows = match_reference([note("wide", "S|D")],
                           [action("aS", "S"), action("aD", "D")])
    assert sum(r["record_type"] == "MATCH" for r in rows) == 0
    assert sum(r["record_type"] == "ACTION" for r in rows) == 2
    assert sum(r["record_type"] == "NOTE" for r in rows) == 1


def test_same_key_consecutive_notes_resolve_by_motion_and_time():
    rows = match_reference([note("n1", crossing=1.0), note("n2", crossing=2.0)],
                           [action("a1", down=1.0), action("a2", down=2.0)])
    pairs = {(r["physical_note_id"], r["action_id"]) for r in rows if r["record_type"] == "MATCH"}
    assert pairs == {("n1", "a1"), ("n2", "a2")}


def test_hold_requires_matching_tail_interval_evidence():
    held = note("hold", kind="hold", tail_crossing=2.0)
    rows = match_reference([held], [action("long", down=1.0, up=2.0)])
    match = next(r for r in rows if r["record_type"] == "MATCH")
    assert match["reason"].endswith("with_hold_tail_interval")
    assert match["tail_observed_y"] == pytest.approx(325.5)
    rows = match_reference([note("missing-tail", kind="hold")],
                           [action("long", down=1.0, up=2.0)])
    assert all(r["record_type"] != "MATCH" for r in rows)


def test_illegal_nearest_key_is_not_paired():
    rows = match_reference([note("s-note", "S")], [action("near-d", "D", down=1.0)])
    assert {r["record_type"] for r in rows} == {"NOTE", "ACTION"}
    assert all(r["reason"] == "no_supported_candidate" for r in rows)


def test_duplicate_physical_hypotheses_are_left_ambiguous():
    rows = match_reference([note("n1"), note("n2")], [action("a")])
    assert not any(r["record_type"] == "MATCH" for r in rows)
    assert sum(r["record_type"] == "NOTE" for r in rows) == 2
    unmatched_action = next(r for r in rows if r["record_type"] == "ACTION")
    assert unmatched_action["candidate_note_ids"] == "n1|n2"


def test_output_is_review_only_and_reports_numeric_cost_not_probability():
    match = next(r for r in match_reference([note("n")], [action("a")]) if r["record_type"] == "MATCH")
    assert match["review_status"] == "AUTOSUPPORTED_NOT_MANUAL"
    assert match["confidence_basis"] == "numeric_cost_margin_not_probability"
    assert match["game_accuracy"] == "UNVERIFIED"
    assert isinstance(match["cost"], float)


def test_list_sample_schema_checks_lane_at_action_time():
    row = note("pooled", "S|D")
    # It was in lane D at the hit, even though the whole trajectory's pooled
    # key mask includes S. The S action is illegal at this specific time.
    row["head_samples_json"] = [
        [0.8, 300.0, 1 / 6, 1 / 3],
        [1.0, 325.5, 1 / 6, 1 / 3],
        [1.2, 351.0, 1 / 6, 1 / 3],
    ]
    row["head_frames_json"] = "[41,42,43]"
    row["keys"] = "S|D"
    rows = match_reference([row], [action("wrong-lane", "S")])
    assert not any(r["record_type"] == "MATCH" for r in rows)
    assert {r["record_type"] for r in rows} == {"NOTE", "ACTION"}


def test_exact_first_session_csv_rows_parse_and_preserve_frame_provenance():
    root = Path(__file__).resolve().parents[1]
    notes_path = root / "output/analysis_reference/run_20261106T164049_800126Z_physical_notes.csv"
    actions_path = root / "output/analysis_reference/player_actions.csv"
    with notes_path.open(encoding="utf-8-sig", newline="") as f:
        notes = list(csv.DictReader(f))[:1]
    with actions_path.open(encoding="utf-8-sig", newline="") as f:
        actions = [r for r in csv.DictReader(f) if r["run_id"] == notes[0]["run_id"]][:1]
    rows = match_reference(notes, actions)
    # This early menu-era action is not forced onto a later crossing, despite
    # the note's pooled all-lane hypothesis mask.
    assert not any(r["record_type"] == "MATCH" for r in rows)
    assert any(r["record_type"] == "ACTION" and r["action_id"] == actions[0]["action_id"] for r in rows)


def test_exact_first_session_matching_row_uses_sample_frame_and_local_span():
    root = Path(__file__).resolve().parents[1]
    notes_path = root / "output/analysis_reference/run_20261106T164049_800126Z_physical_notes.csv"
    actions_path = root / "output/analysis_reference/player_actions.csv"
    with notes_path.open(encoding="utf-8-sig", newline="") as f:
        visual = {r["physical_note_id"]: r for r in csv.DictReader(f)}
    with actions_path.open(encoding="utf-8-sig", newline="") as f:
        physical = {r["action_id"]: r for r in csv.DictReader(f)}
    note_id = "run_20261106T164049_800126Z/note:4"
    action_id = "run_20261106T164049_800126Z:D:000003"
    match = next(r for r in match_reference([visual[note_id]], [physical[action_id]])
                 if r["record_type"] == "MATCH")
    assert match["source_frame"] == 98
    assert match["key_lane_overlap"] >= .05
    assert .0 <= match["observed_span_lo"] < match["observed_span_hi"] <= 1.0
