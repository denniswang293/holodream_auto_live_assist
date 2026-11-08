import csv
import json
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from compare_rebuild import (
    automated_downs,
    evaluate,
    load_tracks,
    map_tracks_to_notes,
    supported_truth,
    track_overlap,
    track_samples,
)


def test_track_overlap_uses_motion_not_identifiers():
    note = {"head_samples_json": json.dumps([[1.0, 20, .1, .25], [1.1, 30, .1, .25], [1.2, 40, .1, .25], [1.3, 50, .1, .25]])}
    track = {"tracker": "new", "note_uid": "entirely-different-id", "history": json.dumps([
        {"capture_timestamp": 1.0, "leading_edge_y": 20, "u_span": [.1, .25]},
        {"capture_timestamp": 1.1, "leading_edge_y": 30, "u_span": [.1, .25]},
        {"capture_timestamp": 1.2, "leading_edge_y": 40, "u_span": [.1, .25]},
        {"capture_timestamp": 1.3, "leading_edge_y": 50, "u_span": [.1, .25]},
    ])}
    assert track_overlap(note, track_samples(track)) == (.30000000000000004, 0.0)


@pytest.mark.parametrize('tracker',['legacy','simple'])
def test_old_center_history_converts_to_bbox_bottom(tracker):
    track = {"tracker": tracker, "history": json.dumps([
        {"capture_timestamp": 1, "y": 20, "bbox": [0, 17, 10, 6]}
    ])}
    assert track_samples(track)[0]["y"] == 23


def test_baseline_physical_export_alias_joins_its_own_action_schema():
    tracks=load_tracks([dict(run_id='run_x',note_uid='run_x:physical:7',tracker='legacy',
        track_id='7',history='[{"capture_timestamp":1,"y":20,"u_span":[0,0.2]}]')])
    assert 'run_x:7' in tracks[0][0]['_aliases']


def test_adjacent_notes_without_clear_track_margin_remain_unmapped():
    points = [[1.0, 20, .1, .25], [1.1, 30, .1, .25], [1.2, 40, .1, .25], [1.3, 50, .1, .25]]
    notes = [
        {"run_id": "r", "physical_note_id": "n1", "color": "cyan", "head_samples_json": json.dumps(points)},
        {"run_id": "r", "physical_note_id": "n2", "color": "cyan",
         "head_samples_json": json.dumps([[t, y + 2, lo, hi] for t, y, lo, hi in points])},
    ]
    tracks = [{"run_id": "r", "event_id": "newly-renumbered", "capture_timestamp": t,
               "y": y, "span": json.dumps([.1, .25]), "color": "cyan"}
              for t, y, *_ in points]
    loaded = load_tracks(tracks)
    assert map_tracks_to_notes(notes, loaded) == {}


def test_flat_replay_track_rows_use_capture_time_span_and_appearance():
    rows = [{"run_id": "r", "event_id": "renumbered-track", "capture_timestamp": str(t),
             "y": str(y), "span": json.dumps([.1, .25]), "native_bbox": "[10,20,30,5]"}
            for t, y in ((1.0, 20), (1.1, 30), (1.2, 40), (1.3, 50))]
    loaded = load_tracks(rows, [{"run_id": "r", "note_uid": "renumbered-track", "color": "cyan"}])
    assert loaded[0][0]["color"] == "cyan"
    assert loaded[0][1][-1] == {"t": 1.3, "y": 50.0, "lo": .1, "hi": .25}


def test_manual_review_reattaches_by_action_when_physical_uid_changed():
    machine = [{"run_id": "r", "physical_note_id": "current-n1", "action_id": "a1", "record_type": "MATCH"}]
    manual = [{"run_id": "r", "physical_note_id": "old-extraction-n2", "action_id": "a1", "accepted_visual_match": "true"}]
    truth, reviewed = supported_truth(machine, manual)
    assert set(truth) == {("r", "current-n1")}
    assert reviewed == {("r", "current-n1")}
    assert truth[("r", "current-n1")]["action_id"] == "a1"
    assert ("r", "old-extraction-n2") not in truth


def test_simulated_event_pair_becomes_one_action_down():
    events = [
        {"run_id": "r", "event_id": "e", "action": "key_down", "key": "J", "timestamp": "3.0"},
        {"run_id": "r", "event_id": "e", "action": "key_up", "key": "J", "timestamp": "3.2"},
    ]
    rows = automated_downs(events)
    assert len(rows) == 1
    assert rows[0]["down"] == 3.0
    assert rows[0]["up"] == 3.2


def write_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_evaluate_marks_unmatched_hypothesis_unknown(tmp_path: Path):
    ref, baseline, rebuild, output = (tmp_path / n for n in ("reference", "baseline", "rebuild", "out"))
    write_csv(ref / "physical_notes.csv", [
        {"run_id": "r", "physical_note_id": "known", "kind": "tap", "color": "cyan",
         "head_samples_json": json.dumps([[1.0, 20, .68, .8], [1.1, 30, .68, .8], [1.2, 40, .68, .8], [1.3, 50, .68, .8]])},
        {"run_id": "r", "physical_note_id": "unknown", "kind": "tap", "color": "pink", "head_samples_json": "[]"},
    ])
    write_csv(ref / "note_action_matches.csv", [{"record_type": "MATCH", "run_id": "r", "physical_note_id": "known", "action_id": "human"}])
    write_csv(ref / "player_actions.csv", [{"run_id": "r", "action_id": "human", "key": "J", "down_timestamp": "1.1", "up_timestamp": "1.3"}])
    write_csv(baseline / "simulated_actions.csv", [{"run_id": "r", "event_id": "b", "action": "key_down", "key": "K", "timestamp": "1.12", "track_uid": "btrack"}])
    write_csv(baseline / "track_summary.csv", [{"run_id": "r", "note_uid": "btrack", "tracker": "new", "history": json.dumps([
        {"capture_timestamp": 1.0, "leading_edge_y": 20, "u_span": [.68, .8]},
        {"capture_timestamp": 1.1, "leading_edge_y": 30, "u_span": [.68, .8]},
        {"capture_timestamp": 1.2, "leading_edge_y": 40, "u_span": [.68, .8]},
        {"capture_timestamp": 1.3, "leading_edge_y": 50, "u_span": [.68, .8]},
    ])}])
    for name in ("simulated_actions.csv", "track_summary.csv"):
        source = baseline / name
        dest = rebuild / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    summary = evaluate(ref, baseline, rebuild, output)
    with (output / "per_note_comparison.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["ground_truth_status"] == "SUPPORTED_MATCH"
    assert rows[0]["baseline_action_id"] == "b"
    assert rows[0]["human_key"] == "J"
    assert rows[0]["baseline_key"] == "K"
    assert rows[1]["ground_truth_status"] == "UNKNOWN"
    assert summary["unknown_hypotheses"] == 1
    assert summary["game_accuracy"] == "UNVERIFIED"


def test_missing_new_outputs_fail_without_creating_evaluation(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="comparison requires existing outputs"):
        evaluate(tmp_path / "ref", tmp_path / "base", tmp_path / "new", tmp_path / "out")
    assert not (tmp_path / "out").exists()
