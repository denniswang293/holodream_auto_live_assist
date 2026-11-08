from types import SimpleNamespace
import re

import numpy as np
import pytest

from src import live
from src.capture import Region
from src.model import Frame


class Target:
    def __init__(self, title):
        assert title == "hololive-Dreams"
    def monitor_region(self):
        return Region(0, 0, 1280, 720)
    def client_region(self):
        return Region(10, 10, 1250, 700)
    def focused(self):
        return True


class Capture:
    def __init__(self, region, backend):
        assert region == Region(0, 0, 1280, 720)
        assert backend == "mss"
        self.error = None
        self.thread = SimpleNamespace(is_alive=lambda: True)
        self.closed = False
        self.n = 0
        self.resolved_backend = "mss"
        self.fallback_reason = ""
        self.captured = 1
        self.dropped = 0
    def start(self):
        return self
    def take(self, timeout):
        self.n += 1
        if self.n > 1:
            return None
        return Frame(0, np.zeros((720, 1280, 3), np.uint8), 1., 1.01)
    def close(self):
        self.closed = True


class Diagnostics:
    def __init__(self, out, record=False):
        self.out = out
        self.error = None
        self.closed = False
        self.metadata = {}
    def event(self, row):
        return True
    def frame(self, image, info, notes):
        return True
    def close(self):
        self.closed = True
        type(self).last_metadata = dict(self.metadata)


def configure(monkeypatch, tmp_path, *, no_logs=False, callback_failure=False,stop_early=False,
              shutdown_scheduler_error=False):
    order = []
    monkeypatch.setattr(live, "enable_dpi_awareness", lambda: None)
    monkeypatch.setattr(live, "Geometry", lambda path: object())
    monkeypatch.setattr(live, "WindowTarget", Target)
    monkeypatch.setattr(live, "CaptureWorker", Capture)
    monkeypatch.setattr(live, "Diagnostics", Diagnostics)
    if callback_failure:
        monkeypatch.setattr(Diagnostics, "event", lambda self, row: False)
    monkeypatch.setattr(live, "WindowsActuator", lambda: object())

    class Scheduler:
        def __init__(self, actuator, **kwargs):
            self.error = None
            self.on_event = kwargs["on_event"]
            self.disarmed = False
            self.closed = False
            order.append("scheduler-created")
        def disarm(self, why):
            self.disarmed = True
            order.append("disarm")
        def start(self):
            return self
        def toggle(self):
            return True
        def drain_events(self):return []
        def close(self):
            self.closed = True
            if shutdown_scheduler_error:
                self.error = RuntimeError("key up failed")
            order.append("scheduler-close")

    class Engine:
        def __init__(self, geometry, scheduler, calibration):
            if callback_failure:
                # Simulate a scheduler event callback failure; the actual
                # Scheduler treats a raised callback error as fail-closed.
                try:
                    scheduler.on_event({"event": "armed"})
                except RuntimeError:
                    scheduler.disarm("event_callback_error")
                    scheduler.error = RuntimeError("event_callback_error")
        def observe(self, frame):
            assert frame.image.shape==(700,1250,3)
            assert not stop_early
            return {"image": frame.image}
        def decide(self, obs):
            return ({"sequence": 0}, [])

    class Controls:
        def __init__(self, on_toggle, on_stop, assist):
            assert assist is True
            self.error = None
            self.on_stop = on_stop
        def start(self):
            if stop_early:self.on_stop()
            return self
        def close(self):
            order.append("controls-close")

    monkeypatch.setattr(live, "Scheduler", Scheduler)
    monkeypatch.setattr(live, "Engine", Engine)
    monkeypatch.setattr(live, "GlobalControls", Controls)
    monkeypatch.setattr(live, "modifiers_down", lambda: False)
    monkeypatch.setattr(live, "_fresh_run_dir", lambda parent: tmp_path / "fresh-run")
    geometry_path = tmp_path / "geometry.json"
    geometry_path.write_text("{}", encoding="utf-8")
    args = SimpleNamespace(max_frames=1, list_windows=False, geometry=str(geometry_path),
                           timing_config=str(_calibration_file(tmp_path)), window_title="hololive-Dreams",
                           no_logs=no_logs, out=str(tmp_path / "out"), record_overlay=False,
                           backend="mss")
    return args, order


def _calibration_file(tmp_path):
    path = tmp_path / "timing.json"
    path.write_text("{}", encoding="utf-8")
    return path


def test_live_cli_uses_full_display_starts_off_and_closes_diagnostics_last(monkeypatch, tmp_path):
    args, order = configure(monkeypatch, tmp_path)
    assert live.run_live(args) == 0
    assert order == ["scheduler-created", "disarm", "controls-close", "scheduler-close"]
    metadata = Diagnostics.last_metadata
    assert metadata["game_title"] == "hololive-Dreams"
    assert metadata["capture_rectangle"] == [0, 0, 1280, 720]
    assert metadata["resolved_backend"] == "mss"
    assert metadata["processed_frames"] == 1
    assert metadata["geometry_config"]["sha256"]


def test_live_reports_scheduler_shutdown_error(monkeypatch, tmp_path, capsys):
    args, _ = configure(monkeypatch, tmp_path, shutdown_scheduler_error=True)
    assert live.run_live(args) == 1
    assert "Scheduler failed during shutdown: key up failed" in capsys.readouterr().err


def test_live_cli_no_logs_disables_diagnostics_output(monkeypatch, tmp_path):
    args, _ = configure(monkeypatch, tmp_path, no_logs=True)
    assert live.run_live(args) == 0
    assert not (tmp_path / "out").exists()


def test_stop_hotkey_callback_disarms_before_waiting_for_main_loop(monkeypatch,tmp_path):
    args,order=configure(monkeypatch,tmp_path,stop_early=True)
    assert live.run_live(args)==0
    assert order.index('disarm')<order.index('controls-close')


def test_diagnostics_callback_failure_stops_before_processing_and_cleans_up(monkeypatch, tmp_path, capsys):
    args, order = configure(monkeypatch, tmp_path, callback_failure=True)
    assert live.run_live(args) == 1
    assert "Scheduler failed closed" in capsys.readouterr().err
    assert order.index("disarm") < order.index("controls-close") < order.index("scheduler-close")


def test_parser_exposes_requested_runtime_options():
    args = live._parser().parse_args(["--window-title", "game", "--geometry", "g.json",
                                      "--timing-config", "t.json", "--backend", "dxcam",
                                      "--out", "runs", "--record-overlay", "--no-logs",
                                      "--max-frames", "12"])
    assert (args.window_title, args.geometry, args.timing_config, args.backend, args.out) == (
        "game", "g.json", "t.json", "dxcam", "runs")
    assert args.record_overlay and args.no_logs and args.max_frames == 12


def test_cli_rejects_recording_when_logs_are_disabled():
    with pytest.raises(SystemExit):
        live.main(["--no-logs", "--record-overlay"])


def test_fresh_run_directories_use_utc_run_prefix(tmp_path):
    path = live._fresh_run_dir(tmp_path)
    assert re.fullmatch(r"run_\d{8}T\d{6}_\d{6}Z", path.name)
    assert path.is_dir()


def test_roi_requires_a_near_fullscreen_client():
    monitor = Region(0, 0, 1280, 720)
    assert live._validate_game_roi(Region(10, 10, 1250, 700), monitor) == (True, "")
    valid, reason = live._validate_game_roi(Region(100, 100, 800, 450), monitor)
    assert not valid
    assert "5%" in reason
