# HoloDream V7.4.2 最小修補報告

基礎 commit：`7c22768`（V7 Beta 2）。本次只做診斷與 gate 修補，沒有大規模重構、沒有新增演算法，也沒有啟用 Active Planner。

## 修補內容

### 1. LinearTimingEstimator

- `hit_at` 以最後有效觀測 timestamp 加上觀測推算出的到達時間。
- `eta` 改為相對於目前 `capture_ts` 的剩餘時間。
- 掉幀時不把 capture timestamp 當成最後觀測時間。
- 已過期預測回傳 `expired_prediction`，保留預測的 `hit_at` 供診斷，但不提供可用 ETA。
- 保留 stale observation、非正運動與無效 ETA 的安全拒絕。

### 2. tap_deadline_amend 設定

`SimpleAssistCore` 現在優先讀取巢狀設定：

```json
"tap_deadline_amend": {
  "enabled": true,
  "freeze_window_ms": 30,
  "max_amend_step_ms": 40,
  "max_total_amend_ms": 80
}
```

四個欄位會正確傳入 `TapIntentManager`；同時保留既有扁平欄位相容性。

### 3. Simplified Planner Shadow gates

補上以下檢查：

- 必須是已確認的普通 Tap，Hold 不會被當成 Tap。
- candidate/stable/known key 的交集必須存在。
- 固定鍵若不在合法鍵集合中直接拒絕。
- 已由 Hold 佔用到 hit time 的鍵拒絕。
- 同鍵時間衝突拒絕。

Shadow 只計算決策與原因，不呼叫 actuator；Legacy 仍是實際輸入路徑。設定仍為 `simplified_tap_planner.enabled=false`、`mode=shadow`。

## 驗收

```text
py -m pytest -q
101 passed in 2.08s
```

新增/補強測試涵蓋：

- 掉幀後 ETA 與最後有效觀測 timestamp
- 已過期預測
- 巢狀 amend 設定傳遞
- Simplified Planner 的 Tap/合法鍵/固定鍵/Hold 佔用/同鍵衝突 gate
- 原有 Particle Filter、Intent 去重、Scheduler、Hold 與安全釋放測試

沒有進行實機輸入測試，因此本報告不宣稱遊戲命中率改善。
