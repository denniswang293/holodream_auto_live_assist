from tools.run_v787_identity_validation import edge_timelines


def test_extra_edge_timeline_keeps_trace_semantics_visible(tmp_path):
    index = [{"source_frame": "385", "capture_timestamp": "29152.4751039"}]
    candidates = [{"source_frame": "385", "stage": "candidate_final", "passed": "True", "candidate_id": "385:candidate:0", "appearance": "cyan_bar"}]
    attempts = []
    tracks = [{"source_frame": "385", "track_id": "1000003", "track_uid": "simple:1000003", "coasting_this_frame": "True"}]
    proposals = []
    rows = edge_timelines(index, candidates, attempts, tracks, proposals, tmp_path)
    center = next(row for row in rows if row["source_frame"] == "385")
    assert center["root_cause"] == "TRACE_SEMANTICS"
    assert center["candidate_ids"] == "385:candidate:0"


def test_edge_timeline_does_not_infer_input_or_game_judgment(tmp_path):
    rows = edge_timelines([], [], [], [], [], tmp_path)
    assert rows
    assert all(row["root_cause"] in {"TRACE_SEMANTICS", "context_frame"} for row in rows)
