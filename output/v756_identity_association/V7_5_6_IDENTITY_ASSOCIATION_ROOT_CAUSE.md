# HoloDream V7.5.6 Identity / Association Root Cause

本報告只分析既有 live/replay Trace；未修改 matcher、PF、Planner、Scheduler、Hold 或安全門檻。Legacy Planner 仍是唯一實際輸入路徑，Shadow/Linear ETA 保持診斷用途。

## PR-0 基線
- baseline commit: `47e30defdce459b890ae7533e7674a68045e6180`
- source frames: 1443; alignment one-to-one=True; capture timestamp strictly increasing=True
- lifecycle note UID: 248; old replay population: 229; difference: 19 late UIDs after replay frame 1328
- source SHA256: `668542fc3908915aeaacdc29b112072e6b04a629eebcb1587b4edc363f96bc43`
- index SHA256: `bc1127202a1b2331b3bc20b598976aaccb80d00f06c3ed287c081e0d45bd52cf`
- existing diagnostic A/B reports zero candidate/tracker signature changes and `shadow_active=false`; no feature flag was enabled.
- conservative live↔replay mapping: `{'HIGH': 51, 'UNKNOWN': 172, 'MEDIUM': 25}`; one-to-one conflicts are demoted to UNKNOWN.

## PR-1 嚴格分類
舊版 `association_competition` 只代表同畫面某候選被其他 track assigned。本版只有在原 track 的 pair 同時 `accepted=True`、`total_cost` 有限、且該候選實際被另一 track assigned 時才標記 probable competition。
- first matched→unmatched tracks: 158
- PROBABLE_ASSOCIATION_COMPETITION: 10
- GATE_REJECTED_WITH_LOCAL_CANDIDATE: 118
- NO_COMPATIBLE_CANDIDATE_NEAR_PREDICTION: 29
- TRACE_INCOMPLETE: 1
- terminal outcome 分開記錄：`track_expired_max_gap` 103、`track_expired_max_missed` 130；不把 terminal outcome 當第一個根因。

### Pair 分母
- all pair rows: 76603; counts: `{'ACCEPTED': 7559, 'candidate_key_no_intersection': 34554, 'backward_motion': 7382, 'motion_residual': 5818, 'lane_step_exceeded': 16491, 'appearance_family_mismatch': 3102, 'timestamp_gap_or_nonpositive': 1475, 'span_width_ratio': 222}`
- nearest pair groups: 10374; counts: `{'ACCEPTED': 7541, 'candidate_key_no_intersection': 34, 'motion_residual': 704, 'lane_step_exceeded': 523, 'appearance_family_mismatch': 99, 'backward_motion': 1253, 'timestamp_gap_or_nonpositive': 202, 'span_width_ratio': 18}`
- unmatched tracker states: 3234; all-pair reject counts不等於漏按數。

## UID population reconciliation
248 個 lifecycle note UID 中，229 個落在 replay trace 的 source frame 範圍內；差異 19 個全部是 live frame 1340–1411，而 replay trace 最後 frame 是 1328。這是 replay 範圍差異，不是猜測成 identity switch。詳見 `uid_population_reconciliation.csv`。

## PR-2 五案
五個 case 的逐幀資料在 `shadow_five_case_timelines.csv`，來源 montage 在 `case_crops/`，判定在 `shadow_five_case_verdicts.md`。視覺核對僅證明畫面存在音符，不代表遊戲命中。
- 1000004：HIGH mapping，但 PF posterior gate 與 tracker current 狀態同時出現，判定 MULTIPLE_BLOCKERS。
- 1000059：cyan tap 與命中閃光共存，live/replay identity 不足，AMBIGUOUS。
- 1000139：cyan tap 與黃色長條重疊，mapping 不足，AMBIGUOUS。
- 1000140：cyan tap 與黃色長條重疊，mapping 不足，AMBIGUOUS。
- 1000143：可見 cyan tap，但缺乏高信心 live/replay identity，AMBIGUOUS。

## PR-3 決策
本輪沒有足夠的多個 HIGH identity 案例證明單一 matcher/PF gate 是根因，因此不實作演算法修補；任何未來 patch 必須是預設 OFF 的獨立 flag。
| 項目 | 決策 |
|---|---|
| assignment tie-break | 暫不修補；只有少量嚴格 probable competition，尚無可證實 physical identity |
| motion gate | 暫不放寬；局部 gate reject 需下一次 live telemetry |
| PF posterior gate | 不切換 Active；五案不是單一 PF 阻礙的充分證據 |
| detector/overlap | 保留現狀；先補 candidate identity trace |

## PR-4 安全與效能
- `v756_ab_summary.json` 保留既有 OFF/ON signature 結果；`shadow_active=false`，Legacy input path unchanged。
- `v756_performance_comparison.csv` 提供現有 live run 的 Capture/Detector/Tracker/PF/Planner/Scheduler/total P50/P95/P99；沒有同一輸入的 trace-on wall-time，因此該欄標為 `trace_on_perf_not_available`，不虛構改善。
- pytest 結果另存 `pytest_v756.txt`；沒有遊戲判定真值，hit rate 維持 UNKNOWN。

## 最小後續 telemetry patch
live trace 需要每幀保存 `candidate_id`、bbox、observed center、normalized u、appearance、lane，以及零候選/被跳過的 association sentinel row；live/replay 共用 capture timestamp + bbox + lane + appearance correlation key。這些只增加可觀測性，不改任何 gate。
