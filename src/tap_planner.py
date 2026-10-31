"""Evidence gates and one-key assignment for ordinary Simple Core Taps."""
from __future__ import annotations

from dataclasses import dataclass
import math

from .assignment import assign
from .common import KEYS
from .simple_tracker import SimpleTrack, is_simple_tap


@dataclass(frozen=True)
class TapProposal:
    note_uid: str
    track_id: int
    key: str
    hit_at: float
    uncertainty: float
    evidence: str
    lane_span: tuple[float, float] = (0., 0.)
    appearance: str = ""
    observed_y: float | None = None


@dataclass
class DecisionTrace:
    note_uid: str
    track_id: int
    gates: dict[str, bool]
    final_reason: str
    eta_s: float | None
    hit_at: float | None
    uncertainty_s: float | None
    key_conflicts: dict[str, str]
    first_possible_schedule_at: float | None = None
    last_safe_schedule_at: float | None = None
    motion_reliable: bool = False
    timing_reliable: bool = False
    timing_quality: float | None = None
    linear_eta_s: float | None = None
    linear_hit_at: float | None = None
    linear_quality: float | None = None


class TapPlanner:
    """Turn confirmed motion evidence into at most one key and one ETA."""

    def __init__(self, event_config: dict | None = None, *, min_y: float = 190.,
                 max_uncertainty_s: float = .04, conflict_window_s: float = .035,
                 simplified_mode: bool = False):
        self.event_config = dict(event_config or {})
        self.min_y = float(min_y)
        self.max_uncertainty_s = float(max_uncertainty_s)
        self.conflict_window_s = float(conflict_window_s)
        self.simplified_mode = bool(simplified_mode)

    def _trace_gates(self, track: SimpleTrack, now: float, known_keys: set[str]):
        c, p = track.candidate, track.prediction
        pf = track.particle_filter
        cfg = pf.cfg if pf is not None else {}
        legal = set(c.candidate_keys) & set(track.stable_keys) & known_keys
        finite_eta = (p.hit_time is not None and p.eta is not None and p.uncertainty is not None and
                      all(math.isfinite(v) for v in (p.hit_time, p.eta, p.uncertainty)))
        width = (p.eta_p90 - p.eta_p10) if p.eta_p10 is not None and p.eta_p90 is not None else None
        gates = {
            "track_confirmed_current": track.status == "confirmed" and not track.missed,
            "ordinary_tap_confirmed": is_simple_tap(c) and track.confirmed_note_type == "tap",
            "stable_key": bool(track.stable_keys),
            "lane_span_valid": (math.isfinite(c.u_min) and math.isfinite(c.u_max) and
                                0 <= c.u_min < c.u_max <= 1),
            "event_min_y_reached": bool(track.history and track.history[-1][1] >= self.min_y),
            "eta_available_finite": finite_eta,
            "eta_future": bool(finite_eta and p.hit_time > now and p.eta > 0),
            "eta_within_horizon": bool(finite_eta and p.eta <= float(self.event_config.get("max_eta_s", .45))),
            "eta_uncertainty_acceptable": bool(finite_eta and 0 <= p.uncertainty <= self.max_uncertainty_s),
            "verified_covered_key": bool(legal),
            "particle_initialized": bool(pf and pf.initialized),
            "particle_real_observations": bool(pf and p.real_observation_count is not None and
                p.real_observation_count >= int(cfg.get("min_real_observations", 4))),
            "particle_posterior_width": bool(width is not None and math.isfinite(width) and
                width <= float(cfg.get("max_posterior_width_ms", 40)) / 1000),
            "particle_crossing_mass": bool(p.valid_crossing_mass is not None and
                p.valid_crossing_mass >= float(cfg.get("min_valid_crossing_mass", .95))),
        }
        gates["motion_reliable"] = (gates["track_confirmed_current"] and
            gates["ordinary_tap_confirmed"] and gates["stable_key"] and
            len(track.history) >= 3 and p.velocity is not None and
            math.isfinite(p.velocity) and p.velocity > 0)
        gates["timing_reliable"] = (gates["eta_available_finite"] and
            gates["eta_future"] and gates["eta_within_horizon"] and
            gates["eta_uncertainty_acceptable"])
        return gates

    def _reason(self, track: SimpleTrack, now: float, known_keys: set[str]):
        c, p = track.candidate, track.prediction
        if track.status != "confirmed" or track.missed:
            return "track_not_current_confirmed"
        if not is_simple_tap(c) or track.confirmed_note_type != "tap":
            return "not_confirmed_ordinary_tap"
        if not track.stable_keys:
            return "key_not_stable"
        if not math.isfinite(c.u_min) or not math.isfinite(c.u_max) or not (0 <= c.u_min < c.u_max <= 1):
            return "invalid_lane_span"
        if not track.history or track.history[-1][1] < self.min_y:
            return "below_event_min_y"
        if p.hit_time is None or p.eta is None or p.uncertainty is None:
            return p.reason or "eta_unavailable"
        if not all(math.isfinite(v) for v in (p.hit_time, p.eta, p.uncertainty)):
            return "invalid_eta"
        if p.hit_time <= now or p.eta <= 0:
            return "hit_time_not_future"
        if p.eta > float(self.event_config.get("max_eta_s", .45)):
            return "eta_outside_horizon"
        if p.uncertainty < 0 or p.uncertainty > self.max_uncertainty_s:
            return "eta_uncertainty_too_high"
        legal = set(c.candidate_keys) & set(track.stable_keys) & known_keys
        if not legal:
            return "no_stable_verified_covered_key"
        pf = track.particle_filter
        if pf is None or not pf.initialized:
            return "particle_not_initialized"
        cfg = pf.cfg
        if (p.real_observation_count is None or
                p.real_observation_count < int(cfg.get("min_real_observations", 4))):
            return "particle_insufficient_real_observations"
        width = (p.eta_p90 - p.eta_p10) if p.eta_p10 is not None and p.eta_p90 is not None else None
        if width is None or not math.isfinite(width) or width > float(cfg.get("max_posterior_width_ms", 40)) / 1000:
            return "particle_posterior_too_wide"
        if (p.valid_crossing_mass is None or
                p.valid_crossing_mass < float(cfg.get("min_valid_crossing_mass", .95))):
            return "particle_crossing_mass_too_low"
        return ""

    @staticmethod
    def _covered_keys(track: SimpleTrack, legal_keys: set[str]):
        c = track.candidate
        return {key: max(0., min(c.u_max, (KEYS.index(key)+1)/6) -
                         max(c.u_min, KEYS.index(key)/6))
                for key in legal_keys if key in KEYS and key in c.candidate_keys and key in track.stable_keys}

    def plan(self, tracks: list[SimpleTrack], now: float, known_keys: set[str], scheduler,
             *, note_uids: dict[int, str] | None = None,
             fixed_keys: dict[str, str] | None = None):
        """Return proposals and per-track reasons; this never changes scheduler state."""
        note_uids = note_uids or {}
        fixed_keys = fixed_keys or {}
        reasons, proposals = {}, {}
        eligible = []
        self.last_traces = {}
        def reservations_for(owner_uid=None):
            own = scheduler.pending_reservations.get(owner_uid) if owner_uid else None
            recent = [(k, h, owner_uid if own == (k, h) else None)
                      for k, h in scheduler.recent]
            pending = [(intent.keys[0], intent.hit_at, uid)
                       for uid, intent in scheduler.pending.items()]
            return recent + pending
        for track in tracks:
            reason = self._reason(track, now, known_keys)
            uid = note_uids.get(track.track_id, f"simple:{track.track_id}")
            gates = self._trace_gates(track, now, known_keys)
            conflicts = {}
            hit = track.prediction.hit_time
            overlaps = self._covered_keys(track, known_keys)
            for key in KEYS:
                if key not in overlaps:
                    conflicts[key] = "not_covered_or_unverified"
                elif hit is not None and any(other == key and owner != uid and
                                             abs(t-hit) < self.conflict_window_s for other, t, owner in
                          reservations_for(uid)):
                    conflicts[key] = "reserved_same_key_time"
                else:
                    conflicts[key] = ""
            first_possible = track.first_time if all(gates.get(name, False) for name in (
                "track_confirmed_current", "ordinary_tap_confirmed", "stable_key",
                "lane_span_valid", "eta_available_finite", "eta_future",
                "eta_within_horizon", "eta_uncertainty_acceptable", "verified_covered_key",
                "particle_initialized", "particle_real_observations",
                "particle_posterior_width", "particle_crossing_mass")) else None
            last_safe = (hit + scheduler.max_lateness if hit is not None and
                         hasattr(scheduler, "max_lateness") else None)
            quality_gates = [gates[name] for name in ("particle_posterior_width",
                "particle_crossing_mass", "eta_uncertainty_acceptable")]
            timing_quality = sum(quality_gates) / len(quality_gates)
            self.last_traces[track.track_id] = DecisionTrace(uid, track.track_id, gates, reason,
                track.prediction.eta, hit, track.prediction.uncertainty, conflicts,
                first_possible, last_safe, gates["motion_reliable"],
                gates["timing_reliable"], timing_quality)
            if reason:
                reasons[track.track_id] = reason
            else:
                eligible.append((track, uid))

        reservations = reservations_for()
        held = {key: release for key, (release, intent) in scheduler.held.items()
                if intent.note_type == "hold"}
        eligible.sort(key=lambda item: (item[0].prediction.hit_time, item[0].track_id))
        while eligible:
            first_hit = eligible[0][0].prediction.hit_time
            split = 1
            while split < len(eligible) and eligible[split][0].prediction.hit_time - first_hit < self.conflict_window_s:
                split += 1
            group, eligible = eligible[:split], eligible[split:]
            costs, choices = [], []
            unmatched = 100. * (len(group) + 1)
            for track, uid in group:
                hit = track.prediction.hit_time
                overlaps = self._covered_keys(track, known_keys)
                fixed = fixed_keys.get(uid)
                row = []
                trace = self.last_traces[track.track_id]
                own_reservation = scheduler.pending_reservations.get(uid)
                for key in KEYS:
                    conflicts = any(other == key and owner != uid and
                                    own_reservation != (other, t) and
                                    abs(t - hit) < self.conflict_window_s
                                    for other, t, owner in reservations)
                    if fixed and key != fixed:
                        trace.key_conflicts[key] = "intent_key_frozen"
                        row.append(1e9)
                    elif key not in overlaps:
                        trace.key_conflicts[key] = "not_covered_or_unverified"
                        row.append(1e9)
                    elif conflicts:
                        trace.key_conflicts[key] = "reserved_same_key_time"
                        row.append(1e9)
                    elif held.get(key, -math.inf) > hit:
                        trace.key_conflicts[key] = "key_held_through_hit_time"
                        row.append(1e9)
                    else:
                        trace.key_conflicts[key] = ""
                        row.append(1. - overlaps[key] * 6.)
                row.extend([unmatched] * len(group))
                costs.append(row)
                choices.append((track, uid))
            for i, j in assign(costs):
                track, uid = choices[i]
                if j < len(KEYS) and costs[i][j] < unmatched:
                    key = KEYS[j]
                    hit = track.prediction.hit_time
                    reservations.append((key, hit, uid))
                    proposals[track.track_id] = TapProposal(uid, track.track_id, key, hit,
                        float(track.prediction.uncertainty),
                        f"confirmed={track.observations};velocity={track.prediction.velocity:.3f};"
                        f"span={track.candidate.u_min:.6f}:{track.candidate.u_max:.6f}",
                        (track.candidate.u_min, track.candidate.u_max),
                        track.candidate.appearance, track.history[-1][1])
                    reasons[track.track_id] = ""
                else:
                    reasons[track.track_id] = "tap_key_conflict"
                    self.last_traces[track.track_id].final_reason = "tap_key_conflict"
        return proposals, reasons
