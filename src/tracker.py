"""Global sorted-pair association with motion gates and explicit lifecycle."""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass, field
import time
import numpy as np
from .detector import Candidate
from .predictor import Prediction, Predictor
from .particle_predictor import ParticlePredictor


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
    particle_filter: ParticlePredictor | None = None
    physical_note_uid: str = ""
    source_track_ids: list[int] = field(default_factory=list)
    reidentified_from_id: int | None = None
    confirmed_note_type: str | None = None
    identity_state: str = "UNCONFIRMED"
    identity_evidence_count: int = 0
    last_reliable_tap_at: float | None = None
    last_reliable_tap_candidate: Candidate | None = None
    selected_key: str | None = None
    identity_transitions: list[dict] = field(default_factory=list)
    last_association: dict = field(default_factory=dict)
    observation_quality: str = "unknown"

    @property
    def kind(self) -> str:
        return self.confirmed_note_type or self.candidate.note_type

    @property
    def current_observation_type(self) -> str:
        return self.candidate.note_type

    def transition_identity(self, state: str, timestamp: float, reason: str, **evidence) -> None:
        if state == self.identity_state:
            return
        previous = self.identity_state
        self.identity_state = state
        self.identity_transitions.append({"physical_note_uid":self.physical_note_uid,
            "track_id":self.track_id,"timestamp":timestamp,"from_state":previous,
            "to_state":state,"reason":reason,"confirmed_note_type":self.confirmed_note_type,
            "current_observation_type":self.current_observation_type,**evidence})

    def eta(self, hit_y: float | None = None, lookahead: float = 1.5) -> float | None:
        return self.prediction.eta if self.status == "confirmed" else None

    def observe(self, c: Candidate, t: float, predictor: Predictor, hit_y: float, cfg: dict,
                *, predictor_mode: str = "legacy", particle_cfg: dict | None = None,
                particle_seed: int = 20261030, physical_hit_y: float | None = None,
                identity_association: dict | None = None) -> None:
        _, y, _, h = c.bbox
        cy = y+h/2
        was_confirmed_tap = self.confirmed_note_type == "tap" and self.was_confirmed
        reliable_tap = (c.note_type == "tap" and c.appearance in
                        ("cyan_bar", "yellow_bar", "neutral_candidate") and
                        c.path_bbox is None and c.hold_path_px <= 0)
        identity_enabled=(particle_cfg or {}).get("identity_continuity",{}).get("enabled",True)
        degraded = (identity_enabled and predictor_mode == "particle" and was_confirmed_tap and
                    c.note_type == "unknown")
        association = {}
        if degraded:
            max_degraded_ms = float((particle_cfg or {}).get("identity_continuity",{}).get("max_degraded_ms",90))
            if (self.last_reliable_tap_at is None or
                    not 0 < t-self.last_reliable_tap_at <= max_degraded_ms/1000):
                self.status, self.reason = "lost", "tap_identity_reliable_observation_expired"
                if self.particle_filter is not None:
                    self.prediction = self.particle_filter.coast_to(t,hit_y)
                self.transition_identity("TAP_COASTING",t,self.reason,
                    reliable_age_ms=(t-self.last_reliable_tap_at)*1000 if self.last_reliable_tap_at is not None else "")
                return
            if self.particle_filter is None or self.last_reliable_tap_candidate is None:
                self.status, self.reason = "lost", "degraded_tap_without_particle_state"
                self.transition_identity("TAP_COASTING",t,self.reason)
                return
            source = self.last_reliable_tap_candidate
            association = identity_association or self.particle_filter.identity_association_score(
                c,t,(source.u_min,source.u_max),self.stable_keys,self.selected_key,
                allow_pinned_key=self.selected_key is not None)
            self.last_association = association
            if not association.get("accepted"):
                self.status, self.reason = "lost", association.get("reason","unknown_observation_rejected")
                self.prediction = self.particle_filter.coast_to(t,hit_y)
                self.transition_identity("TAP_COASTING",t,self.reason,association_score=association.get("association_score"),
                                         innovation_y=association.get("innovation_y"))
                return
        elif was_confirmed_tap and reliable_tap:
            association = {"accepted":True,"reason":"reliable_tap_observation",
                           "association_score":0.0,"measurement_quality":"reliable"}
            self.last_association = association
        self.candidate, self.bbox, self.last_time = c, c.bbox, t
        if not self.appearance_anchor or (self.appearance_anchor == "neutral_candidate" and reliable_tap):
            self.appearance_anchor = c.appearance
        if self.observations == 0:
            self.first_time = t
        self.observations += 1
        self.history.append((t, cy, (c.u_min+c.u_max)/2))
        self.history = self.history[-24:]
        self.y_min, self.y_max = min(self.y_min, cy), max(self.y_max, cy)
        if not degraded:
            self.key_history.append(tuple(c.candidate_keys))
            self.key_history = self.key_history[-7:]
            counts = Counter(k for keys in self.key_history for k in keys)
            self.stable_keys = sorted((k for k, n in counts.items() if n/len(self.key_history) >= 0.6),
                                      key=lambda k: cfg.get("key_map", list("SDFJKL")).index(k))
        self.missed = 0
        is_particle_tap = (predictor_mode == "particle" and
                           (reliable_tap or degraded) and
                           (c.appearance in ("cyan_bar","yellow_bar","neutral_candidate") if degraded else True))
        if is_particle_tap:
            if self.particle_filter is None:
                self.particle_filter = ParticlePredictor(
                    particle_cfg, seed=particle_seed, track_id=self.track_id,
                    physical_hit_y=physical_hit_y)
            self.prediction = self.particle_filter.update(
                self.history, hit_y, physical_hit_y=physical_hit_y,
                measurement_noise_scale=(float(particle_cfg.get("degraded_measurement_noise_scale",2.5))
                                         if degraded else 1.0),
                measurement_status=("DEGRADED_USED" if degraded else "USED"),
                association_score=association.get("association_score"),
                measurement_quality=(association.get("measurement_quality","degraded") if degraded else "reliable"))
        else:
            began = time.perf_counter()
            try:
                self.prediction = predictor.predict(self.history, hit_y)
            finally:
                predictor.elapsed = getattr(predictor, "elapsed", 0.0) + time.perf_counter() - began
        if self.status == "rejected":
            # Keep associating static clutter to its rejected ID.
            return
        if cy > cfg.get('completion_y',hit_y):
            self.status, self.reason = "completed", "past_hit_line"
            if self.confirmed_note_type == "tap":
                self.transition_identity("TAP_COMPLETED",t,"past_physical_completion_line")
            return
        if t-self.first_time >= cfg.get("stationary_after_s", 0.20) and self.y_max-self.y_min < cfg.get("stationary_span_px", 5):
            self.status, self.reason = "rejected", "stationary_background"
            if self.confirmed_note_type == "tap":
                self.transition_identity("TAP_REJECTED",t,"stationary_background")
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
        if was_confirmed_tap and degraded and self.was_confirmed:
            # Identity is supported by the accumulated Tap history; a single
            # poor contour may not revoke it or its key evidence.
            self.status = "confirmed"
            self.transition_identity("TAP_DEGRADED_OBSERVATION",t,"pf_associated_unknown",
                                     association_score=association.get("association_score"),
                                     innovation_y=association.get("innovation_y"),
                                     measurement_quality=association.get("measurement_quality"))
        elif reliable_tap and self.was_confirmed:
            self.confirmed_note_type = "tap"
            self.identity_evidence_count += 1
            self.last_reliable_tap_at = t
            self.last_reliable_tap_candidate = c
            self.observation_quality = "reliable"
            self.transition_identity("CONFIRMED_TAP",t,"reliable_tap_motion_and_history",
                                     evidence_count=self.identity_evidence_count)
        elif not was_confirmed_tap:
            self.observation_quality = "reliable" if reliable_tap else "unknown"
        self.reason = self.prediction.reason
        if self.status == "confirmed" and self.prediction.hit_time is not None:
            self.hit_history.append(self.prediction.hit_time)
            self.hit_history = self.hit_history[-5:]
            drift_window = (cfg.get("tap_hit_drift_window",5)
                            if c.appearance in ("cyan_bar","yellow_bar") else 5)
            if (self.prediction.predictor_mode != "particle" and len(self.hit_history) >= 3 and
                    np.ptp(self.hit_history[-drift_window:]) > cfg.get("max_hit_drift_s", 0.08)):
                self.prediction = Prediction(velocity=self.prediction.velocity,
                                             fitted_y=self.prediction.fitted_y,
                                             reason="hit_time_drift")
                self.reason = "hit_time_drift"
        self.prediction = Prediction(**{**self.prediction.__dict__,
            "identity_state":self.identity_state,
            "observed_y":cy if degraded else self.prediction.observed_y,
            "innovation_y":association.get("innovation_y",self.prediction.innovation_y),
            "identity_ambiguous":self.identity_state=="TAP_IDENTITY_AMBIGUOUS"})


class Tracker:
    def __init__(self, cfg: dict | None = None, hit_y: float = 352, predictor_cfg: dict | None = None,
                 *, predictor_mode: str = "legacy", particle_cfg: dict | None = None,
                 physical_hit_y: float | None = None):
        self.cfg, self.hit_y = cfg or {}, hit_y
        self.predictor = Predictor(predictor_cfg)
        if predictor_mode not in ("legacy", "particle"):
            raise ValueError("predictor mode must be particle or legacy")
        self.predictor_mode = predictor_mode
        self.particle_cfg = dict(particle_cfg or {})
        self.particle_seed = int(self.particle_cfg.get("deterministic_seed", 20261030))
        self.physical_hit_y = physical_hit_y
        self.tracks: list[Track] = []
        self.finished: list[Track] = []
        self.recent_particle_tracks: list[Track] = []
        self.last_unknown_association_audit: list[dict] = []
        self._ambiguous_unknown_pairs: set[tuple[int,int]] = set()
        self._pair_candidate_index: dict[int,int] = {}
        self._unknown_association_cache: dict[tuple[int,int],dict] = {}
        self.stage_times = {"unknown_association_s":0.0,"matching_s":0.0}
        self.next_id = 1

    @property
    def elapsed(self) -> float:
        return getattr(self.predictor, "elapsed", 0.0) + sum(
            pf.elapsed for tr in (*self.tracks, *self.finished)
            if (pf := getattr(tr, "particle_filter", None)) is not None)

    def pair_cost(self, tr: Track, c: Candidate, t: float) -> float | None:
        track_index = next((i for i,item in enumerate(self.tracks) if item is tr),-1)
        candidate_index = self._pair_candidate_index.get(id(c),-1)
        if (tr.confirmed_note_type == "tap" and c.note_type == "unknown" and
                self.predictor_mode == "particle"):
            if not self.particle_cfg.get("identity_continuity",{}).get("enabled",True):
                return None
            if (tr.particle_filter is None or
                    tr.last_reliable_tap_at is None or
                    t-tr.last_reliable_tap_at > float(self.particle_cfg.get("identity_continuity",{}).get("max_degraded_ms",90))/1000 or
                    tr.identity_state in ("TAP_IDENTITY_AMBIGUOUS","TAP_COMPLETED","TAP_REJECTED") or
                    (track_index,candidate_index) in self._ambiguous_unknown_pairs):
                return None
            source=tr.last_reliable_tap_candidate
            if source is None:
                return None
            association=self._unknown_association_cache.get((track_index,candidate_index))
            if association is None:
                association=tr.particle_filter.identity_association_score(
                c,t,(source.u_min,source.u_max),tr.stable_keys,tr.selected_key,
                allow_pinned_key=tr.selected_key is not None)
            if not association.get("accepted"):
                return None
            return float(association["association_score"])
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
        pf_y = tr.particle_filter.position_at(t) if tr.particle_filter else None
        predicted_y = (pf_y if pf_y is not None else
                       last_y + (max(0.0, velocity)*dt if velocity is not None else 0))
        tolerance = max(8.0,220*dt,min(15.0,(tr.bbox[3]+c.bbox[3])*0.35))
        if velocity is None:
            tolerance = min(32.0, 7.0 + (last_y/self.hit_y)*25) * max(1, dt*60)
        residual = abs(cy-predicted_y)
        if residual > tolerance:
            return None
        return du/0.09 + residual/tolerance + 0.35*abs(np.log(ratio)) + color_penalty

    def _particle_handoff_source(self, candidate: Candidate, t: float,
                                  candidate_index: int, candidates: list[Candidate],
                                  used_track_indexes: set[int]) -> Track | None:
        """Return a unique, strictly gated lost Tap whose PF can continue this ID.

        Ambiguous same-lane heads are deliberately left as separate tentative
        tracks. This transfers estimator state only; LiveEngine still owns and
        validates any previously scheduled intent/deadline.
        """
        degraded_unknown = candidate.note_type == "unknown"
        if (degraded_unknown and
                not self.particle_cfg.get("identity_continuity",{}).get("enabled",True)):
            return None
        if (self.predictor_mode != "particle" or
                (candidate.note_type != "tap" and not degraded_unknown) or
                candidate.appearance not in ("cyan_bar", "yellow_bar", "neutral_candidate") or
                candidate.suspected_overlap or candidate.path_bbox is not None or candidate.hold_path_px>0):
            return None
        _, cy0, _, _ = candidate.bbox
        cy = cy0 + candidate.bbox[3] / 2
        u = (candidate.u_min + candidate.u_max) / 2
        viable = []
        possible_sources = [(index, old) for index, old in enumerate(self.tracks)]
        possible_sources.extend((-index-1, old) for index, old in enumerate(self.recent_particle_tracks))
        for index, old in possible_sources:
            pf = old.particle_filter
            lost_active = index >= 0 and old.status == "lost"
            short_expired = index < 0 and old.reason == "track_expired"
            if (index in used_track_indexes or not (lost_active or short_expired) or not old.was_confirmed or
                    old.confirmed_note_type != "tap" or
                    pf is None or not pf.initialized or not old.stable_keys or
                    old.identity_state in ("TAP_IDENTITY_AMBIGUOUS","TAP_COMPLETED","TAP_REJECTED")):
                continue
            dt = t - old.last_time
            predicted = pf.position_at(t)
            if predicted is None or not 0 < dt <= min(pf.max_coast_s, .09):
                continue
            reliable=old.last_reliable_tap_candidate
            if reliable is None:
                continue
            if (old.last_reliable_tap_at is None or
                    t-old.last_reliable_tap_at > float(self.particle_cfg.get("identity_continuity",{}).get("max_degraded_ms",90))/1000):
                continue
            if degraded_unknown:
                identity=pf.identity_association_score(candidate,t,(reliable.u_min,reliable.u_max),
                                                       old.stable_keys,old.selected_key,
                                                       allow_pinned_key=old.selected_key is not None)
                if not identity.get("accepted"):
                    continue
            elif not set(old.stable_keys).intersection(candidate.candidate_keys):
                continue
            if not degraded_unknown and abs(u - old.history[-1][2]) > .025:
                continue
            old_width = max(reliable.u_max-reliable.u_min, .01)
            new_width = max(candidate.u_max-candidate.u_min, .01)
            if not degraded_unknown and not .7 <= new_width/old_width <= 1.4:
                continue
            residual = abs(cy-predicted)
            if residual > max(7., min(14., 180*dt)):
                continue
            viable.append((residual + 300*abs(u-old.history[-1][2]), index, old))
        viable.sort(key=lambda row: row[0])
        if not viable:
            return None
        # If another visible head covers these keys nearby, identity is
        # ambiguous (usually a dense same-lane sequence or split body).
        for other_index, other in enumerate(candidates):
            if other_index == candidate_index or not set(other.candidate_keys).intersection(candidate.candidate_keys):
                continue
            oy = other.bbox[1] + other.bbox[3]/2
            if abs(oy-cy) <= 26:
                return None
        if len(viable) > 1 and viable[1][0] - viable[0][0] < 5.:
            return None
        return viable[0][2]

    def update(self, candidates: list[Candidate], t: float, playing: bool = True) -> list[Track]:
        update_started=time.perf_counter()
        association_elapsed_before=sum(getattr(tr.particle_filter,"association_elapsed",0.0)
            for tr in (*self.tracks,*self.finished) if tr.particle_filter is not None)
        self.last_unknown_association_audit = []
        self._ambiguous_unknown_pairs = set()
        self._unknown_association_cache = {}
        self._pair_candidate_index = {id(c):j for j,c in enumerate(candidates)}
        self.recent_particle_tracks = [old for old in self.recent_particle_tracks
                                       if old.particle_filter is not None and
                                       0 <= t-old.last_time <= old.particle_filter.max_coast_s]
        if not playing:
            for tr in self.tracks:
                tr.status, tr.reason = "completed", "gameplay_gate_closed"
            self.finished.extend(self.tracks)
            self.tracks = []
            self.recent_particle_tracks.clear()
            self.stage_times={"unknown_association_s":0.0,"matching_s":0.0,
                              "total_s":time.perf_counter()-update_started}
            return []
        association_started=time.perf_counter()
        potential = []
        for i,tr in enumerate(self.tracks):
            if (not self.particle_cfg.get("identity_continuity",{}).get("enabled",True) or
                    tr.confirmed_note_type != "tap" or tr.particle_filter is None or
                    tr.last_reliable_tap_candidate is None):
                continue
            ref=tr.last_reliable_tap_candidate
            for j,c in enumerate(candidates):
                if c.note_type != "unknown":
                    continue
                max_degraded=float(self.particle_cfg.get("identity_continuity",{}).get("max_degraded_ms",90))/1000
                if tr.last_reliable_tap_at is None or not 0<t-tr.last_reliable_tap_at<=max_degraded:
                    self.last_unknown_association_audit.append({"timestamp":t,"candidate_index":j,
                        "track_id":tr.track_id,"physical_note_uid":tr.physical_note_uid,
                        "current_observation_type":c.note_type,"association_accepted":False,
                        "final_reason":"tap_identity_reliable_observation_expired"})
                    continue
                score=tr.particle_filter.identity_association_score(
                    c,t,(ref.u_min,ref.u_max),tr.stable_keys,tr.selected_key,
                    allow_pinned_key=tr.selected_key is not None)
                self._unknown_association_cache[(i,j)]=score
                potential.append((i,j,tr,c,score))
        accepted_by_candidate=Counter(j for _,j,_,_,score in potential if score.get("accepted"))
        accepted_by_track=Counter(i for i,_,_,_,score in potential if score.get("accepted"))
        ambiguous_tracks=set()
        for i,j,tr,c,score in potential:
            cy=c.bbox[1]+c.bbox[3]/2
            nearby_competitor=any(k!=j and
                bool(set(other.candidate_keys).intersection(c.candidate_keys)) and
                abs((other.bbox[1]+other.bbox[3]/2)-cy)<=26
                for k,other in enumerate(candidates))
            competing=accepted_by_candidate[j]>1 or accepted_by_track[i]>1 or nearby_competitor
            if competing:
                self._ambiguous_unknown_pairs.add((i,j))
                ambiguous_tracks.add(i)
            self.last_unknown_association_audit.append({"timestamp":t,"candidate_index":j,
                "track_id":tr.track_id,"physical_note_uid":tr.physical_note_uid,
                "current_observation_type":c.note_type,
                "association_accepted":bool(score.get("accepted") and not competing),
                "final_reason":"competing_unknown_associations" if competing else score.get("reason","unknown"),
                **score})
        unknown_association_s=time.perf_counter()-association_started
        matching_started=time.perf_counter()
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
            self.tracks[i].observe(candidates[j], t, self.predictor, self.hit_y, self.cfg,
                                   predictor_mode=self.predictor_mode, particle_cfg=self.particle_cfg,
                                   particle_seed=self.particle_seed, physical_hit_y=self.physical_hit_y,
                                   identity_association=self._unknown_association_cache.get((i,j)))
            used_tracks.add(i)
            used_candidates.add(j)
        for i, tr in enumerate(self.tracks):
            if i not in used_tracks:
                tr.missed += 1
                if tr.status != "rejected":
                    tr.status, tr.reason = "lost", "occluded_or_unmatched"
                if tr.confirmed_note_type == "tap" and tr.particle_filter is not None:
                    if i in ambiguous_tracks:
                        tr.transition_identity("TAP_IDENTITY_AMBIGUOUS",t,"competing_unknown_associations")
                    else:
                        tr.prediction=tr.particle_filter.coast_to(t,self.hit_y)
                        tr.transition_identity("TAP_COASTING",t,"no_accepted_measurement",
                                               coast_ms=tr.prediction.coast_ms)
        for j, c in enumerate(candidates):
            if j not in used_candidates:
                tr = Track(self.next_id, c)
                source = self._particle_handoff_source(c, t, j, candidates, used_tracks)
                if source is not None:
                    tr.history = list(source.history)
                    tr.bbox = source.bbox
                    tr.observations = source.observations
                    tr.first_time = source.first_time
                    tr.y_min, tr.y_max = source.y_min, source.y_max
                    tr.was_confirmed = source.was_confirmed
                    tr.confirmed_note_type = source.confirmed_note_type
                    tr.identity_state = source.identity_state
                    tr.identity_evidence_count = source.identity_evidence_count
                    tr.last_reliable_tap_at = source.last_reliable_tap_at
                    tr.last_reliable_tap_candidate = source.last_reliable_tap_candidate
                    tr.selected_key = source.selected_key
                    tr.identity_transitions = list(source.identity_transitions)
                    tr.hit_history = list(source.hit_history)
                    tr.key_history = list(source.key_history)
                    tr.stable_keys = list(source.stable_keys)
                    tr.appearance_anchor = source.appearance_anchor
                    tr.particle_filter = source.particle_filter
                    tr.physical_note_uid = source.physical_note_uid or f"physical:{source.track_id}"
                    tr.source_track_ids = list(source.source_track_ids or [source.track_id]) + [self.next_id]
                    tr.reidentified_from_id = source.track_id
                    source.particle_filter = None
                tr.observe(c, t, self.predictor, self.hit_y, self.cfg,
                           predictor_mode=self.predictor_mode, particle_cfg=self.particle_cfg,
                           particle_seed=self.particle_seed, physical_hit_y=self.physical_hit_y)
                if not tr.physical_note_uid:
                    tr.physical_note_uid = f"physical:{tr.track_id}"
                    tr.source_track_ids = [tr.track_id]
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
                if (tr.reason == "track_expired" and tr.was_confirmed and
                        tr.particle_filter is not None):
                    self.recent_particle_tracks.append(tr)
            else:
                active.append(tr)
        self.tracks = active
        self.stage_times={"unknown_association_s":unknown_association_s,
                          "matching_s":time.perf_counter()-matching_started,
                          "total_s":time.perf_counter()-update_started,
                          "pf_association_s":max(0.0,sum(getattr(tr.particle_filter,"association_elapsed",0.0)
                              for tr in (*self.tracks,*self.finished) if tr.particle_filter is not None)-association_elapsed_before)}
        return self.tracks
