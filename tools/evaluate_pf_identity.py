"""Emit deterministic synthetic PF identity diagnostics (never game accuracy).

The current checkout has no recorded source video/index. This fixture verifies
the identity and frozen-intent path using the production Tracker and MockActuator.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
import time
from types import SimpleNamespace

from src.detector import Candidate
from src.geometry import Playfield
from src.live_input import ActionIntent, MockActuator, TapScheduler
from src.tracker import Tracker


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "assist" / "pf_identity_20261030"


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def candidate(y: float, unknown: bool = False) -> Candidate:
    field = Playfield(28, 346, 374, 352, 36, 684)
    left, right = field.bounds(y)
    u0, u1 = .33, .47
    box = (round(left + u0 * (right-left)), round(y-3), round((u1-u0)*(right-left)), 6)
    return Candidate(box, "neutral_candidate" if unknown else "cyan_bar", .9, u0, u1,
                     ["F"], "unknown" if unknown else "tap", body_bbox=box)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    config = json.loads((ROOT / "config/live_assist_v5.json").read_text(encoding="utf-8-sig"))
    particle = dict(config["predictor"]["particle"])
    particle["identity_continuity"] = config["predictor"]["particle"].get("identity_continuity", {
        "enabled": True, "confirmed_tap_only": True, "allow_degraded_unknown": True,
        "max_degraded_ms": 90, "reject_competing_heads": True,
        "preserve_frozen_key": True, "preserve_original_deadline": True})
    tracker = Tracker({"max_gap_s": .16, "max_missed_frames": 8, "confirm_observations": 4,
                       "key_map": list("SDFJKL")}, 310.5,
                      predictor_mode="particle", particle_cfg=particle, physical_hit_y=352)
    transition_rows, association_rows, eta_rows = [], [], []
    current = []
    tracker_update_ms = []
    pf_update_ms = []
    for frame in range(9):
        t = frame / 60
        degraded = frame in (7, 8)
        y = 140 + frame * 4
        candidates = [candidate(y, degraded)]
        pf_before = tracker.elapsed
        started = time.perf_counter()
        current = tracker.update(candidates, t)
        tracker_update_ms.append((time.perf_counter()-started)*1000)
        pf_update_ms.append(max(0.,tracker.elapsed-pf_before)*1000)
        transition_rows.extend(dict(source_frame=frame, **row)
                               for tr in (*current, *tracker.finished)
                               for row in tr.identity_transitions
                               if not any(x.get("physical_note_uid") == row.get("physical_note_uid") and
                                          x.get("timestamp") == row.get("timestamp") and
                                          x.get("to_state") == row.get("to_state") for x in transition_rows))
        association_rows.extend(dict(source_frame=frame, **row)
                                for row in tracker.last_unknown_association_audit)
        for tr in current:
            if tr.confirmed_note_type != "tap" or tr.particle_filter is None:
                continue
            assoc = tr.last_association or {}
            eta_rows.append({"physical_note_uid": tr.physical_note_uid, "track_id": tr.track_id,
                "source_track_ids": "|".join(map(str,tr.source_track_ids)), "source_frame": frame,
                "capture_timestamp": t, "confirmed_note_type": tr.confirmed_note_type,
                "current_observation_type": tr.current_observation_type, "identity_state": tr.identity_state,
                "particle_predicted_y": tr.prediction.fitted_y, "observed_y": assoc.get("observed_y", ""),
                "innovation_y": assoc.get("innovation_y", ""),
                "association_score": assoc.get("association_score", ""),
                "association_accepted": assoc.get("accepted", ""),
                "measurement_quality": tr.prediction.measurement_quality,
                "measurement_status": tr.prediction.measurement_status,
                "eta_p10": tr.prediction.eta_p10, "eta_p50": tr.prediction.eta_p50,
                "eta_p90": tr.prediction.eta_p90, "hit_at": tr.prediction.hit_time,
                "physical_hit_time": tr.prediction.physical_hit_time,
                "valid_crossing_mass": tr.prediction.valid_crossing_mass, "particle_ess": tr.prediction.ess,
                "coast_ms": tr.prediction.coast_ms, "original_selected_key": "F",
                "original_hit_at": .25, "final_action": "MOCK_PENDING",
                "final_reason": tr.reason})

    # Contrast the former cancel-on-unknown behavior with the fixed-intent path.
    # This is a deterministic synthetic sequence, not a replay from gameplay.
    clock = SimpleNamespace(now=6/60)
    actuator = MockActuator()
    scheduler = TapScheduler("assist", actuator, clock=lambda: clock.now,
                             focus_check=lambda: True, modifiers_check=lambda: False)
    scheduler.armed, scheduler.arm_generation = True, 1
    scheduler.update_context(clock.now, "PLAYING", True, True)
    intent = ActionIntent("synthetic:physical:1", ("F",), .25, .01, "tap")
    accepted = scheduler.offer(intent)
    before = [{"mode":"before_synthetic_prior_logic", "timestamp":7/60,
               "physical_note_uid":"physical:1", "action":"canceled",
               "key":"F", "scheduled_hit":.25,
               "reason":"unknown_candidate_no_tap_track_association"}]
    for frame in (7, 8, 9, 10, 11, 12, 13, 14, 15):
        clock.now = frame / 60
        scheduler.update_context(clock.now, "PLAYING", True, True)
        scheduler.poll()
    after = [{"mode":"after_pf_synthetic_fixture", "timestamp":row[2] if len(row)>2 else .25,
              "physical_note_uid":"physical:1", "action":row[0],
              "key":row[1] if len(row)>1 else "F", "scheduled_hit":.25,
              "reason":"original_intent_retained_once"}
             for row in actuator.calls]
    if not accepted:
        after = [{"mode":"after_pf_synthetic_fixture", "timestamp":6/60,
                  "physical_note_uid":"physical:1", "action":"schedule_rejected",
                  "key":"F", "scheduled_hit":.25, "reason":"mock_scheduler_not_ready"}]
    scheduler.close()
    write_csv(OUT/"pf_identity_transitions.csv", transition_rows,
              ["source_frame","physical_note_uid","track_id","timestamp","from_state","to_state",
               "reason","confirmed_note_type","current_observation_type","evidence_count",
               "association_score","innovation_y","measurement_quality"])
    write_csv(OUT/"pf_unknown_association_audit.csv", association_rows,
              ["source_frame","timestamp","candidate_index","track_id","physical_note_uid",
               "current_observation_type","association_accepted","final_reason","association_score",
               "predicted_y","observed_y","innovation_y","sigma_y","predicted_u","innovation_u",
               "sigma_u","span_overlap","span_width_ratio","key_match","measurement_quality","coast_ms"])
    write_csv(OUT/"pf_hit_eta_diagnostics.csv", eta_rows,
              ["physical_note_uid","track_id","source_track_ids","source_frame","capture_timestamp",
               "confirmed_note_type","current_observation_type","identity_state","particle_predicted_y",
               "observed_y","innovation_y","association_score","association_accepted","measurement_quality",
               "measurement_status","eta_p10","eta_p50","eta_p90","hit_at","physical_hit_time",
               "valid_crossing_mass","particle_ess","coast_ms","original_selected_key","original_hit_at",
               "final_action","final_reason"])
    write_csv(OUT/"pf_before_after_actions.csv", before + after,
              ["mode","timestamp","physical_note_uid","action","key","scheduled_hit","reason"])
    (OUT/"fixture_metadata.json").write_text(json.dumps({
        "classification":"SYNTHETIC_ONLY_NOT_VIDEO_REPLAY",
        "frames":9,"capture_fps":60,"mock_actuator_calls":actuator.calls,
        "tracker_update_ms_median":sorted(tracker_update_ms)[len(tracker_update_ms)//2],
        "tracker_update_ms_max":max(tracker_update_ms),
        "pf_update_ms_median":sorted(pf_update_ms)[len(pf_update_ms)//2],
        "pf_update_ms_max":max(pf_update_ms),
        "source_video_available":False},indent=2)+"\n",encoding="utf-8")
    print(f"Wrote deterministic synthetic diagnostics to {OUT}")


if __name__ == "__main__":
    main()
