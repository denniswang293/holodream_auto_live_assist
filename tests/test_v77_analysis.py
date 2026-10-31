from pathlib import Path

from tools.run_v77_analysis import frame_uid, f, i, read_csv


def test_v77_frame_uid_is_source_frame_based():
    assert frame_uid("run_x", 17) == "run_x:17"


def test_v77_numeric_helpers_keep_timestamp_precision():
    assert f("242.4515462") == 242.4515462
    assert i("321.0") == 321
    assert f("not-a-time") is None


def test_v77_run_index_has_capture_timestamps_and_source_frames():
    path = Path("output/assist/run_20261031T194457_212618Z/live_video_index.csv")
    rows = read_csv(path)
    if not rows:
        return
    assert all(row.get("capture_timestamp") for row in rows)
    assert all(row.get("source_frame") for row in rows)
    assert len({row["capture_timestamp"] for row in rows}) == len(rows)
