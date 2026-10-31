# V7.5.5.2 Association Root-Cause Report

分析基準：`output/v755_tracker_association/`（V7.5.5.1 replay trace）、
`output/assist/run_20261031T181722_597143Z/`（同一來源影片、索引與 live CSV）。

本輪只讀取既有 Trace CSV；沒有重新執行 detector/tracker，也沒有修改
Legacy Planner、Particle Filter、Scheduler、Hold 或安全停止條件。

## 1. `association_audit.csv` 統計

共有 76,603 個 pair rows；7,559 個 pair 被接受，69,044 個被拒絕。拒絕成本欄位在 gate 拒絕時刻意寫成 `INF`，所以不能把 `INF` 當成可比較的幾何距離。

### 全部 pair

| reject_reason | count |
|---|---:|
| candidate_key_no_intersection | 34,554 |
| lane_step_exceeded | 16,491 |
| backward_motion | 7,382 |
| motion_residual | 5,818 |
| appearance_family_mismatch | 3,102 |
| timestamp_gap_or_nonpositive | 1,475 |
| span_width_ratio | 222 |
| accepted（空白 reject_reason） | 7,559 |

### 每個 track/frame 的最近候選 pair

共 10,374 個 track/frame groups。先取有限 `total_cost` 的最小值；整組沒有有限成本時，依 `residual_px`、`abs(dy_px)`、`abs(du)`、candidate ID 排序。這個定義只表示 trace 中的「最近候選」，不表示遊戲真值。

| reject_reason | count |
|---|---:|
| candidate_key_no_intersection | 1,295 |
| lane_step_exceeded | 647 |
| backward_motion | 416 |
| timestamp_gap_or_nonpositive | 202 |
| motion_residual | 150 |
| appearance_family_mismatch | 107 |
| span_width_ratio | 16 |
| accepted | 7,541 |

最近候選仍以 `candidate_key_no_intersection` 和 `lane_step_exceeded` 為主；這是 lane/association gate 的拒絕分布，不是建議放寬 gate 的證據。

## 2. Unmatched 與 Tracker lost 前第一個異常

`tracker_frame_state.csv` 有 3,234 個 `matched_this_frame=False` 狀態，涵蓋 242 個 replay track。分類規則如下：

- 有 pair 且該 candidate 在同一 frame 被另一 track assigned：`association_competition`。
- 沒有 pair，但 detector 有 `candidate_final`：`trace_gap_with_detector_candidate`（候選存在，association trace 沒有記錄該 track 的 pair；不能誤稱 detector 漏檢）。
- 有 pair、沒有 assigned/competition，且有 `candidate_final`：`candidate_gate_rejected`。
- 該 frame 沒有 `candidate_final`：`detector_no_candidate`。
- `track_expired_max_gap` 另作 terminal outcome，不當成第一個根因。

### 所有 unmatched 狀態

| 分類 | count |
|---|---:|
| association_competition | 2,990 |
| trace_gap_with_detector_candidate | 244 |
| candidate_gate_rejected | 0 |
| detector_no_candidate | 0 |

這份 trace 中，每個 unmatched frame 都仍有至少一個 `candidate_final`；因此不能支持「Detector 沒有候選」或「候選被 gate 全部拒絕」的結論。244 筆是 instrumentation gap：detector 有候選，但該 track 沒有 pair row。

### 每個 track 的第一個 matched→unmatched 轉換

共有 158 個 track 可找到明確的第一個轉換：

| 第一個異常 | tracks |
|---|---:|
| association_competition | 157 |
| trace_gap_with_detector_candidate | 1 |
| candidate_gate_rejected | 0 |
| detector_no_candidate | 0 |

終止結果另計：`track_expired_max_gap` 103 筆，`track_expired_max_missed` 130 筆。這些是最後狀態，不代表最初一定是 max-gap 造成失配。

## 3. Live UID / Replay UID 對應

使用 live event 的 capture timestamp、source frame、crossing_y、appearance、key_candidates，與 replay state 的 source frame、bbox 中心 y、appearance、stable_keys 做軌跡配對；沒有使用整數 UID 相等。

| 對應結果 | live UID 數 |
|---|---:|
| HIGH | 62 |
| MEDIUM | 42 |
| UNKNOWN | 125 |
| 合計 | 229 |

HIGH 代表至少兩個取樣點的外觀與鍵位一致、平均 y 誤差小於 8 px 且最佳候選和次佳候選有明顯差距；MEDIUM 只代表可用證據較少，不能當成確定 identity。

目前資料缺少三個直接欄位，因此仍有 125 個 UNKNOWN：

1. live event 沒有每幀 `candidate_id` 與完整 bbox，無法把 live candidate 精確連到 replay candidate。
2. live 與 replay 沒有共用的 stable physical-note identity；capture timestamp 只能縮小候選範圍。
3. 沒有 `physical_note_id`／遊戲判定真值，不能由 key-down 或 FIRED 推論命中。

最小必要修改（本輪未實作）：live trace 每幀保存 `candidate_id`、bbox、觀測中心、appearance、lane；association 在零候選或 track 被跳過時也寫一列 `association_attempt`（含 skip reason）；兩次流程共同保存 `capture_timestamp + bbox + lane + appearance` correlation key。

## 4. 五個 Shadow 優勢案例的來源影格核對

逐一查看來源影片代表影格及前後兩幀。以下是「畫面上確實看得到音符」的視覺結論，不是遊戲 Perfect/MISS 真值。

| live UID | frame | candidate evidence | 視覺核對 |
|---|---:|---|---|
| 1000004 | 257 | `257:candidate:0`, S\|D, cyan_bar | TRUE_VISIBLE_NOTE；連續影格可見向下移動的 cyan tap，非雜訊。|
| 1000059 | 615 | `615:candidate:0/2/5/7`, D\|F, cyan_bar | TRUE_VISIBLE_NOTE；cyan tap 與命中閃光同時出現，閃光不是唯一證據。|
| 1000139 | 923 | `923:candidate:0/2`, D\|F, cyan_bar | TRUE_VISIBLE_NOTE；畫面另有黃色長條，但 D\|F 的 cyan tap 仍可見，不能把黃色長條誤當此 UID。|
| 1000140 | 935 | `935:candidate:0`, K\|L, cyan_bar | TRUE_VISIBLE_NOTE；cyan tap 與獨立黃色長條重疊，兩者是不同視覺物件。|
| 1000143 | 963 | `963:candidate:0/3`, S\|D, cyan_bar | TRUE_VISIBLE_NOTE；相鄰影格仍可見 S\|D cyan tap；背景特效不構成候選本身。|

因此五案不能分類為「Shadow 只抓到雜訊」。但 1000139/1000140 同時存在黃色長條，顯示 appearance label 與畫面中多物件重疊，後續仍需保留 candidate ID 才能做物理音符級對應。

## 5. 最值得修補的前 10 個案例

`total_cost=INF` 是 gate 拒絕的設計值；括號中的 residual/competition IDs 是可追溯證據，不把 INF 解讀成實際距離。對應信心沿用上述保守 UID 配對。

| # | frame / capture_timestamp | replay track | live UID | conf. | candidate | reject_reason | cost / residual | competition |
|---:|---|---:|---|---|---|---|---|---|
| 1 | 208 / 677763.6754287 | 1 | 1000000 | HIGH | NONE | NO_PAIR_TRACE | N/A | — |
| 2 | 218 / 677763.8466062 | 2 | 1000001 | HIGH | 218:candidate:0 | candidate_key_no_intersection | INF | 1 |
| 3 | 234 / 677764.1269267 | 3 | 1000011 | MEDIUM | 234:candidate:1 | motion_residual | INF / 19.975 px | 1 |
| 4 | 241 / 677764.2355003 | 4 | AMBIGUOUS | UNKNOWN | 241:candidate:0 | motion_residual | INF / 19.512 px | 2 |
| 5 | 262 / 677764.6077316 | 5 | 1000004 | HIGH | 262:candidate:0 | lane_step_exceeded | INF | 4 |
| 6 | 283 / 677764.9663614 | 6 | 1000005 | HIGH | 283:candidate:0 | appearance_family_mismatch | INF | 3 |
| 7 | 302 / 677765.3423416 | 7 | AMBIGUOUS | UNKNOWN | 302:candidate:3 | motion_residual | INF / 120.536 px | 2 |
| 8 | 351 / 677766.2004020 | 11 | 1000010 | HIGH | 351:candidate:0 | lane_step_exceeded | INF | 3,10 |
| 9 | 378 / 677766.6861014 | 17 | 1000015 | HIGH | 378:candidate:6 | backward_motion | INF / 4.000 px | 5 |
| 10 | 389 / 677766.8908656 | 18 | 1000017 | HIGH | 389:candidate:2 | motion_residual | INF / 33.500 px | 11 |

前 10 案例的共同點是競爭或 trace 缺口，而不是 detector 沒有產生任何候選。第 1 案沒有 candidate ID，不能猜測被哪個 candidate 拒絕。

## 結論與最小後續動作

有證據支持的前三個問題：

1. **Association competition（157/158 個 track 的第一個失配）**：同一 frame 的 candidate 被別的 track assigned，且 pair row 留有 competition track IDs。
2. **Association trace 不完整（244 個 unmatched states）**：detector 有 `candidate_final`，但該 track 沒有 pair row；這是可觀測性缺口，不足以判定 detector 或 gate 失敗。
3. **黃色長條與 cyan tap 重疊造成 identity 風險**：五個 Shadow 優勢 case 都有可見真音符，但其中兩個同時有黃色長條；沒有 candidate-level live identity 時容易錯配。

不建議本輪修改任何判定門檻。下一步最小修補只應補齊 live/replay correlation 欄位與零候選 association attempt 記錄，然後重跑同一來源資料驗證 unmatched 是否能被明確歸類。`key_down`、`FIRED`、Shadow eligible 仍不能當作遊戲命中率。

## 清理項目

已移除不再被目前 V7.5.5.1 流程引用的舊驗證工具與舊報告：

- `tools/benchmark_detector_v75.py`
- `tools/replay_pink_tracker_v75.py`
- `output/v755_tracker_association/V7_5_5_TRACKER_ASSOCIATION_REPORT.md`

保留目前 association replay 核心工具 `tools/replay_tracker_association_v755.py`，以及本輪使用的 Trace CSV、來源影片和 case crops。
