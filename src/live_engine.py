"""Live Assist decision engine and overlay."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math
import time
import uuid

import cv2
import numpy as np

from .calibration import geometry_hash
from .detector import detect
from .events import EventCollector
from .gameplay import GameplayGate
from .live_capture import normalize_frame
from .live_input import ActionIntent, verified_keys
from .overlay import render
from .tracker import Tracker
from .tap_assignment import AnyCoveredKeyRule
from .hold_visual import path_runs, nearest_run
from .judgment_time import JudgmentTimeEstimator
from .hold_tracker import HoldTracker
from .simple_core import SimpleAssistCore
from .simple_tracker import is_simple_tap

PROVISIONAL_TAP_LOSS_GRACE_S = .070


@dataclass(frozen=True)
class ParticleEtaEvidence:
    """Conservative scheduling evidence derived from one PF posterior."""
    hit_at: float | None
    credible_width_ms: float | None
    valid_crossing_mass: float | None
    ess_fraction: float | None
    real_observation_count: int
    measurement_age_ms: float | None
    coast_ms: float
    identity_state: str
    is_usable: bool
    reject_reason: str = ""


def particle_eta_evidence(track, now, event_cfg):
    p = track.prediction
    pf = getattr(track, "particle_filter", None)
    cfg = getattr(pf, "cfg", {}) if pf is not None else {}
    count = int(getattr(pf, "count", cfg.get("count", 0)) or 0)
    ess = p.ess
    ess_fraction = float(ess) / count if ess is not None and count else None
    width_ms = (1000 * (p.eta_p90 - p.eta_p10)
                if p.eta_p90 is not None and p.eta_p10 is not None else None)
    last_time = getattr(pf, "last_time", None)
    age_ms = max(0., (now - last_time) * 1000) if last_time is not None else None
    observations = int(p.real_observation_count or 0)
    coast_ms = float(p.coast_ms or 0.)
    identity = str(getattr(track, "identity_state", "UNCONFIRMED"))
    reason = ""
    if p.predictor_mode != "particle": reason = "not_particle_predictor"
    elif pf is None or not getattr(pf, "initialized", False): reason = "particle_not_initialized"
    elif track.confirmed_note_type != "tap": reason = "tap_identity_unconfirmed"
    elif identity in ("TAP_IDENTITY_AMBIGUOUS", "TAP_REJECTED", "TAP_COMPLETED"):
        reason = "tap_identity_not_schedulable"
    elif not p.reason == "": reason = p.reason or "particle_prediction_invalid"
    elif p.hit_time is None or not math.isfinite(p.hit_time) or p.hit_time <= now:
        reason = "particle_hit_time_not_future"
    elif p.eta_p10 is None or p.eta_p90 is None or not all(
            math.isfinite(v) for v in (p.eta_p10, p.eta_p90)):
        reason = "particle_credible_interval_missing"
    elif width_ms is None or width_ms < 0 or width_ms > 2 * float(event_cfg.get("max_uncertainty_s", .04)) * 1000:
        reason = "particle_posterior_too_wide"
    elif p.valid_crossing_mass is None or p.valid_crossing_mass < float(cfg.get("min_valid_crossing_mass", .95)):
        reason = "particle_crossing_mass_too_low"
    elif observations < int(cfg.get("min_real_observations", 4)):
        reason = "particle_insufficient_real_observations"
    elif ess_fraction is None or ess_fraction < float(cfg.get("identity_min_ess_fraction", .1)):
        reason = "particle_ess_too_low"
    elif coast_ms > float(cfg.get("max_coast_ms", 90)):
        reason = "particle_coast_expired"
    elif age_ms is not None and age_ms > float(cfg.get("max_coast_ms", 90)):
        reason = "particle_measurement_stale"
    elif p.hit_time - now > float(event_cfg.get("max_eta_s", .45)):
        reason = "particle_eta_outside_horizon"
    return ParticleEtaEvidence(p.hit_time, width_ms, p.valid_crossing_mass,
                               ess_fraction, observations, age_ms, coast_ms,
                               identity, not reason, reason)


def track_options(track, now, known_keys, event_cfg, *, allow_range=False, speculative=None,
                  nearline_y=None):
    """Validate motion/timing and return allowed options, never a chord."""
    c, p = track.candidate, track.prediction
    if track.status != "confirmed" or track.missed:
        return (), "track_not_current_confirmed"
    speculative = speculative or {}
    experimental = bool(speculative.get("enabled"))
    degraded_tap = (getattr(track,"confirmed_note_type",None)=="tap" and
                    getattr(track,"identity_state","")=="TAP_DEGRADED_OBSERVATION" and
                    c.note_type=="unknown" and
                    bool(getattr(track,"last_association",{}).get("accepted")))
    allowed_appearances = ("cyan_bar", "yellow_bar", "green_candidate",
                           "pink_candidate", "neutral_candidate") if experimental else ("cyan_bar", "yellow_bar")
    if ((c.note_type not in (("tap", "unknown") if experimental else ("tap",)) and not degraded_tap) or
            (c.appearance not in allowed_appearances and not (degraded_tap and c.appearance=="neutral_candidate"))):
        return (), "unverified_special_or_neutral"
    if c.suspected_overlap and not experimental:
        return (), "suspected_overlap"
    options = ([key for key in track.stable_keys if key in c.candidate_keys]
               if allow_range else track.stable_keys)
    if experimental and allow_range and not options:
        # An uncertain lane uses the current geometric footprint. The matcher
        # still chooses just one key and keeps a previous binding fixed.
        options = list(c.candidate_keys)
    if (not options or (not allow_range and
            (c.candidate_keys!=track.stable_keys or len(track.stable_keys)!=1))):
        return (), "ambiguous_or_unstable_keys"
    if p.hit_time is None or p.eta is None or p.uncertainty is None:
        return (), p.reason or "no_valid_prediction"
    if not all(math.isfinite(value) for value in (p.hit_time,p.eta,p.uncertainty)):
        return (), "invalid_prediction"
    if p.hit_time <= now:
        return (), "past_hit_time"
    max_uncertainty = speculative.get("max_uncertainty_s", .04) if experimental else .04
    if p.hit_time-now > event_cfg.get("max_eta_s", .45) or not 0<=p.uncertainty<=max_uncertainty:
        return (), "outside_horizon_or_uncertain"
    if p.predictor_mode == "particle":
        evidence = particle_eta_evidence(track, now, event_cfg)
        if not evidence.is_usable:
            return (), evidence.reject_reason
        if any(key not in known_keys for key in options):
            return (), "unverified_key_mapping"
        return tuple(options), ""
    max_drift = speculative.get("max_hit_drift_s", event_cfg.get("max_hit_drift_s", .06)) if experimental else event_cfg.get("max_hit_drift_s", .06)
    # Assist may use two consistent hit estimates for ordinary colored bars.
    # Special appearances and the conservative path still require three.
    min_hits = (speculative.get("tap_min_hit_observations",3)
                if experimental and c.appearance in ("cyan_bar","yellow_bar") else 3)
    last_chance = (experimental and speculative.get('tap_last_chance_single_fit',False) and
                   c.appearance in ('cyan_bar','yellow_bar') and c.note_type=='unknown' and
                   nearline_y is not None and track.history and track.history[-1][1]>=nearline_y and
                   len(track.hit_history)==1 and p.hit_time-now<=.05 and p.uncertainty<=.02)
    if not last_chance and (len(track.hit_history) < min_hits or
                            np.ptp(track.hit_history[-min_hits:]) > max_drift):
        return (), "unstable_hit_time"
    if any(key not in known_keys for key in options):
        return (), "unverified_key_mapping"
    return tuple(options), ""


def track_decision(track,now,known_keys,event_cfg):
    """Legacy singleton-only path unless an explicit range rule is configured."""
    return track_options(track,now,known_keys,event_cfg)


class LiveEngine:
    def __init__(self, config, geometry, scheduler, clock=time.perf_counter, detector=detect):
        self.config, self.geometry, self.scheduler, self.clock = config, geometry, scheduler, clock
        self.detector = detector
        self.geometry_hash = geometry_hash(geometry.document)
        self.known_keys = verified_keys(config, self.geometry_hash)
        self.tap_rule = AnyCoveredKeyRule.from_config(config,self.geometry_hash)
        self.speculative = config.get("live",{}).get("speculative_taps",{}) if self.tap_rule else {}
        if self.speculative.get("enabled"):
            limit = float(self.speculative.get("max_uncertainty_s",.04))
            drift = float(self.speculative.get("max_hit_drift_s",.06))
            min_hits = self.speculative.get("tap_min_hit_observations",3)
            drift_window = self.speculative.get("tap_hit_drift_window",5)
            if not (.04 <= limit <= .12 and .06 <= drift <= .2 and
                    type(min_hits) is int and min_hits in (2,3) and
                    type(drift_window) is int and drift_window in (3,4,5) and
                    type(self.speculative.get('tap_last_chance_single_fit',False)) is bool):
                raise ValueError("Speculative Tap uncertainty/drift/observation limits are outside supported range")
        self.input_advance_px = float(config.get("live",{}).get("input_advance_px",0)) if self.tap_rule else 0.0
        judgment_cfg = config.get("live", {}).get("judgment_calibration_v2", {})
        self.judgment_time = JudgmentTimeEstimator(
            enabled=judgment_cfg.get("enabled", False),
            mode=judgment_cfg.get("mode", "shadow"),
            offset_ms=judgment_cfg.get("offset_ms", 0),
            input_latency_ms=judgment_cfg.get("input_latency_ms", 0),
            min_samples=judgment_cfg.get("min_samples", 20))
        self.pixel_scale_y = geometry.reference_resolution[1]/404
        self.pixel_scale_x = geometry.reference_resolution[0]/720
        if not (math.isfinite(self.input_advance_px) and 0 <= self.input_advance_px <= 40*self.pixel_scale_y):
            raise ValueError("Assist input advance is outside the supported reference-scaled range")
        # This is a control timing target, not a change to measured geometry.
        self.trigger_y = geometry.hit_y-self.input_advance_px
        # A confirmed, already scheduled head may vanish briefly behind score
        # effects before it reaches the input line. Keep only its existing
        # deadline; never create or retarget an action from a lost track.
        self.dropout_grace_s = (float(config.get("live",{}).get("dropout_grace_ms",0))/1000
                                if self.tap_rule else 0.0)
        self.dropout_min_y = float(config.get("live",{}).get("dropout_min_y",265*self.pixel_scale_y))
        if not (math.isfinite(self.dropout_grace_s) and 0<=self.dropout_grace_s<=.2 and
                math.isfinite(self.dropout_min_y) and 230*self.pixel_scale_y<=self.dropout_min_y<self.trigger_y):
            raise ValueError("Assist dropout grace must be 0-200 ms with a valid near-line entry")
        # Only already scheduled, confirmed cyan/yellow heads get the longer
        # retention used when their edge track fragments before the hit line.
        self.tap_dropout_grace_s = (float(config.get('live',{}).get('tap_dropout_grace_ms',
                                            self.dropout_grace_s*1000))/1000
                                    if self.speculative.get('enabled') else self.dropout_grace_s)
        self.tap_dropout_min_y = (float(config.get('live',{}).get('tap_dropout_min_y',
                                               self.dropout_min_y))
                                  if self.speculative.get('enabled') else self.dropout_min_y)
        if not (math.isfinite(self.tap_dropout_grace_s) and
                self.dropout_grace_s<=self.tap_dropout_grace_s<=.3 and
                math.isfinite(self.tap_dropout_min_y) and
                230*self.pixel_scale_y<=self.tap_dropout_min_y<self.trigger_y):
            raise ValueError("Assist Tap dropout retention must be at most 300 ms inside the calibrated playfield")
        hold_cfg = config.get('live',{}).get('hold_visual',{}) if self.tap_rule else {}
        self.hold_enabled = bool(hold_cfg.get('enabled',False))
        colors = hold_cfg.get('path_appearances',['green_candidate'])
        if (not isinstance(colors,list) or not colors or
                any(color not in ('green_candidate','yellow_bar') for color in colors)):
            raise ValueError('Visual Hold paths must use supported green/yellow appearances')
        self.hold_path_colors = set(colors)
        if self.hold_enabled and (hold_cfg.get('control_rule')!='hold_start_key_to_visible_tail' or
                                  hold_cfg.get('confirmed_by')!='user' or
                                  not str(hold_cfg.get('confirmation','')).strip()):
            raise ValueError('Visual Hold input needs the user-confirmed start-key rule')
        self.hold_path_px = int(hold_cfg.get('min_path_px',40*self.pixel_scale_y))
        self.hold_release_gap_s = float(hold_cfg.get('release_gap_ms',120))/1000
        if not (32*self.pixel_scale_y<=self.hold_path_px<=100*self.pixel_scale_y and .06<=self.hold_release_gap_s<=.25):
            raise ValueError('Hold path and release limits are outside supported range')
        self.hold_ids = set()
        hold_tracker_cfg = config.get("live", {}).get("hold_tracker_v2", {})
        self.hold_tracker_v2 = HoldTracker(
            min_path_px=self.hold_path_px,
            min_head_observations=hold_tracker_cfg.get("min_head_observations", 2),
            max_gap_s=max(.08, self.hold_release_gap_s),
            dropout_grace_ms=hold_tracker_cfg.get("dropout_grace_ms", 120)) if hold_tracker_cfg.get("enabled", False) else None
        self.hold_colors = {}
        self.hold_watch = {}
        self.hold_spans = {}
        if self.tap_rule:
            self.known_keys = self.tap_rule.allowed_keys
        self.last_decisions = {}
        self.simple_decision_reasons = {}
        self.occlusion_commits = {}
        self.dropout_commits = {}
        self.edge_fragment_commits = set()
        self.tap_edge_evidence = {}
        self.provisional_tap_losses = {}
        # A reidentified ID is consumed for this session so the same physical
        # head cannot be scheduled again after its original action fires.
        self.reidentified_tracker_ids = {}
        self.judgment_bar_top = geometry.document.get('live_measurement',{}).get('judgment_bar_top_y')
        self.gate = GameplayGate(config.get("gameplay"), geometry.reference_resolution)
        tracker_cfg = {**config.get("tracker", {}), "key_map": config["key_map"]}
        # Advancing input changes the prediction target, not the physical end
        # of the visible note. Keep tracking until the measured judgment row.
        tracker_cfg['completion_y'] = geometry.hit_y
        predictor_cfg = dict(config.get("predictor",{}))
        particle_cfg = dict(predictor_cfg.get("particle", {}))
        self.tap_identity_cfg = dict(particle_cfg.get("identity_continuity",{}))
        self.tap_identity_cfg = {"enabled":True,"confirmed_tap_only":True,
            "allow_degraded_unknown":True,"max_degraded_ms":90,
            "reject_competing_heads":True,"preserve_frozen_key":True,
            "preserve_original_deadline":True,**self.tap_identity_cfg}
        max_degraded=float(self.tap_identity_cfg["max_degraded_ms"])
        if (self.tap_identity_cfg["confirmed_tap_only"] is not True or
                self.tap_identity_cfg["preserve_frozen_key"] is not True or
                self.tap_identity_cfg["preserve_original_deadline"] is not True or
                not 0<max_degraded<=min(90,float(particle_cfg.get("max_coast_ms",90)))):
            raise ValueError("Tap identity continuity must remain confirmed-only and within the 90ms PF coast limit")
        if self.speculative.get("enabled"):
            tracker_cfg["max_hit_drift_s"] = self.speculative["max_hit_drift_s"]
            tracker_cfg["tap_hit_drift_window"] = self.speculative.get("tap_hit_drift_window",5)
            predictor_cfg["max_uncertainty_s"] = self.speculative["max_uncertainty_s"]
        # The legacy tracker remains only as the visual Hold path.
        hold_predictor_mode = "legacy"
        self.tracker = Tracker(tracker_cfg,self.trigger_y,predictor_cfg,
                               predictor_mode=hold_predictor_mode,particle_cfg=particle_cfg,
                               physical_hit_y=geometry.hit_y)
        self.collector = EventCollector({**config.get("events", {}), "reference_height": geometry.reference_resolution[1]})
        self.diagnostic_sink = None
        self._identity_transition_offsets = {}
        self._emitted_identity_transition_ids = set()
        self._scheduler_trace_last = {}
        self.tap_decision_context = {}
        self._tap_decision_trace_last = {}
        self._tap_track_state = {}
        # Near-target commitment must move with the trigger when input is
        # advanced; otherwise the track finishes before reaching the corridor.
        self.commit_entry_y = (min(self.judgment_bar_top,self.trigger_y-12.5*self.pixel_scale_y)
                               if self.judgment_bar_top is not None else None)
        self.dc = {**config.get("detector", {}), "reference_resolution": geometry.reference_resolution}
        self.session_id = uuid.uuid4().hex[:12]
        self.simple_core = None
        self.simple_tracks = []
        self.simple_core = SimpleAssistCore(session_id=self.session_id,
            tracker_cfg={**tracker_cfg, "max_eta_s": config.get("events", {}).get("max_eta_s", .45)},
            particle_cfg=particle_cfg, hit_y=self.trigger_y,
            event_cfg=config.get("events", {}),
            min_y=float(config.get("events", {}).get("min_y",190*self.pixel_scale_y)),
            known_keys=self.known_keys,
            timing_cfg=config.get("live", {}).get("tap_deadline_amend", {}))
        self.simple_core.tracker.next_id = 1_000_000
        self.seen_ids, self.input_eligible_ids = set(), {}
        self.track_births, self.recycled_ids = {}, set()
        self.last_capture = -math.inf
        self.latencies, self.capture_times, self.process_times = deque(maxlen=600), deque(maxlen=120), deque(maxlen=120)
        self.stale, self.events, self.abstentions, self.frames = 0, 0, 0, 0
        self.stage_times = {}

    def invalidate(self, reason="invalid_frame"):
        self.scheduler.disarm(reason)
        self.edge_fragment_commits.clear()
        self.tap_edge_evidence.clear()
        self.provisional_tap_losses.clear()
        self.gate.streak, self.gate.state = 0, "UNCERTAIN"
        # Do not recycle IDs on resuming or lose emergency de-duplication state.
        self.tracker.update([], self.last_capture, playing=False)
        self.tracker.finished.clear()
        self.simple_core.tracker.update([], self.last_capture, playing=False)
        self.simple_tracks = []
        if self.hold_tracker_v2:
            self.hold_tracker_v2.reset()

    def _commit_still_valid(self,tr,commit,now):
        """A committed deadline uses its validated fit, not a noisy new fit.

        Current visual evidence must still cover the chosen key, or be a
        cyan/yellow fragment of this already validated head, in the measured
        judgment corridor. Global freshness/focus is checked by
        the caller and again by the scheduler immediately before key-down.
        """
        intent,generation,expires,original_span,*source = commit
        c = tr.candidate
        original_appearance = source[0] if source else "cyan_bar"
        original_box = source[1] if len(source)>1 else None
        original_type = source[2] if len(source)>2 else None
        visual_match = (c.appearance in ('cyan_bar','yellow_bar') if original_appearance in
                        ('cyan_bar','yellow_bar') else
                        bool(self.speculative.get('enabled') and c.appearance==original_appearance))
        if (generation!=self.scheduler.arm_generation or now>expires or
                tr.status in ('rejected','completed') or self.judgment_bar_top is None or
                c.note_type not in ('tap','unknown') or
                not visual_match or (c.suspected_overlap and not self.speculative.get('enabled'))):
            return False
        if not (math.isfinite(c.u_min) and math.isfinite(c.u_max) and 0<=c.u_min<c.u_max<=1):
            return False
        lane = self.config['key_map'].index(intent.keys[0])
        jitter = self.config.get('tracker',{}).get('backward_jitter_px',3.5)
        key_covered = (intent.keys[0] in c.candidate_keys and
                       min(c.u_max,(lane+1)/6)>max(c.u_min,lane/6))
        overlap = max(0.,min(c.u_max,original_span[1])-max(c.u_min,original_span[0]))
        partial_head = (c.note_type=='unknown' and
                        overlap>=.5*min(c.u_max-c.u_min,original_span[1]-original_span[0]))
        fragment_in_original_body = False
        if (overlap>=.5*min(c.u_max-c.u_min,original_span[1]-original_span[0]) and
                original_type=='tap' and original_box is not None and
                original_appearance in ('cyan_bar','yellow_bar')):
            _,old_y,_,old_h = original_box
            _,y,_,height = c.bbox
            fragment_in_original_body = (
                height<=max(4*self.pixel_scale_y,old_h*.5) and y>=old_y-jitter and y+height<=old_y+old_h+jitter and
                c.u_max-c.u_min<=1.25*(original_span[1]-original_span[0]))
        # A cyan/yellow edge fragment does not establish a NEW Tap. It may only
        # maintain the already validated key/deadline of this committed Tap.
        return ((key_covered or partial_head or fragment_in_original_body) and
                (c.bbox[1]+c.bbox[3]>=self.commit_entry_y-jitter or fragment_in_original_body) and
                tr.history[-1][1]<=self.geometry.hit_y)

    def _dropout_still_valid(self, event_id, now, tr=None):
        commit = self.dropout_commits.get(event_id)
        if not commit or event_id not in self.scheduler.pending:
            return False
        intent, generation, last_seen, original_span, original_appearance, original_y, original_type = commit
        ordinary_tap = (original_appearance in ('cyan_bar','yellow_bar') and
                        original_type=='tap' and intent.note_type=='tap')
        grace = self.tap_dropout_grace_s if ordinary_tap else self.dropout_grace_s
        minimum_y = self.tap_dropout_min_y if ordinary_tap else self.dropout_min_y
        if (generation != self.scheduler.arm_generation or
                self.scheduler.pending[event_id] != intent or
                not 0 <= now-last_seen <= grace or
                now > intent.hit_at+self.scheduler.max_lateness):
            return False
        if tr is not None:
            if tr.status == 'lost' and tr.last_time == last_seen:
                return bool(tr.missed)
            # A single position outlier can be a different edge of the same
            # bar. It may maintain an existing deadline only when its current
            # color, lane, span and near-line position still agree.
            if (tr.status not in ('tentative','lost') or
                    (tr.status == 'tentative' and tr.missed) or
                    (tr.status == 'lost' and not tr.missed) or
                    tr.prediction.reason != 'latest_position_outlier' or
                    tr.last_time <= last_seen):
                return False
            c = tr.candidate
            same_color = (c.appearance == original_appearance or
                          {c.appearance,original_appearance} <= {'cyan_bar','yellow_bar'})
            overlap = max(0.,min(c.u_max,original_span[1])-max(c.u_min,original_span[0]))
            if (not same_color or c.note_type not in ('tap','unknown') or
                    not (math.isfinite(c.u_min) and math.isfinite(c.u_max) and
                         0 <= c.u_min < c.u_max <= 1) or
                    overlap < .5*min(c.u_max-c.u_min,original_span[1]-original_span[0]) or
                    intent.keys[0] not in c.candidate_keys or
                    not minimum_y-4*self.pixel_scale_y <= tr.history[-1][1] <= self.trigger_y+3*self.pixel_scale_y or
                    abs(tr.history[-1][1]-original_y) > 25*self.pixel_scale_y):
                return False
        return True

    def _can_start_provisional_tap_loss(self, tr, intent, now):
        """Only coast an already scheduled ordinary colored Tap at early y."""
        p = tr.prediction
        valid_eta = (p.hit_time is not None and p.eta is not None and p.uncertainty is not None and
                     all(math.isfinite(value) for value in (p.hit_time,p.eta,p.uncertainty)) and
                     p.hit_time > now)
        if (not self.tap_rule or intent.note_type != 'tap' or not tr.was_confirmed or
                tr.status != 'lost' or tr.missed != 1 or tr.kind != 'tap' or
                tr.candidate.appearance not in ('cyan_bar','yellow_bar') or
                intent.keys[0] not in tr.candidate.candidate_keys or
                not valid_eta or not 0 <= now-tr.last_time <= PROVISIONAL_TAP_LOSS_GRACE_S):
            return False
        y = tr.history[-1][1] if tr.history else math.inf
        return 230*self.pixel_scale_y <= y <= 250*self.pixel_scale_y and now < intent.hit_at

    def _edge_fragment_commit(self, tr, event_id, intent, now):
        """Freeze an existing Tap deadline across a matching thin edge fragment.

        This path cannot create an input. It requires a previously scheduled,
        confirmed cyan/yellow Tap and one same-track latest-position outlier
        that still overlaps the validated note body and key lane.
        """
        evidence = self.tap_edge_evidence.get(event_id)
        if not evidence:
            return None
        c = tr.candidate
        if (evidence['intent'] is not intent or
                evidence['generation'] != self.scheduler.arm_generation or
                evidence['first_time'] != tr.first_time or
                intent.note_type != 'tap' or evidence['note_type'] != 'tap' or
                not tr.was_confirmed or tr.status not in ('tentative','lost') or
                tr.prediction.reason != 'latest_position_outlier' or tr.missed > 1 or
                c.note_type not in ('tap','unknown') or
                c.appearance not in ('cyan_bar','yellow_bar') or
                evidence['appearance'] not in ('cyan_bar','yellow_bar') or
                not 0 <= now-evidence['timestamp'] <= .10 or
                now > intent.hit_at+self.scheduler.max_lateness or
                not tr.history):
            return None
        old_span = evidence['span']
        span = (c.u_min,c.u_max)
        if not (math.isfinite(span[0]) and math.isfinite(span[1]) and
                0 <= span[0] < span[1] <= 1):
            return None
        overlap = max(0.,min(span[1],old_span[1])-max(span[0],old_span[0]))
        if overlap < .5*min(span[1]-span[0],old_span[1]-old_span[0]):
            return None
        lane = self.config['key_map'].index(intent.keys[0])
        old_key_overlap = max(0.,min(old_span[1],(lane+1)/6)-max(old_span[0],lane/6))
        if old_key_overlap < .1*(old_span[1]-old_span[0]):
            return None
        _, old_y, _, old_h = evidence['bbox']
        _, y, _, height = c.bbox
        jitter = self.config.get('tracker',{}).get('backward_jitter_px',3.5)
        center_y = tr.history[-1][1]
        if (height > max(4*self.pixel_scale_y,old_h*.5) or
                y < old_y-jitter or y+height > old_y+old_h+jitter or
                abs(center_y-evidence['center_y']) > 25*self.pixel_scale_y or
                not 230*self.pixel_scale_y <= center_y <= self.trigger_y+3*self.pixel_scale_y):
            return None
        return (intent,self.scheduler.arm_generation,
                intent.hit_at+self.scheduler.max_lateness,old_span,
                evidence['appearance'],evidence['bbox'],evidence['note_type'])

    def _edge_fragment_commit_still_valid(self, tr, commit, now):
        """Keep the frozen Tap through same-track fragment recovery/expansion."""
        intent,generation,expires,old_span,old_appearance,_,old_type=commit
        c=tr.candidate
        evidence=self.tap_edge_evidence.get(intent.event_id)
        if (not evidence or generation!=self.scheduler.arm_generation or now>expires or
                evidence['intent'] is not intent or evidence['first_time']!=tr.first_time or
                tr.status in ('rejected','completed') or c.note_type not in ('tap','unknown') or
                old_type!='tap' or intent.note_type!='tap' or
                old_appearance not in ('cyan_bar','yellow_bar') or
                c.appearance not in ('cyan_bar','yellow_bar') or
                not tr.history):
            return False
        span=(c.u_min,c.u_max)
        if not (math.isfinite(span[0]) and math.isfinite(span[1]) and 0<=span[0]<span[1]<=1):
            return False
        overlap=max(0.,min(span[1],old_span[1])-max(span[0],old_span[0]))
        if overlap < .5*min(span[1]-span[0],old_span[1]-old_span[0]):
            return False
        lane=self.config['key_map'].index(intent.keys[0])
        key_overlap=max(0.,min(span[1],(lane+1)/6)-max(span[0],lane/6))
        center_y=tr.history[-1][1]
        return (key_overlap>0 and
                abs(center_y-evidence['center_y'])<=25*self.pixel_scale_y and
                center_y<=self.trigger_y+3*self.pixel_scale_y and
                center_y<=self.geometry.hit_y)

    def _provisional_tap_reconfirmed(self, tr, event_id, coast, now):
        intent = self.scheduler.pending.get(event_id)
        c = tr.candidate
        if (intent is not coast['intent'] or coast['generation'] != self.scheduler.arm_generation or
                now > coast['expires_at'] or now > intent.hit_at+self.scheduler.max_lateness or
                tr.status != 'confirmed' or tr.missed or
                tr.prediction.reason not in ('','outside_lookahead') or
                tr.kind != 'tap' or c.note_type != 'tap' or
                c.appearance not in ('cyan_bar','yellow_bar') or
                intent.keys[0] not in c.candidate_keys or not tr.history or
                tr.history[-1][1] > self.geometry.hit_y):
            return False
        if c.appearance != coast['appearance'] and {c.appearance,coast['appearance']} != {'cyan_bar','yellow_bar'}:
            return False
        span = (c.u_min,c.u_max)
        old = coast['span']
        overlap = max(0.,min(span[1],old[1])-max(span[0],old[0]))
        return (math.isfinite(span[0]) and math.isfinite(span[1]) and
                overlap >= .5*min(span[1]-span[0],old[1]-old[0]))

    def _matches_provisional_reidentification(self, tr, event_id, coast, now):
        """Match a new tracker ID to a coasting, already scheduled Tap.

        This is deliberately local to the old Tap's saved trajectory. It does
        not widen the scheduler's same-key/time de-duplication window or alter
        any prediction/deadline. A match suppresses only the new ID's offer;
        the old ID keeps its original key and deadline under normal gates.
        """
        intent = coast['intent']
        if (event_id == intent.event_id or intent.note_type != 'tap' or
                coast.get('generation') != self.scheduler.arm_generation or
                intent.event_id not in self.scheduler.pending or
                now > intent.hit_at+self.scheduler.max_lateness or
                tr.status != 'confirmed' or tr.missed or tr.kind not in ('tap', 'unknown') or
                tr.candidate.note_type not in ('tap', 'unknown') or
                tr.candidate.appearance not in ('cyan_bar', 'yellow_bar') or
                not tr.history or intent.keys[0] not in tr.candidate.candidate_keys):
            return False
        if tr.candidate.appearance != coast['appearance'] and {
                tr.candidate.appearance, coast['appearance']} != {'cyan_bar', 'yellow_bar'}:
            return False
        span = (tr.candidate.u_min, tr.candidate.u_max)
        old_span = coast['span']
        if not (all(math.isfinite(v) for v in (*span, *old_span)) and
                0 <= span[0] < span[1] <= 1 and 0 <= old_span[0] < old_span[1] <= 1):
            return False
        overlap = max(0., min(span[1], old_span[1])-max(span[0], old_span[0]))
        if overlap < .60*min(span[1]-span[0], old_span[1]-old_span[0]):
            return False
        dt = tr.last_time-coast['last_time']
        if not 0 < dt <= .30:
            return False
        expected_y = coast['center_y'] + max(0., coast['velocity'])*dt
        observed_y = tr.history[-1][1]
        return abs(observed_y-expected_y) <= 18*self.pixel_scale_y

    def _keep_absent_provisional_tap(self, event_id, coast, finished,
                                     present_ids, finished_tracks, finished_past_ids):
        """Keep a frozen Tap only inside its original scheduler deadline."""
        return (event_id not in present_ids and event_id not in finished_tracks and
                event_id not in finished_past_ids and
                self._keep_coasting_provisional_tap(coast,finished))

    def _retain_reidentified_intent(self, event_id, now):
        """Transfer tracking ownership without replacing a scheduled Tap."""
        coast = self.provisional_tap_losses.get(event_id)
        intent = self.scheduler.pending.get(event_id)
        has_replacement = any(owner == event_id for owner in self.reidentified_tracker_ids.values())
        valid = (coast is not None and intent is coast['intent'] and
                 coast['generation'] == self.scheduler.arm_generation and has_replacement and
                 now <= intent.hit_at+self.scheduler.max_lateness)
        if not valid:
            return False
        self.scheduler.resume(event_id)
        self.scheduler._log('reidentified_intent_retained',
                            'replacement_tracker_owns_original_key_and_deadline',intent)
        return True

    def _tap_identity_intent_failures(self, tr, event_id, intent, now, *, state, focused, roi_valid, stale):
        """Return named failed predicates for an existing Tap identity intent."""
        failures = []
        def fail(condition, name):
            if condition:
                failures.append(name)
        fail(not self.tap_identity_cfg.get("enabled"), "IDENTITY_CONTINUITY_DISABLED")
        try:
            origin_track_id=int(event_id.rsplit(":",1)[1])
        except (IndexError,ValueError):
            return ["INVALID_EVENT_ID"]
        max_ms=float(self.tap_identity_cfg["max_degraded_ms"])
        valid_state=tr.identity_state in ("CONFIRMED_TAP","TAP_DEGRADED_OBSERVATION","TAP_COASTING")
        fail(not valid_state, "TRACK_IDENTITY_STATE_NOT_ELIGIBLE")
        fail(tr.identity_state == "TAP_DEGRADED_OBSERVATION" and
             (tr.status != "confirmed" or tr.missed > 0), "TRACKER_NOT_CURRENT_CONFIRMED")
        fail(tr.identity_state == "TAP_COASTING" and tr.status not in ("lost", "completed"),
             "TRACKER_COAST_STATE_INCONSISTENT")
        fail(tr.confirmed_note_type != "tap", "CONFIRMED_TYPE_NOT_TAP")
        fail(not tr.was_confirmed, "TRACK_NEVER_CONFIRMED")
        fail(tr.identity_state == "TAP_IDENTITY_AMBIGUOUS", "ASSOCIATION_AMBIGUOUS")
        fail(intent.note_type != "tap", "INTENT_NOT_TAP")
        fail(event_id not in self.scheduler.pending, "PENDING_INTENT_MISSING")
        fail(event_id in self.scheduler.pending and self.scheduler.pending[event_id] is not intent,
             "PENDING_INTENT_REPLACED")
        fail(origin_track_id not in tr.source_track_ids, "SOURCE_TRACK_ID_MISMATCH")
        fail(not tr.physical_note_uid, "PHYSICAL_UID_MISSING")
        fail(self.input_eligible_ids.get(origin_track_id) != self.scheduler.arm_generation,
             "ARM_GENERATION_MISMATCH")
        fail(self.scheduler.arm_generation <= 0 or not self.scheduler.armed, "ASSIST_DISARMED")
        fail(not intent.keys or (intent.keys[0] not in tr.stable_keys and
             (bool(tr.stable_keys) or tr.selected_key != intent.keys[0])),
             "FROZEN_KEY_NOT_STABLE_OR_PINNED")
        fail(bool(intent.keys) and tr.selected_key is not None and tr.selected_key != intent.keys[0],
             "SELECTED_KEY_CHANGED")
        fail(state != "PLAYING", "GAME_NOT_PLAYING")
        fail(not focused, "FOCUS_LOST")
        fail(not roi_valid, "ROI_INVALID")
        fail(stale, "STALE_FRAME")
        fail(now > intent.hit_at+self.scheduler.max_lateness, "DEADLINE_EXPIRED")
        fail(tr.last_reliable_tap_at is None, "RELIABLE_OBSERVATION_MISSING")
        fail(tr.last_reliable_tap_at is not None and
             not 0 <= now-tr.last_reliable_tap_at <= max_ms/1000,
             "REL_OBSERVATION_AGE_EXCEEDED")
        pf = tr.particle_filter
        fail(pf is None, "PF_MISSING")
        fail(pf is not None and not pf.initialized, "PF_NOT_INITIALIZED")
        if pf is not None and pf.initialized:
            fail(not math.isfinite(pf.ess) or pf.ess < pf.count*float(pf.cfg.get("identity_min_ess_fraction",.1)),
                 "PF_ESS_LOW")
            mass = tr.prediction.valid_crossing_mass
            fail(mass is None or mass < pf.min_crossing_mass, "PF_CROSSING_MASS_LOW")
            fail(tr.prediction.reason == "PF_POSTERIOR_TOO_WIDE", "PF_POSTERIOR_TOO_WIDE")
        fail(event_id in self.hold_ids, "HOLD_INTENT")
        if tr.identity_state=="TAP_DEGRADED_OBSERVATION":
            fail(not self.tap_identity_cfg.get("allow_degraded_unknown"), "DEGRADED_UNKNOWN_DISABLED")
            fail(tr.current_observation_type != "unknown", "CURRENT_TYPE_NOT_UNKNOWN")
            fail(not tr.last_association.get("accepted"), "ASSOCIATION_REJECTED")
            fail(bool(intent.keys) and intent.keys[0] not in tr.candidate.candidate_keys,
                 "FROZEN_KEY_NOT_IN_CURRENT_CANDIDATE")
            fail(tr.candidate.path_bbox is not None or tr.candidate.hold_path_px > 0,
                 "SPECIAL_PATH_FEATURE_PRESENT")
        elif tr.identity_state=="TAP_COASTING":
            fail(tr.missed < 1 and tr.status != "completed", "COAST_STATE_NOT_MISSED")
        return failures

    def _tap_identity_intent_still_valid(self, tr, event_id, intent, now, *,
                                         state, focused, roi_valid, stale):
        """Keep only an existing Tap intent for its original UID/key/deadline."""
        failures = self._tap_identity_intent_failures(tr,event_id,intent,now,
            state=state,focused=focused,roi_valid=roi_valid,stale=stale)
        self._record_scheduler_trace(tr,event_id,intent,now,failures)
        return not failures

    def _record_scheduler_trace(self,tr,event_id,intent,now,failures):
        signature=(tuple(failures),getattr(tr,"identity_state",""),getattr(tr,"status",""))
        if signature != self._scheduler_trace_last.get(event_id):
            self._scheduler_trace_last[event_id]=signature
            self._emit_diagnostic("scheduler_trace",{
                "timestamp":now,"event_id":event_id,"track_id":tr.track_id,
                "physical_note_uid":tr.physical_note_uid,"source_track_ids":"|".join(map(str,tr.source_track_ids)),
                "original_selected_key":intent.keys[0] if intent.keys else "",
                "original_hit_at":intent.hit_at,"tracker_status":tr.status,
                "current_type":tr.current_observation_type,"confirmed_note_type":tr.confirmed_note_type or "",
                "identity_state":tr.identity_state,"measurement_status":tr.prediction.measurement_status,
                "association_reason":tr.last_association.get("reason",""),
                "first_failed_predicate":failures[0] if failures else "NONE",
                "all_failed_predicates":"|".join(failures) if failures else "NONE"})

    def _emit_diagnostic(self, name, row):
        if self.diagnostic_sink is not None:
            self.diagnostic_sink(name,row)

    def _emit_tap_decision(self, tr, event_id, frame, now, stage, result,
                           reason="", retryable=False, *, scheduled=None,
                           final_action="PENDING", final_reason=""):
        p=tr.prediction
        pending=self.scheduler.pending.get(event_id)
        selected_key=tr.selected_key or (pending.keys[0] if pending and pending.keys else "")
        signature=(stage,result,reason,tr.identity_state,tr.status,selected_key,
                   round(p.hit_time*100,0) if p.hit_time is not None else None,
                   bool(pending),self.scheduler.arm_generation)
        if self._tap_decision_trace_last.get(event_id)==signature:
            return
        self._tap_decision_trace_last[event_id]=signature
        pf=getattr(tr,"particle_filter",None)
        cfg=getattr(pf,"cfg",{}) if pf is not None else {}
        count=int(getattr(pf,"count",cfg.get("count",0)) or 0)
        ess_fraction=(p.ess/count if p.ess is not None and count else "")
        evidence=(particle_eta_evidence(tr,now,self.config.get("events",{}))
                  if p.predictor_mode=="particle" else None)
        source=getattr(tr,"last_reliable_tap_candidate",None)
        row={
            "timestamp":now,"source_frame":frame.sequence,"event_id":event_id,
            "track_id":tr.track_id,"physical_note_uid":tr.physical_note_uid,
            "source_track_ids":"|".join(map(str,tr.source_track_ids)),
            "candidate_type":tr.current_observation_type,
            "confirmed_note_type":tr.confirmed_note_type or "",
            "identity_state":tr.identity_state,"track_status":tr.status,
            "missed_frames":tr.missed,"appearance":tr.candidate.appearance,
            "candidate_keys":"|".join(tr.candidate.candidate_keys),
            "stable_keys":"|".join(tr.stable_keys),"selected_key":selected_key,
            "particle_initialized":bool(pf and pf.initialized),
            "particle_measurement_status":p.measurement_status,
            "particle_ess":p.ess if p.ess is not None else "",
            "particle_ess_fraction":ess_fraction,
            "particle_valid_crossing_mass":p.valid_crossing_mass if p.valid_crossing_mass is not None else "",
            "particle_coast_ms":p.coast_ms,
            "particle_real_observation_count":p.real_observation_count if p.real_observation_count is not None else "",
            "particle_measurement_age_ms":evidence.measurement_age_ms if evidence and evidence.measurement_age_ms is not None else "",
            "particle_eta_usable":evidence.is_usable if evidence else "",
            "particle_eta_reject_reason":evidence.reject_reason if evidence else "",
            "eta_p10":p.eta_p10 if p.eta_p10 is not None else "",
            "eta_p50":p.eta_p50 if p.eta_p50 is not None else "",
            "eta_p90":p.eta_p90 if p.eta_p90 is not None else "",
            "predicted_hit_time":p.hit_time if p.hit_time is not None else "",
            "hit_history_count":len(tr.hit_history),
            "hit_history_drift_ms":(1000*float(np.ptp(tr.hit_history[-3:]))
                                     if len(tr.hit_history)>=2 else ""),
            "decision_stage":stage,"decision_result":result,
            "reject_reason":reason,"is_retryable":bool(retryable),
            "pending_intent_exists":bool(pending),
            "original_hit_at":pending.hit_at if pending else (p.hit_time if scheduled else ""),
            "original_key":pending.keys[0] if pending and pending.keys else selected_key,
            "arm_generation":self.scheduler.arm_generation,
            "eventually_scheduled":bool(scheduled) if scheduled is not None else bool(pending),
            "eventually_key_down":False,"eventually_canceled":False,
            "final_action":final_action,"final_reason":final_reason or reason,
            "reliable_candidate_appearance":source.appearance if source else "",
            "reliable_candidate_span":(f"{source.u_min:.6f}:{source.u_max:.6f}" if source else ""),
            "current_candidate_span":f"{tr.candidate.u_min:.6f}:{tr.candidate.u_max:.6f}",
            "original_appearance":"","original_span":"","original_position_y":"",
            "current_position_y":(tr.history[-1][1] if tr.history else ""),
            "particle_predicted_position_y":p.fitted_y if p.fitted_y is not None else "",
            "position_compatible":"","span_compatible":"","appearance_compatible":"",
            "identity_compatible":not bool(p.identity_ambiguous or tr.identity_state=="TAP_IDENTITY_AMBIGUOUS"),
            "competing_candidate_exists":"","remaining_to_hit_ms":
                (1000*(p.hit_time-now) if p.hit_time is not None else ""),
        }
        self.tap_decision_context[event_id]=row
        self._emit_diagnostic("tap_decision",row)

    def record_scheduler_action(self, action):
        event_id=action.get("event_id")
        self.simple_core.record_scheduler_action(action)
        if not event_id or event_id not in self.tap_decision_context:
            return
        row=dict(self.tap_decision_context[event_id])
        kind=action.get("action","")
        mapping={"key_down":("KEY_DOWN_SENT",True,False),
                 "canceled":("PENDING_CANCELED",False,True),
                 "abstain":("PENDING_EXPIRED",False,True),
                 "commit_retained":("PENDING_RETAINED",False,False),
                 "dropout_retained":("PENDING_RETAINED",False,False),
                 "tap_identity_continuity_retained":("PENDING_RETAINED",False,False),
                 "tap_identity_handoff_retained":("PENDING_RETAINED",False,False),
                 "provisional_loss_retained":("PENDING_RETAINED",False,False),
                 "provisional_loss_resumed":("PENDING_RETAINED",False,False),
                 "reidentified_intent_retained":("PENDING_RETAINED",False,False)}
        if kind not in mapping:
            return
        stage,down,canceled=mapping[kind]
        row.update(timestamp=action.get("timestamp",row["timestamp"]),
                   decision_stage=stage,decision_result=stage,
                   eventually_key_down=down,eventually_canceled=canceled,
                   final_action=kind.upper(),final_reason=action.get("reason", ""))
        if stage=="PENDING_RETAINED":
            row["eventually_scheduled"]=True
            row["pending_intent_exists"]=True
        self.tap_decision_context[event_id]=row
        self._emit_diagnostic("tap_decision",row)

    def _keep_coasting_provisional_tap(self, coast, finished):
        return (coast['generation'] == self.scheduler.arm_generation and
                finished <= coast['intent'].hit_at+self.scheduler.max_lateness)

    def _update_held_holds(self, work, now):
        if not self.hold_enabled:
            return
        runs_by_color = {}
        current = set()
        for key, (_, intent) in list(self.scheduler.held.items()):
            if intent.note_type != 'hold':
                continue
            appearance = intent.path_appearance or 'green_candidate'
            if appearance not in runs_by_color:
                runs_by_color[appearance] = path_runs(work,self.geometry,self.trigger_y-6.5*self.pixel_scale_y,appearance)
            current.add(intent.event_id)
            watch = self.hold_watch.setdefault(intent.event_id,
                        {'u':intent.path_u,'start':now,'last_visible':now})
            run = nearest_run(runs_by_color[appearance],watch['u'],.12)
            if run is not None:
                watch['u'] = min(max(watch['u'],run[0]),run[1])
                watch['last_visible'] = now
            elif (now-watch['last_visible'] >= self.hold_release_gap_s and
                  now-watch['start'] >= self.hold_release_gap_s):
                color = 'yellow' if appearance=='yellow_bar' else 'green'
                self.scheduler.release_hold(intent.event_id,f'{color}_tail_left_judgment_row')
        self.hold_watch = {event_id:watch for event_id,watch in self.hold_watch.items()
                           if event_id in current and any(intent.event_id==event_id
                           for _,intent in self.scheduler.held.values())}

    def process(self, frame, focused=True, roi_valid=True):
        wall_begin = time.perf_counter()
        measured = dict.fromkeys(("normalization","state_detector","note_detector","tracking","prediction",
                                  "unknown_association","tracker_matching","diagnostic_write","decision"),0.0)
        started = self.clock()
        if not (math.isfinite(frame.captured_at) and math.isfinite(frame.acquired_at) and
                frame.acquired_at >= frame.captured_at and frame.captured_at > self.last_capture):
            self.invalidate("invalid_or_nonmonotonic_capture_clock")
            raise ValueError("Capture timestamps must be finite and strictly monotonic")
        self.last_capture = frame.captured_at
        self.capture_times.append(frame.captured_at)
        self.frames += 1
        age = started-frame.captured_at
        stale = age < 0 or age > self.scheduler.max_age
        if not stale and focused and roi_valid:
            # Normalization and the state gate are part of checking this fresh
            # capture. Announce it before either can outlast the old decision.
            # This only pauses key-down; the state gate still validates input.
            self.scheduler.begin_decision(frame.captured_at)
        phase = time.perf_counter()
        work = normalize_frame(frame.image, self.geometry.reference_resolution)
        measured["normalization"] = time.perf_counter()-phase
        if stale or not focused or not roi_valid:
            self.invalidate("stale_capture" if stale else "focus_or_roi_lost")
            state, tracks, candidates = ("STALE" if stale else "ROI_BLOCKED" if not roi_valid else "FOCUS_LOST"), [], []
        else:
            phase = time.perf_counter()
            state = self.gate.update(work)
            measured["state_detector"] = time.perf_counter()-phase
            phase = time.perf_counter()
            candidates = self.detector(work, self.geometry, self.config["key_map"], self.dc) if state == "PLAYING" else []
            measured["note_detector"] = time.perf_counter()-phase
            prediction_before = self.tracker.elapsed
            phase = time.perf_counter()
            simple_candidates = [c for c in candidates if is_simple_tap(c)]
            hold_candidates = []
            if self.hold_enabled and state == "PLAYING":
                raw_holds = [c for c in candidates if c.appearance in self.hold_path_colors and
                             (c.hold_path_px > 0 or c.path_bbox is not None)]
                hold_candidates = (self.hold_tracker_v2.observe(raw_holds, frame.captured_at)
                                   if self.hold_tracker_v2 else
                                   [c for c in raw_holds if c.hold_path_px >= self.hold_path_px])
            simple_started = time.perf_counter()
            self.simple_tracks = self.simple_core.tracker.update(
                simple_candidates, frame.captured_at, playing=state == "PLAYING")
            simple_elapsed = time.perf_counter() - simple_started
            tracks = self.tracker.update(hold_candidates, frame.captured_at,
                                         playing=state == "PLAYING")
            measured["prediction"] = self.tracker.elapsed-prediction_before
            measured["tracking"] = max(0.0, time.perf_counter()-phase-
                measured["prediction"]-simple_elapsed)
            measured["simple_core"] = simple_elapsed
            measured["unknown_association"] = self.tracker.stage_times.get("unknown_association_s",0.0)
            measured["tracker_matching"] = max(0.0,
                self.tracker.stage_times.get("matching_s",0.0)-measured["prediction"])
            diagnostic_started=time.perf_counter()
            for audit in self.tracker.last_unknown_association_audit:
                self._emit_diagnostic("unknown_association",{"source_frame":frame.sequence,**audit})
            for tracked in (*tracks,*self.tracker.finished):
                for transition in getattr(tracked,"identity_transitions",[]):
                    transition_id=(tracked.physical_note_uid,transition.get("timestamp"),transition.get("to_state"))
                    if transition_id not in self._emitted_identity_transition_ids:
                        self._emitted_identity_transition_ids.add(transition_id)
                        self._emit_diagnostic("identity_transition",{"source_frame":frame.sequence,**transition})
            measured["diagnostic_write"] = time.perf_counter()-diagnostic_started
        finished = self.clock()
        latency = finished-frame.captured_at
        if latency > self.scheduler.max_age and not stale:
            stale = True
            self.invalidate("frame_expired_during_processing")
            state, tracks = "STALE", []
            self.simple_tracks = []
        created = []
        active_events = set()
        phase = time.perf_counter()
        # Publish fresh context and withdraw invalid intents atomically. The
        # scheduler must not fire an old intent between these two operations.
        with self.scheduler.lock:
            self.scheduler.update_context(frame.captured_at, state, focused, roi_valid and not stale)
            if state=='PLAYING' and focused and roi_valid and not stale:
                self._update_held_holds(work,finished)
            ready = []
            retained = {}
            reidentified = {}
            retained_reidentified_events = set()
            present_ids = set()
            for tr in tracks:
                parent_id = getattr(tr, "reidentified_from_id", None)
                if parent_id is None:
                    continue
                old_event_id = f"{self.session_id}:{parent_id}"
                if (old_event_id in self.scheduler.pending or
                        old_event_id in self.provisional_tap_losses):
                    self.reidentified_tracker_ids[tr.track_id] = old_event_id
                    self.scheduler._log("track_reidentified",
                        f"particle_state_handoff;physical_note_uid={tr.physical_note_uid};source_track_ids={tr.source_track_ids}",
                        self.scheduler.pending.get(old_event_id))
            finished_tracks = {f"{self.session_id}:{tr.track_id}":tr for tr in self.tracker.finished}
            finished_past_ids = {event_id for event_id,tr in finished_tracks.items()
                                 if tr.reason == 'past_hit_line'}
            for detected_track in tracks:
                detected_event=f"{self.session_id}:{detected_track.track_id}"
                previous=self._tap_track_state.get(detected_track.track_id)
                current=(detected_track.status,detected_track.identity_state)
                if previous is None:
                    self._emit_tap_decision(detected_track,detected_event,frame,finished,
                        "DETECTION_ACCEPTED","DETECTION_ACCEPTED",scheduled=False)
                    state_stage="TRACK_CREATED"
                elif previous!=current:
                    state_stage=("TRACK_CONFIRMED" if current[0]=="confirmed" else
                                 "TRACK_IDENTITY_AMBIGUOUS" if current[1]=="TAP_IDENTITY_AMBIGUOUS" else
                                 "TRACK_TEMPORARILY_LOST" if current[0]=="lost" else "TRACK_STATE_CHANGED")
                else:
                    state_stage=""
                self._tap_track_state[detected_track.track_id]=current
                if state_stage:
                    self._emit_tap_decision(detected_track,detected_event,frame,finished,
                        state_stage,state_stage,scheduled=detected_event in self.scheduler.pending)
            for tr in tracks:
                event_id = f"{self.session_id}:{tr.track_id}"
                present_ids.add(event_id)
                birth = self.track_births.setdefault(tr.track_id, tr.first_time)
                if birth != tr.first_time:
                    self.recycled_ids.add(tr.track_id)
                if tr.track_id in self.recycled_ids:
                    self.scheduler.withdraw(event_id, "recycled_track_id")
                    continue
                coast = self.provisional_tap_losses.get(event_id)
                pending = self.scheduler.pending.get(event_id)
                if (pending and tr.confirmed_note_type=="tap" and tr.selected_key is None and
                        pending.note_type=="tap" and pending.keys[0] in tr.stable_keys):
                    tr.selected_key=pending.keys[0]
                if (pending and tr.status == 'confirmed' and not tr.missed and
                        pending.note_type == 'tap' and tr.candidate.note_type == 'tap' and
                        tr.candidate.appearance in ('cyan_bar','yellow_bar') and tr.history):
                    self.tap_edge_evidence[event_id] = {
                        'intent':pending,'generation':self.scheduler.arm_generation,
                        'first_time':tr.first_time,'timestamp':tr.last_time,
                        'span':(tr.candidate.u_min,tr.candidate.u_max),
                        'appearance':tr.candidate.appearance,'bbox':tr.candidate.bbox,
                        'note_type':tr.candidate.note_type,'center_y':tr.history[-1][1],
                    }
                if coast:
                    if self._provisional_tap_reconfirmed(tr,event_id,coast,frame.captured_at):
                        self.provisional_tap_losses.pop(event_id,None)
                        self.scheduler.resume(event_id)
                        active_events.add(event_id)
                        retained[tr.track_id] = coast['intent'].keys,""
                        self.scheduler._log('provisional_loss_resumed',
                                            'same_track_reconfirmed_original_key_and_deadline',
                                            coast['intent'])
                        continue
                    if (pending is coast['intent'] and
                            self._keep_coasting_provisional_tap(coast,finished)):
                        # Once a confirmed Tap has an original key/deadline,
                        # temporary tracker loss must not erase that action.
                        # Resume it under the scheduler's normal freshness,
                        # focus and PLAYING checks; never infer a new key/time.
                        self.scheduler.resume(event_id)
                        active_events.add(event_id)
                        retained[tr.track_id] = coast['intent'].keys,""
                        self.scheduler._log('provisional_loss_retained',
                                            'same_track_missing_original_key_and_deadline',
                                            coast['intent'])
                        continue
                    self.provisional_tap_losses.pop(event_id,None)
                    if pending is coast['intent']:
                        self.scheduler.resume(event_id)
                    continue
                if (pending and tr.identity_state in ("TAP_DEGRADED_OBSERVATION","TAP_COASTING") and
                        self._tap_identity_intent_still_valid(tr,event_id,pending,finished,
                            state=state,focused=focused,roi_valid=roi_valid,stale=stale)):
                    self.scheduler.resume(event_id)
                    active_events.add(event_id)
                    retained[tr.track_id]=(pending.keys,"")
                    self.scheduler._log("tap_identity_continuity_retained",
                        f"{tr.identity_state};uid={tr.physical_note_uid};original_hit_at={pending.hit_at:.6f};"
                        f"key={pending.keys[0]};measurement={tr.prediction.measurement_status}",pending)
                    continue
                if tr.track_id in self.reidentified_tracker_ids:
                    old_event_id = self.reidentified_tracker_ids[tr.track_id]
                    reidentified[tr.track_id] = old_event_id
                    old_intent=self.scheduler.pending.get(old_event_id)
                    if (old_intent and self._tap_identity_intent_still_valid(
                            tr,old_event_id,old_intent,finished,state=state,focused=focused,
                            roi_valid=roi_valid,stale=stale)):
                        self.scheduler.consumed.add(event_id)
                        self.scheduler.resume(old_event_id)
                        active_events.add(old_event_id)
                        retained[tr.track_id]=(old_intent.keys,"")
                        self.scheduler._log("tap_identity_handoff_retained",
                            f"uid={tr.physical_note_uid};source_ids={tr.source_track_ids};"
                            f"original_hit_at={old_intent.hit_at:.6f};key={old_intent.keys[0]}",old_intent)
                        continue
                    if (old_event_id not in retained_reidentified_events and
                            self._retain_reidentified_intent(old_event_id,finished)):
                        self.scheduler.consumed.add(event_id)
                        active_events.add(old_event_id)
                        retained_reidentified_events.add(old_event_id)
                # A fragmented/recreated ID can still be the same physical
                # head. Keep the old pending intent and suppress this new ID
                # only when color, selected-lane coverage, span, and projected
                # vertical position all match the saved trajectory.
                if (tr.track_id not in reidentified and state == 'PLAYING' and
                        focused and roi_valid and not stale):
                    for old_event_id, old_coast in self.provisional_tap_losses.items():
                        if self._matches_provisional_reidentification(
                                tr, event_id, old_coast, finished):
                            reidentified[tr.track_id] = old_event_id
                            self.reidentified_tracker_ids[tr.track_id] = old_event_id
                            self.scheduler.consumed.add(event_id)
                            old_intent = old_coast['intent']
                            self.scheduler.resume(old_event_id)
                            active_events.add(old_event_id)
                            self.scheduler._log('track_reidentified',
                                f'same_physical_tap_keep_old_key_and_deadline;new_track_id={tr.track_id}',
                                old_intent)
                            break
                if pending and self._can_start_provisional_tap_loss(tr,pending,finished):
                    expires_at = min(tr.last_time+PROVISIONAL_TAP_LOSS_GRACE_S,
                                     pending.hit_at+self.scheduler.max_lateness)
                    if frame.captured_at <= expires_at:
                        self.provisional_tap_losses[event_id] = {
                            'intent':pending, 'generation':self.scheduler.arm_generation,
                            'expires_at':expires_at,
                            'span':(tr.candidate.u_min,tr.candidate.u_max),
                            'appearance':tr.candidate.appearance,
                            'last_time':tr.last_time,
                            'center_y':tr.history[-1][1],
                            'velocity':(tr.prediction.velocity if
                                        tr.prediction.velocity is not None and
                                        math.isfinite(tr.prediction.velocity) else 0.0),
                        }
                        self.scheduler.resume(event_id)
                        active_events.add(event_id)
                        retained[tr.track_id] = pending.keys,""
                        self.scheduler._log('provisional_loss_started',
                                            f'early_confirmed_tap;grace_ms='
                                            f'{max(0.,(expires_at-frame.captured_at)*1000):.1f}',pending)
                        continue
                commit = self.occlusion_commits.get(event_id)
                if pending and not commit:
                    edge_commit = self._edge_fragment_commit(tr,event_id,pending,frame.captured_at)
                    if edge_commit:
                        self.occlusion_commits[event_id] = edge_commit
                        self.edge_fragment_commits.add(event_id)
                        commit = edge_commit
                        self.scheduler._log('edge_fragment_commit',
                                            'same_confirmed_tap_latest_position_outlier',pending)
                if commit and event_id in self.scheduler.pending:
                    still_valid = (self._edge_fragment_commit_still_valid(tr,commit,frame.captured_at)
                                   if event_id in self.edge_fragment_commits else
                                   self._commit_still_valid(tr,commit,finished))
                    if (still_valid and state=='PLAYING' and
                            focused and roi_valid and not stale):
                        active_events.add(event_id)
                        retained[tr.track_id] = commit[0].keys,""
                        if tr.status!='confirmed' or tr.prediction.reason:
                            self.scheduler._log('commit_retained',f'{tr.status}:{tr.prediction.reason}',commit[0])
                    else:
                        c=tr.candidate
                        failures=[]
                        if tr.status!="confirmed": failures.append("TRACKER_NOT_CURRENT_CONFIRMED")
                        if tr.missed: failures.append("TRACK_MISSED")
                        if tr.prediction.reason: failures.append(f"PREDICTION_{tr.prediction.reason.upper()}")
                        if state!="PLAYING": failures.append("GAME_NOT_PLAYING")
                        if not focused: failures.append("FOCUS_LOST")
                        if not roi_valid: failures.append("ROI_INVALID")
                        if stale: failures.append("STALE_FRAME")
                        self._record_scheduler_trace(tr,event_id,commit[0],finished,failures or ["COMMIT_OBSERVATION_CHANGED"])
                        detail = (f'{tr.status}:{tr.prediction.reason};missed={tr.missed};y={tr.history[-1][1]:.1f};'
                                  f'type={c.note_type};appearance={c.appearance};keys={"|".join(c.candidate_keys)};'
                                  f'bbox={c.bbox};span={c.u_min:.4f}:{c.u_max:.4f}')
                        original_span=commit[3]
                        original_appearance=commit[4] if len(commit)>4 else "cyan_bar"
                        original_box=commit[5] if len(commit)>5 else None
                        original_y=(original_box[1]+original_box[3]/2 if original_box else "")
                        overlap=max(0.,min(c.u_max,original_span[1])-max(c.u_min,original_span[0]))
                        span_ratio=overlap/max(1e-9,min(c.u_max-c.u_min,original_span[1]-original_span[0]))
                        appearance_compatible=(c.appearance in ("cyan_bar","yellow_bar")
                            if original_appearance in ("cyan_bar","yellow_bar") else
                            bool(self.speculative.get("enabled") and c.appearance==original_appearance))
                        cy=c.bbox[1]+c.bbox[3]/2
                        competing=any(other is not c and
                            set(other.candidate_keys).intersection(c.candidate_keys) and
                            abs((other.bbox[1]+other.bbox[3]/2)-cy)<=26
                            for other in candidates)
                        evidence_row=dict(self.tap_decision_context.get(event_id,{}),
                            timestamp=finished,source_frame=frame.sequence,
                            decision_stage="COMMIT_VALIDATION",decision_result="COMMIT_REJECTED",
                            reject_reason="committed_observation_changed",final_action="CANCELED",
                            final_reason="committed_observation_changed",pending_intent_exists=True,
                            eventually_scheduled=True,eventually_canceled=True,
                            original_hit_at=commit[0].hit_at,original_key=commit[0].keys[0],
                            original_appearance=original_appearance,
                            original_span=f"{original_span[0]:.6f}:{original_span[1]:.6f}",
                            original_position_y=original_y,
                            current_candidate_span=f"{c.u_min:.6f}:{c.u_max:.6f}",
                            current_position_y=cy,
                            particle_predicted_position_y=tr.prediction.fitted_y if tr.prediction.fitted_y is not None else "",
                            span_compatible=span_ratio>=.5,
                            appearance_compatible=appearance_compatible,
                            competing_candidate_exists=competing,
                            remaining_to_hit_ms=1000*(commit[0].hit_at-finished))
                        self._emit_diagnostic("tap_decision",evidence_row)
                        self.scheduler._log('commit_invalidated',detail,commit[0])
                        self.scheduler.withdraw(event_id,'committed_observation_changed')
                    continue
                if self._dropout_still_valid(event_id,finished,tr):
                    active_events.add(event_id)
                    retained[tr.track_id] = self.scheduler.pending[event_id].keys,""
                    self.scheduler._log('dropout_retained',
                                        'compatible_position_outlier' if tr.last_time >
                                        self.dropout_commits[event_id][2] else 'recent_confirmed_head',
                                        self.scheduler.pending[event_id])
                    continue
                if tr.status != "confirmed" or tr.missed or tr.history[-1][1] < self.config.get("events", {}).get("min_y", 190*self.pixel_scale_y):
                    gate_failures=[]
                    if tr.status!="confirmed": gate_failures.append(
                        "TRACKER_TENTATIVE" if tr.status=="tentative" else "TRACKER_LOST_OR_REJECTED")
                    if tr.missed: gate_failures.append("TRACK_MISSED")
                    if tr.history[-1][1] < self.config.get("events", {}).get("min_y",190*self.pixel_scale_y):
                        gate_failures.append("BELOW_EVENT_MIN_Y")
                    if state!="PLAYING": gate_failures.append("GAME_NOT_PLAYING")
                    if not focused: gate_failures.append("FOCUS_LOST")
                    if not roi_valid: gate_failures.append("ROI_INVALID")
                    if stale: gate_failures.append("STALE_FRAME")
                    if event_id in self.scheduler.pending:
                        c=tr.candidate
                        failures=gate_failures
                        self._record_scheduler_trace(tr,event_id,self.scheduler.pending[event_id],finished,failures)
                        self._emit_tap_decision(tr,event_id,frame,finished,"PENDING_CANCELED",
                            "PENDING_CANCELED","|".join(failures),False,scheduled=True,
                            final_action="CANCELED",final_reason="|".join(failures))
                        detail=(f'{tr.status}:{tr.prediction.reason};missed={tr.missed};y={tr.history[-1][1]:.1f};'
                                f'type={c.note_type};appearance={c.appearance};keys={"|".join(c.candidate_keys)}')
                        self.scheduler._log('track_gate_rejected',detail,self.scheduler.pending[event_id])
                    self.scheduler.withdraw(event_id, "track_not_current_or_confirmed",retryable=bool(self.tap_rule))
                    if event_id not in self.scheduler.pending:
                        self._emit_tap_decision(tr,event_id,frame,finished,"TRACK_GATE",
                            "TRACK_GATE_REJECTED","|".join(gate_failures),False,
                            scheduled=False,final_action="NOT_SCHEDULED",
                            final_reason="|".join(gate_failures))
                    continue
                self.collector.consider(tr, frame.sequence, state)
                if tr.track_id not in self.seen_ids:
                    if tr.kind == "tap" and tr.track_id not in self.collector.emitted:
                        # Wait for the existing multi-observation timing gate.
                        # A too-early proposal must not consume a future tap.
                        if not (tr.candidate.suspected_overlap and tr.history[-1][1] >= 270*self.pixel_scale_y):
                            self._emit_tap_decision(tr,f"{self.session_id}:{tr.track_id}",frame,finished,
                                "WAIT_MORE_ETA_EVIDENCE","WAIT_MORE_ETA_EVIDENCE",
                                "event_collector_unconfirmed",True,scheduled=False,
                                final_action="NOT_SCHEDULED",final_reason="event_collector_unconfirmed")
                            continue
                    elif tr.kind != "tap" and tr.history[-1][1] < 270*self.pixel_scale_y:
                        continue
                ready.append(tr)
            if self.tap_rule:
                if self.hold_enabled:
                    for tr in ready:
                        if (tr.candidate.appearance in self.hold_path_colors and
                                (self.hold_tracker_v2 is not None or
                                 tr.candidate.hold_path_px >= self.hold_path_px)):
                            event_id=f"{self.session_id}:{tr.track_id}"
                            self.hold_ids.add(event_id)
                            self.hold_colors.setdefault(event_id,tr.candidate.appearance)
                options = {tr.track_id:track_options(tr,finished,self.known_keys,self.config.get("events",{}),
                              allow_range=True,speculative=self.speculative,
                              nearline_y=self.trigger_y-25*self.pixel_scale_y)
                           for tr in ready}
                for track_id in reidentified:
                    if track_id in options:
                        options[track_id] = (), 'reidentified_same_physical_tap'
                if self.hold_enabled:
                    # One connected green body can yield a wide head plus
                    # narrow edge fragments. Keep the widest physical span.
                    held_ids = {intent.event_id for _,intent in self.scheduler.held.values()
                                if intent.note_type=='hold'}
                    prior = [(span,hit,event_id in held_ids,event_id) for event_id,(span,hit)
                             in self.hold_spans.items()
                             if event_id in self.scheduler.pending or event_id in held_ids]
                    for tr in sorted(ready,key=lambda tr:-(tr.candidate.u_max-tr.candidate.u_min)):
                        event_id = f"{self.session_id}:{tr.track_id}"
                        keys,reason = options[tr.track_id]
                        if reason or event_id not in self.hold_ids:
                            continue
                        span = tr.candidate.u_min,tr.candidate.u_max
                        hit = tr.prediction.hit_time
                        duplicate = any(
                            other_id != event_id and
                            (held or abs(hit-other_hit)<=.15) and
                            max(0.,min(span[1],old[1])-max(span[0],old[0])) >=
                                .75*min(span[1]-span[0],old[1]-old[0])
                            for old,other_hit,held,other_id in prior)
                        if duplicate:
                            options[tr.track_id] = (), 'duplicate_hold_path'
                        else:
                            prior.append((span,hit,False,event_id))
                decisions = self.tap_rule.decide(ready,options,self.scheduler,active_ids={tr.track_id for tr in tracks})
            else:
                decisions = {tr.track_id:track_decision(tr,finished,self.known_keys,self.config.get("events",{}))
                             for tr in ready}
            for track_id in reidentified:
                if track_id in decisions:
                    decisions[track_id] = (), 'reidentified_same_physical_tap'
            self.last_decisions = {**decisions,**retained}
            for tr in ready:
                event_id = f"{self.session_id}:{tr.track_id}"
                keys,reason = decisions[tr.track_id]
                retryable = bool(self.tap_rule and reason in (
                    "suspected_overlap","ambiguous_or_unstable_keys","unstable_hit_time",
                    "assigned_key_temporarily_unstable"))
                self._emit_tap_decision(
                    tr,event_id,frame,finished,"SCHEDULE_ELIGIBILITY",
                    "SCHEDULE_ELIGIBLE" if not reason else "SCHEDULE_REJECTED",
                    reason,retryable,scheduled=event_id in self.scheduler.pending)
                if tr.track_id not in self.seen_ids:
                    self.seen_ids.add(tr.track_id)
                    self.events += 1
                    self.abstentions += bool(reason)
                    speculative_action = bool(keys and self.speculative.get('enabled') and
                        (tr.kind!='tap' or tr.candidate.suspected_overlap or
                         tr.prediction.uncertainty>.04 or not set(keys).intersection(tr.stable_keys)))
                    created.append({"event_id": event_id, "track_id": tr.track_id, "source_frame": frame.sequence,
                                    "capture_timestamp": frame.captured_at, "processing_timestamp": finished,
                                    "predicted_hit_time": tr.prediction.hit_time if tr.prediction.hit_time is not None else "",
                                    "uncertainty_s": tr.prediction.uncertainty if tr.prediction.uncertainty is not None else "",
                                    "key_candidates": "|".join(tr.stable_keys), "resolved_keys": "|".join(keys),
                                    "type": tr.candidate.note_type, "appearance": tr.candidate.appearance,
                                    "confidence_label": f"heuristic_only:{tr.candidate.score:.3f}",
                                    "resolution_basis": "speculative_visible_candidate" if speculative_action else
                                                        "user_confirmed_any_covered_key" if keys and self.tap_rule else
                                                        "manual_key_evidence" if keys else "",
                                    "abstain_reason": reason, "gameplay_state": state,
                                    "predictor_mode": tr.prediction.predictor_mode,
                                    "eta_p10_s": tr.prediction.eta_p10 if tr.prediction.eta_p10 is not None else "",
                                    "eta_p50_s": tr.prediction.eta_p50 if tr.prediction.eta_p50 is not None else "",
                                    "eta_p90_s": tr.prediction.eta_p90 if tr.prediction.eta_p90 is not None else "",
                                    "valid_crossing_mass": tr.prediction.valid_crossing_mass if tr.prediction.valid_crossing_mass is not None else "",
                                    "particle_ess": tr.prediction.ess if tr.prediction.ess is not None else "",
                                    "real_observation_count": tr.prediction.real_observation_count if tr.prediction.real_observation_count is not None else "",
                                    "coast_ms": tr.prediction.coast_ms,
                                    "physical_hit_time": tr.prediction.physical_hit_time if tr.prediction.physical_hit_time is not None else "",
                                    "measurement_status": tr.prediction.measurement_status,
                                    "physical_track_uid": tr.physical_note_uid,
                                    "source_track_ids": "|".join(map(str,tr.source_track_ids)),
                                    "reidentified_from_id": tr.reidentified_from_id if tr.reidentified_from_id is not None else "",
                                    "confirmed_note_type": tr.confirmed_note_type or "",
                                    "current_observation_type": tr.current_observation_type,
                                    "identity_state": tr.identity_state,
                                    "association_score": tr.last_association.get("association_score", ""),
                                    "measurement_quality": tr.prediction.measurement_quality,
                                "eta_expired": bool(tr.prediction.hit_time is not None and tr.prediction.hit_time <= finished),
                                "eta_abstain_reason": "predicted_hit_not_future" if tr.prediction.hit_time is not None and tr.prediction.hit_time <= finished else "",
                                    "geometry_status": self.geometry.status, "geometry_sha256": self.geometry_hash})
                    # Record WHEN it was first seen, separately from readiness.
                    # Same-arm improved observations can become eligible later;
                    # events first seen while OFF or in an older arm never do.
                    if self.scheduler.armed and (self.tap_rule or not reason):
                        self.input_eligible_ids[tr.track_id] = self.scheduler.arm_generation
                if not reason and self.input_eligible_ids.get(tr.track_id) == self.scheduler.arm_generation:
                    active_events.add(event_id)
                    hold = event_id in self.hold_ids
                    intent = ActionIntent(event_id, keys, tr.prediction.hit_time, tr.prediction.uncertainty,
                                          'hold' if hold else 'tap',
                                          (tr.candidate.u_min+tr.candidate.u_max)/2 if hold else None,
                                          self.hold_colors.get(event_id) if hold else None)
                    commit = self.occlusion_commits.get(event_id)
                    if commit and commit[1]==self.scheduler.arm_generation:
                        intent = commit[0]
                    offer_result = self.scheduler.offer(intent)
                    accepted = offer_result.accepted
                    self._emit_tap_decision(
                        tr,event_id,frame,finished,"SCHEDULE_OFFERED",
                        "SCHEDULE_ACCEPTED" if accepted else "SCHEDULE_REJECTED",
                        "" if accepted else offer_result.reason,
                        not accepted,scheduled=accepted)
                    if (accepted and not hold and tr.confirmed_note_type=="tap" and tr.selected_key is None):
                        tr.selected_key=keys[0]
                    if accepted and hold:
                        self.hold_spans[event_id] = ((tr.candidate.u_min,tr.candidate.u_max),intent.hit_at)
                    ordinary_tap = (tr.candidate.appearance in ('cyan_bar','yellow_bar') and
                                    tr.candidate.note_type=='tap' and not hold)
                    if (accepted and ordinary_tap and tr.status=='confirmed' and tr.history):
                        self.tap_edge_evidence[event_id] = {
                            'intent':intent,'generation':self.scheduler.arm_generation,
                            'first_time':tr.first_time,'timestamp':tr.last_time,
                            'span':(tr.candidate.u_min,tr.candidate.u_max),
                            'appearance':tr.candidate.appearance,'bbox':tr.candidate.bbox,
                            'note_type':tr.candidate.note_type,'center_y':tr.history[-1][1],
                        }
                    grace = self.tap_dropout_grace_s if ordinary_tap else self.dropout_grace_s
                    minimum_y = self.tap_dropout_min_y if ordinary_tap else self.dropout_min_y
                    if (accepted and grace and
                            tr.history[-1][1] >= minimum_y and
                            0 < intent.hit_at-finished <= grace):
                        self.dropout_commits[event_id] = (
                            intent,self.scheduler.arm_generation,tr.last_time,
                            (tr.candidate.u_min,tr.candidate.u_max),tr.candidate.appearance,
                            tr.history[-1][1],tr.candidate.note_type)
                    if (accepted and not commit and self.tap_rule and self.tap_rule.commit_horizon and
                            self.judgment_bar_top is not None and
                            tr.candidate.bbox[1]+tr.candidate.bbox[3]>=self.commit_entry_y-
                                self.config.get('tracker',{}).get('backward_jitter_px',3.5) and
                            0<intent.hit_at-finished<=self.tap_rule.commit_horizon):
                        # The horizon is relative to decision completion. Never
                        # expire an accepted action before its frozen deadline;
                        # only the scheduler's existing lateness budget follows.
                        self.occlusion_commits[event_id] = (intent,self.scheduler.arm_generation,
                            intent.hit_at+self.scheduler.max_lateness,
                            (tr.candidate.u_min,tr.candidate.u_max),tr.candidate.appearance,
                            tr.candidate.bbox,tr.candidate.note_type)
                        self.scheduler._log('committed_near_judgment','measured_judgment_bar_occlusion',intent)
                else:
                    self._emit_tap_decision(
                        tr,event_id,frame,finished,"SCHEDULE_OFFERED",
                        "SCHEDULE_REJECTED",
                        reason or "not_eligible_in_current_arm",retryable,
                        scheduled=False,final_action="NOT_SCHEDULED",
                        final_reason=reason or "not_eligible_in_current_arm")
                    self.scheduler.withdraw(event_id, reason or "not_created_while_armed",retryable=retryable)
            for event_id in list(self.scheduler.pending):
                if event_id.startswith(f"{self.simple_core.session_id}:simple:"):
                    # The sole Tap intent owner is the Simple Core.
                    continue
                coast = self.provisional_tap_losses.get(event_id)
                if coast and event_id not in active_events:
                    if self._retain_reidentified_intent(event_id,finished):
                        active_events.add(event_id)
                    elif self._keep_absent_provisional_tap(event_id,coast,finished,
                            present_ids,finished_tracks,finished_past_ids):
                        self.scheduler.resume(event_id)
                        active_events.add(event_id)
                        self.scheduler._log('provisional_loss_retained',
                                            'track_id_absent_original_key_and_deadline',coast['intent'])
                    else:
                        self.provisional_tap_losses.pop(event_id,None)
                        self.scheduler.withdraw(event_id,'provisional_loss_expired',retryable=True)
                        continue
                edge_commit = self.occlusion_commits.get(event_id)
                if (event_id in self.edge_fragment_commits and event_id not in active_events and
                        event_id not in present_ids):
                    if (edge_commit and event_id not in finished_past_ids and
                            edge_commit[1] == self.scheduler.arm_generation and
                            frame.captured_at <= edge_commit[2] and
                            finished <= edge_commit[0].hit_at+self.scheduler.max_lateness and
                            state == 'PLAYING' and focused and roi_valid and not stale):
                        active_events.add(event_id)
                        self.scheduler._log('edge_fragment_retained',
                                            'same_confirmed_tap_pending_original_deadline',edge_commit[0])
                    else:
                        self.edge_fragment_commits.discard(event_id)
                        self.scheduler.withdraw(event_id,'edge_fragment_commit_expired')
                        continue
                if (event_id not in active_events and event_id not in present_ids and
                        event_id not in finished_past_ids):
                    try:
                        origin_track_id=int(event_id.rsplit(":",1)[1])
                    except (IndexError,ValueError):
                        origin_track_id=-1
                    source_track=next((candidate for candidate in
                        (*self.tracker.finished,*self.tracker.recent_particle_tracks)
                        if candidate.track_id==origin_track_id),None)
                    intent=self.scheduler.pending.get(event_id)
                    if (source_track is not None and intent is not None and
                            self._tap_identity_intent_still_valid(source_track,event_id,intent,finished,
                                state=state,focused=focused,roi_valid=roi_valid,stale=stale)):
                        self.scheduler.resume(event_id)
                        active_events.add(event_id)
                        self.scheduler._log("tap_identity_coast_retained",
                            f"uid={source_track.physical_note_uid};coast_ms={source_track.prediction.coast_ms:.1f};"
                            f"original_hit_at={intent.hit_at:.6f};key={intent.keys[0]}",intent)
                if (event_id not in active_events and event_id not in present_ids and
                        event_id not in finished_past_ids and
                        self._dropout_still_valid(event_id,finished)):
                    active_events.add(event_id)
                    self.scheduler._log('dropout_retained','track_expired_after_recent_head',
                                        self.scheduler.pending[event_id])
                if event_id not in active_events:
                    ended = finished_tracks.get(event_id)
                    if ended is not None:
                        detail=(f'{ended.reason};y={ended.history[-1][1]:.1f};'
                                f'target_y={self.trigger_y:.1f};completion_y={self.geometry.hit_y:.1f};'
                                f'bbox={ended.candidate.bbox}')
                        self.scheduler._log('track_finished',detail,self.scheduler.pending[event_id])
                    self.scheduler.withdraw(event_id, "no_current_eligible_observation")
            self.occlusion_commits = {event_id:commit for event_id,commit in self.occlusion_commits.items()
                                      if event_id in self.scheduler.pending and commit[1]==self.scheduler.arm_generation}
            self.edge_fragment_commits.intersection_update(self.scheduler.pending)
            self.dropout_commits = {event_id:commit for event_id,commit in self.dropout_commits.items()
                                    if event_id in self.scheduler.pending and commit[1]==self.scheduler.arm_generation}
            self.provisional_tap_losses = {
                event_id:coast for event_id,coast in self.provisional_tap_losses.items()
                if event_id in self.scheduler.pending and coast['generation']==self.scheduler.arm_generation
            }
            self.tap_edge_evidence = {
                event_id:evidence for event_id,evidence in self.tap_edge_evidence.items()
                if event_id in self.scheduler.pending and evidence['generation']==self.scheduler.arm_generation
            }
            safe_context = (state == "PLAYING" and focused and roi_valid and not stale)
            proposals, accepted = self.simple_core.plan_tracks(
                self.simple_tracks, frame.captured_at, finished, self.scheduler,
                enabled=safe_context)
            for tr in self.simple_tracks:
                uid = self.simple_core.note_uid(tr.track_id)
                intent = self.simple_core.intents.intents.get(uid)
                if intent is not None and intent.state == "PENDING":
                    self.last_decisions[tr.track_id] = ((intent.key,), "")
                    tr.selected_key = intent.key
                    self.simple_decision_reasons.pop(tr.track_id, None)
                elif intent is not None:
                    self.last_decisions[tr.track_id] = ((), intent.state.lower())
                    self.simple_decision_reasons.pop(tr.track_id, None)
                else:
                    reason = self.simple_core.last_reasons.get(tr.track_id, "not_scheduled")
                    self.last_decisions[tr.track_id] = ((), reason)
                    if reason != self.simple_decision_reasons.get(tr.track_id):
                        prediction = tr.prediction
                        created.append({
                            "event_id": uid, "note_uid": uid, "track_id": tr.track_id,
                            "source_frame": frame.sequence,
                            "capture_timestamp": frame.captured_at,
                            "processing_timestamp": finished,
                            "predicted_hit_time": prediction.hit_time if prediction.hit_time is not None else "",
                            "uncertainty_s": prediction.uncertainty if prediction.uncertainty is not None else "",
                            "key_candidates": "|".join(tr.stable_keys), "resolved_keys": "",
                            "type": "tap", "appearance": tr.candidate.appearance,
                            "confidence_label": "heuristic_only", "abstain_reason": reason,
                            "gameplay_state": state, "predictor_mode": "particle",
                            "geometry_status": self.geometry.status,
                            "geometry_sha256": self.geometry_hash,
                            "resolution_basis": "simple_confirmed_tap",
                            "eta_p10_s": prediction.eta_p10 if prediction.eta_p10 is not None else "",
                            "eta_p50_s": prediction.eta_p50 if prediction.eta_p50 is not None else "",
                            "eta_p90_s": prediction.eta_p90 if prediction.eta_p90 is not None else "",
                            "valid_crossing_mass": prediction.valid_crossing_mass if prediction.valid_crossing_mass is not None else "",
                            "particle_ess": prediction.ess if prediction.ess is not None else "",
                            "real_observation_count": prediction.real_observation_count if prediction.real_observation_count is not None else "",
                            "coast_ms": prediction.coast_ms,
                            "measurement_status": prediction.measurement_status,
                            "particle_predicted_y": prediction.fitted_y if prediction.fitted_y is not None else "",
                            "particle_velocity_px_s": prediction.velocity if prediction.velocity is not None else "",
                            "simple_track_observations": tr.observations,
                            "simple_track_status": tr.status,
                            "particle_rejection_streak": tr.particle_rejection_streak,
                            "particle_reinitializations": tr.particle_reinitializations,
                            "simple_core_state": "NOT_SCHEDULED",
                            "simple_core_reason": reason,
                            "lane_span": f"{tr.candidate.u_min:.6f}:{tr.candidate.u_max:.6f}",
                            "crossing_y": tr.history[-1][1] if tr.history else ""})
                    self.simple_decision_reasons[tr.track_id] = reason
            current_simple_ids = {tr.track_id for tr in self.simple_tracks}
            self.simple_decision_reasons = {
                track_id: reason for track_id, reason in self.simple_decision_reasons.items()
                if track_id in current_simple_ids}
            scheduler_started=time.perf_counter()
            self.scheduler.poll()
            measured["scheduler_update"]=time.perf_counter()-scheduler_started
            live_holds = set(self.scheduler.pending) | {intent.event_id for _,intent in self.scheduler.held.values()}
            self.hold_spans = {event_id:value for event_id,value in self.hold_spans.items()
                               if event_id in live_holds}
            if self.simple_core is not None:
                current_simple = {track.track_id: track for track in self.simple_tracks}
                for transition in self.simple_core.drain_transitions():
                    uid = transition["note_uid"]
                    try:
                        simple_id = int(uid.rsplit(":", 1)[1])
                    except (IndexError, ValueError):
                        simple_id = 0
                    tr = current_simple.get(simple_id)
                    intent = self.simple_core.intents.intents.get(uid)
                    proposal = next((item for item in proposals.values()
                                     if item.note_uid == uid), None)
                    created.append({
                        "event_id": uid, "note_uid": uid, "track_id": simple_id,
                        "source_frame": frame.sequence,
                        "capture_timestamp": transition.get("timestamp", frame.captured_at),
                        "processing_timestamp": finished,
                        "predicted_hit_time": (intent.hit_at if intent else
                            proposal.hit_at if proposal else ""),
                        "uncertainty_s": (intent.uncertainty if intent else
                            proposal.uncertainty if proposal else ""),
                        "key_candidates": "|".join(tr.stable_keys) if tr else "",
                        "resolved_keys": intent.key if intent else
                            proposal.key if proposal else transition.get("key", ""),
                        "type": "tap", "appearance": tr.candidate.appearance if tr else "",
                        "confidence_label": "heuristic_only",
                        "abstain_reason": transition.get("reason", ""),
                        "gameplay_state": state,
                        "predictor_mode": "particle",
                        "geometry_status": self.geometry.status,
                        "geometry_sha256": self.geometry_hash,
                        "resolution_basis": "simple_confirmed_tap",
                        "simple_core_state": transition.get("state", ""),
                        "simple_core_reason": transition.get("reason", ""),
                        "revision": transition.get("revision", intent.revision if intent else 0),
                        "lane_span": (f"{tr.candidate.u_min:.6f}:{tr.candidate.u_max:.6f}" if tr else
                            f"{intent.lane_span[0]:.6f}:{intent.lane_span[1]:.6f}" if intent else
                            f"{proposal.lane_span[0]:.6f}:{proposal.lane_span[1]:.6f}" if proposal else ""),
                        "crossing_y": (tr.history[-1][1] if tr and tr.history else
                            intent.observed_y if intent else proposal.observed_y if proposal else "")})
                    if transition.get("state") == "DETECTED":
                        self.events += 1
        measured["decision"] = max(0.,time.perf_counter()-phase-measured.get("scheduler_update",0.))
        late_diagnostic_started=time.perf_counter()
        for tracked in (*tracks,*self.tracker.finished):
            if getattr(tracked,"confirmed_note_type",None)!="tap" or getattr(tracked,"particle_filter",None) is None:
                continue
            event_id=f"{self.session_id}:{tracked.track_id}"
            pending=self.scheduler.pending.get(event_id)
            parent_event=self.reidentified_tracker_ids.get(tracked.track_id)
            if pending is None and parent_event:
                pending=self.scheduler.pending.get(parent_event)
            association=tracked.last_association or {}
            observed_y=association.get("observed_y")
            if observed_y is None and tracked.history:
                observed_y=tracked.history[-1][1]
            self._emit_diagnostic("hit_eta",{
                "physical_note_uid":tracked.physical_note_uid,"track_id":tracked.track_id,
                "source_track_ids":"|".join(map(str,tracked.source_track_ids)),
                "source_frame":frame.sequence,"capture_timestamp":frame.captured_at,
                "confirmed_note_type":tracked.confirmed_note_type,
                "current_observation_type":tracked.current_observation_type,
                "identity_state":tracked.identity_state,
                "particle_predicted_y":tracked.prediction.fitted_y if tracked.prediction.fitted_y is not None else "",
                "observed_y":observed_y if observed_y is not None else "",
                "innovation_y":association.get("innovation_y",tracked.prediction.innovation_y or ""),
                "association_score":association.get("association_score",tracked.prediction.association_score or ""),
                "association_accepted":association.get("accepted",False),
                "measurement_quality":association.get("measurement_quality",tracked.prediction.measurement_quality),
                "measurement_status":tracked.prediction.measurement_status,
                "eta_p10":tracked.prediction.eta_p10 if tracked.prediction.eta_p10 is not None else "",
                "eta_p50":tracked.prediction.eta_p50 if tracked.prediction.eta_p50 is not None else "",
                "eta_p90":tracked.prediction.eta_p90 if tracked.prediction.eta_p90 is not None else "",
                "hit_at":tracked.prediction.hit_time if tracked.prediction.hit_time is not None else "",
                "physical_hit_time":tracked.prediction.physical_hit_time if tracked.prediction.physical_hit_time is not None else "",
                "valid_crossing_mass":tracked.prediction.valid_crossing_mass if tracked.prediction.valid_crossing_mass is not None else "",
                "particle_ess":tracked.prediction.ess if tracked.prediction.ess is not None else "",
                "coast_ms":tracked.prediction.coast_ms,"original_selected_key":pending.keys[0] if pending else tracked.selected_key or "",
                "original_hit_at":pending.hit_at if pending else "",
                "final_action":"PENDING" if pending else "NO_PENDING_INTENT",
                "final_reason":tracked.reason,
                "last_reliable_tap_at":tracked.last_reliable_tap_at if tracked.last_reliable_tap_at is not None else "",
                "tracker_status":tracked.status})
        measured["diagnostic_write"] += time.perf_counter()-late_diagnostic_started
        self.tracker.finished.clear()
        self.collector.rows.clear()  # live CSV is streamed; no growing frame/event queue
        self.stale += stale
        self.latencies.append(latency*1000)
        self.process_times.append(finished)
        info = {"frame": frame.sequence, "capture_timestamp": frame.captured_at,
                "acquired_timestamp": frame.acquired_at, "processing_timestamp": finished,
                "timestamp_source": frame.timestamp_source, "gameplay_state": state,
                "focused": focused, "roi_status": "BLOCKED" if not roi_valid else "STALE" if stale else "ASPECT_FIT_16_9",
                "frame_age_ms": age*1000, "latency_ms": latency*1000,
                "processing_ms": (finished-started)*1000,
                "acquire_queue_wait_ms": max(0.0,started-frame.acquired_at)*1000,
                "normalization_ms":measured["normalization"]*1000,
                "state_detector_ms":measured["state_detector"]*1000,
                "note_detector_ms":measured["note_detector"]*1000,
                "tracker_matching_ms":measured["tracker_matching"]*1000,
                "simple_core_ms":measured.get("simple_core",0.)*1000,
                "unknown_association_ms":measured["unknown_association"]*1000,
                "pf_prediction_update_ms":measured["prediction"]*1000,
                "decision_ms":measured["decision"]*1000,
                "scheduler_update_ms":measured.get("scheduler_update",0.)*1000,
                "diagnostic_write_ms":measured["diagnostic_write"]*1000,
                "capture_fps": self._fps(self.capture_times), "processing_fps": self._fps(self.process_times),
                "latency_p50_ms": float(np.median(self.latencies)), "latency_p95_ms": float(np.percentile(self.latencies, 95)),
                "stale_total": self.stale, "candidate_count": len(candidates),
                "tracked_count": len(tracks)+len(self.simple_tracks),
                "input_armed": self.scheduler.armed}
        measured["cv_total"] = time.perf_counter()-wall_begin
        self.stage_times = measured
        display_tracks = [*tracks, *self.simple_tracks]
        return work, display_tracks, created, info

    @staticmethod
    def _fps(times):
        return (len(times)-1)/(times[-1]-times[0]) if len(times)>1 and times[-1]>times[0] else 0


def draw_live_overlay(work, tracks, info, engine, dropped=0):
    status_label = 'ASSIST ARMED' if engine.scheduler.armed else 'ASSIST INPUT OFF'
    footer_label = 'cand=possible lanes; selected key in right panel | Yellow:tent Green:conf Red:rej Orange:lost Gray:done'
    base = render(work, engine.geometry, tracks, info["gameplay_state"], info["capture_timestamp"],
                  engine.gate.evidence, engine.config["key_map"], explicit_candidates=True,
                  status_label=status_label, footer_label=footer_label)
    if engine.input_advance_px:
        row = engine.geometry.lane_bounds_at_y(engine.trigger_y)
        if row is not None:
            cv2.line(base,(round(row[0]),round(engine.trigger_y)),
                     (round(row[-1]),round(engine.trigger_y)),(0,155,255),max(1,round(2*engine.pixel_scale_y)),cv2.LINE_AA)
    # The game view keeps native pixels; the status panel is outside the ROI.
    scale = max(.1,min(base.shape[1]/720,base.shape[0]/404))
    panel_width = round(480*scale)
    canvas = np.zeros((max(round(560*scale),base.shape[0]), base.shape[1]+panel_width, 3), np.uint8)
    canvas[:base.shape[0], :base.shape[1]] = base
    label = "ASSIST / ARMED" if engine.scheduler.armed else "ASSIST / INPUT OFF"
    lines = ["LIVE | "+label, f"game: {info['gameplay_state']} | ROI: {info['roi_status']}",
             f"geometry: {engine.geometry.status} | {engine.geometry_hash[:12]}"]
    lines.append(f"input trigger: y={engine.trigger_y:.1f} ({engine.input_advance_px:.1f}px early)")
    held_holds = [key for key,(_,intent) in engine.scheduler.held.items() if intent.note_type=='hold']
    if held_holds:
        lines.append(f"holding: {','.join(held_holds)}")
    lines += [f"capture FPS: {info['capture_fps']:.1f} | process FPS: {info['processing_fps']:.1f}",
             f"age: {info['frame_age_ms']:.1f}ms | latency: {info['latency_ms']:.1f}ms",
             f"latency P50/P95: {info['latency_p50_ms']:.1f}/{info['latency_p95_ms']:.1f}ms",
             f"dropped: {dropped} | stale: {info['stale_total']} | events: {engine.events}",
             f"abstain: {engine.abstentions} | taps: {getattr(engine.scheduler,'sent_taps',engine.scheduler.sent)} | holds: {getattr(engine.scheduler,'sent_holds',0)}",
             "Ctrl+Shift+Alt+Q: toggle Assist",
             "Esc / F12: STOP, release keys", f"control: {engine.scheduler.last_reason}",
             "UNVERIFIED: no accuracy inferred from heuristic scores", ""]
    for tr in sorted(tracks, key=lambda t: -t.bbox[1])[:8]:
        keys, reason = engine.last_decisions.get(tr.track_id,((),"not_current_eligible_tap"))
        hit = f"{tr.prediction.hit_time:.4f}" if tr.prediction.hit_time is not None else "?"
        uncertainty = f"{tr.prediction.uncertainty:.4f}" if tr.prediction.uncertainty is not None else "?"
        simple_uid = engine.simple_core.note_uid(tr.track_id) if engine.simple_core else ""
        simple_intent = engine.simple_core.intents.intents.get(simple_uid) if engine.simple_core else None
        if simple_intent is not None:
            lifecycle = "SCHEDULED" if simple_intent.state == "PENDING" else simple_intent.state
            selected = simple_intent.key
        elif tr.status != "confirmed":
            lifecycle, selected = "TRACKING", ""
        elif tr.confirmed_note_type == "tap" and not reason:
            lifecycle, selected = "ELIGIBLE", (keys[0] if keys else "")
        elif tr.confirmed_note_type == "tap":
            lifecycle, selected = "CONFIRMED", ""
        else:
            lifecycle, selected = "TRACK_CONFIRMED", ""
        kind = ('hold_candidate' if
                f"{engine.session_id}:{tr.track_id}" in engine.hold_ids else tr.kind)
        outcome = f"key:{selected} {lifecycle}" if selected else lifecycle
        if reason:
            outcome += f" | {reason}"
        lines += [f"#{tr.track_id} {kind} cand:{'/'.join(tr.stable_keys) or '?'} hit:{hit}",
                  f"  +/-{uncertainty}s {outcome}"]
    for i, line in enumerate(lines):
        cv2.putText(canvas, line[:80], (base.shape[1]+round(8*scale), round(19*scale)+i*round(18*scale)),
                    cv2.FONT_HERSHEY_SIMPLEX, .37*scale, (170,235,255) if i == 0 else (220,220,220), max(1,round(scale)), cv2.LINE_AA)
    return canvas
