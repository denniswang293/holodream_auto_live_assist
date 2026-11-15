from tools.audit_v86_stale_track_lineage import resolve


def audit(**overrides):
    row = {"provider": "segmented", "capture_timestamp": "10.2",
           "candidate_tracker_uid_provider_local": "uid-1",
           "candidate_track_last_observation": "10.1", "last_observation_age_ms": "100"}
    row.update(overrides)
    return row


def tracker(**overrides):
    row = {"provider": "segmented", "candidate_stage": "tracker_input",
           "tracker_uid": "uid-1", "capture_timestamp": "10.1",
           "video_frame": "4", "source_frame": "44", "component_id": "7"}
    row.update(overrides)
    return row


def component(**overrides):
    row = {"provider": "segmented", "candidate_stage": "segmentation_to_detector",
           "video_frame": "4", "component_id": "7", "role": "hold_head",
           "color": "cyan", "bbox": "(1,2,3,4)", "area": "12",
           "conversion": "accepted", "reason": "ok", "connection_group_id": "9"}
    row.update(overrides)
    return row


def test_prior_frame_observation_links_to_component():
    result = resolve(audit(), [tracker(), component()])
    assert result["lineage_status"] == "matched"
    assert result["matched_video_frame"] == "4"
    assert result["matched_source_frame"] == "44"
    assert result["component_role"] == "hold_head"
    assert result["component_connection_group_id"] == "9"
    assert result["stale_age_ms"] == "100"


def test_provider_uid_and_time_mismatches_are_rejected():
    for t in (tracker(provider="v85"), tracker(tracker_uid="other"),
              tracker(capture_timestamp="10.102")):
        assert resolve(audit(), [t, component()])["lineage_status"] == "unmatched"


def test_future_only_observation_is_rejected():
    row = audit(capture_timestamp="10.0", candidate_track_last_observation="10.1")
    assert resolve(row, [tracker()])["lineage_status"] == "future_only_rejected"
    # Future tracker rows cannot satisfy a past observation timestamp either.
    row = audit(candidate_track_last_observation="10.201")
    assert resolve(row, [tracker(capture_timestamp="10.201")])["lineage_status"] == "future_only_rejected"


def test_duplicate_tracker_input_is_ambiguous():
    assert resolve(audit(), [tracker(), tracker()])["lineage_status"] == "ambiguous_tracker_input"


def test_missing_component_conversion_is_preserved():
    result = resolve(audit(), [tracker()])
    assert result["lineage_status"] == "missing_component_conversion"
    assert result["component_component_id"] == "7"
