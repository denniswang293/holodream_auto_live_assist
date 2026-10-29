"""Global sorted-pair association with motion gates and explicit lifecycle."""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass, field
import numpy as np
from .detector import Candidate
from .predictor import Prediction, Predictor


@dataclass
class Track:
    track_id: int
    candidate: Candidate
    history: list[tuple[float, float, float]] = field(default_factory=list)
    bbox: tuple[int, int, int, int] = (0, 0, 0, 0)
    status: str = "tentative"
    reason: str = "insufficient_observations"
    missed: int = 0
    was_confirmed: bool = False
    observations: int = 0
    first_time: float = 0.0
    last_time: float = 0.0
    y_min: float = float("inf")
    y_max: float = float("-inf")
    prediction: Prediction = field(default_factory=Prediction)
    hit_history: list[float] = field(default_factory=list)
    key_history: list[tuple[str, ...]] = field(default_factory=list)
    stable_keys: list[str] = field(default_factory=list)
    rejected_position: tuple[float, float] | None = None
    appearance_anchor: str = ""

    @property
    def kind(self) -> str:
        return self.candidate.note_type

    def eta(self, hit_y: float | None = None, lookahead: float = 1.5) -> float | None:
        return self.prediction.eta if self.status == "confirmed" else None

    def observe(self, c: Candidate, t: float, predictor: Predictor, hit_y: float, cfg: dict) -> None:
        _, y, _, h = c.bbox
        cy = y+h/2
        self.candidate, self.bbox, self.last_time = c, c.bbox, t
        if not self.appearance_anchor or self.appearance_anchor == "neutral_candidate":
            self.appearance_anchor = c.appearance
        if self.observations == 0:
            self.first_time = t
        self.observations += 1
        self.history.append((t, cy, (c.u_min+c.u_max)/2))
        self.history = self.history[-24:]
        self.y_min, self.y_max = min(self.y_min, cy), max(self.y_max, cy)
        self.key_history.append(tuple(c.candidate_keys))
        self.key_history = self.key_history[-7:]
        counts = Counter(k for keys in self.key_history for k in keys)
        self.stable_keys = sorted((k for k, n in counts.items() if n/len(self.key_history) >= 0.6),
                                  key=lambda k: cfg.get("key_map", list("SDFJKL")).index(k))
        self.missed = 0
        self.prediction = predictor.predict(self.history, hit_y)
        if self.status == "rejected":
            # Keep associating static clutter to its rejected ID.
            return
        if cy > cfg.get('completion_y',hit_y):
            self.status, self.reason = "completed", "past_hit_line"
            return
        if t-self.first_time >= cfg.get("stationary_after_s", 0.20) and self.y_max-self.y_min < cfg.get("stationary_span_px", 5):
            self.status, self.reason = "rejected", "stationary_background"
            self.rejected_position = (float(np.median([p[1] for p in self.history])),
                                      float(np.median([p[2] for p in self.history])))
            return
        motion_ok = (self.prediction.velocity is not None and
                     self.prediction.velocity >= predictor.cfg.get("min_velocity", 20) and
                     self.prediction.reason in ("", "outside_lookahead"))
        if self.observations >= cfg.get("confirm_observations", 5) and motion_ok:
            self.was_confirmed = True
            self.status = "confirmed"
        else:
            self.status = "tentative"
        self.reason = self.prediction.reason
        if self.status == "confirmed" and self.prediction.hit_time is not None:
            self.hit_history.append(self.prediction.hit_time)
            self.hit_history = self.hit_history[-5:]
            drift_window = (cfg.get("tap_hit_drift_window",5)
                            if c.appearance in ("cyan_bar","yellow_bar") else 5)
            if (len(self.hit_history) >= 3 and
                    np.ptp(self.hit_history[-drift_window:]) > cfg.get("max_hit_drift_s", 0.08)):
                self.prediction = Prediction(velocity=self.prediction.velocity,
                                             fitted_y=self.prediction.fitted_y,
                                             reason="hit_time_drift")
                self.reason = "hit_time_drift"


class Tracker:
    def __init__(self, cfg: dict | None = None, hit_y: float = 352, predictor_cfg: dict | None = None):
        self.cfg, self.hit_y = cfg or {}, hit_y
        self.predictor = Predictor(predictor_cfg)
        self.tracks: list[Track] = []
        self.finished: list[Track] = []
        self.next_id = 1

    def pair_cost(self, tr: Track, c: Candidate, t: float) -> float | None:
        anchor = tr.appearance_anchor
        color_penalty = 0.0
        if c.appearance != anchor:
            # Pale cores can alternate with a colored border across frames.
            # This continuity does not upgrade neutral detections to taps.
            normal = {"cyan_bar","yellow_bar","neutral_candidate"}
            if c.appearance in normal and anchor in normal and "neutral_candidate" in (c.appearance,anchor):
                color_penalty = 0.4
            else:
                return None
        dt = t-tr.last_time
        if dt <= 0 or dt > self.cfg.get("max_gap_s", 0.16):
            return None
        _, y, _, h = c.bbox
        cy, last_y = y+h/2, tr.history[-1][1]
        u, last_u = (c.u_min+c.u_max)/2, tr.history[-1][2]
        if tr.rejected_position is not None:
            anchor_y, anchor_u = tr.rejected_position
            if abs(cy-anchor_y) > 3.5 or abs(u-anchor_u) > 0.025:
                return None
        old_width = max(tr.candidate.u_max-tr.candidate.u_min, 0.01)
        width = max(c.u_max-c.u_min, 0.01)
        ratio = width/old_width
        if not 0.45 <= ratio <= 2.2:
            return None
        if not set(c.candidate_keys).intersection(tr.candidate.candidate_keys):
            return None
        du = abs(u-last_u)
        if du > self.cfg.get("max_u_step", 0.09):
            return None
        dy = cy-last_y
        jitter = max(self.cfg.get("backward_jitter_px", 3.5),min(7.0,tr.bbox[3]*0.35))
        if dy < -jitter:
            return None
        if dy > self.predictor.cfg.get("max_velocity", 1800)*dt+3:
            return None
        velocity = tr.prediction.velocity
        predicted_y = last_y + (max(0.0, velocity)*dt if velocity is not None else 0)
        tolerance = max(8.0,220*dt,min(15.0,(tr.bbox[3]+c.bbox[3])*0.35))
        if velocity is None:
            tolerance = min(32.0, 7.0 + (last_y/self.hit_y)*25) * max(1, dt*60)
        residual = abs(cy-predicted_y)
        if residual > tolerance:
            return None
        return du/0.09 + residual/tolerance + 0.35*abs(np.log(ratio)) + color_penalty

    def update(self, candidates: list[Candidate], t: float, playing: bool = True) -> list[Track]:
        if not playing:
            for tr in self.tracks:
                tr.status, tr.reason = "completed", "gameplay_gate_closed"
            self.finished.extend(self.tracks)
            self.tracks = []
            return []
        pairs = []
        for i, tr in enumerate(self.tracks):
            for j, c in enumerate(candidates):
                cost = self.pair_cost(tr, c, t)
                if cost is not None:
                    pairs.append((cost, tr.track_id, i, j))
        used_tracks, used_candidates = set(), set()
        # Review-approved globally sorted legal pairs; not Hungarian optimality.
        for _, _, i, j in sorted(pairs):
            if i in used_tracks or j in used_candidates:
                continue
            self.tracks[i].observe(candidates[j], t, self.predictor, self.hit_y, self.cfg)
            used_tracks.add(i)
            used_candidates.add(j)
        for i, tr in enumerate(self.tracks):
            if i not in used_tracks:
                tr.missed += 1
                if tr.status != "rejected":
                    tr.status, tr.reason = "lost", "occluded_or_unmatched"
        for j, c in enumerate(candidates):
            if j not in used_candidates:
                tr = Track(self.next_id, c)
                tr.observe(c, t, self.predictor, self.hit_y, self.cfg)
                self.tracks.append(tr)
                self.next_id += 1
        active = []
        for tr in self.tracks:
            expired = (tr.missed > self.cfg.get("max_missed_frames", 8) or
                       t-tr.last_time > self.cfg.get("max_gap_s", 0.16))
            if expired or tr.status == "completed":
                if tr.status != "rejected":
                    tr.status, tr.reason = "completed", tr.reason if tr.reason == "past_hit_line" else "track_expired"
                self.finished.append(tr)
            else:
                active.append(tr)
        self.tracks = active
        return self.tracks
