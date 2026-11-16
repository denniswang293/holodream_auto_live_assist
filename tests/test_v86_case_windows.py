import json
import gzip

from tools import v86_case_windows as cases


def test_read_csv_uses_gzip_sibling_only_when_plain_file_is_missing(tmp_path):
    plain = tmp_path / "candidate_trace.csv"
    compressed = tmp_path / "candidate_trace.csv.gz"
    with gzip.open(compressed, "wt", encoding="utf-8", newline="") as handle:
        handle.write("provider,video_frame\nv85,7\n")

    assert cases.read_csv(plain) == [{"provider": "v85", "video_frame": "7"}]

    plain.write_text("provider,video_frame\nv85,8\n", encoding="utf-8")
    assert cases.read_csv(plain) == [{"provider": "v85", "video_frame": "8"}]
    assert cases.read_csv(tmp_path / "missing.csv") == []


def test_selection_uses_indexed_action_categories_slowest_and_first_gap():
    index = [
        {"video_frame": str(frame), "source_frame": str(1000 + frame),
         "capture_timestamp": str(frame / 60)}
        for frame in range(6)
    ]
    attribution = [
        {"video_frame": "2", "root_cause_stage": "TAP_VISIBILITY_GATE", "case_id": "a"},
        {"video_frame": "4", "root_cause_stage": "TAP_VISIBILITY_GATE", "case_id": "b"},
        {"video_frame": "5", "root_cause_stage": "TYPE_PENDING", "case_id": "c"},
    ]
    profile = [
        {"provider": "v85", "video_frame": "0", "processing_ms": "1.2"},
        {"provider": "v85", "video_frame": "2", "processing_ms": "9.5"},
        {"provider": "legacy", "video_frame": "3", "processing_ms": "99"},
    ]
    admission = [{"provider": "v85", "decoded_frames": "6"}]

    selected = cases.select_review_targets(attribution, profile, admission, index)
    by_category = {row["category"]: row for row in selected}
    assert by_category["tap_visibility_gate"]["video_frame"] == 2
    assert by_category["type_pending"]["video_frame"] == 5
    assert by_category["slowest_processing_frame"]["video_frame"] == 2
    assert by_category["first_latest_frame_drop"]["video_frame"] == 1


def test_selection_stratifies_distinct_frames_and_keeps_provider_local_uids():
    index = [{"video_frame": str(n), "source_frame": str(n), "capture_timestamp": str(n)}
             for n in range(10)]
    attribution = [{"video_frame": str(n), "root_cause_stage": "TAP_VISIBILITY_GATE",
                    "case_id": str(n), "legacy_tracker_uid_provider_local": f"l{n}",
                    "candidate_tracker_uid_provider_local": f"c{n}"} for n in range(1, 9)]
    attribution.insert(1, {**attribution[0], "case_id": "duplicate-later"})
    selected = cases.select_review_targets(attribution, [], [], index, samples_per_bucket=3)
    rows = [r for r in selected if r["category"] == "tap_visibility_gate"]
    assert [r["video_frame"] for r in rows] == [1, 5, 8]
    assert len({r["window_id"] for r in rows}) == 3
    assert [r["candidate_tracker_uid_provider_local"] for r in rows] == ["c1", "c5", "c8"]


def test_uid_frame_evidence_joins_only_matching_uid_and_leaves_absent_events_blank():
    evidence = cases.uid_frame_evidence("c1", [
        {"tracker_uid": "c1", "role": "TAP_FACE", "kind": "tap", "color": "red",
         "bbox": "1,2,3,4", "component_id": "cmp1", "tracker_state": "trace-state",
         "timing_reason": "trace-timing"},
        {"tracker_uid": "c2", "role": "HOLD_HEAD", "kind": "hold_head"},
    ], [{"note_uid": "c1", "confirmed": "true", "identity_state": "decision-state",
         "visibility_state": "observed", "reason": "visible", "press_at": "4.5",
         "timing_reason": "", "crossing_at": "4.4", "uncertainty": "0.2"}], [
        {"uid": "c1", "event": "pressed", "key": "A"},
        {"uid": "c2", "event": "released", "key": "B"},
    ])
    assert evidence["detection_role"] == "TAP_FACE"
    assert evidence["candidate_component_id"] == "cmp1"
    assert evidence["down_up_events"] == "pressed"
    assert evidence["identity"] == "decision-state"
    assert evidence["visibility"] == "observed"
    assert evidence["timing_reason"] == "trace-timing"
    assert evidence["crossing_at"] == "4.4"
    assert evidence["uncertainty"] == "0.2"
    absent = cases.uid_frame_evidence("missing", [], [], [])
    assert all(value == "" for value in absent.values())


def test_quick_target_is_middle_available_indexed_replay_frame(tmp_path):
    index = [
        {"video_frame": str(frame), "source_frame": str(frame + 900),
         "capture_timestamp": str(frame / 30)}
        for frame in range(5)
    ]
    fixed = tmp_path / "fixed"
    fixed.mkdir()
    (fixed / "frame_summary.csv").write_text(
        "provider,video_frame\nv85,0\nv85,2\nv85,4\nlegacy,3\n", encoding="utf-8")
    target = cases.quick_target(fixed, index)
    assert target["video_frame"] == 2
    assert target["selection_basis"] == "middle indexed V85 frame available in limited quick replay"


def test_sequential_decoder_pairs_each_frame_with_its_index_row(tmp_path, monkeypatch):
    class FakeCapture:
        def __init__(self, _path):
            self.frames = ["decoded-0", "decoded-1", "decoded-2"]
            self.position = 0
            self.released = False

        def isOpened(self):
            return True

        def read(self):
            if self.position == len(self.frames):
                return False, None
            frame = self.frames[self.position]
            self.position += 1
            return True, frame

        def release(self):
            self.released = True

    capture = FakeCapture(None)
    monkeypatch.setattr(cases.cv2, "VideoCapture", lambda _path: capture)
    indexed = {
        0: {"video_frame": "0", "source_frame": "41", "capture_timestamp": "1.0"},
        1: {"video_frame": "1", "source_frame": "47", "capture_timestamp": "1.2"},
        2: {"video_frame": "2", "source_frame": "52", "capture_timestamp": "1.4"},
    }

    rows = list(cases.sequential_indexed_frames(tmp_path, indexed, max_frame=2))
    assert [(n, frame, row["source_frame"]) for n, frame, row in rows] == [
        (0, "decoded-0", "41"), (1, "decoded-1", "47"), (2, "decoded-2", "52")
    ]
    assert capture.released


def test_manifest_records_provenance_and_unknown_provisional_status(tmp_path):
    run = tmp_path / "run_synthetic"
    run.mkdir()
    (run / "live_source.mp4").write_bytes(b"synthetic-video")
    (run / "live_video_index.csv").write_text(
        "video_frame,source_frame,capture_timestamp\n0,10,0.0\n", encoding="utf-8")
    output = tmp_path / "review"
    queue = [{"target_video_frame": 0, "target_source_frame": "10",
              "annotation_status": cases.ANNOTATION_STATUS,
              "physical_note_status": cases.PHYSICAL_STATUS}]

    cases.write_manifest(output, "quick_preview", [run], queue)
    manifest = json.loads((output / "review_manifest.json").read_text(encoding="utf-8"))
    assert manifest["review_status"] == "UNKNOWN_PROVISIONAL"
    assert manifest["physical_note_status"] == "UNKNOWN"
    assert manifest["random_seek_used"] is False
    source = manifest["source_index_provenance"][0]
    assert source["live_source.mp4"]["sha256"]
    assert source["live_video_index.csv"]["sha256"]
    assert source["index_row_count"] == 1
    assert manifest["cases"] == queue
    assert "HUMAN_REVIEWED" not in (output / "review_manifest.json").read_text(encoding="utf-8")
