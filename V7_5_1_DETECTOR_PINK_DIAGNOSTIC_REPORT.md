# HoloDream V7.5.1 Detector / Pink Tap 診斷報告

## 範圍

- 基準：`d368b10`（工作樹未執行 Git push）。
- 來源：`output/assist/run_20261031T162704_001503Z/live_source.mp4`，1,355 幀，60 FPS。
- 回放時間使用 `live_video_index.csv` 的 `source_video_frame -> capture_timestamp`；沒有再用固定 `frame / 60` 當事件時間。
- 本次沒有改幾何、ETA 門檻、Legacy Planner、Scheduler 安全門或 Hold 流程。

## A. Pink track 根因

基線檔 `pink_track_replay.csv`（舊版固定 60 FPS）有 316 筆、37 個 pink UID、3 個曾進入 confirmed。以真實 capture timestamp 重播後仍是 37 個 UID；加入本次粉色專用的最小實際位移門檻後為 361 筆、37 個 UID、1 個 confirmed UID。這些數字是 tracker 狀態，不是遊戲命中率。

| 證據 | 結果 |
|---|---:|
| 具長時間連續性的實體粉色 Tap（track 6） | 103 次觀測、約 2,321.8 ms、frame 183–311，保持 confirmed |
| 主要終止原因 | 22 個到達實體完成線；15 個 `track_expired` |
| `track_expired` 最後狀態 | `no_current_observation`，不是 ETA 或 scheduler 取消 |
| lost 列中完全沒有 pink candidate | 75 / 144 列 |
| 有 candidate 但全為 `unknown` | 31 / 144 列 |
| 有同幀可疑 tap candidate 的 lost 列 | 38 列；以相同 key、鄰近位置再縮小後 18 列屬於「可能 association competition」，沒有人工真值不能定成漏按 |

逐幀檢查顯示 frame 285 的粉色箭頭音符能形成 `pink_candidate/tap`，並沿 track 6 穩定追蹤。frame 887–1,041 一帶多數粉色長條停留在判定線附近，位移只有 0–3 px；這類畫面特效曾讓 track 215 以微小抖動達到速度門檻而被誤確認。這不是降低全域 confirmation 的理由。每個 UID 的觀測數、時間跨度、最後原因與 `nearby_uid_rebuild` 已輸出到 `pink_track_replay_v751_summary.csv`。

### 修正

`SimpleTracker` 只對 `pink_candidate` 增加既有 `min_displacement_px`（預設 5 px）的實際垂直位移檢查；一般 cyan/yellow/neutral、Legacy、Hold 完全不變。track 6 通過此檢查；判定線附近 3 px 漂移的效果不再 confirmed。`pink_min_displacement_px=0` 可回退此單一修正。

回放仍將粉色 Tap 送入原有 `SimpleTracker -> SimpleAssistCore/Planner -> Intent -> Scheduler` 路徑；離線工具本身不送按鍵。

## B. Detector 第二階段效能

瓶頸是 `candidate_classification` 的 Hold path-depth 全畫面掃描。普通 Tap 沒有 `path_bbox` 時不再呼叫 `path_depth`；只有已找到 path contour 的候選仍計算 Hold 深度，因此沒有以降低偵測率換 FPS。

### Detector A/B（同一來源、cache on、3 repeats；warm-up 30 幀排除）

| 指標 | 優化前 | V7.5.1 | 變化 |
|---|---:|---:|---:|
| detector P50 (ms) | 14.1022 | 13.9537 | -1.05% |
| detector P95 (ms) | 20.9278 | 20.5364 | -1.87% |
| detector P99 (ms) | 24.4894 | 24.3069 | -0.75% |
| candidate_classification P50 (ms) | 2.5401 | 2.4982 | -1.65% |
| candidate_classification P95 (ms) | 8.0911 | 7.8915 | -2.47% |
| candidate_classification P99 (ms) | 11.0290 | 11.0273 | -0.02% |
| total candidates (3 repeats) | 35,793 | 35,793 | unchanged |
| pink candidates / pink taps | 891 / 606 | 891 / 606 | unchanged |

benchmark 現在把 `cap.read()` 解碼時間獨立計算：V7.5.1 detector 累計 54.671 s、decode 2.237 s、完整 wall time 57.005 s；`detector_wall_seconds_excluding_decode` 已不再誤標整段影片解碼時間。

## 驗收

- `py -m pytest -q`：**108 passed**。
- 新增回歸：粉色判定線小位移不確認、真實移動粉色 Tap 仍確認。
- pink candidate 數、pink tap 數未下降；track 6 continuity 未下降。
- 未宣稱遊戲命中率；candidate、confirmed UID、key_down 都不是遊戲判定。
- 未改送鍵高度、全域容忍度、幾何或 Hold 控制。

## 修改檔案

- `src/detector.py`：只跳過無 path 的普通 Tap path-depth 掃描。
- `src/simple_tracker.py`：粉色專用實際位移防止判定線特效誤確認。
- `config.json`：`tracker.pink_min_displacement_px = 5`，可設為 0 回退。
- `tools/benchmark_detector_v75.py`：分離 detector、decode、完整 wall time。
- `tools/replay_pink_tracker_v75.py`：讀取真實 capture timestamp、輸出 UID summary 與終止原因。
- `tests/test_simple_core.py`：新增兩個粉色回歸測試。

## 下一步優先項

1. 對 887–1,041 的判定線粉色畫面建立人工 `physical_note_id` 標註，確認哪些是特效、哪些是真音符。
2. 對 18 個「同 key、鄰近候選」案例做逐幀人工檢查，再決定是否需要 pink-specific association 修補；目前證據不足，不放寬 association gate。
3. 若要再降 Detector tail，先針對 `candidate_classification` 的 profile 長尾取樣；不得改變 cyan/yellow/neutral/pink/green/Hold 的偵測結果。

