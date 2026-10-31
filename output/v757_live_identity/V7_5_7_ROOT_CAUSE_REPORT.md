# V7.5.7 Live Identity Telemetry / Gate A-B Report

本版已完成診斷 telemetry 程式與既有資料的離線根因分析；沒有直接啟用寬鬆 gate，也沒有改變 Legacy 實際輸入路徑。

## 基線與分母
- source video/index: 1,443 / 1,443 frames（frame 0–1442）。
- replay tracker trace: UNKNOWN covered frames（205–1328）、UNKNOWN unique replay tracks、UNKNOWN state rows。
- raw association/tracker/detector CSV available for V7.5.7 recomputation: `False`; if false, the files were removed during cleanup and the following classification values are preserved V7.5.6 summaries, not re-derived rows.
- live lifecycle UID: 248；以「至少一個 live frame 落在 replay trace 範圍」計算的舊母體為 229；其餘 19 個確實只出現在 trace 範圍外的 live frame。
- 248/229/19 的逐 UID 首末幀與覆蓋狀態在 `uid_population_reconciliation_v757.csv`，不是用最後一筆事件推論影片末幀。

## PR-1 嚴格首次失配分類
- PROBABLE_IDENTITY_SWITCH / strict competition: 10
- GATE_REJECTED_LOCAL: 118
- LOCAL_CANDIDATE_ABSENT: 29
- TRACE_INCOMPLETE: 1
- 這些是 track 事件分母，不是 118 顆已證實漏按。局部 gate 的數值 margin 在 `gate_margin_distribution.csv`。
- strict competition 必須同時滿足 hard gate pass、finite cost、assignment 實際給另一 track；不能只因同 frame 有其他 assignment 就稱被搶走。若 raw trace 缺失，本版不重新宣稱任何新 case。

## PR-2/PR-3 五案與粉色回歸
五個 Shadow case 的逐幀資料、候選、PF/ETA、Legacy/Shadow/intent 欄位在 `shadow_five_case_timeline_v757.csv`；畫面裁圖在 `case_crops/`；物理可見標註與遊戲真值分離於 `physical_note_review_v757.md`。
- `1000004` 的 `track_not_current_confirmed`、`below_event_min_y`、`eta_outside_horizon`、`particle_posterior_too_wide` 均保留時間序列，不能只看次數。
- 粉色 `1000005` 加上 10 個短 pink candidate 已列入 `pink_regression_cases.csv`；pink 仍是普通 Tap，`pink_min_displacement_px` 未變。
- 所有 physical_note_status/game_hit_status 在沒有人工/遊戲真值時維持 UNKNOWN。

## PR-4 Gate A/B 決策
`PATCH_NOT_JUSTIFIED`。現有 run 沒有兩個 HIGH-confidence、可視真音符、同一具體 gate 且可證明為唯一連續性根因的案例；而且目前工作區已沒有 V7.5.5 raw association/tracker/detector CSV，因此沒有執行 local re-association 實驗。`local_gate_ab_summary.json` 與 `V7_5_7_PATCH_DECISION.md` 已明確記錄，feature flag 預設 OFF、offline-only。

## PR-5 Telemetry 與效能驗收
程式已加入預設 OFF 的 bounded async writer：`live_candidate_trace.csv`、`live_association_attempts.csv`、`live_track_identity.csv`、`live_identity_trace_health.json`。目前既有 run 是 V7.5.7 前錄製，這四份檔案只提供 schema/不可用狀態，沒有偽造 live rows。下一次開啟 flag 的新 run 才能驗證 dropped_diagnostic_rows、trace coverage 與 live FPS。
`diagnostic_off_on_performance.csv` 保留既有 run 的實測 baseline P50/P95/P99；trace-on 同輸入的耗時標為 NOT_AVAILABLE，不能把離線 signature parity 當成效能證明。

## 安全與測試
- `diagnostic_signature_ab.json`：既有 OFF/ON signature parity 未改變，Shadow Active=false，Legacy input path unchanged。
- `pytest_v757.txt`：本次全量 pytest 結果。
- 沒有遊戲 Perfect/Great/Miss 真值；不把 candidate、FIRED 或 key_down 當命中率。

## 下一步實機操作
在 dry-run 或手動 Assist 測試前，將 `config.json` 的 `diagnostics.live_identity_trace.enabled` 暫設 `true`，執行一段 30–60 秒簡單歌曲；結束後確認 health 的 dropped rows 為 0 或可解釋，再把 flag 改回 false。不要開啟 `tracker.experimental_local_reassociation`。
