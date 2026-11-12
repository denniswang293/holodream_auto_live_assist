"""Bounded, asynchronous runtime diagnostics and optional paired video."""
from __future__ import annotations

import csv
import copy
import base64
from dataclasses import asdict
import json
import queue
import threading
import zlib
from pathlib import Path

import cv2
import numpy as np


def raw_identity_trace(engine,observation):
    """Copy mutable pixels only; encoding belongs to the bounded writer."""
    planes={name:np.array(value,copy=True) for name,value in
            [('labels',engine.perception.last_labels),('path',engine.perception.last_path)] if value is not None}
    return dict(schema=1,tracker='one_to_one',
                detections=tuple(observation['detections']),planes=planes,
                ownership_events=copy.deepcopy(engine.tracker.audit))


def pack_identity_trace(raw):
    """Lossless diagnostic payload, never passed through display truncation."""
    planes={}
    for name,value in raw['planes'].items():
        planes[name]=dict(shape=list(value.shape),dtype=value.dtype.str,
                          zlib_b64=base64.b64encode(zlib.compress(value.tobytes(),1)).decode('ascii'))
    return dict(schema=raw['schema'],tracker=raw['tracker'],
                candidates=[asdict(d) for d in raw['detections']],
                ownership_events=raw['ownership_events'],planes=planes,
                association_recording='recompute_offline_from_raw_candidates')


def trace_planes(trace, shape):
    """Decode bounded current-frame arrays; reject incomplete/mismatched traces."""
    result={}
    for name,item in trace.get('planes',{}).items():
        if name not in ('labels','path') or tuple(item['shape'])!=tuple(shape):
            raise ValueError('Identity trace shape/name mismatch')
        dtype=np.dtype(item['dtype'])
        if dtype not in (np.dtype('int32'),np.dtype('uint8')):
            raise ValueError('Unsupported identity trace array type')
        size=int(np.prod(shape))*dtype.itemsize
        decoder=zlib.decompressobj()
        raw=decoder.decompress(base64.b64decode(item['zlib_b64'],validate=True),size+1)
        if len(raw)!=size or not decoder.eof or decoder.unused_data:
            raise ValueError('Incomplete/oversized identity trace')
        result[name]=np.frombuffer(raw,dtype=dtype).reshape(shape).copy()
    if set(result)!={'labels','path'}:raise ValueError('Missing current-frame identity planes')
    return result


class Diagnostics:
    @property
    def error(self):return self._error

    def __init__(self, out: Path | None, record=False, *, writer_factory=None, close_timeout=5):
        self.out = Path(out) if out is not None else None
        self.record = bool(record and out is not None)
        self.writer_factory = writer_factory or self._video_writer
        self.close_timeout = close_timeout
        self.actions = queue.Queue(maxsize=4096)
        self._condition = threading.Condition()
        self._latest = None
        self._closing = False
        self._error = None
        self._frame_overwrites = 0
        self._action_count = self._frame_count = 0
        self._first_capture = self._last_capture = None
        self._last_acquired = None
        # Caller-owned session facts are attached after capture shutdown and
        # merged into session.json on close, outside the capture thread.
        self.metadata = {}
        self.thread = None
        if self.out is not None:
            self.out.mkdir(parents=True, exist_ok=True)
            self.thread = threading.Thread(target=self._run, name="assist-diagnostics", daemon=True)
            self.thread.start()

    @staticmethod
    def _video_writer(path, fps, size):
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
        if not writer.isOpened(): raise OSError(f"Cannot open video writer: {path}")
        return writer

    @staticmethod
    def _json(value):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)

    def event(self, row):
        if self.out is None: return False
        if self._error: return False
        try:
            self.actions.put_nowait(copy.deepcopy(dict(row)))
            return True
        except queue.Full:
            self._error = RuntimeError("Diagnostics action queue overflow (4096 rows)")
            return False

    def frame(self, image, info: dict, notes: list[dict], *, raw_trace=None):
        if self.out is None: return False
        if self._error: return False
        packet = (np.array(image, copy=True), _display_copy(info), _display_copy(notes),raw_trace)
        with self._condition:
            if self._closing: return False
            if self._latest is not None: self._frame_overwrites += 1
            self._latest = packet
            self._condition.notify_all()
        return True

    def _csv(self, name, fields):
        f = (self.out / name).open("w", newline="", encoding="utf-8")
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        return f, writer

    def _run(self):
        files, writers = [], []
        action_csv = decision_csv = frame_csv = index_csv = None
        source = overlay = None
        encoded = 0
        try:
            while True:
                row = None
                try: row = self.actions.get_nowait()
                except queue.Empty: pass
                with self._condition:
                    if self._latest is not None:
                        packet, self._latest = self._latest, None
                    else: packet = None
                    done = self._closing and packet is None and self.actions.empty()
                    if packet is None and row is None and not done:
                        self._condition.wait(.01)
                if row is not None:
                    if action_csv is None:
                        action_csv = self._csv("actions.csv", ["event", "at", "uid", "key", "kind", "reason", "generation", "payload_json"]); files.append(action_csv[0])
                    standard = {"event", "at", "uid", "key", "kind", "reason", "generation"}
                    action_csv[1].writerow({**{key: row.get(key, "") for key in standard},
                                           "payload_json": self._json({k: v for k, v in row.items() if k not in standard})})
                    self._action_count += 1
                if packet is not None:
                    image, info, notes,raw_trace = packet
                    if raw_trace is not None:info['identity_trace']=pack_identity_trace(raw_trace)
                    if image.shape != (404, 720, 3): raise ValueError("Diagnostics frames must be 720x404 BGR")
                    if frame_csv is None:
                        frame_csv = self._csv("frames.csv", ["encoded_frame", "source_frame", "captured_at", "acquired_at", "info_json", "notes_json"]); files.append(frame_csv[0])
                        decision_csv = self._csv("note_decisions.csv", ["encoded_frame", "decision_json"]); files.append(decision_csv[0])
                        if self.record:
                            index_csv = self._csv("live_video_index.csv", ["video_frame", "source_video_frame", "source_frame", "capture_timestamp", "acquired_timestamp", "focused", "roi_valid"]); files.append(index_csv[0])
                            source = self.writer_factory(self.out / "live_source.mp4", 60, (720, 404)); writers.append(source)
                            overlay = self.writer_factory(self.out / "live_overlay.mp4", 60, (720, 404)); writers.append(overlay)
                    source_frame = info.get("sequence", info.get("source_frame", ""))
                    captured = info.get("captured_at", info.get("capture_timestamp", ""))
                    acquired = info.get("acquired_at", info.get("acquired_timestamp", ""))
                    if self._first_capture is None:self._first_capture=captured
                    self._last_capture=captured;self._last_acquired=acquired
                    frame_csv[1].writerow(dict(encoded_frame=encoded, source_frame=source_frame,
                        captured_at=captured, acquired_at=acquired, info_json=self._json(info), notes_json=self._json(notes)))
                    for note in notes:
                        decision_csv[1].writerow(dict(encoded_frame=encoded, decision_json=self._json(note)))
                    if self.record:
                        source.write(image)
                        canvas = image.copy()
                        capture_time=info.get('captured_at')
                        hit_y=info.get('hit_y')
                        if hit_y is not None:
                            cv2.line(canvas,(0,round(hit_y)),(719,round(hit_y)),(0,160,255),1)
                        for note in notes:
                            box = note.get("bbox")
                            fresh=note.get('last_observation',capture_time)==capture_time
                            late_fragment=(note.get('detection_kind')=='plate_fragment' and
                                           note.get('state')=='TRACKING' and hit_y is not None and
                                           note.get('origin_y') is not None and note['origin_y']>hit_y-45)
                            if box and len(box) == 4 and fresh and not late_fragment:
                                x, y, w, h = map(int, box)
                                cv2.rectangle(canvas, (x, y), (x+w, y+h), (0, 255, 255), 1)
                                label_kind=note.get('kind','')
                                if label_kind=='tap' and (note.get('reason')=='tap_face_not_visible' or
                                        (note.get('state')=='TRACKING' and (note.get('detection_kind')=='plate_fragment' or
                                         (h<8 and note.get('last_full_tap_at') is None)))):
                                    label_kind='fragment'
                                label=f"{note.get('note_uid','')} {label_kind} {note.get('key','')}"
                                cv2.putText(canvas,label,(x,max(35,y-3)),cv2.FONT_HERSHEY_SIMPLEX,.35,(0,255,255),1)
                            tail_box=note.get('tail_bbox')
                            if tail_box and note.get('tail_last_observation')==capture_time:
                                x,y,w,h=map(int,tail_box)
                                cv2.rectangle(canvas,(x,y),(x+w,y+h),(255,0,255),1)
                        status = info.get("status")
                        if status: cv2.putText(canvas, str(status)[:100], (8, 22), cv2.FONT_HERSHEY_SIMPLEX, .5, (0,255,255), 1, cv2.LINE_AA)
                        cv2.putText(canvas,'HELD: '+str(info.get('held_keys','')),(8,400),cv2.FONT_HERSHEY_SIMPLEX,.4,(255,255,255),1)
                        overlay.write(canvas)
                        index_csv[1].writerow(dict(video_frame=encoded, source_video_frame=encoded,
                            source_frame=source_frame, capture_timestamp=captured, acquired_timestamp=acquired,
                            focused=info.get('focused',True),roi_valid=info.get('roi_valid',True)))
                    encoded += 1
                    self._frame_count += 1
                if done: break
        except Exception as exc:
            self._error = self._error or exc
        finally:
            for writer in writers:
                try: writer.release()
                except Exception as exc: self._error = self._error or exc
            for f in files:
                try: f.close()
                except Exception as exc: self._error = self._error or exc

    def close(self):
        if self.out is None:
            return {"actions": 0, "frames": 0, "frame_overwrites": 0, "error": None, "unverified": []}
        with self._condition:
            self._closing = True
            self._condition.notify_all()
        self.thread.join(self.close_timeout)
        if self.thread.is_alive():
            self._error = self._error or RuntimeError("Diagnostics writer did not flush within timeout")
        summary = {"actions": self._action_count, "frames": self._frame_count,
                   "frame_overwrites": self._frame_overwrites,
                   "action_queue_remaining": self.actions.qsize(),
                   "error": str(self._error) if self._error else None,
                   "game_accuracy": "UNVERIFIED",
                   "unverified": ["video encoding and frame-index playback; CSV index timestamps are authoritative, nominal 60 FPS is playback-only"] if self.record else []}
        try:
            (self.out / "summary.json").write_text(self._json(summary), encoding="utf-8")
            session=dict(tool='HoloDream Assist',capture_kind='auto_assist',
                timestamp_source='host_perf_counter',automatic_input=True,
                start_timestamp=self._first_capture,stopped_timestamp=self._last_acquired,
                nominal_video_fps=60,video_size=[720,404],recording_enabled=self.record,
                written_video_frames=self._frame_count if self.record else 0,
                video_integrity_verified=False,complete=not self._error,
                game_judgment_accuracy='UNVERIFIED',
                timing_note='Index capture/acquired timestamps are clocks; nominal FPS is playback only; actions.csv records injection, not human events')
            session.update(_display_copy(self.metadata))
            (self.out / 'session.json').write_text(self._json(session),encoding='utf-8')
        except Exception as exc: self._error = self._error or exc
        if self._error: raise RuntimeError(f"Diagnostics failed: {self._error}") from self._error
        return summary


def _display_copy(value, depth=0):
    """Copy small display metadata without doing serialization on the caller."""
    if depth >= 6: return "[depth-limited]"
    if value is None or isinstance(value, (bool, int, float)): return value
    if isinstance(value, str): return value[:4096]
    if isinstance(value, dict):
        return {str(key)[:256]: _display_copy(item, depth+1)
                for key, item in list(value.items())[:256]}
    if isinstance(value, (list, tuple)):
        return [_display_copy(item, depth+1) for item in value[:512]]
    if isinstance(value, np.generic): return value.item()
    return str(value)[:4096]

