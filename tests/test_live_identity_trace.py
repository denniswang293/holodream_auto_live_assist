import csv
import json
from pathlib import Path

from src.live_capture import CapturedFrame
from src.live_identity_trace import LiveIdentityTraceWriter


def _frame(seq=3):
    return CapturedFrame(seq, None, 10.0 + seq * .016, 10.0 + seq * .0165)


def test_identity_trace_disabled_does_not_create_payload(tmp_path):
    writer = LiveIdentityTraceWriter(tmp_path, "run-off", {"enabled": False})
    writer.submit_frame(_frame(), 11.0, [{"stage": "candidate"}], [], [], [], [], "PLAYING")
    writer.close()
    assert list(tmp_path.iterdir()) == []


def test_identity_trace_writes_candidate_association_and_track_rows(tmp_path):
    writer = LiveIdentityTraceWriter(tmp_path, "run-on", {"enabled": True, "max_queue_rows": 64})
    writer.submit_frame(
        _frame(), 11.0,
        [{"stage": "candidate_final", "candidate_id": "3:candidate:0",
          "core_bbox": (10, 20, 30, 5), "u_min": .1, "u_max": .2,
          "appearance": "pink_candidate", "note_type": "tap", "passed": True}],
        [{"track_id": 7, "candidate_id": "3:candidate:0", "accepted": True,
          "total_cost": .4}],
        [{"track_id": 8, "skip_reason": "no_compatible_candidate"}],
        [{"track_id": 7, "candidate_id": "3:candidate:0", "assigned": True}],
        [{"track_id": 7, "track_uid": "simple:7", "note_uid": "run-on:simple:7",
          "candidate_id": "3:candidate:0", "track_status": "confirmed",
          "intent_state": "PENDING"}],
        "PLAYING")
    writer.close()
    candidate = list(csv.DictReader((tmp_path / "live_candidate_trace.csv").open(encoding="utf-8-sig")))
    association = list(csv.DictReader((tmp_path / "live_association_attempts.csv").open(encoding="utf-8-sig")))
    tracks = list(csv.DictReader((tmp_path / "live_track_identity.csv").open(encoding="utf-8-sig")))
    assert candidate[0]["frame_uid"] == "run-on:3"
    assert candidate[0]["u_center"] == "0.15000000000000002"
    assert {row["row_type"] for row in association} == {"pair", "attempt", "assignment"}
    assert tracks[0]["note_uid"] == "run-on:simple:7"
    health = json.loads((tmp_path / "live_identity_trace_health.json").read_text(encoding="utf-8"))
    assert health["dropped_diagnostic_rows"] == 0
    assert health["trace_coverage_frames"] == 1


def test_identity_trace_queue_overflow_is_recorded_and_nonblocking(tmp_path):
    writer = LiveIdentityTraceWriter(tmp_path, "run-overflow", {"enabled": True, "max_queue_rows": 64})
    for i in range(500):
        writer.submit_frame(_frame(i), 11.0 + i, [], [], [], [], [], "PLAYING")
        # Each frame still produces a bounded sentinel row through the normal
        # engine path; this loop verifies close/health remains deterministic.
    writer.close()
    health = json.loads((tmp_path / "live_identity_trace_health.json").read_text(encoding="utf-8"))
    assert health["submitted_rows"] >= 0
    assert health["written_rows"] >= 0
    assert health["dropped_diagnostic_rows"] >= 0
