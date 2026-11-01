"""PF-assisted track reacquisition proposal layer.

This module is intentionally diagnostic-only by default.  It scores real
detector candidates against an existing track's particle state, but it never
mutates a track, creates an observation, changes assignment, or schedules
input.  A future active mode must be separately enabled and validated.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from collections import defaultdict


@dataclass(frozen=True)
class PFReassociationConfig:
    enabled: bool = False
    mode: str = "shadow"
    offline_only: bool = True
    require_real_candidate: bool = True
    allow_coasting_to_fire: bool = False
    preserve_hard_gates: bool = True
    min_score_margin: float = 0.50

    @classmethod
    def from_dict(cls, data: dict | None) -> "PFReassociationConfig":
        raw = dict(data or {})
        mode = str(raw.get("mode", "shadow")).lower()
        if mode not in {"shadow", "active"}:
            mode = "shadow"
        # V7.8.4 is an offline/Shadow-only experiment.  Even an accidental
        # active-mode flag must not become an input path.
        if bool(raw.get("offline_only", True)):
            mode = "shadow"
        return cls(
            enabled=bool(raw.get("enabled", False)), mode=mode,
            offline_only=bool(raw.get("offline_only", True)),
            require_real_candidate=bool(raw.get("require_real_candidate", True)),
            allow_coasting_to_fire=bool(raw.get("allow_coasting_to_fire", False)),
            preserve_hard_gates=bool(raw.get("preserve_hard_gates", True)),
            min_score_margin=max(0.0, float(raw.get("min_score_margin", .50))),
        )


class PFAssistedReassociation:
    """Create auditable, non-mutating PF-to-candidate proposals."""

    def __init__(self, config: dict | None = None):
        self.config = PFReassociationConfig.from_dict(config)

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    def propose(self, tracks: list, candidates: list, timestamp: float,
                *, assigned_candidate_ids: set[str] | None = None) -> list[dict]:
        """Return proposal rows; no row is an input decision.

        A row is emitted for each real candidate/track pair considered, plus
        sentinels for missing PF state or missing candidates.  Candidates
        already assigned by the legacy matcher are only evidence for the
        competitor field and are never taken over by this layer.
        """
        if not self.enabled:
            return []
        assigned = set(assigned_candidate_ids or ())
        rows: list[dict] = []
        if not tracks:
            return [{"decision": "NO_ACTIVE_TRACK", "reason": "no_active_track",
                     "timestamp": timestamp, "old_uid": "", "candidate_id": ""}]
        if not candidates:
            return [{"decision": "NO_REAL_CANDIDATE", "reason": "no_real_candidate",
                     "timestamp": timestamp, "old_uid": track.physical_note_uid,
                     "track_id": track.track_id, "candidate_id": ""}
                    for track in tracks]
        for track in tracks:
            uid = track.physical_note_uid
            pf = getattr(track, "particle_filter", None)
            if pf is None or not getattr(pf, "initialized", False):
                rows.append(self._sentinel(track, "PF_STATE_UNAVAILABLE", "pf_state_unavailable", timestamp))
                continue
            scored = []
            for candidate in candidates:
                candidate_id = getattr(candidate, "diagnostic_id", "")
                result = pf.identity_association_score(
                    candidate, timestamp,
                    (track.candidate.u_min, track.candidate.u_max),
                    track.stable_keys, track.selected_key,
                    allow_pinned_key=False,
                    allow_confirmed_candidate=True,
                )
                row = {
                    "timestamp": timestamp, "old_uid": uid, "track_id": track.track_id,
                    "candidate_id": candidate_id, "candidate_appearance": candidate.appearance,
                    "candidate_note_type": candidate.note_type,
                    "candidate_keys": "|".join(candidate.candidate_keys),
                    "pf_predicted_y": result.get("predicted_y", ""),
                    "pf_predicted_u": result.get("predicted_u", ""),
                    "pf_sigma_y": result.get("sigma_y", ""),
                    "pf_sigma_u": result.get("sigma_u", ""),
                    "pf_association_score": result.get("association_score", ""),
                    "coast_ms": result.get("coast_ms", ""),
                    "gate_result": "accepted" if result.get("accepted") else "rejected",
                    "reason": result.get("reason", "unknown"),
                    "competitor_track_ids": "", "decision": "PAIR_REJECTED",
                    "real_candidate": True, "input_sent": False,
                }
                scored.append((row, result))
            accepted = [(row, result) for row, result in scored
                        if result.get("accepted") and row["candidate_id"] not in assigned]
            accepted.sort(key=lambda item: float(item[1].get("association_score", math.inf)))
            if not accepted:
                rows.extend(row for row, _ in scored)
                continue
            best_row, best_result = accepted[0]
            second_score = float(accepted[1][1].get("association_score", math.inf)) if len(accepted) > 1 else math.inf
            best_score = float(best_result.get("association_score", math.inf))
            margin = second_score - best_score
            competitors = [str(other.track_id) for other in tracks
                           if other.track_id != track.track_id and
                           any(item[0].get("candidate_id") == best_row["candidate_id"]
                               for item in self._score_track(other, candidates, timestamp))]
            best_row["competitor_track_ids"] = "|".join(competitors)
            best_row["score_margin"] = margin if math.isfinite(margin) else ""
            if best_row["candidate_id"] in assigned:
                best_row.update(decision="REJECTED_CANDIDATE_IN_USE", reason="candidate_in_use")
            elif competitors:
                best_row.update(decision="REJECTED_COMPETITION", reason="candidate_competition")
            elif len(accepted) > 1 and margin < self.config.min_score_margin:
                best_row.update(decision="REJECTED_AMBIGUOUS", reason="best_second_margin_too_small")
            else:
                best_row.update(decision="SHADOW_REACQUIRE_PROPOSAL", reason="pf_real_candidate_match")
            rows.extend(row for row, _ in scored if row is not best_row)
            rows.append(best_row)
        return rows

    def propose_targeted(self, tracks: list, candidates: list, timestamp: float,
                         *, assigned_candidate_ids: set[str] | None = None) -> list[dict]:
        """Score only post-Legacy unmatched tracks against real candidates.

        This is the V7.8.4 rescue path.  It is deliberately non-mutating: the
        caller supplies the Legacy assignment result, and this method only
        returns auditable rows.  A candidate already used by Legacy is retained
        as a negative-control row and can never become a proposal.
        """
        if not self.enabled:
            return []
        assigned = set(assigned_candidate_ids or ())
        rows: list[dict] = []
        eligible = []
        for track in tracks:
            pf = getattr(track, "particle_filter", None)
            confirmed = bool(getattr(track, "was_confirmed", False) or
                             getattr(track, "confirmed_note_type", None) == "tap")
            history_ok = len(getattr(track, "history", ())) >= max(3, getattr(self.config, "min_history", 3))
            coast_ms = max(0., (timestamp - float(getattr(track, "last_time", timestamp))) * 1000.)
            if (confirmed and history_ok and pf is not None and
                    getattr(pf, "initialized", False) and coast_ms <= pf.max_coast_s * 1000 and
                    getattr(track, "status", "") != "completed" and
                    not getattr(track, "input_completed", False)):
                eligible.append(track)
            else:
                rows.append(self._sentinel(track, "NOT_ELIGIBLE", "rescue_track_not_eligible", timestamp))
        if not eligible:
            return rows
        if not candidates:
            for track in eligible:
                rows.append(self._sentinel(track, "NO_REAL_CANDIDATE", "no_real_candidate", timestamp))
            return rows
        scored: dict[int, list[tuple[dict, dict]]] = {}
        for track in eligible:
            pair_rows = []
            for candidate in candidates:
                cid = getattr(candidate, "diagnostic_id", "")
                if cid in assigned:
                    pair_rows.append((self._pair_row(track, candidate, timestamp, "BASELINE_ALREADY_MATCHED", "already_legacy_assigned", legacy_unmatched=False), {}))
                    continue
                pf = track.particle_filter
                result = pf.identity_association_score(
                    candidate, timestamp,
                    (track.candidate.u_min, track.candidate.u_max),
                    track.stable_keys, track.selected_key,
                    allow_pinned_key=False, allow_confirmed_candidate=True,
                )
                pair_rows.append((self._pair_row(track, candidate, timestamp, "PAIR_REJECTED", result.get("reason", "unknown"), legacy_unmatched=True, result=result), result))
            scored[track.track_id] = pair_rows
            rows.extend(pair for pair, _ in pair_rows)
        accepted: list[tuple[object, dict, dict]] = []
        for track in eligible:
            for row, result in scored[track.track_id]:
                if result.get("accepted") and row.get("candidate_id") not in assigned:
                    accepted.append((track, row, result))
        # Deterministic global one-to-one matching.  A candidate with a near
        # tie is rejected for every competing track rather than arbitrarily
        # handed to whichever track happened to be iterated first.
        by_candidate: dict[str, list[tuple[object, dict, dict]]] = defaultdict(list)
        for item in accepted:
            by_candidate[item[1]["candidate_id"]].append(item)
        winners: list[tuple[object, dict, dict]] = []
        for cid, options in sorted(by_candidate.items()):
            options.sort(key=lambda item: (float(item[2].get("association_score", math.inf)), int(item[0].track_id)))
            best = options[0]
            margin = (float(options[1][2].get("association_score", math.inf)) -
                      float(best[2].get("association_score", math.inf))) if len(options) > 1 else math.inf
            if len(options) > 1 and margin < self.config.min_score_margin:
                for track, row, result in options:
                    row.update(decision="REJECTED_AMBIGUOUS", reason="best_second_margin_too_small",
                               competitor_track_ids="|".join(str(x[0].track_id) for x in options),
                               score_margin=margin, legacy_unmatched=True)
                continue
            winners.append(best)
            best[1].update(decision="INCREMENTAL_SHADOW_REACQUIRE_PROPOSAL", reason="pf_real_candidate_match",
                           score_margin=margin, legacy_unmatched=True, input_sent=False)
            for track, row, result in options[1:]:
                row.update(decision="REJECTED_COMPETITION", reason="candidate_competition",
                           competitor_track_ids="|".join(str(x[0].track_id) for x in options),
                           score_margin=float(result.get("association_score", math.inf)) - float(best[2].get("association_score", math.inf)),
                           legacy_unmatched=True)
        # Apply per-track second-best margin only to rows that otherwise won a
        # candidate; never turn a baseline match into a rescue result.
        for track, row, result in winners:
            own = sorted((r for r, v in scored[track.track_id] if v.get("accepted") and r.get("candidate_id") not in assigned),
                         key=lambda r: float(r.get("pf_association_score", math.inf)))
            if len(own) > 1:
                margin = float(own[1].get("pf_association_score", math.inf)) - float(own[0].get("pf_association_score", math.inf))
                if margin < self.config.min_score_margin:
                    row.update(decision="REJECTED_AMBIGUOUS", reason="track_best_second_margin_too_small", score_margin=margin)
        return rows

    @staticmethod
    def _pair_row(track, candidate, timestamp: float, decision: str, reason: str,
                  *, legacy_unmatched: bool, result: dict | None = None) -> dict:
        result = result or {}
        return {
            "timestamp": timestamp, "old_uid": track.physical_note_uid, "track_id": track.track_id,
            "candidate_id": getattr(candidate, "diagnostic_id", ""), "candidate_appearance": candidate.appearance,
            "candidate_note_type": candidate.note_type, "candidate_keys": "|".join(candidate.candidate_keys),
            "candidate_bbox": candidate.bbox, "pf_predicted_y": result.get("predicted_y", ""),
            "pf_predicted_u": result.get("predicted_u", ""), "pf_sigma_y": result.get("sigma_y", ""),
            "pf_sigma_u": result.get("sigma_u", ""), "innovation_y": result.get("innovation_y", ""),
            "innovation_u": result.get("innovation_u", ""), "observed_y": result.get("observed_y", ""),
            "span_overlap": result.get("span_overlap", ""), "span_width_ratio": result.get("span_width_ratio", ""),
            "pf_association_score": result.get("association_score", ""), "coast_ms": result.get("coast_ms", ""),
            "gate_result": "accepted" if result.get("accepted") else "rejected", "decision": decision,
            "reason": reason, "legacy_unmatched": legacy_unmatched, "real_candidate": True,
            "input_sent": False, "competitor_track_ids": "", "score_margin": "",
        }

    @staticmethod
    def _sentinel(track, decision: str, reason: str, timestamp: float) -> dict:
        return {"timestamp": timestamp, "old_uid": track.physical_note_uid,
                "track_id": track.track_id, "candidate_id": "", "decision": decision,
                "reason": reason, "real_candidate": False, "input_sent": False}

    def _score_track(self, track, candidates, timestamp):
        pf = getattr(track, "particle_filter", None)
        if pf is None or not getattr(pf, "initialized", False):
            return []
        scored = []
        for candidate in candidates:
            result = pf.identity_association_score(
                candidate, timestamp, (track.candidate.u_min, track.candidate.u_max),
                track.stable_keys, track.selected_key, allow_confirmed_candidate=True)
            scored.append(({"candidate_id": getattr(candidate, "diagnostic_id", "")}, result))
        return scored
