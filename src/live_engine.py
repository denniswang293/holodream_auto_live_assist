"""Live Assist decision engine and overlay."""
from __future__ import annotations

from collections import deque
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


def track_options(track, now, known_keys, event_cfg, *, allow_range=False, speculative=None,
                  nearline_y=None):
    """Validate motion/timing and return allowed options, never a chord."""
    c, p = track.candidate, track.prediction
    if track.status != "confirmed" or track.missed:
        return (), "track_not_current_confirmed"
    speculative = speculative or {}
    experimental = bool(speculative.get("enabled"))
    allowed_appearances = ("cyan_bar", "yellow_bar", "green_candidate",
                           "pink_candidate", "neutral_candidate") if experimental else ("cyan_bar", "yellow_bar")
    if c.note_type not in (("tap", "unknown") if experimental else ("tap",)) or c.appearance not in allowed_appearances:
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
        self.hold_colors = {}
        self.hold_watch = {}
        self.hold_spans = {}
        if self.tap_rule:
            self.known_keys = self.tap_rule.allowed_keys
        self.last_decisions = {}
        self.occlusion_commits = {}
        self.dropout_commits = {}
        self.judgment_bar_top = geometry.document.get('live_measurement',{}).get('judgment_bar_top_y')
        self.gate = GameplayGate(config.get("gameplay"), geometry.reference_resolution)
        tracker_cfg = {**config.get("tracker", {}), "key_map": config["key_map"]}
        # Advancing input changes the prediction target, not the physical end
        # of the visible note. Keep tracking until the measured judgment row.
        tracker_cfg['completion_y'] = geometry.hit_y
        predictor_cfg = dict(config.get("predictor",{}))
        if self.speculative.get("enabled"):
            tracker_cfg["max_hit_drift_s"] = self.speculative["max_hit_drift_s"]
            tracker_cfg["tap_hit_drift_window"] = self.speculative.get("tap_hit_drift_window",5)
            predictor_cfg["max_uncertainty_s"] = self.speculative["max_uncertainty_s"]
        self.tracker = Tracker(tracker_cfg,self.trigger_y,predictor_cfg)
        self.collector = EventCollector({**config.get("events", {}), "reference_height": geometry.reference_resolution[1]})
        # Near-target commitment must move with the trigger when input is
        # advanced; otherwise the track finishes before reaching the corridor.
        self.commit_entry_y = (min(self.judgment_bar_top,self.trigger_y-12.5*self.pixel_scale_y)
                               if self.judgment_bar_top is not None else None)
        self.dc = {**config.get("detector", {}), "reference_resolution": geometry.reference_resolution}
        self.session_id = uuid.uuid4().hex[:12]
        self.seen_ids, self.input_eligible_ids = set(), {}
        self.track_births, self.recycled_ids = {}, set()
        self.last_capture = -math.inf
        self.latencies, self.capture_times, self.process_times = deque(maxlen=600), deque(maxlen=120), deque(maxlen=120)
        self.stale, self.events, self.abstentions, self.frames = 0, 0, 0, 0
        self.stage_times = {}

    def invalidate(self, reason="invalid_frame"):
        self.scheduler.disarm(reason)
        self.gate.streak, self.gate.state = 0, "UNCERTAIN"
        # Do not recycle IDs on resuming or lose emergency de-duplication state.
        self.tracker.update([], self.last_capture, playing=False)
        self.tracker.finished.clear()

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
        measured = dict.fromkeys(("normalization","state_detector","note_detector","tracking","prediction","decision"),0.0)
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
            prediction_before = getattr(self.tracker.predictor,"elapsed",0.0)
            phase = time.perf_counter()
            tracks = self.tracker.update(candidates, frame.captured_at, playing=state == "PLAYING")
            measured["prediction"] = getattr(self.tracker.predictor,"elapsed",0.0)-prediction_before
            measured["tracking"] = max(0.0,time.perf_counter()-phase-measured["prediction"])
        finished = self.clock()
        latency = finished-frame.captured_at
        if latency > self.scheduler.max_age and not stale:
            stale = True
            self.invalidate("frame_expired_during_processing")
            state, tracks = "STALE", []
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
            present_ids = set()
            finished_tracks = {f"{self.session_id}:{tr.track_id}":tr for tr in self.tracker.finished}
            finished_past_ids = {event_id for event_id,tr in finished_tracks.items()
                                 if tr.reason == 'past_hit_line'}
            for tr in tracks:
                event_id = f"{self.session_id}:{tr.track_id}"
                present_ids.add(event_id)
                birth = self.track_births.setdefault(tr.track_id, tr.first_time)
                if birth != tr.first_time:
                    self.recycled_ids.add(tr.track_id)
                if tr.track_id in self.recycled_ids:
                    self.scheduler.withdraw(event_id, "recycled_track_id")
                    continue
                commit = self.occlusion_commits.get(event_id)
                if commit and event_id in self.scheduler.pending:
                    if (self._commit_still_valid(tr,commit,finished) and state=='PLAYING' and
                            focused and roi_valid and not stale):
                        active_events.add(event_id)
                        retained[tr.track_id] = commit[0].keys,""
                        if tr.status!='confirmed' or tr.prediction.reason:
                            self.scheduler._log('commit_retained',f'{tr.status}:{tr.prediction.reason}',commit[0])
                    else:
                        c=tr.candidate
                        detail = (f'{tr.status}:{tr.prediction.reason};missed={tr.missed};y={tr.history[-1][1]:.1f};'
                                  f'type={c.note_type};appearance={c.appearance};keys={"|".join(c.candidate_keys)};'
                                  f'bbox={c.bbox};span={c.u_min:.4f}:{c.u_max:.4f}')
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
                    if event_id in self.scheduler.pending:
                        c=tr.candidate
                        detail=(f'{tr.status}:{tr.prediction.reason};missed={tr.missed};y={tr.history[-1][1]:.1f};'
                                f'type={c.note_type};appearance={c.appearance};keys={"|".join(c.candidate_keys)}')
                        self.scheduler._log('track_gate_rejected',detail,self.scheduler.pending[event_id])
                    self.scheduler.withdraw(event_id, "track_not_current_or_confirmed",retryable=bool(self.tap_rule))
                    continue
                self.collector.consider(tr, frame.sequence, state)
                if tr.track_id not in self.seen_ids:
                    if tr.kind == "tap" and tr.track_id not in self.collector.emitted:
                        # Wait for the existing multi-observation timing gate.
                        # A too-early proposal must not consume a future tap.
                        if not (tr.candidate.suspected_overlap and tr.history[-1][1] >= 270*self.pixel_scale_y):
                            continue
                    elif tr.kind != "tap" and tr.history[-1][1] < 270*self.pixel_scale_y:
                        continue
                ready.append(tr)
            if self.tap_rule:
                if self.hold_enabled:
                    for tr in ready:
                        if (tr.candidate.appearance in self.hold_path_colors and
                                tr.candidate.hold_path_px>=self.hold_path_px):
                            event_id=f"{self.session_id}:{tr.track_id}"
                            self.hold_ids.add(event_id)
                            self.hold_colors.setdefault(event_id,tr.candidate.appearance)
                options = {tr.track_id:track_options(tr,finished,self.known_keys,self.config.get("events",{}),
                              allow_range=True,speculative=self.speculative,
                              nearline_y=self.trigger_y-25*self.pixel_scale_y)
                           for tr in ready}
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
            self.last_decisions = {**decisions,**retained}
            for tr in ready:
                event_id = f"{self.session_id}:{tr.track_id}"
                keys,reason = decisions[tr.track_id]
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
                    accepted = self.scheduler.offer(intent)
                    if accepted and hold:
                        self.hold_spans[event_id] = ((tr.candidate.u_min,tr.candidate.u_max),intent.hit_at)
                    ordinary_tap = (tr.candidate.appearance in ('cyan_bar','yellow_bar') and
                                    tr.candidate.note_type=='tap' and not hold)
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
                    retryable = bool(self.tap_rule and reason in (
                        "suspected_overlap","ambiguous_or_unstable_keys","unstable_hit_time",
                        "assigned_key_temporarily_unstable"))
                    self.scheduler.withdraw(event_id, reason or "not_created_while_armed",retryable=retryable)
            for event_id in list(self.scheduler.pending):
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
            self.dropout_commits = {event_id:commit for event_id,commit in self.dropout_commits.items()
                                    if event_id in self.scheduler.pending and commit[1]==self.scheduler.arm_generation}
            self.scheduler.poll()
            live_holds = set(self.scheduler.pending) | {intent.event_id for _,intent in self.scheduler.held.values()}
            self.hold_spans = {event_id:value for event_id,value in self.hold_spans.items()
                               if event_id in live_holds}
        measured["decision"] = time.perf_counter()-phase
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
                "capture_fps": self._fps(self.capture_times), "processing_fps": self._fps(self.process_times),
                "latency_p50_ms": float(np.median(self.latencies)), "latency_p95_ms": float(np.percentile(self.latencies, 95)),
                "stale_total": self.stale, "candidate_count": len(candidates), "tracked_count": len(tracks),
                "input_armed": self.scheduler.armed}
        measured["cv_total"] = time.perf_counter()-wall_begin
        self.stage_times = measured
        return work, tracks, created, info

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
        kind = ('hold_candidate' if
                f"{engine.session_id}:{tr.track_id}" in engine.hold_ids else tr.kind)
        lines += [f"#{tr.track_id} {kind} cand:{'/'.join(tr.stable_keys) or '?'} hit:{hit}",
                  f"  +/-{uncertainty}s {reason or ('selected:'+','.join(keys))}"]
    for i, line in enumerate(lines):
        cv2.putText(canvas, line[:80], (base.shape[1]+round(8*scale), round(19*scale)+i*round(18*scale)),
                    cv2.FONT_HERSHEY_SIMPLEX, .37*scale, (170,235,255) if i == 0 else (220,220,220), max(1,round(scale)), cv2.LINE_AA)
    return canvas
