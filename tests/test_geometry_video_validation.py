from tools.geometry_video_v1_fresh.validate_geometry_video import is_causal_instance_record


def test_causal_instance_schema_accepts_renderer_label_without_redundant_flag() -> None:
    assert is_causal_instance_record({"offline_mode": "CURRENT_FRAME_CAUSAL; NO_FUTURE_FRAMES"})


def test_causal_instance_schema_rejects_explicit_future_frame_use() -> None:
    assert not is_causal_instance_record({
        "offline_mode": "CURRENT_FRAME_CAUSAL",
        "future_frames_used": True,
    })


def test_causal_instance_schema_rejects_missing_mode_label() -> None:
    assert not is_causal_instance_record({"future_frames_used": False})
