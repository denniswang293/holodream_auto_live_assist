"""Build V7.5.7 evidence artifacts from the existing V7.5.6 run.

The live telemetry CSVs are intentionally schema-only until a new run is made
with diagnostics.live_identity_trace.enabled=true.  No old live rows are
relabelled as fresh telemetry.
"""
from __future__ import annotations

import csv
import json
import math
import platform
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_identity_association_v756 import (  # noqa: E402
    CASES,
    classify_first_unmatched,
    fnum,
    mapping_candidates,
    q,
    read_csv,
    sha256,
    write_csv,
)
from src.live_identity_trace import (  # noqa: E402
    ASSOCIATION_FIELDS,
    CANDIDATE_FIELDS,
    TRACK_FIELDS,
)


RUN = ROOT / "output/assist/run_20261031T181722_597143Z"
TRACE = ROOT / "output/v755_tracker_association"
V756 = ROOT / "output/v756_identity_association"
OUT = ROOT / "output/v757_live_identity"


def empty_schema(path: Path, fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        csv.DictWriter(fh, fieldnames=fields).writeheader()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    live = read_csv(RUN / "live_events.csv")
    index = read_csv(RUN / "live_video_index.csv")
    frames = read_csv(RUN / "live_frames.csv")
    eta = read_csv(RUN / "tap_eta_comparison.csv")
    shadow = read_csv(RUN / "tap_planner_shadow.csv")
    intents = read_csv(RUN / "tap_intents.csv")
    raw_trace_available = all((TRACE / name).exists() for name in (
        "association_audit.csv", "tracker_frame_state.csv",
        "detector_candidate_audit.csv"))
    if raw_trace_available:
        pairs_rows = read_csv(TRACE / "association_audit.csv")
        tracker = read_csv(TRACE / "tracker_frame_state.csv")
        detector = read_csv(TRACE / "detector_candidate_audit.csv")
        alignment = read_csv(TRACE / "frame_alignment_audit.csv")
    else:
        # The raw V7.5.5 trace was removed during project cleanup.  Do not
        # reconstruct pair rows from the summary or label them as new data.
        pairs_rows, tracker, detector = [], [], []
        alignment = read_csv(V756 / "frame_alignment_audit.csv")

    pairs = defaultdict(list)
    for row in pairs_rows:
        pairs[(row["source_video_frame"], row["track_id"])].append(row)
    final_candidates = defaultdict(list)
    for row in detector:
        if row["stage"] == "candidate_final" and row["passed"] == "True":
            final_candidates[row["source_video_frame"]].append(row)
    assigned = defaultdict(set)
    for row in pairs_rows:
        if row["assigned"] == "True":
            assigned[row["source_video_frame"]].add(row["candidate_id"])
    first = (classify_first_unmatched(tracker, pairs, final_candidates, assigned)
             if raw_trace_available else [])

    mapping = read_csv(V756 / "uid_mapping_v756.csv")
    map_by_replay = {r["replay_track_id"]: r for r in mapping if r["replay_track_id"] not in {"UNKNOWN", "AMBIGUOUS"}}
    live_by_uid = defaultdict(list)
    for row in live:
        if row.get("note_uid"):
            live_by_uid[row["note_uid"]].append(row)

    # Frame coverage and UID denominator reconciliation.
    video_frames = [int(r["video_frame"]) for r in index]
    index_source = [int(r["source_video_frame"]) for r in index]
    trace_frames = sorted({int(r["source_video_frame"]) for r in tracker})
    trace_tracks = sorted({r["track_id"] for r in tracker})
    if not raw_trace_available:
        old_reconciliation = read_csv(V756 / "uid_population_reconciliation.csv")
        trace_min = min(int(r["first_source_frame"]) for r in old_reconciliation)
        trace_max = max(int(r["replay_max_source_frame"]) for r in old_reconciliation)
    else:
        trace_min, trace_max = min(trace_frames), max(trace_frames)
    lifecycle_uids = sorted(live_by_uid)
    coverage_rows = [
        {"dataset": "video_frames", "count": len(video_frames), "min_frame": min(video_frames), "max_frame": max(video_frames), "source": str(RUN / "live_source.mp4")},
        {"dataset": "video_index_rows", "count": len(index), "min_frame": min(index_source), "max_frame": max(index_source), "source": str(RUN / "live_video_index.csv")},
        {"dataset": "replay_trace_covered_frames", "count": len(trace_frames) if raw_trace_available else "UNKNOWN", "min_frame": trace_min, "max_frame": trace_max, "source": str(TRACE / "tracker_frame_state.csv") if raw_trace_available else "raw trace missing; range from V7.5.6 reconciliation"},
        {"dataset": "tracker_state_rows", "count": len(tracker) if raw_trace_available else "UNKNOWN", "min_frame": trace_min, "max_frame": trace_max, "source": str(TRACE / "tracker_frame_state.csv") if raw_trace_available else "raw trace missing"},
        {"dataset": "unique_replay_tracks", "count": len(trace_tracks) if raw_trace_available else "UNKNOWN", "min_frame": trace_min, "max_frame": trace_max, "source": str(TRACE / "tracker_frame_state.csv") if raw_trace_available else "raw trace missing"},
        {"dataset": "live_lifecycle_uids", "count": len(lifecycle_uids), "min_frame": min(int(r["source_frame"]) for r in live if r.get("note_uid")), "max_frame": max(int(r["source_frame"]) for r in live if r.get("note_uid")), "source": str(RUN / "live_events.csv")},
    ]
    write_csv(OUT / "frame_coverage_reconciliation.csv", coverage_rows, list(coverage_rows[0]))
    trace_frame_set = set(trace_frames) if raw_trace_available else set(
        range(trace_min, trace_max + 1))
    uid_rows = []
    for uid in lifecycle_uids:
        rows = live_by_uid[uid]
        source_frames = sorted({int(r["source_frame"]) for r in rows})
        covered = sorted(set(source_frames) & trace_frame_set)
        uid_rows.append({
            "note_uid": uid,
            "live_track_id": rows[0]["track_id"],
            "first_source_frame": min(source_frames),
            "last_source_frame": max(source_frames),
            "live_observation_count": len(rows),
            "trace_covered_frame_count": len(covered),
            "trace_first_frame": min(covered) if covered else "",
            "trace_last_frame": max(covered) if covered else "",
            "replay_track_available": bool(covered),
            "reason": "covered_by_replay_frame_range" if covered else "live_uid_outside_replay_trace_frame_range",
        })
    write_csv(OUT / "uid_population_reconciliation_v757.csv", uid_rows, list(uid_rows[0]))

    # Strict first-loss rows and gate margins.
    first_rows = []
    margin_rows = []
    for item in first:
        local_pairs = item["pair_rows"]
        candidate = None
        if item["category"] == "PROBABLE_ASSOCIATION_COMPETITION":
            candidates = [p for p in local_pairs if p["accepted"] == "True" and p["candidate_id"] in assigned.get(item["frame"], set())]
            candidate = min(candidates, key=lambda p: fnum(p.get("total_cost"), 1e9), default=None)
        elif item["category"] == "GATE_REJECTED_WITH_LOCAL_CANDIDATE":
            candidates = [p for p in local_pairs if math.isfinite(fnum(p.get("residual_px"))) or math.isfinite(fnum(p.get("du")))]
            candidate = min(candidates, key=lambda p: (abs(fnum(p.get("residual_px"), 1e9)), abs(fnum(p.get("du"), 1e9)), p["candidate_id"]), default=None)
        elif local_pairs:
            candidate = local_pairs[0]
        m = map_by_replay.get(item["track_id"], {})
        first_rows.append({
            "frame": item["frame"], "capture_timestamp": item["capture_timestamp"],
            "replay_track_id": item["track_id"], "live_uid": m.get("live_uid", "UNKNOWN"),
            "mapping_confidence": m.get("confidence", "UNKNOWN"),
            "classification": item["category"].replace("WITH_LOCAL_CANDIDATE", "LOCAL"),
            "candidate_id": candidate.get("candidate_id", "") if candidate else "",
            "reject_reason": candidate.get("reject_reason", "TRACE_INCOMPLETE") if candidate else "TRACE_INCOMPLETE",
            "total_cost": candidate.get("total_cost", "") if candidate else "",
            "residual_px": candidate.get("residual_px", "") if candidate else "",
            "tolerance_px": candidate.get("tolerance_px", "") if candidate else "",
            "du": candidate.get("du", "") if candidate else "",
            "competition_track_ids": candidate.get("competition_track_ids", "") if candidate else "",
            "terminal_reason": item["termination_reason"],
            "trace_evidence": "association_audit.csv" if candidate else "missing_pair_row",
        })
        if item["category"] == "GATE_REJECTED_WITH_LOCAL_CANDIDATE" and candidate:
            reason = candidate.get("reject_reason", "")
            if reason == "motion_residual":
                value, threshold = fnum(candidate.get("residual_px")), fnum(candidate.get("tolerance_px"))
                metric = "residual_px"; margin = value - threshold
            elif reason == "lane_step_exceeded":
                value, threshold = fnum(candidate.get("du")), .09
                metric = "du"; margin = value - threshold
            elif reason == "backward_motion":
                value, threshold = fnum(candidate.get("dy_px")), -3.5
                metric = "dy_px"; margin = threshold - value
            else:
                value = threshold = margin = math.nan
                metric = "not_numeric"
            margin_rows.append({
                "frame": item["frame"], "capture_timestamp": item["capture_timestamp"],
                "replay_track_id": item["track_id"], "live_uid": m.get("live_uid", "UNKNOWN"),
                "mapping_confidence": m.get("confidence", "UNKNOWN"),
                "candidate_id": candidate["candidate_id"], "first_reject_gate": reason,
                "metric": metric, "value": value, "threshold": threshold,
                "margin_over_threshold": margin, "total_cost": candidate.get("total_cost", ""),
                "evidence": "association_audit.csv",
            })
    first_fields = ["frame", "capture_timestamp", "replay_track_id", "live_uid", "mapping_confidence", "classification", "candidate_id", "reject_reason", "total_cost", "residual_px", "tolerance_px", "du", "competition_track_ids", "terminal_reason", "trace_evidence"]
    write_csv(OUT / "first_unmatched_reclassified_v757.csv", first_rows, first_fields)
    write_csv(OUT / "gate_margin_distribution.csv", margin_rows, list(margin_rows[0]) if margin_rows else ["frame", "capture_timestamp", "replay_track_id", "live_uid", "mapping_confidence", "candidate_id", "first_reject_gate", "metric", "value", "threshold", "margin_over_threshold", "total_cost", "evidence"])

    # Top 20 evidence cases: strict competition first, then local gate, then
    # no-compatible and trace incomplete. This is not a miss ranking.
    priority = {"PROBABLE_ASSOCIATION_COMPETITION": 0, "GATE_REJECTED_LOCAL": 1, "NO_COMPATIBLE_CANDIDATE_NEAR_PREDICTION": 2, "TRACE_INCOMPLETE": 3}
    top = sorted(first_rows, key=lambda r: (priority.get(r["classification"], 9), int(r["frame"])))[:20]
    lines = ["# V7.5.7 Association case top 20", "", "這是追蹤證據優先序，不是 MISS 排名；沒有遊戲判定真值。", ""]
    if not raw_trace_available:
        lines.extend(["RAW V7.5.5 association/tracker/detector CSV 已在清理時移除；本檔不重新列出 V7.5.6 摘要中的 158 個案例，也不偽造 candidate/frame pair。", "", "`PATCH_NOT_JUSTIFIED`; 需恢復同一來源的 raw trace 或重新產生 telemetry 後才能列出 top 20。", ""])
    lines.extend(["| # | frame | replay track | live UID | class | candidate | gate | cost/residual | mapping |", "|---:|---:|---:|---|---|---|---|---|---|"])
    for i, row in enumerate(top, 1):
        cost = row["total_cost"] or (f"residual={row['residual_px']}" if row["residual_px"] else "N/A")
        lines.append(f"| {i} | {row['frame']} | {row['replay_track_id']} | {row['live_uid']} | {row['classification']} | {row['candidate_id'] or 'NONE'} | {row['reject_reason']} | {cost} | {row['mapping_confidence']} |")
    (OUT / "association_case_top20.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # The existing five-case timeline already has the required joined fields;
    # copy it under the V7.5.7 contract without inventing live trace rows.
    v756_timeline = read_csv(V756 / "shadow_five_case_timelines.csv")
    write_csv(OUT / "shadow_five_case_timeline_v757.csv", v756_timeline, list(v756_timeline[0]))
    review_lines = ["# V7.5.7 Physical note review", "", "視覺標註只代表 `VISIBLE_NOTE`；沒有遊戲 Perfect/Great/Miss 真值。", ""]
    review_lines.append("| UID | representative frame | visual status | mapping | reason |")
    review_lines.append("|---|---:|---|---|---|")
    for uid, (frame, keys) in CASES.items():
        full = f"cdaf4ddbea12:simple:{uid}"
        m = next((r for r in mapping if r["live_uid"] == full), {})
        review_lines.append(f"| `{uid}` | {frame} | VISIBLE_NOTE (visual only) | {m.get('confidence', 'UNKNOWN')} | cyan Tap verified in adjacent frames; yellow/FX objects kept separate |")
    review_lines.extend(["", "Pink arrows remain ordinary Tap; no Flick interpretation was added."])
    (OUT / "physical_note_review_v757.md").write_text("\n".join(review_lines) + "\n", encoding="utf-8")

    # Pink regression corpus: 1000005 plus ten single-frame/small-window pink UIDs.
    pink_uids = defaultdict(list)
    for row in live:
        if row.get("appearance") == "pink_candidate" and row.get("note_uid"):
            pink_uids[row["note_uid"]].append(row)
    pink_rows = []
    for uid, rows in sorted(pink_uids.items(), key=lambda item: int(item[1][0]["source_frame"])):
        frames_for_uid = sorted({int(r["source_frame"]) for r in rows})
        pink_rows.append({
            "note_uid": uid, "track_id": rows[0]["track_id"],
            "first_source_frame": min(frames_for_uid), "last_source_frame": max(frames_for_uid),
            "observation_count": len(rows), "appearance": "pink_candidate",
            "candidate_keys": rows[0].get("key_candidates", ""),
            "simple_statuses": "|".join(sorted({r.get("simple_track_status", "") for r in rows})),
            "pink_min_displacement_px": 5,
            "physical_note_status": "UNKNOWN",
            "game_hit_status": "UNKNOWN",
        })
    pink_rows.sort(key=lambda r: (0 if r["track_id"] == "1000005" else 1, int(r["first_source_frame"])))
    write_csv(OUT / "pink_regression_cases.csv", pink_rows[:11], list(pink_rows[0]) if pink_rows else ["note_uid", "track_id", "first_source_frame", "last_source_frame", "observation_count", "appearance", "candidate_keys", "simple_statuses", "pink_min_displacement_px", "physical_note_status", "game_hit_status"])
    crop_dir = OUT / "case_crops"
    crop_dir.mkdir(exist_ok=True)
    for source in (V756 / "case_crops").glob("*.jpg"):
        shutil.copy2(source, crop_dir / source.name)

    # Existing run has no V7.5.7 telemetry.  Emit schemas and an explicit
    # unavailable health record instead of relabelling old live_events.
    empty_schema(OUT / "live_candidate_trace.csv", CANDIDATE_FIELDS)
    empty_schema(OUT / "live_association_attempts.csv", ASSOCIATION_FIELDS)
    empty_schema(OUT / "live_track_identity.csv", TRACK_FIELDS)
    (OUT / "live_identity_trace_health.json").write_text(json.dumps({
        "enabled": False,
        "status": "NOT_AVAILABLE_FOR_EXISTING_RUN",
        "reason": "run_20261031T181722_597143Z was recorded before V7.5.7 live_identity_trace was enabled",
        "schema_ready": True,
        "dropped_diagnostic_rows": None,
        "trace_coverage_frames": 0,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Performance and signature A/B: baseline numbers are real; trace-on
    # performance remains unavailable until a fresh same-input run.
    perf_fields = ["acquire_queue_wait_ms", "note_detector_ms", "tracker_matching_ms", "pf_prediction_update_ms", "decision_ms", "scheduler_update_ms", "processing_ms", "diagnostic_write_ms"]
    perf_rows = []
    for stage in perf_fields:
        vals = [fnum(r.get(stage)) for r in frames]
        vals = [v for v in vals if math.isfinite(v)]
        perf_rows.append({"mode": "baseline_existing_run", "stage": stage, "count": len(vals), "p50_ms": q(vals, .5), "p95_ms": q(vals, .95), "p99_ms": q(vals, .99), "wall_time_status": "available_from_live_frames"})
        perf_rows.append({"mode": "trace_on_same_input", "stage": stage, "count": "", "p50_ms": "", "p95_ms": "", "p99_ms": "", "wall_time_status": "NOT_AVAILABLE_UNTIL_FRESH_LIVE_RUN"})
    write_csv(OUT / "diagnostic_off_on_performance.csv", perf_rows, list(perf_rows[0]))
    ab_path = TRACE / "diagnostic_off_on_ab.json"
    if ab_path.exists():
        ab = json.loads(ab_path.read_text(encoding="utf-8"))
    else:
        old_ab = json.loads((V756 / "v756_ab_summary.json").read_text(encoding="utf-8"))
        ab = dict(old_ab.get("diagnostic_off_on", old_ab))
    (OUT / "diagnostic_signature_ab.json").write_text(json.dumps({**ab, "v757_live_trace_on": "NOT_RUN", "active_planner": False, "legacy_input_path_changed": False}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # No two HIGH-confidence, visible, same-gate physical cases are proven;
    # do not create or run a relaxed association experiment.
    ab_case_fields = ["case_id", "frame", "track_id", "candidate_id", "gate", "baseline_state", "experimental_state", "physical_truth", "result"]
    write_csv(OUT / "local_gate_ab_cases.csv", [], ab_case_fields)
    (OUT / "local_gate_ab_summary.json").write_text(json.dumps({
        "status": "PATCH_NOT_JUSTIFIED",
        "experiment_executed": False,
        "reason": "No two HIGH-confidence, visually verified physical notes share one proven gate failure; live/replay identity telemetry was absent in the existing run.",
        "feature_flag": "tracker.experimental_local_reassociation.enabled",
        "enabled": False,
        "offline_only": True,
        "legacy_input_path": "unchanged",
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "V7_5_7_PATCH_DECISION.md").write_text(
        "# V7.5.7 Patch Decision\n\n"
        "`PATCH_NOT_JUSTIFIED`. Existing evidence does not prove two HIGH-confidence physical notes with the same gate as the sole continuity cause. No local gate experiment was executed; `tracker.experimental_local_reassociation.enabled=false` and `offline_only=true` remain unchanged.\n\n"
        "The next required step is one fresh dry-run/live run with `diagnostics.live_identity_trace.enabled=true`; it must produce candidate, association sentinel, track identity and health CSVs before any local re-association A/B is considered.\n",
        encoding="utf-8")

    manifest = {
        "plan": "V7.5.7_LIVE_IDENTITY_TELEMETRY_AND_GATE_AB_PLAN",
        "baseline_commit": "1a838f679c01616a65ba829e757fb424fb88756e",
        "analysis_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "source_video": str(RUN / "live_source.mp4"),
        "source_video_sha256": sha256(RUN / "live_source.mp4"),
        "video_index": str(RUN / "live_video_index.csv"),
        "video_index_sha256": sha256(RUN / "live_video_index.csv"),
        "config_sha256": sha256(ROOT / "config.json"),
        "geometry_sha256": sha256(ROOT / "config/geometry_live_assist.json"),
        "video_frame_count": len(video_frames),
        "video_frame_range": [min(video_frames), max(video_frames)],
        "index_rows": len(index),
        "trace_covered_frame_count": len(trace_frames) if raw_trace_available else "UNKNOWN",
        "trace_frame_range": [trace_min, trace_max],
        "unique_replay_tracks": len(trace_tracks) if raw_trace_available else "UNKNOWN",
        "live_lifecycle_uids": len(lifecycle_uids),
        "live_trace_status": "SCHEMA_ONLY_UNTIL_FRESH_RUN",
        "raw_v755_trace_available": raw_trace_available,
        "local_gate_patch": "PATCH_NOT_JUSTIFIED",
        "legacy_input_path": "unchanged",
        "feature_flags": {"live_identity_trace": False, "experimental_local_reassociation": False},
        "truth_status": "UNKNOWN",
    }
    (OUT / "v757_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if raw_trace_available:
        first_counts = Counter(r["classification"] for r in first_rows)
    else:
        old_counts = json.loads((V756 / "association_root_cause_counts.json").read_text(encoding="utf-8"))
        first_counts = Counter({
            "PROBABLE_ASSOCIATION_COMPETITION": old_counts.get("first_unmatched_by_track", {}).get("PROBABLE_ASSOCIATION_COMPETITION", 0),
            "GATE_REJECTED_LOCAL": old_counts.get("first_unmatched_by_track", {}).get("GATE_REJECTED_WITH_LOCAL_CANDIDATE", 0),
            "NO_COMPATIBLE_CANDIDATE_NEAR_PREDICTION": old_counts.get("first_unmatched_by_track", {}).get("NO_COMPATIBLE_CANDIDATE_NEAR_PREDICTION", 0),
            "TRACE_INCOMPLETE": old_counts.get("first_unmatched_by_track", {}).get("TRACE_INCOMPLETE", 0),
        })
    report = [
        "# V7.5.7 Live Identity Telemetry / Gate A-B Report", "",
        "本版已完成診斷 telemetry 程式與既有資料的離線根因分析；沒有直接啟用寬鬆 gate，也沒有改變 Legacy 實際輸入路徑。",
        "", "## 基線與分母", 
        f"- source video/index: 1,443 / 1,443 frames（frame 0–1442）。",
        f"- replay tracker trace: {len(trace_frames) if raw_trace_available else 'UNKNOWN'} covered frames（{trace_min}–{trace_max}）、{len(trace_tracks) if raw_trace_available else 'UNKNOWN'} unique replay tracks、{len(tracker) if raw_trace_available else 'UNKNOWN'} state rows。",
        f"- raw association/tracker/detector CSV available for V7.5.7 recomputation: `{raw_trace_available}`; if false, the files were removed during cleanup and the following classification values are preserved V7.5.6 summaries, not re-derived rows.",
        f"- live lifecycle UID: {len(lifecycle_uids)}；以「至少一個 live frame 落在 replay trace 範圍」計算的舊母體為 {sum(bool(set(int(r['source_frame']) for r in live_by_uid[uid]) & trace_frame_set) for uid in lifecycle_uids)}；其餘 19 個確實只出現在 trace 範圍外的 live frame。",
        "- 248/229/19 的逐 UID 首末幀與覆蓋狀態在 `uid_population_reconciliation_v757.csv`，不是用最後一筆事件推論影片末幀。",
        "", "## PR-1 嚴格首次失配分類",
        f"- PROBABLE_IDENTITY_SWITCH / strict competition: {first_counts.get('PROBABLE_ASSOCIATION_COMPETITION', 0)}",
        f"- GATE_REJECTED_LOCAL: {first_counts.get('GATE_REJECTED_LOCAL', 0)}",
        f"- LOCAL_CANDIDATE_ABSENT: {first_counts.get('NO_COMPATIBLE_CANDIDATE_NEAR_PREDICTION', 0)}",
        f"- TRACE_INCOMPLETE: {first_counts.get('TRACE_INCOMPLETE', 0)}",
        "- 這些是 track 事件分母，不是 118 顆已證實漏按。局部 gate 的數值 margin 在 `gate_margin_distribution.csv`。",
        "- strict competition 必須同時滿足 hard gate pass、finite cost、assignment 實際給另一 track；不能只因同 frame 有其他 assignment 就稱被搶走。若 raw trace 缺失，本版不重新宣稱任何新 case。",
        "", "## PR-2/PR-3 五案與粉色回歸",
        "五個 Shadow case 的逐幀資料、候選、PF/ETA、Legacy/Shadow/intent 欄位在 `shadow_five_case_timeline_v757.csv`；畫面裁圖在 `case_crops/`；物理可見標註與遊戲真值分離於 `physical_note_review_v757.md`。",
        "- `1000004` 的 `track_not_current_confirmed`、`below_event_min_y`、`eta_outside_horizon`、`particle_posterior_too_wide` 均保留時間序列，不能只看次數。",
        "- 粉色 `1000005` 加上 10 個短 pink candidate 已列入 `pink_regression_cases.csv`；pink 仍是普通 Tap，`pink_min_displacement_px` 未變。",
        "- 所有 physical_note_status/game_hit_status 在沒有人工/遊戲真值時維持 UNKNOWN。",
        "", "## PR-4 Gate A/B 決策",
        "`PATCH_NOT_JUSTIFIED`。現有 run 沒有兩個 HIGH-confidence、可視真音符、同一具體 gate 且可證明為唯一連續性根因的案例；而且目前工作區已沒有 V7.5.5 raw association/tracker/detector CSV，因此沒有執行 local re-association 實驗。`local_gate_ab_summary.json` 與 `V7_5_7_PATCH_DECISION.md` 已明確記錄，feature flag 預設 OFF、offline-only。",
        "", "## PR-5 Telemetry 與效能驗收",
        "程式已加入預設 OFF 的 bounded async writer：`live_candidate_trace.csv`、`live_association_attempts.csv`、`live_track_identity.csv`、`live_identity_trace_health.json`。目前既有 run 是 V7.5.7 前錄製，這四份檔案只提供 schema/不可用狀態，沒有偽造 live rows。下一次開啟 flag 的新 run 才能驗證 dropped_diagnostic_rows、trace coverage 與 live FPS。",
        "`diagnostic_off_on_performance.csv` 保留既有 run 的實測 baseline P50/P95/P99；trace-on 同輸入的耗時標為 NOT_AVAILABLE，不能把離線 signature parity 當成效能證明。",
        "", "## 安全與測試",
        "- `diagnostic_signature_ab.json`：既有 OFF/ON signature parity 未改變，Shadow Active=false，Legacy input path unchanged。",
        "- `pytest_v757.txt`：本次全量 pytest 結果。",
        "- 沒有遊戲 Perfect/Great/Miss 真值；不把 candidate、FIRED 或 key_down 當命中率。",
        "", "## 下一步實機操作",
        "在 dry-run 或手動 Assist 測試前，將 `config.json` 的 `diagnostics.live_identity_trace.enabled` 暫設 `true`，執行一段 30–60 秒簡單歌曲；結束後確認 health 的 dropped rows 為 0 或可解釋，再把 flag 改回 false。不要開啟 `tracker.experimental_local_reassociation`。",
    ]
    (OUT / "V7_5_7_ROOT_CAUSE_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), "first_unmatched": dict(first_counts), "trace_status": "SCHEMA_ONLY_UNTIL_FRESH_RUN", "patch": "PATCH_NOT_JUSTIFIED"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
