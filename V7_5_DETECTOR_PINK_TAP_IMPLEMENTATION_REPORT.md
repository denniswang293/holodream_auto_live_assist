# V7.5 Detector Optimization + Pink Tap 實作報告

基準 commit：`51a6b6c`  
資料：`output/assist/run_20261031T162704_001503Z/live_source.mp4`  
本次沒有修改 stale_context_timeout、安全停止、Hold 按住/釋放規則，也沒有啟用 Simplified Planner Active 或 Linear ETA 輸入路徑。

## 變更摘要

### Detector

- 快取固定 geometry/shape 的 playfield ROI mask。
- 重用 horizontal morphology kernels。
- 增加 optional detector stage profiler，分解 HSV/ROI、Gray/Sobel/Morphology、Contours/Merge、Path mask/contours、Candidate classification。
- 粉色只在 `detector.pink_tap.enabled=true` 時取得 Tap 語意。
- 粉色完整方塊若只超出校正外框不超過 `max_core_trim_px=8`，使用可追溯的 inner core bbox；全域 physical ROI/lane gate 仍保留。
- 新增粉色 rejection count/sample：`geometry_roi`、`shape` 等，含原始 bbox、core bbox、mask 覆蓋率與 frame index。

### Tracker / Tap path

- `pink_candidate` 加入普通 Tap 的 appearance family。
- 仍必須通過原有 motion、速度、PF、ETA、合法鍵、同鍵衝突、Intent 去重及 Scheduler safety gates。
- 沒有新增 Flick、方向鍵或特殊手勢。
- Overlay 標籤改為 `pink/tap`。
- `pink_tap.enabled=false` 可回退到原本 `pink_candidate + unknown` 行為。

## 離線 Detector A/B

同一來源影片、同一 config、同一 Python/OpenCV 環境，各跑 3 次；排除前 30 幀暖機。此 A/B 是 detector replay，不等同實機 FPS。

| 指標 | cache off baseline | cache on optimized | 變化 |
|---|---:|---:|---:|
| Detector P50 | 14.212 ms | 14.102 ms | -0.8% |
| Detector P95 | 21.268 ms | 20.928 ms | -1.6% |
| Detector P99 | 24.941 ms | 24.489 ms | -1.8% |
| Detector wall time（3 runs） | 58.258 s | 57.854 s | -0.7% |

這次局部快取優化有小幅改善，但未達到 20% 的建議目標；因此不能宣稱已解決整體 Processing FPS 落後。原始實機 run 的主要瓶頸仍是 Note Detector 與 queue backlog，應列為下一輪局部優化項目。

Profiler stage CSV：

- `output/assist/v75_detector_cache_off/detector_stage_perf.csv`
- `output/assist/v75_detector_cache_on/detector_stage_perf.csv`

基準/優化 summary：

- `output/assist/v75_detector_cache_off/detector_perf_baseline.json`
- `output/assist/v75_detector_cache_on/detector_perf_optimized.json`

## 粉色音符回放

代表性 frame 285 的粉色框原始 `(432,219,141,21)`，約 90% 以上像素符合粉色 mask；修正後得到：

```text
bbox       = (432, 219, 134, 21)
appearance = pink_candidate
note_type  = tap
keys       = K|L
```

同來源單次 detector replay：

- 202 個 `pink_candidate + tap`
- 95 個 `pink_candidate + unknown`
- 分布於 150 個影格
- 217 個舊版粉色富集 geometry rejection 不再全部卡在外框；只對不超過 8px 的粉色外緣做 core trim

Tracker replay：

- 37 個 pink track IDs 出現
- 3 個 track IDs 達到原有 Tap confirmation 條件
- 未有人工逐顆真值，因此不能把 3 個 confirmed 或任何 key_down 當成遊戲命中率

逐幀/逐 track 輸出：`output/assist/v75_detector_cache_on/pink_track_replay.csv`。其中包含不少未知/短暫候選，必須用人工標註分辨真正音符與粉色特效；目前沒有把它們宣稱為 recall 提升。

## Regression / 安全驗收

```text
py -m pytest -q
106 passed in 2.19s
```

新增覆蓋：

- 粉色箭頭方塊生成 Tap candidate
- frame-285 代表性外框 core trim 與 K/L lane
- `pink_tap.enabled=false` 回退
- 靜態粉色效果不會被 SimpleTracker 確認為 Tap
- 原有 cyan/yellow/neutral/green、Hold、dropout、Scheduler 與安全釋放測試

## 尚未完成 / 限制

- 尚未有粉色音符人工 bounding-box、lane、出現/離開時間與遊戲 Perfect/Great/Miss 標註，因此粉色 recall、precision、實際命中率均為 `UNKNOWN`。
- 尚未完成新的實機 baseline/new 2–3 次對照；離線 detector A/B 不可直接替代實機 Processing FPS。
- CSV logging、overlay render、encoder 的 per-frame 實際耗時仍未完全分離；目前只有 encoder queue wait 可由 `live_video_index.csv` 取得。
- HWND/PID focus telemetry 不在本次範圍內，仍只能依 `focused` 欄位分析。

## 回退方式

在 `config.json` 的 `detector` 區塊將：

```json
"pink_tap": {"enabled": false}
```

改為停用粉色 Tap 語意；Detector cache 可保留，不會改變 Legacy 的其他輸入路徑。若要完全回到粉色修改前，回退 `src/detector.py`、`src/simple_tracker.py`、`src/overlay.py` 與相關測試/工具即可；不要改動 stale 或 Hold safety 設定。

## 下一次實機測試要蒐集

1. 使用相同歌曲與視窗，記錄 `live_run.json`、`live_frames.csv`、`live_key_actions.csv`。
2. 保留 `tap_eta_comparison.csv`、`tap_planner_shadow.csv`、`pink_track_replay.csv` 或等效粉色候選表。
3. 針對每顆粉色音符人工標註：是否真音符、lane、是否普通 Tap、遊戲判定；沒有標註時維持 `UNKNOWN`。
4. 比較 Processing/Capture FPS、dropped frames、Detector P95/P99、pink UID continuity、誤觸與安全停用；Legacy 仍是唯一真實輸入路徑。
