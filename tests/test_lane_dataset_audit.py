import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_lane_dataset


def test_source_gaps_are_separate_from_encoded_video_frame_gaps(tmp_path):
    path = tmp_path / "index.csv"
    path.write_text(
        "video_frame,source_frame,capture_timestamp,acquired_timestamp\n"
        "0,10,1.0,1.01\n"
        "1,12,1.02,1.03\n",
        encoding="utf-8",
    )
    result = audit_lane_dataset.csv_stats(path, "video_frame", "source_frame",
                                         ["capture_timestamp", "acquired_timestamp"])
    assert result["video_frame_gaps"] == 0
    assert result["source_frame_gaps"] == 1
    assert result["timestamp_reversals"] == 0
    assert result["acquired_before_capture_rows"] == 0


def test_negative_capture_to_acquired_delta_is_audited(tmp_path):
    path = tmp_path / "index.csv"
    path.write_text(
        "video_frame,source_frame,capture_timestamp,acquired_timestamp\n"
        "0,0,2.0,1.99\n",
        encoding="utf-8",
    )
    result = audit_lane_dataset.csv_stats(path, "video_frame", "source_frame",
                                         ["capture_timestamp", "acquired_timestamp"])
    assert result["acquired_before_capture_rows"] == 1
    assert result["capture_to_acquired_ms"][0] < 0
