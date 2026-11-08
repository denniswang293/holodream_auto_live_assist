"""Windows live runtime for the independent rebuild pipeline.

Input starts disarmed. Ctrl+Shift+Alt+Q requests an arm after the modifier keys
are released; Esc or F12 stops the process. Nothing in this module imports or
calls the legacy assist runtime.
"""
from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timezone
import sys
import threading
import time
from pathlib import Path

import cv2

from .capture import CaptureWorker
from .diagnostics import Diagnostics
from .engine import Engine
from .model import Geometry, Frame
from .scheduler import Scheduler
from .windows import (DEFAULT_WINDOW_TITLE, GlobalControls, WindowTarget,
                      WindowsActuator, enable_dpi_awareness, list_windows,
                      modifiers_down)


def _parser():
    parser = argparse.ArgumentParser(description="Run hololive-Dreams live detection; keyboard assist starts OFF.")
    parser.add_argument("--window-title", default=DEFAULT_WINDOW_TITLE)
    parser.add_argument("--list-windows", action="store_true", help="list visible windows and exit")
    parser.add_argument("--geometry", default="config/geometry_live_assist.json")
    parser.add_argument("--timing-config", default="config/reference_timing.json")
    parser.add_argument("--backend", choices=("auto", "mss", "dxcam"), default="auto")
    parser.add_argument("--out", default="output/assist", help="parent directory for a fresh diagnostics run")
    parser.add_argument("--record-overlay", action="store_true")
    parser.add_argument("--no-logs", action="store_true", help="disable all output files")
    parser.add_argument("--max-frames", type=int, default=0, help="stop after N processed frames (0 runs until Esc/F12)")
    return parser


def _fresh_run_dir(parent):
    parent = Path(parent)
    parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    path = parent / f"run_{stamp}"
    path.mkdir(exist_ok=False)
    return path


def _validate_game_roi(client, monitor):
    """Check that the game client is the fullscreen display being captured."""
    if client.width <= 0 or client.height <= 0:
        return False, f"client area is {client.width}x{client.height}"
    margins = (client.left - monitor.left,
               client.top - monitor.top,
               monitor.left + monitor.width - (client.left + client.width),
               monitor.top + monitor.height - (client.top + client.height))
    x_limit, y_limit = monitor.width * .05, monitor.height * .05
    if (margins[0] < 0 or margins[2] < 0 or margins[1] < 0 or margins[3] < 0):
        return False, f"client area {client.bounds} extends outside captured display {monitor.bounds}"
    if margins[0] > x_limit or margins[2] > x_limit or margins[1] > y_limit or margins[3] > y_limit:
        return False, (f"client area {client.width}x{client.height} has display insets "
                       f"left/top/right/bottom={margins}, exceeding 5% of the display")
    coverage = client.width * client.height / (monitor.width * monitor.height)
    if coverage < .90:
        return False, f"client area covers {coverage:.1%} of the captured display; at least 90% is required"
    return True, ""


def _config_provenance(path):
    path = Path(path)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def run_live(args):
    """Run one live session; module boundaries are intentionally monkeypatchable."""
    if args.max_frames < 0:
        raise ValueError("--max-frames must be zero or positive")
    if args.no_logs and args.record_overlay:
        raise ValueError("--record-overlay cannot be used with --no-logs")
    if args.list_windows:
        for hwnd, title in list_windows():
            print(f"{hwnd}\t{title}")
        return 0

    diagnostics = None
    capture = controls = scheduler = None
    failure = None
    processed = 0
    geometry = calibration = target = region = None
    last_client = None
    try:
        enable_dpi_awareness()
        cv2.setNumThreads(4)
        geometry = Geometry(args.geometry)
        calibration = Path(args.timing_config)
        if not calibration.is_file():
            raise FileNotFoundError(f"Timing calibration is required: {calibration}")
        target = WindowTarget(args.window_title)
        region = target.monitor_region()
        out = None if args.no_logs else _fresh_run_dir(args.out)
        diagnostics = Diagnostics(out, record=args.record_overlay)

        def log_event(row):
            # Diagnostics.event returns False both when deliberately disabled
            # and on queue/error failure. Only the former is tolerated.
            if diagnostics.out is None:
                return
            if not diagnostics.event(row):
                raise RuntimeError("Diagnostics action queue rejected an event")

        actuator = WindowsActuator()
        scheduler = Scheduler(actuator, clock=time.perf_counter, focus_check=target.focused,
                              modifiers_check=modifiers_down, on_event=log_event)
        scheduler.start()
        engine = Engine(geometry, scheduler, calibration)
        print(f"Geometry status: {getattr(geometry, 'status', 'unknown')}")
        print("Reference-success input calibration loaded; its offset reflects successful inputs, not an ideal judgment center.")
        print(f"Output directory: {out}" if out is not None else "Output files disabled (--no-logs).")
        capture = CaptureWorker(region, backend=args.backend).start()
        # assist=True makes hotkey registration mandatory, while Scheduler is
        # still initially disarmed. The hotkey only requests an arm.
        stop_event = threading.Event()
        def stop_requested():
            scheduler.disarm('stop_hotkey')
            stop_event.set()
        controls = GlobalControls(scheduler.toggle, stop_requested, assist=True).start()
        print("Assist is OFF. Ctrl+Shift+Alt+Q toggles it after key release; Esc/F12 stops.")

        last_roi_error = None
        while not stop_event.is_set():
            for event in scheduler.drain_events():
                if event['event'] in ('armed','disarmed','arm_rejected','arm_requested'):
                    print('INPUT '+event['event']+': '+str(event.get('reason','')))
            if controls.error:
                raise RuntimeError(f"Global controls failed: {controls.error}")
            if scheduler.error:
                raise RuntimeError(f"Scheduler failed closed: {scheduler.error}")
            if diagnostics.error:
                scheduler.disarm("diagnostics_error")
                raise RuntimeError(f"Diagnostics failed: {diagnostics.error}")
            if capture.error:
                raise RuntimeError(f"Capture failed: {capture.error}")
            frame = capture.take(timeout=.05)
            if frame is None:
                if capture.error:
                    raise RuntimeError(f"Capture failed: {capture.error}")
                if capture.thread and not capture.thread.is_alive():
                    break
                continue

            focused = bool(target.focused())
            try:
                client = target.client_region()
                roi_valid, roi_error = _validate_game_roi(client, region)
                if roi_valid:last_client=client
            except Exception as exc:
                roi_valid = False
                roi_error = f"cannot read game client area: {exc}"
            if roi_error != last_roi_error and roi_error:
                print(f"Game ROI invalid: {roi_error}", file=sys.stderr)
            last_roi_error = roi_error
            game_image=frame.image
            if roi_valid:
                if frame.image.shape[:2] != (region.height,region.width):
                    raise ValueError('Capture dimensions disagree with the physical display rectangle')
                x,y=client.left-region.left,client.top-region.top
                game_image=frame.image[y:y+client.height,x:x+client.width]
            live_frame = Frame(frame.sequence, game_image, frame.captured_at,
                               frame.acquired_at, focused, roi_valid)
            observation = engine.observe(live_frame)
            info, notes = engine.decide(observation)
            info['capture_rectangle']=list(region.bounds)
            info["captured_at"] = frame.captured_at
            info["acquired_at"] = frame.acquired_at
            info["capture_backend"] = getattr(capture, "resolved_backend", None) or args.backend
            info["capture_count"] = getattr(capture, "captured", None)
            info["capture_dropped"] = getattr(capture, "dropped", None)
            if roi_valid:info['client_rectangle']=list(client.bounds)
            if roi_error:
                info["roi_error"] = roi_error
            if scheduler.error:
                raise RuntimeError(f"Scheduler failed closed: {scheduler.error}")
            if diagnostics.out is not None:
                if not diagnostics.frame(observation["image"], info, notes):
                    scheduler.disarm("diagnostics_frame_rejected")
                    raise RuntimeError("Diagnostics rejected a frame")
                if diagnostics.error:
                    scheduler.disarm("diagnostics_error")
                    raise RuntimeError(f"Diagnostics failed: {diagnostics.error}")
            processed += 1
            if args.max_frames and processed >= args.max_frames:
                stop_event.set()
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        failure = exc
        print(f"Live runtime stopped: {exc}", file=sys.stderr)
        return 1
    finally:
        # Release keys before stopping workers or flushing/closing recordings.
        if scheduler is not None:
            try:
                scheduler.disarm('runtime_stop')
            except Exception as exc:
                failure = failure or exc
        if controls is not None:
            try:
                controls.close()
            except Exception as exc:
                failure = failure or exc
        if scheduler is not None:
            try:
                scheduler.close()
                scheduler_error = getattr(scheduler, "error", None)
                if scheduler_error:
                    failure = failure or RuntimeError(f"Scheduler failed during shutdown: {scheduler_error}")
            except Exception as exc:
                failure = failure or exc
        if capture is not None:
            try:
                capture.close()
            except Exception as exc:
                failure = failure or exc
        if diagnostics is not None:
            metadata = getattr(diagnostics, "metadata", None)
            if isinstance(metadata, dict) and region is not None and diagnostics.out is not None:
                try:
                    client = last_client
                    metadata.update({
                        "game_title": args.window_title,
                        "geometry_config": _config_provenance(args.geometry),
                        "timing_config": _config_provenance(calibration),
                        "capture_rectangle": list(region.bounds),
                        "capture_size": [region.width, region.height],
                        "client_rectangle": list(client.bounds) if client is not None else None,
                        "requested_backend": args.backend,
                        "resolved_backend": getattr(capture, "resolved_backend", None) or args.backend,
                        "backend_fallback_reason": getattr(capture, "fallback_reason", "") or "",
                        "captured_frames": getattr(capture, "captured", None),
                        "capture_dropped_frames": getattr(capture, "dropped", None),
                        "processed_frames": processed,
                    })
                except Exception as exc:
                    failure = failure or RuntimeError(f"Could not prepare session metadata: {exc}")
            try:
                diagnostics.close()
            except Exception as exc:
                failure = failure or exc
        if failure:
            # An exception during cleanup must still be visible to CLI users.
            print(f"Live cleanup reported: {failure}", file=sys.stderr)
    return 1 if failure else 0


def main(argv=None):
    parser = _parser()
    args = parser.parse_args(argv)
    if args.no_logs and args.record_overlay:
        parser.error("--record-overlay cannot be used with --no-logs")
    return run_live(args)


if __name__ == "__main__":
    raise SystemExit(main())
