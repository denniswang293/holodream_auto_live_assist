import json
from pathlib import Path

import cv2
import numpy as np

from src.detector import Candidate, detect
from src.geometry import Playfield
from src.simple_tracker import SimpleTracker


def _detector_cfg():
    cfg = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text())
    return cfg, {**cfg["detector"], "reference_resolution": cfg["reference_resolution"]}


def _tap(y=180, *, diagnostic_id=""):
    return Candidate((280, int(y - 3), 65, 6), "cyan_bar", .9, .38, .52,
                     ["F"], "tap", body_bbox=(280, int(y - 3), 65, 6),
                     diagnostic_id=diagnostic_id)


def test_detector_trace_is_optional_and_does_not_change_candidates():
    cfg, detector_cfg = _detector_cfg()
    frame = np.zeros((404, 720, 3), np.uint8)
    cv2.rectangle(frame, (280, 200), (345, 207), (255, 255, 0), -1)
    off = detect(frame, Playfield.from_config(cfg["playfield"]), cfg["key_map"], detector_cfg,
                 frame_index=10)
    diagnostics = {}
    on_cfg = {**detector_cfg, "association_diagnostics": {"enabled": True}}
    on = detect(frame, Playfield.from_config(cfg["playfield"]), cfg["key_map"], on_cfg,
                diagnostics, frame_index=10)
    assert [(c.bbox, c.appearance, c.note_type, c.candidate_keys) for c in off] == \
           [(c.bbox, c.appearance, c.note_type, c.candidate_keys) for c in on]
    assert diagnostics.get("candidate_trace")
    assert all(str(row["frame"]) == "10" for row in diagnostics["candidate_trace"])


def test_tracker_trace_records_match_and_preserves_last_real_observation_during_coast():
    tracker = SimpleTracker({"confirm_observations": 3, "max_gap_s": .16},
                            {"min_observations": 3, "min_velocity": 20}, hit_y=295.5)
    first_trace = {"max_rows": 100}
    tracks = tracker.update([_tap(180, diagnostic_id="1:candidate:0")], 10.0,
                            trace=first_trace, frame_index=1, capture_gap_ms=16)
    track_id = tracks[0].track_id
    assert first_trace["track_rows"][0]["state_transition"] == "new"
    second_trace = {"max_rows": 100}
    tracks = tracker.update([_tap(186, diagnostic_id="2:candidate:0")], 10.016,
                            trace=second_trace, frame_index=2, capture_gap_ms=16)
    assert any(row["accepted"] and row["assigned"] for row in second_trace["pair_rows"])
    assert any(row["track_id"] == track_id and row["matched_this_frame"]
               for row in second_trace["track_rows"])
    coast_trace = {"max_rows": 100}
    tracks = tracker.update([], 10.08, trace=coast_trace, frame_index=3, capture_gap_ms=64)
    state = next(row for row in coast_trace["track_rows"] if row["track_id"] == track_id)
    assert state["coasting_this_frame"] is True
    assert state["last_real_observation_timestamp"] == 10.016
    assert state["time_since_last_real_observation_ms"] > 60


def test_tracker_trace_reports_actual_max_gap_termination_reason():
    tracker = SimpleTracker({"max_gap_s": .05, "max_missed_frames": 8},
                            {"min_observations": 3}, hit_y=295.5)
    tracker.update([_tap(180, diagnostic_id="1:candidate:0")], 1.0,
                   frame_index=1, trace={"max_rows": 100})
    trace = {"max_rows": 100}
    tracker.update([], 1.10, frame_index=2, trace=trace)
    state = next(row for row in trace["track_rows"] if row["track_id"] == 1)
    assert state["termination_reason"] == "track_expired_max_gap"
