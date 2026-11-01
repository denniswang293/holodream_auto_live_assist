from tools.run_v786_replay_validation import raw_and_semantic_parity


def test_canonical_parity_deduplicates_pair_and_assignment_trace_rows(tmp_path):
    recorded = [
        {"assigned": "True", "source_frame": "10", "capture_timestamp": "1.25", "track_id": "7", "candidate_id": "10:candidate:0"},
        {"assigned": "True", "source_frame": "10", "capture_timestamp": "1.25", "track_id": "7", "candidate_id": "10:candidate:0"},
    ]
    replay = [{"frame": 10, "timestamp": "1.25", "track_id": 1, "candidate_id": "10:candidate:0"}]
    raw, semantic, _ = raw_and_semantic_parity(recorded, replay, tmp_path)
    assert raw["recorded_assigned_rows"] == 2
    assert raw["recorded_duplicate_rows"] == 1
    assert semantic["semantic_assignment_parity"] == "PASS"


def test_canonical_parity_retains_replay_extra_edge(tmp_path):
    recorded = [{"assigned": "True", "source_frame": "10", "capture_timestamp": "1.25", "track_id": "7", "candidate_id": "10:candidate:0"}]
    replay = [
        {"frame": 10, "timestamp": "1.25", "track_id": 1, "candidate_id": "10:candidate:0"},
        {"frame": 11, "timestamp": "1.30", "track_id": 1, "candidate_id": "11:candidate:0"},
    ]
    _, semantic, _ = raw_and_semantic_parity(recorded, replay, tmp_path)
    assert semantic["semantic_assignment_parity"] == "PARTIAL"
    assert semantic["extra_edges"] == 1
