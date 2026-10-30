"""Summarize recorded/replayed stage timing without claiming live accuracy."""
from __future__ import annotations
import argparse,csv,json
from collections import Counter
from pathlib import Path
import numpy as np


def rows(path):
    with path.open(newline="",encoding="utf-8-sig") as f:return list(csv.DictReader(f))

def nums(data,key):
    return np.asarray([float(r[key]) for r in data if r.get(key) not in (None,"")],dtype=float)

def stat(a):
    if not len(a):return "n/a"
    return f"mean {np.mean(a):.3f} | P50 {np.percentile(a,50):.3f} | P95 {np.percentile(a,95):.3f} | P99 {np.percentile(a,99):.3f} ms"

def main():
    p=argparse.ArgumentParser();p.add_argument("run_dir",type=Path);args=p.parse_args()
    d=args.run_dir.resolve(); timing=rows(d/"pf_stage_timing.csv")
    original=rows(d/"live_frames.csv"); run=json.loads((d/"live_run.json").read_text(encoding="utf-8-sig"))
    index=rows(d/"live_video_index.csv"); events=rows(d/"live_events.csv")
    replay=json.loads((d/"pf_mock_replay_summary.json").read_text(encoding="utf-8-sig")) if (d/"pf_mock_replay_summary.json").exists() else {}
    playing=[r for r in timing if r.get("gameplay_state")=="PLAYING"]
    full_fields=[("Acquire/queue wait","acquire_queue_wait_ms"),("Normalization/resize/color path","normalization_ms"),
      ("Game state detector","state_detector_ms"),("Note detector","note_detector_ms"),
      ("Tracker matching net of PF","tracker_matching_ms"),("Unknown PF association","unknown_association_ms"),
      ("PF update/prediction","pf_prediction_update_ms"),("LiveEngine decision/scheduler","decision_ms"),
      ("Scheduler poll","scheduler_update_ms"),
      ("Diagnostic queue enqueue","diagnostic_write_ms"),("Overlay render","overlay_ms"),
      ("Replay total processing","processing_ms"),("Decision latency","latency_ms")]
    lines=["# PF Stage Performance Report","",f"Run: `{d.name}`","",
      "The recorded live run is the real-time baseline. Stage timings below come from an offline MockActuator reprocessing of the clean indexed source video. These timings diagnose current code cost; they are not real capture FPS or game accuracy.","",
      "## Original live run","",f"- Capture / processed / dropped: {run['acquired_frames']} / {run['processed_frames']} / {run['dropped_frames']} ({run['dropped_frames']/max(1,run['acquired_frames']):.2%} dropped)",
      f"- Processing FPS: {run['wall_processing_fps']:.2f}; latency P95: {run['latency_p95_ms']:.2f} ms; frames: {len(original)}",
      f"- Actual encoded-frame encoder queue wait: {stat(nums(index,'encoder_queue_wait_ms'))}",
      "- The original run did not record isolated per-stage processing time; total stage attribution cannot be reconstructed from that run's timing logs.","",
      "## Current-code source-video replay (all frames / PLAYING only)","",
      "| Stage (ms) | All replayed frames | PLAYING frames |","|---|---:|---:|"]
    for label,key in full_fields:
        lines.append(f"| {label} | {stat(nums(timing,key))} | {stat(nums(playing,key))} |")
    cand=nums(timing,"candidate_count"); total=nums(timing,"processing_ms"); unknown=nums(timing,"unknown_association_ms")
    def corr(x,y):
        return float(np.corrcoef(x,y)[0,1]) if len(x)==len(y) and len(x)>1 and np.std(x)>0 and np.std(y)>0 else float("nan")
    predictor=Counter(r.get("predictor_mode","UNKNOWN") for r in events)
    unstable=Counter(r.get("predictor_mode","UNKNOWN") for r in events if r.get("abstain_reason")=="unstable_hit_time")
    counts=Counter(r.get("to_state","") for r in rows(d/"pf_identity_transitions.csv"))
    audit_rows=rows(d/"pf_unknown_association_audit.csv")
    accepted=sum(r.get("association_accepted")=="True" for r in audit_rows)
    lines += ["","## Workload and interpretation","",
      f"- Original events by predictor: `{dict(predictor)}`; `unstable_hit_time` by predictor: `{dict(unstable)}`. In this run all 46 unstable-hit candidates were Legacy; they are not PF ETA failures.",
      f"- PF identity transition counts: `{dict(counts)}`; audit rows: {len(audit_rows)}; accepted rows: {accepted}.",
      f"- Current replay candidate-count vs processing-time correlation: {corr(cand,total):.3f}; candidate-count vs unknown-association-time correlation: {corr(cand,unknown):.3f}.",
      f"- The original run wrote {len(audit_rows):,} Unknown-association audit rows. Current Tracker caches each eligible track/candidate score once per pair.",
      "- Diagnostic CSV writes now use a bounded 8,192-row queue and batched writer. Overflow/schema loss is recorded in `pf_diagnostic_health.json`; scheduler/action logs remain synchronous.",
      f"- Mock replay indexed/replayed {replay.get('indexed_frames','UNKNOWN')}/{replay.get('replayed_frames','UNKNOWN')} frames in {replay.get('wall_seconds','UNKNOWN')} s. Events: replay {replay.get('replay_events','UNKNOWN')} vs live {len(events)}; Mock key-down IDs {replay.get('mock_key_down_ids','UNKNOWN')} vs recorded live key-down IDs {replay.get('actual_key_down_ids','UNKNOWN')}. Exact event/UID/frame joins: {replay.get('same_event_identity_rows','UNKNOWN')}; {replay.get('not_comparable_rows','UNKNOWN')} IDs NOT_COMPARABLE. Mock totals are diagnostic only, not a hit-rate comparison.",
      "- No note accuracy conclusion is available. Real game accuracy remains UNVERIFIED.",""]
    (d/"pf_perf_report.md").write_text("\n".join(lines),encoding="utf-8")
    print(f"Wrote {d/'pf_perf_report.md'}")

if __name__=="__main__":main()
