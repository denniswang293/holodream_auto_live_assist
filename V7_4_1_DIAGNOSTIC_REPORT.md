# HoloDream V7.4.1 Tap Pipeline 診斷修正報告

本次以工作目錄中與 V7.4 Beta 1（`231fba1`）相容的程式為基礎完成最小修正；沒有執行 checkout、commit、push，也沒有切換實際輸入路徑。Particle Filter、Intent 去重、Scheduler 安全檢查與 Hold 控制均保留。

## 已完成

- `LinearTimingEstimator` 以最後有效觀測的 timestamp 計算 `hit_at`，並區分 `stale_observation`、`prediction_unavailable`、非正 ETA 和無效運動。
- 新增低 FPS、掉幀、速度變化、過期觀測及 malformed tail 回歸測試。
- Planner 狀態分為 `legacy`、`shadow`、`active`。目前設定仍為 `mode=shadow`、`enabled=false`；Shadow 只讀取資料並計算簡化決策，絕不呼叫 actuator 或 scheduler 送鍵。Active 有獨立 proposal 轉換，但只有 `enabled=true` 且明確設定 `allow_active=true` 才會使用，預設仍可立即回退到 legacy。
- 每個處理影格、每個目前 note UID 都會寫入 `tap_eta_comparison.csv`，不依賴 lifecycle fingerprint。
- 每個 Shadow/legacy 配對決策都會寫入 `tap_planner_shadow.csv`，包含決策狀態、原因、key、hit_at 及是否實際送鍵（Shadow 為 `False`）。

## 回歸驗收

```text
py -m pytest -q
95 passed
```

另以 `py -m compileall -q src tests` 驗證語法。測試涵蓋：

- Linear ETA 的不同 FPS、掉幀、速度變化、過期及 malformed observation。
- Tracker dropout、Tap 重複預約、到期/失焦/停用安全路徑、Hold 放鍵。
- Shadow planner 的獨立決策與「不產生 actuator 呼叫」。

## 最新完整執行資料

來源：`output/run_20261031T021321_930689Z`。這份 run 在本次逐幀 ETA CSV 修正前完成，因此 PF/Linear 對照欄位在該 run 中仍不可用，相關命中率標示 `UNKNOWN`，不回填推論數值。

| 指標 | 數值 | 解讀 |
|---|---:|---|
| 擷取/處理影格 | 2215 / 2063 | 丟棄 152，stale 0 |
| Capture FPS / Processing FPS | 60.470 / 55.407 | 診斷資料，不代表遊戲命中率 |
| Latency P50 / P95 | 14.114 / 31.552 ms | 從 capture 到 decision |
| Tap intent FIRED | 70 | 已送出流程事件，非遊戲成功判定 |
| key_down / key_up | 91 / 91 | 包含 Tap 與 Hold；不是遊戲命中數 |
| deadline amended | 546 | 既有 Tap deadline 修正事件 |
| canceled | 10 | 需要依新 CSV 的 scheduler 原因再分流 |
| neutral_candidate | 558 | 灰色候選獨立統計；其中是否為實體音符仍 `UNKNOWN` |

### 流失分類（目前證據）

- **Detector：UNKNOWN。** 舊 run 有 `neutral_candidate=558`，但沒有遊戲判定標註，不能把候選數當成真值。
- **Tracker：** 主要事件原因為 `track_not_current_confirmed`（967）與 `below_event_min_y`（451）；這些是追蹤/進入事件門檻，不等於 MISS。
- **Planner：** `eta_outside_horizon`（87）、`particle_posterior_too_wide`（36）、`PF_NO_VALID_CROSSING`（34）、`tap_key_conflict`（2）。
- **Scheduler：** `deadline_freeze_window`（42）、`invalid_intent_or_timing`（2）及 `canceled`（10）。需使用新 run 的 `scheduler_result/scheduler_reason` 做逐 UID 終因分類。
- **Actuator：** 舊資料有 91 次 key_down 和 91 次 key_up，沒有 actuator API 失敗記錄；遊戲是否命中為 `UNKNOWN`。

## 下一次實機測試

1. 保持 `config/live_assist.json` 的 `simplified_tap_planner.enabled=false` 與 `mode=shadow`。
2. 啟動 Assist，確認視窗標題、ROI、PLAYING 狀態後按 `Ctrl+Shift+Alt+Q`，放開修飾鍵再開始歌曲。
3. 結束後提供新 run 目錄，優先檢查 `tap_eta_comparison.csv`、`tap_planner_shadow.csv`、`live_key_actions.csv`；不要把 key_down 直接當成 Perfect/MISS。

## 下一版優先三項問題

1. **掉幀與佇列等待。** 證據：最新 run 丟棄 152/2215 影格、處理 FPS 55.407。先用 `live_frames.csv` 的 `acquire_queue_wait_ms`、`processing_ms` 和各 stage 欄位找真正瓶頸。
2. **ETA 修正幅度過大或頻繁。** 證據：546 次 `amended`，遠多於 70 個 Tap FIRED；先用新的 PF vs Linear 逐幀 CSV 判斷是觀測延遲、速度變化還是 scheduler freeze 造成，不先放寬門檻。
3. **Hold/失焦取消的可追溯性。** 證據：10 次 `canceled`、1 次 `input_not_ready`；需要下一次 run 的逐 UID scheduler/actuator 原因及焦點狀態，才能區分真正漏按與安全取消。

所有未具有遊戲判定標註的統計均為診斷 funnel，標記 `UNKNOWN`，不宣稱準確率改善。
