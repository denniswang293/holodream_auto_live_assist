# HoloDream V7.5.3 漏按根因分析

## 分析範圍

- 基準 commit：`da7a67c`。
- 最新完整實機 run：`output/assist/run_20261031T181722_597143Z`。
- 使用：`live_source.mp4`、`live_video_index.csv`、`live_events.csv`、`tap_decisions.csv`、`tap_eta_comparison.csv`、`tap_intents.csv`、`tap_planner_shadow.csv`、`live_key_actions.csv`。
- 本次沒有修改 Detector、Tracker、Particle Filter、Planner 或任何決策門檻。
- `physical_note_status` 與 `game_hit_status` 全部保留為 `UNKNOWN`；`key_down` 只代表程式送出輸入，不代表遊戲 Perfect、命中或 MISS。

## Funnel 解讀

指標是 lifecycle funnel，不是遊戲準確率：

| 階段 | 數量 | 定義 |
|---|---:|---|
| DETECTED | 248 | 248 個獨立 `note_uid` 建立 |
| CONFIRMED | 95 | 95 個 UID 曾達到 confirmed；其中 71 個後續排程、24 個未排程 |
| SCHEDULED | 71 | 71 個 Tap intent 進入 scheduler |
| FIRED | 70 | 70 個 UID 發生 `key_down` |
| EXPIRED | 1 | `cdaf4ddbea12:simple:1000129` |

因此唯一 UID 的終態分布為：153 只停在 DETECTED、24 停在 CONFIRMED、70 FIRED、1 EXPIRED。不能把 178 個非 FIRED UID 直接稱為 MISS。

## 逐顆對應資料

- `physical_note_funnel.csv`：248 個 UID 的首末 frame、capture timestamp、lane/key span、appearance、最高 lifecycle、scheduler 結果、最後原因與證據 frame。
- `miss_cases.csv`：178 個未 FIRED UID，分類為未確認/追蹤不再 current、confirmed 後未排程、ETA gate、過期；每列附 frame、timestamp、UID、lane/key 與 `UNKNOWN` 標籤。
- 由於沒有遊戲畫面判定或人工 `physical_note_id`，Detector 漏檢的「真實物理音符」數量無法從這次 run 單獨反推；CSV 明確保留此限制。

### 未 FIRED 分類

| 分類 | 數量 | 證據 |
|---|---:|---|
| 未達確認 / `track_not_current_confirmed` | 153 | 最高狀態仍 DETECTED，最後 tap decision 為 `track_not_current_confirmed` |
| 已 confirmed 但排程前不再 current | 22 | 最高狀態 CONFIRMED，最後原因 `track_not_current_confirmed` |
| ETA 超出 horizon | 1 | UID `1000219`，最後原因 `eta_outside_horizon` |
| 低於事件最小 y | 1 | UID `1000241`，最後原因 `below_event_min_y` |
| 已排程後過期 | 1 | UID `1000129`，`late_or_key_already_held` |

## Pink Tap

`pink_tap_cases.csv` 共 11 個 pink UID：

- 1 個 FIRED：`cdaf4ddbea12:simple:1000005`，frame 279–412，K，最後 `key_down` frame 412，capture timestamp `677767.2847377`。
- 10 個只停在 DETECTED，均只有單幀 pink candidate，沒有足夠追蹤證據；它們可能是特效或短暫候選，不能直接稱為漏按。

因此本 run 可確認的 pink UID FIRED 數是 **1**，不是 pink 遊戲命中數。

## Deadline amendment

`deadline_amendment_analysis.csv` 包含 71 個 Tap 排程 UID：

- 555 次 amendment，分布於 60 個 UID；另有 11 個 Tap 沒有 amendment。
- 最終 hit time 相對初始值：P50 **-14.56 ms**，P95 **0 ms**，最大提前 **60.08 ms**。
- 單一 UID 的 amendment range：P50 **19.02 ms**，P95 **49.30 ms**，最大 **60.08 ms**。
- 70 個 Tap 有 key-down；key-down 相對最終 deadline：P50 **+2.08 ms**，P95 **+4.03 ms**，範圍 **+0.46 到 +5.26 ms**。
- 唯一過期案例 UID `1000129`：frame 985、capture timestamp `677777.7242012`，K，最終 deadline `677777.722374385`，原因 `late_or_key_already_held`。

這表示送鍵時間相對「最後 deadline」通常很近；不能據此推論遊戲判定成功。較大的 drift 主要發生在排程早期反覆修正階段。

## Legacy Planner vs Simplified Shadow

- `tap_planner_shadow.csv`：10,357 筆逐幀比較。
- Legacy rejected 123 筆：`particle_posterior_too_wide` 84、`tap_key_conflict` 20、`hit_time_not_future` 19。
- 共 21 個 UID 曾出現「Legacy 拒絕、Shadow 可 schedule」：16 個後來仍由 Legacy 路徑排程並 FIRED；5 個最後沒有排程：

  - `1000004` frame 257，`particle_posterior_too_wide`
  - `1000059` frame 615，`particle_posterior_too_wide`
  - `1000139` frame 923，`particle_posterior_too_wide`
  - `1000140` frame 935，`particle_posterior_too_wide`
  - `1000143` frame 963，`particle_posterior_too_wide`

這 5 個是「值得回放」的候選，不是已證實的 MISS；Shadow 仍未送出實際輸入。

## 效能與丟幀背景

- acquired 1,526、processed 1,443、dropped 83、stale 0。
- Capture FPS 58.25，processing FPS 52.06，decision latency P95 30.58 ms。
- 目前資料支持「處理速度低於擷取速度，可能增加 tracker current window 壓力」，但沒有足夠遊戲真值把每一筆 dropped frame 直接歸因成漏按。

## 前三大根因（依證據排序）

1. **Tracker/current gate 流失**：153 個 UID 從 DETECTED 未再達到可排程狀態，另有 22 個 confirmed UID 在排程前變成 `track_not_current_confirmed`。優先做逐 UID association / dropout replay，不要先放寬全域 gate。
2. **Legacy PF posterior gate**：84 次 `particle_posterior_too_wide`；5 個 UID 同時被 Shadow 判為可排程且最後未排程。先做 paired replay 與真值標註，再決定是否需要局部修補。
3. **Deadline 反覆修正與處理落後**：555 次 amendment、P95 deadline range 49.30 ms，加上 processing FPS 低於 capture FPS；唯一已排程未送出的 Tap 是過期/按鍵仍佔用，不是無理由取消。

## 最小修改建議（本次未執行）

1. 針對 153 + 22 個 `track_not_current_confirmed` UID 增加逐幀 association/dropout 原因記錄，先分 Detector 無候選、Tracker association failure、current timeout。
2. 對上述 5 個 Shadow 優勢 UID 做原始影片 paired replay；只有在 physical note 真值確認後，才考慮局部 PF gate 修正。
3. 對 amendment 量最高的 UID 做 ETA 時間線分析，優先降低無效重算與 deadline 抖動，不改安全 freeze window 或整體容忍度。

