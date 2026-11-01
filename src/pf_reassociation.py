"""PF-assisted track reacquisition proposal layer.

This module is intentionally diagnostic-only by default.  It scores real
detector candidates against an existing track's particle state, but it never
mutates a track, creates an observation, changes assignment, or schedules
input.  A future active mode must be separately enabled and validated.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


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
