from tools.attribute_lane_action_losses import (
    cross_score, linked_component, classify_case, classify_at_reference_frame,
    nearest_action_event, find_alternate_same_key_action,
    classify_with_association_collision,
)


def test_wrong_key_event_within_auxiliary_window_is_paired():
    events = [{"event": "pressed", "key": "K", "at": "10.05", "uid": "near"}]
    paired, nearest, signed, absolute, status = nearest_action_event(events, 10.0)
    assert paired is nearest
    assert classify_case(None, None, None, paired, "J")[0] == "SEGMENTED_ACTION_WRONG_KEY"
    assert round(signed, 3) == 0.05
    assert absolute <= 0.080
    assert status == "PAIRED_WITHIN_AUXILIARY_WINDOW"


def test_different_uid_same_key_action_with_exact_frame_overlap_is_ambiguous():
    actions = [
        {"provider": "segmented", "event": "pressed", "uid": "paired",
         "key": "K", "injection_started_at": "10.05"},
        {"provider": "segmented", "event": "pressed", "uid": "alternate",
         "key": "J", "injection_started_at": "10.02",
         "decision_capture_timestamp": "9.9"},
    ]
    rows = {
        "segmented": {
            "paired": [],
            "alternate": [{"video_frame": "20", "capture_timestamp": "9.9",
                            "last_observation": "9.9",
                            "bbox": "[105, 105, 35, 20]", "color": "cyan",
                            "key": "J", "keys": "J"}],
        }
    }
    legacy_track = [{"video_frame": "20", "capture_timestamp": "9.9",
                     "last_observation": "9.9",
                     "bbox": "[100, 100, 40, 20]", "color": "cyan"}]
    collision = find_alternate_same_key_action(
        actions, rows, "segmented", legacy_track, "paired", "J", 10.0)
    assert collision is not None
    assert collision["uid"] == "alternate"
    assert collision["frame"] == 20
    stage, confidence, reason = classify_case(
        None, None, None, actions[0], "J", collision)
    assert stage == "ASSOCIATION_AMBIGUOUS"
    assert confidence == "MEDIUM"
    assert "no_reassignment" in reason


def test_spatially_separate_alternate_same_key_press_stays_wrong_key():
    actions = [
        {"provider": "segmented", "event": "pressed", "uid": "paired",
         "key": "K", "injection_started_at": "10.05"},
        {"provider": "segmented", "event": "pressed", "uid": "separate",
         "key": "J", "injection_started_at": "10.02",
         "decision_capture_timestamp": "9.9"},
    ]
    rows = {"segmented": {"separate": [{"video_frame": "20", "capture_timestamp": "9.9",
                                         "last_observation": "9.9",
                                         "bbox": "[300, 300, 40, 20]", "color": "cyan",
                                         "key": "J", "keys": "J"}]}}
    legacy_track = [{"video_frame": "20", "capture_timestamp": "9.9",
                     "last_observation": "9.9",
                     "bbox": "[100, 100, 40, 20]", "color": "cyan"}]
    collision = find_alternate_same_key_action(
        actions, rows, "segmented", legacy_track, "paired", "J", 10.0)
    assert collision is None
    assert classify_case(None, None, None, actions[0], "J")[0] == "SEGMENTED_ACTION_WRONG_KEY"


def test_stale_exact_frame_bbox_does_not_qualify_as_alternate_geometry():
    actions = [{"provider": "segmented", "event": "pressed", "uid": "alternate",
                "key": "J", "injection_started_at": "10.02",
                "decision_capture_timestamp": "9.9"}]
    candidate = {"video_frame": "20", "capture_timestamp": "9.9",
                 "last_observation": "9.8", "bbox": "[105, 105, 35, 20]",
                 "color": "cyan", "key": "J", "keys": "J"}
    fresh_legacy = {"video_frame": "20", "capture_timestamp": "9.9",
                    "last_observation": "9.9", "bbox": "[100, 100, 40, 20]",
                    "color": "cyan"}
    rows = {"segmented": {"alternate": [candidate]}}
    assert find_alternate_same_key_action(
        actions, rows, "segmented", [fresh_legacy], "selected", "J", 10.0) is None

    candidate["last_observation"] = "9.9"
    stale_legacy = dict(fresh_legacy, last_observation="9.8")
    assert find_alternate_same_key_action(
        actions, rows, "segmented", [stale_legacy], "selected", "J", 10.0) is None


def test_no_paired_press_with_overlapping_alternate_is_ambiguous_and_preserves_stage():
    actions = [{"provider": "segmented", "event": "pressed", "uid": "alternate",
                "key": "J", "injection_started_at": "10.02",
                "decision_capture_timestamp": "9.9"}]
    rows = {"segmented": {"alternate": [{"video_frame": "20", "capture_timestamp": "9.9",
                                          "last_observation": "9.9",
                                          "bbox": "[105, 105, 35, 20]", "color": "cyan",
                                          "key": "J", "keys": "J"}]}}
    legacy_track = [{"video_frame": "20", "capture_timestamp": "9.9",
                     "last_observation": "9.9",
                     "bbox": "[100, 100, 40, 20]", "color": "cyan"}]
    collision = find_alternate_same_key_action(
        actions, rows, "segmented", legacy_track, "selected", "J", 10.0)
    match = ((1, 1.0, -1.0), "selected", [17, 18])
    last = {"video_frame": "18", "reason": "type_pending", "state": "TRACKING",
            "confirmed": "True"}
    stage, confidence, reason, underlying_stage, underlying_reason = classify_with_association_collision(
        match, None, last, None, None, "J", 20, collision)
    assert stage == "ASSOCIATION_AMBIGUOUS"
    assert confidence == "MEDIUM"
    assert "alternate_same_key_action" in reason
    assert underlying_stage == "TRACK_NOT_ACTIVE_AT_REFERENCE_FRAME"
    assert "last decision frame=18" in underlying_reason


def test_spatially_separate_alternate_without_paired_press_keeps_original_stage():
    actions = [{"provider": "segmented", "event": "pressed", "uid": "separate",
                "key": "J", "injection_started_at": "10.02",
                "decision_capture_timestamp": "9.9"}]
    rows = {"segmented": {"separate": [{"video_frame": "20", "capture_timestamp": "9.9",
                                         "last_observation": "9.9",
                                         "bbox": "[300, 300, 40, 20]", "color": "cyan",
                                         "key": "J", "keys": "J"}]}}
    legacy_track = [{"video_frame": "20", "capture_timestamp": "9.9",
                     "last_observation": "9.9",
                     "bbox": "[100, 100, 40, 20]", "color": "cyan"}]
    collision = find_alternate_same_key_action(
        actions, rows, "segmented", legacy_track, "selected", "J", 10.0)
    match = ((1, 1.0, -1.0), "selected", [17, 18])
    last = {"video_frame": "18", "reason": "type_pending", "state": "TRACKING",
            "confirmed": "True"}
    stage, _, _, underlying_stage, _ = classify_with_association_collision(
        match, None, last, None, None, "J", 20, collision)
    assert collision is None
    assert stage == "TRACK_NOT_ACTIVE_AT_REFERENCE_FRAME"
    assert underlying_stage == ""


def test_selected_uid_same_key_press_is_not_overridden_by_alternate_collision():
    selected = {"event": "pressed", "uid": "selected", "key": "J"}
    collision = {"uid": "alternate"}
    result = classify_with_association_collision(
        None, None, None, None, selected, "J", 20, collision)
    assert result[:3] == ("SEGMENTED_ACTION_PRESENT", "HIGH", "paired_mock_down_same_key")
    assert result[3:] == ("", "")


def test_out_of_window_nearest_event_is_diagnostic_only():
    events = [{"event": "pressed", "key": "K", "at": "10.2", "uid": "far"}]
    paired, nearest, signed, absolute, status = nearest_action_event(events, 10.0)
    assert paired is None
    assert nearest["uid"] == "far"
    assert signed > 0 and absolute > 0.080
    assert status == "NEAREST_EVENT_OUTSIDE_AUXILIARY_WINDOW"
    assert classify_case(None, None, None, paired, "J")[0] != "SEGMENTED_ACTION_WRONG_KEY"


def test_no_candidate_action_event_has_explicit_status():
    paired, nearest, signed, absolute, status = nearest_action_event([], 10.0)
    assert (paired, nearest, signed, absolute, status) == (None, None, None, None, "NO_EVENT")


def test_cross_provider_pairing_uses_same_frame_geometry_not_equal_uids():
    legacy = [
        {"video_frame": str(frame), "bbox": "[400, 100, 80, 20]", "color": "green"}
        for frame in (10, 11, 12)
    ]
    segmented = {
        frame: [{"video_frame": str(frame), "bbox": "[400, 100, 80, 20]",
                 "color": "green", "keys": "J", "note_uid": "different-provider-uid"}]
        for frame in (10, 11, 12)
    }
    matched = cross_score(legacy, segmented, "J")
    assert matched is not None
    assert matched[1] == "different-provider-uid"
    assert matched[2] == [10, 11, 12]


def test_component_body_is_attributed_to_adapter_gate_without_forcing_unknown():
    stage, confidence, reason = classify_case(None, None,
        {"role": "hold_body", "conversion": "accepted"}, None, "J")
    assert stage == "ADAPTER_BODY_CANNOT_SEED_NOTE"
    assert confidence == "HIGH"
    assert "requires" in reason


def test_matched_track_stop_reasons_get_specific_terminal_stages():
    cases = (
        ("confirmed_tap_observation_lost", "ENGINE_TAP_VISIBILITY_GATE"),
        ("type_pending", "ENGINE_TYPE_PENDING"),
        ("insufficient_observations", "TIMING_INSUFFICIENT_OBSERVATIONS"),
    )
    match = ((3, 1.0, -1.0), "provider-local-track", [10, 11, 12])
    # Component semantics remain independent upstream evidence; they do not
    # replace the terminal reason observed on the matched trajectory.
    component = {"role": "unknown", "conversion": "dropped_semantic_gate",
                 "reason": "role_not_actionable"}
    for reason, expected_stage in cases:
        stage, confidence, attribution_reason = classify_case(
            match, {"reason": reason, "state": "TRACKING", "confirmed": "True"},
            component, None, "J")
        assert (stage, confidence, attribution_reason) == (expected_stage, "HIGH", reason)


def test_unrecognized_matched_track_reason_stays_unresolved():
    match = ((1, 1.0, -1.0), "provider-local-track", [10])
    stage, confidence, reason = classify_case(
        match, {"reason": "future_unrecognized_reason", "state": "TRACKING",
                "confirmed": "True"},
        {"role": "unknown", "conversion": "dropped_semantic_gate"}, None, "J")
    assert stage == "UNRESOLVED_AFTER_TRACKING"
    assert confidence == "MEDIUM"
    assert reason == "future_unrecognized_reason"


def test_missing_reference_frame_row_is_not_misclassified_from_nearest_track_row():
    match = ((3, 1.0, -1.0), "provider-local-track", [10, 11, 12])
    last = {"video_frame": "12", "reason": "confirmed_tap_observation_lost",
            "state": "TRACKING", "confirmed": "True"}
    stage, confidence, reason = classify_at_reference_frame(
        match, None, last, {"role": "unknown", "conversion": "dropped_semantic_gate"},
        None, "J", 20)
    assert stage == "TRACK_NOT_ACTIVE_AT_REFERENCE_FRAME"
    assert confidence == "HIGH"
    assert "last decision frame=12" in reason


def test_exact_reference_frame_reason_wins_over_last_or_future_rows():
    match = ((3, 1.0, -1.0), "provider-local-track", [10, 11, 12])
    exact = {"video_frame": "20", "capture_timestamp": "10.0", "last_observation": "10.0",
             "reason": "type_pending", "state": "TRACKING", "confirmed": "True"}
    later = {"video_frame": "21", "reason": "confirmed", "state": "TRACKING",
             "confirmed": "True"}
    stage, confidence, reason = classify_at_reference_frame(
        match, exact, later, {"component_id": "cmp20"}, None, "J", 20)
    assert (stage, confidence, reason) == ("ENGINE_TYPE_PENDING", "HIGH", "type_pending")


def test_component_link_requires_exact_provider_frame_and_tracker_uid():
    trace = [
        {"provider": "segmented", "video_frame": "177", "candidate_stage": "segmentation_to_detector",
         "component_id": "cmp70", "role": "tap_face", "conversion": "accepted"},
        {"provider": "segmented", "video_frame": "177", "candidate_stage": "tracker_input",
         "component_id": "cmp70", "tracker_uid": "track100"},
    ]
    row = {"bbox": "[400, 100, 80, 20]"}
    assert linked_component(row, trace, "segmented", "track100", 177)["component_id"] == "cmp70"
    assert linked_component(row, trace, "segmented", "other-track", 177) is None
    assert linked_component(row, trace, "v85", "track100", 177) is None
    assert linked_component(row, trace, "segmented", "track100", 178) is None


def test_unassigned_nearby_component_is_not_claimed_as_track_cause():
    trace = [
        {"provider": "segmented", "video_frame": "177", "candidate_stage": "segmentation_to_detector",
         "component_id": "cmp70", "role": "tap_face", "conversion": "accepted"},
        {"provider": "segmented", "video_frame": "177", "candidate_stage": "tracker_input",
         "component_id": "cmp70", "tracker_uid": ""},
    ]
    assert linked_component({"bbox": "[400, 100, 80, 20]"}, trace,
                            "segmented", "track100", 177) is None
    assert classify_case(None, None, None, None, "J") == (
        "UNKNOWN", "LOW", "no_spatially_matched_segmented_component_or_track")


def test_stale_matched_track_with_unassigned_detection_stays_unverified():
    match = ((3, 1.0, -1.0), "track100", [175, 176, 177])
    trace = [
        {"provider": "segmented", "video_frame": "177", "candidate_stage": "segmentation_to_detector",
         "component_id": "cmp70", "role": "tap_face", "conversion": "accepted"},
        {"provider": "segmented", "video_frame": "177", "candidate_stage": "tracker_input",
         "component_id": "cmp70", "tracker_uid": ""},
    ]
    assert linked_component({"bbox": "[400, 100, 80, 20]"}, trace,
                            "segmented", "track100", 177) is None
    stale = {"video_frame": "177", "capture_timestamp": "10.0", "last_observation": "9.8",
             "reason": "confirmed_tap_observation_lost", "state": "TRACKING", "confirmed": "True"}
    stage, confidence, reason = classify_at_reference_frame(
        match, stale, stale, None, None, "J", 177)
    assert (stage, confidence) == ("TRACK_ASSOCIATION_UNVERIFIED", "LOW")
    assert "tracker_uid-to-component" in reason


def test_equal_score_cross_provider_tracks_are_left_ambiguous():
    legacy = [
        {"video_frame": str(frame), "bbox": "[400, 100, 80, 20]", "color": "green"}
        for frame in (10, 11, 12)
    ]
    segmented = {
        frame: [
            {"video_frame": str(frame), "bbox": "[400, 100, 80, 20]", "color": "green",
             "keys": "J", "note_uid": uid}
            for uid in ("track-a", "track-b")
        ] for frame in (10, 11, 12)
    }
    assert cross_score(legacy, segmented, "J") is None
