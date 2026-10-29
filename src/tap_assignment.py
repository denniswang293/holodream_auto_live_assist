"""One action key per Tap under an explicitly user-confirmed range rule.

This selects actions; it does not verify detections or mutate candidate lanes.
"""
from __future__ import annotations

import math
from .common import KEYS
from .assignment import assign


class AnyCoveredKeyRule:
    conflict_window = .035  # Scheduler's existing same-key separation window.

    def __init__(self,settings,geometry_sha256,key_order):
        if (settings.get("rule")!="any_covered_key" or settings.get("confirmed_by")!="user" or
                not str(settings.get("confirmation","")).strip()):
            raise ValueError("Any-covered-key input needs the user's explicit rule confirmation")
        if settings.get("geometry_sha256")!=geometry_sha256:
            raise ValueError("Assist key rule belongs to a different geometry; update the explicit control profile")
        if settings.get("key_order")!=list(KEYS) or list(key_order)!=list(KEYS):
            raise ValueError("Confirmed key order must be S,D,F,J,K,L")
        self.settings = dict(settings)
        self.commit_horizon = float(settings.get('commit_horizon_ms',0))/1000
        if not 0<=self.commit_horizon<=.1:
            raise ValueError('Near-judgment commit horizon must be between 0 and 100 ms')
        self.allowed_keys = set(KEYS)
        self.bindings = {}

    @classmethod
    def from_config(cls,config,geometry_sha256):
        settings = config.get("live",{}).get("tap_rule",{})
        return cls(settings,geometry_sha256,config["key_map"]) if settings else None

    def metadata(self):
        return {**self.settings,"resolution_basis":"user_confirmed_any_covered_key",
                "recognition_accuracy":"UNVERIFIED"}

    def decide(self,tracks,options,scheduler, *, active_ids=None):
        """Match new simultaneous notes to distinct keys, retaining old choices.

        Options have already passed the usual track/motion/ETA gates. Each
        assignment is locked while its track exists; loss of validity cancels
        rather than retargeting an already scheduled physical key press.
        """
        active = {tr.track_id for tr in tracks} if active_ids is None else active_ids
        self.bindings = {i:key for i,key in self.bindings.items() if i in active}
        decisions,reservations,new = {},[],[]
        # A fragmented horizontal head can produce two confirmed contours.
        # If they have the same color, lane footprint and nearly identical
        # predicted hit/span, treat them as one physical note so range-based
        # assignment cannot turn one cross-lane note into a two-key chord.
        candidates = [tr for tr in tracks if options.get(tr.track_id,((),""))[0] and
                      tr.prediction.hit_time is not None]
        candidates.sort(key=lambda tr:(tr.track_id in self.bindings,
                                       tr.candidate.note_type=='tap',
                                       tr.candidate.score,len(tr.history),-tr.track_id),
                        reverse=True)
        retained_candidates=[]
        for tr in candidates:
            c=tr.candidate
            duplicate=False
            for other in retained_candidates:
                old=other.candidate
                if (c.appearance not in ('cyan_bar','yellow_bar') or
                        c.appearance!=old.appearance or c.candidate_keys!=old.candidate_keys or
                        abs(tr.prediction.hit_time-other.prediction.hit_time)>=self.conflict_window):
                    continue
                width=min(c.u_max-c.u_min,old.u_max-old.u_min)
                overlap=max(0.,min(c.u_max,old.u_max)-max(c.u_min,old.u_min))
                if width>0 and overlap/width>=.90:
                    duplicate=True
                    break
            if duplicate:
                options[tr.track_id]=((),"duplicate_physical_note_candidate")
                self.bindings.pop(tr.track_id,None)
            else:
                retained_candidates.append(tr)
        for tr in sorted(tracks,key=lambda tr:(tr.prediction.hit_time or math.inf,tr.track_id)):
            keys,reason = options[tr.track_id]
            if reason:
                decisions[tr.track_id] = (),reason
                continue
            c = tr.candidate
            if not (math.isfinite(c.u_min) and math.isfinite(c.u_max) and 0<=c.u_min<c.u_max<=1):
                decisions[tr.track_id] = (),"invalid_tap_span"
                continue
            overlaps = {key:max(0.,min(c.u_max,(KEYS.index(key)+1)/6)-max(c.u_min,KEYS.index(key)/6))
                        for key in keys}
            overlaps = {key:value for key,value in overlaps.items() if value>0}
            if not overlaps:
                decisions[tr.track_id] = (),"no_covered_key"
                continue
            previous = self.bindings.get(tr.track_id)
            if previous is not None:
                if previous not in overlaps:
                    lane = KEYS.index(previous)
                    still_visible = (previous in c.candidate_keys and
                                     min(c.u_max,(lane+1)/6)>max(c.u_min,lane/6))
                    decisions[tr.track_id] = (),('assigned_key_temporarily_unstable' if still_visible else
                                                'assigned_key_no_longer_valid')
                elif any(key==previous and abs(hit-tr.prediction.hit_time)<self.conflict_window
                         for key,hit in reservations):
                    decisions[tr.track_id] = (),"tap_key_conflict"
                else:
                    decisions[tr.track_id] = (previous,),""
                    reservations.append((previous,tr.prediction.hit_time))
            else:
                new.append((tr,overlaps))
        # Exclude keys already used by earlier accepted/sent notes. Existing
        # bindings above retain their own reservations and are not reassigned.
        reservations.extend(scheduler.recent)
        reservations.extend((intent.keys[0],intent.hit_at) for intent in scheduler.pending.values())
        held = {key:release for key,(release,_) in scheduler.held.items()}
        while new:
            first_hit = new[0][0].prediction.hit_time
            group = [item for item in new if item[0].prediction.hit_time-first_hit<self.conflict_window]
            new = new[len(group):]
            costs = []
            unmatched = 100.*(len(group)+1)
            for tr,overlaps in group:
                hit = tr.prediction.hit_time
                costs.append([1-overlaps[key]*6 if key in overlaps and
                              held.get(key,-math.inf)<=hit and
                              not any(other==key and abs(t-hit)<self.conflict_window for other,t in reservations)
                              else 1e9 for key in KEYS]+[unmatched]*len(group))
            for i,j in assign(costs):
                tr,_ = group[i]
                if j<len(KEYS) and costs[i][j]<unmatched:
                    key = KEYS[j]
                    self.bindings[tr.track_id] = key
                    reservations.append((key,tr.prediction.hit_time))
                    decisions[tr.track_id] = (key,),""
                else:
                    decisions[tr.track_id] = (),"tap_key_conflict"
        return decisions
