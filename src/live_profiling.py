"""Measured stages and timestamp-based state/segment accounting (never FPS guesses)."""
from __future__ import annotations

from collections import defaultdict
import csv
import math
from pathlib import Path
import threading

import numpy as np

STAGES = ("capture", "normalization", "state_detector", "note_detector", "tracking", "prediction",
          "decision", "overlay_draw", "video_encoding", "disk_write", "ui_display",
          "cv_backlog", "overlay_backlog", "encoder_backlog", "cv_total")


def write_csv(path, rows, fields=None):
    rows = list(rows)
    with Path(path).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields or (list(rows[0]) if rows else ["status"]))
        writer.writeheader()
        writer.writerows(rows)


class StageProfiler:
    def __init__(self):
        self.lock = threading.Lock()
        self.samples = defaultdict(list)

    def record(self, stage, seconds, state="ALL"):
        if stage not in STAGES or not math.isfinite(seconds) or seconds < 0:
            raise ValueError("Invalid measured stage sample")
        with self.lock:
            self.samples[(stage, state)].append(seconds*1000)

    def rows(self):
        with self.lock:
            samples = {k:list(v) for k,v in self.samples.items()}
        rows = []
        for stage in STAGES:
            pooled = [x for (s,_),values in samples.items() if s == stage for x in values]
            groups = {state:values for (s,state),values in samples.items() if s == stage and state != "ALL"}
            groups["ALL"] = pooled
            for state, values in groups.items():
                rows.append({"stage":stage, "state":state, "status":"MEASURED" if values else "NOT_MEASURED",
                             "samples":len(values), "p50_ms":float(np.percentile(values,50)) if values else "",
                             "p95_ms":float(np.percentile(values,95)) if values else "",
                             "p99_ms":float(np.percentile(values,99)) if values else "",
                             "total_ms":sum(values) if values else ""})
        return rows


class TimedPredictor:
    def __init__(self, predictor, clock):
        self.predictor, self.clock = predictor, clock
        self.elapsed = 0.0

    @property
    def cfg(self):
        return self.predictor.cfg

    def predict(self, *args, **kwargs):
        begin = self.clock()
        try:
            return self.predictor.predict(*args, **kwargs)
        finally:
            self.elapsed += self.clock()-begin


def _period(frames):
    periods = [(float(b["capture_timestamp"])-float(a["capture_timestamp"]))/
               (int(b["frame"])-int(a["frame"])) for a,b in zip(frames,frames[1:])
               if int(b["frame"])>int(a["frame"]) and float(b["capture_timestamp"])>float(a["capture_timestamp"])]
    return float(np.median(periods)) if periods else 0.0


def performance_by_state(frames, acquisitions=None):
    """State is inferred between processed observations; never visual truth for drops.

    Legacy runs lack acquisition timestamps: source sequence spans are reported
    explicitly as estimates. Source/processed counts must not be called sliding FPS.
    """
    frames = sorted(frames,key=lambda r:float(r["capture_timestamp"]))
    if not frames:
        return [], []
    period = _period(frames)
    if acquisitions and len(acquisitions)>1:
        acquisition_times = sorted(float(r["capture_timestamp"]) for r in acquisitions)
        positive = [b-a for a,b in zip(acquisition_times,acquisition_times[1:]) if b>a]
        if positive: period=float(np.median(positive))
    by_state = defaultdict(lambda: {"processed":0,"acquired":0,"dropped":0,"stale":0,"duration":0.,"latencies":[],"ages":[],"gaps":[]})
    times = np.array([float(r["capture_timestamp"]) for r in frames])
    source_end = max((float(r["capture_timestamp"]) for r in acquisitions),default=times[-1])+period if acquisitions is not None else times[-1]+period
    indices = {int(r["frame"]) for r in frames}
    exact = acquisitions is not None
    for i, row in enumerate(frames):
        state = row["gameplay_state"]
        data = by_state[state]
        data["processed"] += 1
        data["stale"] += state == "STALE"
        end = times[i+1] if i+1<len(frames) else max(times[i]+period,source_end)
        data["duration"] += max(0,end-times[i])
        data["latencies"].append(float(row["latency_ms"]))
        data["ages"].append(float(row["frame_age_ms"]))
        if i+1<len(frames) and frames[i+1]["gameplay_state"] == state:
            data["gaps"].append(times[i+1]-times[i])
        if not exact:
            count = max(1,int(frames[i+1]["frame"])-int(row["frame"])) if i+1<len(frames) else 1
            data["acquired"] += count
            data["dropped"] += count-1
    if exact:
        for acq in acquisitions:
            timestamp = float(acq["capture_timestamp"])
            i = int(np.searchsorted(times,timestamp,side="right"))-1
            state = frames[i]["gameplay_state"] if i>=0 else "BEFORE_FIRST_DECISION"
            data = by_state[state]
            data["acquired"] += 1
            data["dropped"] += int(acq["frame"]) not in indices
    result = []
    for state, data in sorted(by_state.items()):
        seconds = data["duration"]
        result.append({"state":state, "processed":data["processed"], "acquired":data["acquired"],
                       "dropped":data["dropped"], "stale":data["stale"], "duration_s":seconds,
                       "acquired_fps":data["acquired"]/seconds if seconds else "",
                       "processed_fps":data["processed"]/seconds if seconds else "",
                       "dropped_fps":data["dropped"]/seconds if seconds else "",
                       "stale_fps":data["stale"]/seconds if seconds else "",
                       "drop_ratio":data["dropped"]/data["acquired"] if data["acquired"] else "",
                       "latency_p50_ms":float(np.percentile(data["latencies"],50)) if data["latencies"] else "",
                       "latency_p95_ms":float(np.percentile(data["latencies"],95)) if data["latencies"] else "",
                       "frame_age_p95_ms":float(np.percentile(data["ages"],95)) if data["ages"] else "",
                       "max_contiguous_gap_ms":1000*max(data["gaps"],default=0),
                       "acquisition_method":"capture_log; state carried forward from processed observations" if exact else
                                            "ESTIMATED source-sequence spans; no acquisition log",
                       "state_of_unprocessed_frames":"INFERRED, not visually verified"})
    segments = []
    begin = 0
    for end in range(1,len(frames)+1):
        if end<len(frames) and frames[end]["gameplay_state"] == frames[begin]["gameplay_state"]:
            continue
        group = frames[begin:end]
        first,last = group[0],group[-1]
        span = int(last["frame"])-int(first["frame"])+1
        seconds = float(last["capture_timestamp"])-float(first["capture_timestamp"])+period
        segments.append({"segment":len(segments), "state":first["gameplay_state"],
                         "first_source_frame":int(first["frame"]), "last_source_frame":int(last["frame"]),
                         "processed":len(group), "source_span":span, "unprocessed_inside_span":span-len(group),
                         "source_span_drop_ratio":(span-len(group))/span, "duration_s":seconds,
                         "processed_fps":len(group)/seconds if seconds else 0,
                         "max_gap_ms":1000*max((float(b["capture_timestamp"])-float(a["capture_timestamp"]) for a,b in zip(group,group[1:])),default=0),
                         "acquisition_note":"sequence span includes dropped frames; state is sampled"})
        begin = end
    return result, segments
