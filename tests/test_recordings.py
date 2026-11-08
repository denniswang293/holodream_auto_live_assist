import csv
import json

import cv2
import numpy as np
import pytest

from src.recordings import Recording, normalize_key_actions


def _recording(tmp_path, rows, frames):
    run = tmp_path / "run_test"
    run.mkdir(parents=True)
    (run / "session.json").write_text(json.dumps({"start_timestamp": 100.0, "stopped_timestamp": 101.0}), encoding="utf-8")
    with (run / "live_video_index.csv").open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["video_frame", "source_frame", "capture_timestamp", "acquired_timestamp"]
        if any("source_video_frame" in row for row in rows):
            fieldnames.insert(2, "source_video_frame")
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    writer = cv2.VideoWriter(str(run / "live_source.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 10, (16, 12))
    for frame in frames:
        writer.write(frame)
    writer.release()
    return run


def test_reader_preserves_source_gaps_and_causal_order(tmp_path):
    rows = [
        {"video_frame": "0", "source_frame": "4", "capture_timestamp": "100.0", "acquired_timestamp": "100.01"},
        {"video_frame": "1", "source_frame": "7", "capture_timestamp": "100.04", "acquired_timestamp": "100.05"},
    ]
    run = _recording(tmp_path, rows, [np.zeros((12, 16, 3), np.uint8), np.ones((12, 16, 3), np.uint8)])
    frames = list(Recording(run).iter_frames())
    assert [x.video_frame for x in frames] == [0, 1]
    assert [x.source_video_frame for x in frames] == [0, 1]
    assert [x.source_frame for x in frames] == [4, 7]
    assert [x.capture_timestamp for x in frames] == [100.0, 100.04]
    assert frames[1].capture_timestamp >= frames[0].capture_timestamp


def test_reader_rejects_truncated_video(tmp_path):
    rows = [
        {"video_frame": "0", "source_frame": "0", "capture_timestamp": "100.0", "acquired_timestamp": "100.01"},
        {"video_frame": "1", "source_frame": "1", "capture_timestamp": "100.04", "acquired_timestamp": "100.05"},
    ]
    run = _recording(tmp_path, rows, [np.zeros((12, 16, 3), np.uint8)])
    with pytest.raises(ValueError, match="ended before indexed frame 1"):
        list(Recording(run).iter_frames())


def test_reader_rejects_noncausal_timestamps(tmp_path):
    rows = [
        {"video_frame": "0", "source_frame": "0", "capture_timestamp": "100.0", "acquired_timestamp": "100.01"},
        {"video_frame": "1", "source_frame": "1", "capture_timestamp": "99.9", "acquired_timestamp": "100.05"},
    ]
    run = _recording(tmp_path, rows, [np.zeros((12, 16, 3), np.uint8), np.ones((12, 16, 3), np.uint8)])
    with pytest.raises(ValueError, match="nonmonotone capture_timestamp at video_frame 1"):
        list(Recording(run).iter_frames())


@pytest.mark.parametrize('bad',['nan','inf','-inf'])
def test_reader_rejects_nonfinite_clock_values(tmp_path,bad):
    rows=[dict(video_frame=0,source_frame=0,capture_timestamp=bad,acquired_timestamp=100.01)]
    run=_recording(tmp_path,rows,[np.zeros((12,16,3),np.uint8)])
    with pytest.raises(ValueError,match='nonfinite'):
        list(Recording(run).iter_frames())


def test_reader_rejects_extra_encoded_frames_and_bad_index_order(tmp_path):
    row = {"video_frame": "0", "source_frame": "0", "capture_timestamp": "100.0", "acquired_timestamp": "100.01"}
    run = _recording(tmp_path, [row], [np.zeros((12, 16, 3), np.uint8), np.ones((12, 16, 3), np.uint8)])
    with pytest.raises(ValueError, match="beyond index length"):
        list(Recording(run).iter_frames())
    # Keep the encoded video with two frames; a malformed second index row fails at row validation.
    rows = [row, {**row, "video_frame": "3", "source_frame": "4"}]
    run = _recording(tmp_path / "second", rows, [np.zeros((12, 16, 3), np.uint8), np.ones((12, 16, 3), np.uint8)])
    with pytest.raises(ValueError, match="index video_frame 3 at row 1"):
        list(Recording(run).iter_frames())


def test_reader_validates_explicit_playable_source_video_ordinal(tmp_path):
    rows = [{"video_frame": "0", "source_video_frame": "7", "source_frame": "10",
             "capture_timestamp": "100.0", "acquired_timestamp": "100.01"}]
    run = _recording(tmp_path, rows, [np.zeros((12, 16, 3), np.uint8)])
    # The reader remains sequential and rejects treating a capture ID as an MP4 seek ordinal.
    with pytest.raises(ValueError, match="source_video_frame 7 does not match playable encoded ordinal 0"):
        list(Recording(run).iter_frames())


def test_key_normalization_covers_initial_repeats_unpaired_and_partial():
    session = {"start_timestamp": 10.0, "stopped_timestamp": 13.0, "initial_held_keys": ["S"]}
    events = [
        {"timestamp": "10.5", "action": "key_down", "key": "D", "focused": "True", "injected": "False"},
        {"timestamp": "10.7", "action": "key_down", "key": "D", "focused": "True", "injected": "False"},
        {"timestamp": "11.0", "action": "key_up", "key": "D", "focused": "True", "injected": "False"},
        {"timestamp": "12.0", "action": "key_up", "key": "J", "focused": "True", "injected": "False"},
        {"timestamp": "12.2", "action": "key_down", "key": "K", "focused": "True", "injected": "False"},
    ]
    rows, issues = normalize_key_actions("run_test", events, session)
    by_key = {r["key"]: r for r in rows}
    assert by_key["D"]["status"] == "complete"
    assert by_key["D"]["repeat_down_count"] == 1
    assert by_key["D"]["duration_s"] == pytest.approx(0.5)
    assert by_key["S"]["status"] == "initial_held_partial_at_stop"
    assert by_key["S"]["down_timestamp"] == 10.0
    assert by_key["J"]["status"] == "unpaired_up"
    assert by_key["K"]["status"] == "partial_at_stop"
    assert by_key["K"]["duration_s"] == pytest.approx(0.8)
    assert any(x.startswith("repeat_key_down:D") for x in issues)
    assert any(x.startswith("held_at_stop:K") for x in issues)
    assert len({r["action_id"] for r in rows}) == len(rows)
