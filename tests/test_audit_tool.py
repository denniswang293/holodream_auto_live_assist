import csv
import json
from types import SimpleNamespace

import numpy as np

from tools import audit_recordings


def _recording(root, name, *, events=None, focus="True", complete=True, elapsed_offset=0.0):
    folder = root / name
    folder.mkdir(parents=True)
    session = {
        "started_utc": "2026-01-01T00:00:00+00:00", "capture_kind": "manual_player",
        "window_title": "test", "start_timestamp": 100.0, "stopped_timestamp": 100.1,
        "duration_s": .1, "video_size": [4, 3], "nominal_video_fps": 60,
        "complete": complete, "keyboard_trace_complete": True, "automatic_input": False,
        "audio_recorded": False, "game_judgment_accuracy": "UNKNOWN",
        "verified_video_frames": 2, "lost_keyboard_events": 0, "initial_held_keys": [],
    }
    (folder / "session.json").write_text(json.dumps(session), encoding="utf-8")
    index = [
        {"video_frame": str(i), "source_frame": str(i), "capture_timestamp": str(100.01 + .04*i),
         "acquired_timestamp": str(100.02 + .04*i), "elapsed_s": str(.01 + .04*i + elapsed_offset),
         "encoded_at_host": str(100.03 + .04*i), "focused": focus}
        for i in range(2)
    ]
    _write(folder / "live_video_index.csv", index)
    _write(folder / "player_key_events.csv", events or [])
    _write(folder / "markers.csv", [
        {"timestamp": "100", "elapsed_s": "0", "kind": "recording_started", "note": "start"},
        {"timestamp": "100.1", "elapsed_s": ".1", "kind": "recording_stopped", "note": "stop"},
    ])
    sentinel = folder / "live_source.mp4"
    sentinel.write_bytes(b"source must remain unchanged")
    return folder


def _write(path, rows):
    fields = list(rows[0]) if rows else ["timestamp", "elapsed_s", "action", "key"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_audit_cli_outputs_compatible_tables_and_preserves_source(tmp_path, monkeypatch):
    source = tmp_path / "recordings"
    source.mkdir()
    folder = _recording(source, "run_one", events=[
        {"timestamp": "100.05", "elapsed_s": ".05", "action": "key_down", "key": "K",
         "focused": "True", "injected": "False", "scan_code": "37"},
        {"timestamp": "100.08", "elapsed_s": ".08", "action": "key_up", "key": "K",
         "focused": "True", "injected": "False", "scan_code": "37"},
    ])
    before = (folder / "live_source.mp4").read_bytes()

    class FakeRecording:
        def __init__(self, path):
            self.path = path
            self.run_id = path.name
            self.session = json.loads((path / "session.json").read_text())
            self.index = audit_recordings._csv(path / "live_video_index.csv")

        def iter_frames(self):
            for _ in self.index:
                yield SimpleNamespace(image=np.zeros((3, 4, 3), dtype=np.uint8))

    monkeypatch.setattr(audit_recordings, "Recording", FakeRecording)
    out = tmp_path / "audit"
    assert audit_recordings.main(["--recordings", str(source), "--out", str(out)]) == 0
    assert sorted(p.name for p in out.iterdir()) == ["clock_anomalies.csv", "data_quality.json", "player_actions.csv", "reference_timeline.csv", "sessions.csv"]
    with (out / "sessions.csv").open(encoding="utf-8", newline="") as f:
        sessions = list(csv.DictReader(f))
    assert sessions[0]["classification"] == "usable"
    assert sessions[0]["song"] == sessions[0]["difficulty"] == "UNKNOWN"
    assert sessions[0]["decoded_video_frames"] == "2"
    with (out / "player_actions.csv").open(encoding="utf-8", newline="") as f:
        actions = list(csv.DictReader(f))
    assert actions[0]["action_id"] == "run_one:K:000001"
    assert actions[0]["status"] == "complete"
    assert len(list(csv.DictReader((out / "reference_timeline.csv").open(encoding="utf-8", newline="")))) == 2
    dq = json.loads((out / "data_quality.json").read_text(encoding="utf-8"))
    assert dq["classification_counts"] == {"usable": 1}
    assert (folder / "live_source.mp4").read_bytes() == before


def test_partial_keyboard_and_clock_anomalies_are_reported(tmp_path, monkeypatch):
    source = tmp_path / "recordings"
    source.mkdir()
    _recording(source, "run_bad", elapsed_offset=.02, events=[
        {"timestamp": "100.05", "elapsed_s": ".05", "action": "key_down", "key": "K",
         "focused": "False", "injected": "True"},
        {"timestamp": "100.06", "elapsed_s": ".06", "action": "key_down", "key": "K",
         "focused": "False", "injected": "False"},
    ])

    class FakeRecording:
        def __init__(self, path):
            self.path, self.run_id = path, path.name
            self.session = json.loads((path / "session.json").read_text())
            self.index = audit_recordings._csv(path / "live_video_index.csv")

        def iter_frames(self):
            yield from [SimpleNamespace(image=np.zeros((3, 4, 3))), SimpleNamespace(image=np.zeros((3, 4, 3)))]

    monkeypatch.setattr(audit_recordings, "Recording", FakeRecording)
    out = tmp_path / "audit"
    audit_recordings.main(["--recordings", str(source), "--out", str(out)])
    rows = list(csv.DictReader((out / "clock_anomalies.csv").open(encoding="utf-8", newline="")))
    names = {r["anomaly"] for r in rows}
    assert "key_repeat_key_down" in names
    assert "nonfocused_key_events" in names
    assert "injected_key_events" in names
    assert "index_elapsed_clock_mismatch" in names
    session = next(csv.DictReader((out / "sessions.csv").open(encoding="utf-8", newline="")))
    assert session["classification"] == "unreliable"


def test_bad_run_is_recorded_and_does_not_abort_other_runs(tmp_path, monkeypatch):
    source = tmp_path / "recordings"
    source.mkdir()
    good = _recording(source, "run_good")
    (source / "run_missing_session").mkdir()

    class FakeRecording:
        def __init__(self, path):
            self.path, self.run_id = path, path.name
            self.session = json.loads((path / "session.json").read_text())
            self.index = audit_recordings._csv(path / "live_video_index.csv")

        def iter_frames(self):
            yield from [SimpleNamespace(image=np.zeros((3, 4, 3))), SimpleNamespace(image=np.zeros((3, 4, 3)))]

    monkeypatch.setattr(audit_recordings, "Recording", FakeRecording)
    out = tmp_path / "audit"
    audit_recordings.main(["--recordings", str(source), "--out", str(out)])
    rows = {r["run_id"]: r for r in csv.DictReader((out / "sessions.csv").open(encoding="utf-8", newline=""))}
    assert rows[good.name]["classification"] == "usable"
    assert rows["run_missing_session"]["classification"] == "unreliable"
    anomalies = list(csv.DictReader((out / "clock_anomalies.csv").open(encoding="utf-8", newline="")))
    assert any(a["run_id"] == "run_missing_session" and a["severity"] == "unreliable" for a in anomalies)
    dq = json.loads((out / "data_quality.json").read_text(encoding="utf-8"))
    assert dq["session_count"] == 2
    assert dq["classification_counts"] == {"usable": 1, "unreliable": 1}

