from tools.attribute_lane_action_losses import cross_score, classify_case


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
