"""Once-per-track telemetry events for the live Assist engine."""
from __future__ import annotations
import numpy as np
from .common import KEYS
from .tracker import Track


class EventCollector:
    def __init__(self, cfg: dict | None = None):
        self.cfg = cfg or {}
        self.emitted: set[int] = set()
        self.rows: list[dict] = []

    def consider(self, tr: Track, frame: int, gameplay_state: str) -> dict | None:
        if gameplay_state != "PLAYING" or tr.track_id in self.emitted or tr.status != "confirmed" or tr.missed:
            return None
        c, prediction = tr.candidate, tr.prediction
        if c.note_type != "tap" or c.appearance not in ("cyan_bar", "yellow_bar") or c.suspected_overlap:
            return None
        if prediction.hit_time is None or prediction.eta is None:
            return None
        if prediction.eta > self.cfg.get("max_eta_s", 0.45) or tr.history[-1][1] < self.cfg.get("min_y", 190):
            return None
        if len(tr.hit_history) < 3 or np.ptp(tr.hit_history[-3:]) > self.cfg.get("max_hit_drift_s", 0.06):
            return None
        if not tr.stable_keys:
            return None
        row = {"note_id": tr.track_id, "type": "tap", "key_candidates": "|".join(tr.stable_keys),
               "candidate_lanes": "|".join(str(KEYS.index(k)) for k in tr.stable_keys),
               "resolved_keys": "", "u_min": f"{c.u_min:.6f}", "u_max": f"{c.u_max:.6f}",
               "source_v": f"{(c.bbox[1]+c.bbox[3]/2)/self.cfg.get('reference_height',404):.6f}",
               "hit_time": f"{prediction.hit_time:.6f}", "confidence": f"{c.score:.3f}",
               "status": "candidate", "source_frame": frame, "source_timestamp": f"{tr.last_time:.6f}",
               "executable": "false", "notes": "heuristic_score_not_probability;type_timing_and_candidate_lanes_unverified;no_chord_claim"}
        self.emitted.add(tr.track_id)
        self.rows.append(row)
        return row
