from tools.analyze_v78_live_trace import classify_blocker, index_maps, resolve_trace_rows


def test_v78_timestamp_join_resolves_encoded_frame_without_fps_math():
    index = [{"source_frame": "7", "capture_timestamp": "12.3456", "source_video_frame": "3"}]
    by_key, by_source = index_maps(index)
    rows = resolve_trace_rows([{"source_frame": "7", "capture_timestamp": "12.3456"}], by_key, by_source)
    assert rows[0]["source_video_frame_resolved"] == "3"
    assert rows[0]["video_frame_join_confidence"] == "HIGH"


def test_v78_fired_is_not_game_truth():
    result = classify_blocker("FIRED", [{"state": "FIRED"}], [], [], [])
    assert result[0] == "KEY_DOWN_LOGGED_GAME_TRUTH_UNKNOWN"
    assert result[4] == "MEDIUM"
