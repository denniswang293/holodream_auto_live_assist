# Geometry Video V1 — fresh source replay result

## 結論

**機械驗證：`PASS_MECHANICAL_PROVISIONAL`。整體視覺驗收：`REVIEW_REQUIRED`。**

本輪從唯讀的 `output/recording/` 重新建立幾何輸出，完成 8 場、26,259 個來源影格。每場的 source video、index、輸出影格順序、capture/acquired timestamps、像素遮罩編碼、影片解碼幀數與 checksum 均通過獨立機械驗證。這代表輸出可追溯且檔案結構正確，不代表音符辨識品質已驗收。

人工物理音符真值為零；Tap/Hold 真正 recall、precision、遊戲命中率及 hold endpoint ownership 均不可計算。所有候選數是逐影格觀測列，不是去重後的實體音符數。

## 輸出

- 全部影片與逐影格資料：`output/geometry_video_v1/fresh_20261117/run_<run_id>/`
- 原片/幾何並排影片：各 run 的 `comparison.mp4`
- 純幾何影片：各 run 的 `geometry.mp4`
- 來源 frame、PTS、capture/acquired timestamp 對照：各 run 的 `frame_index.csv`
- 候選及壓縮像素遮罩：各 run 的 `instances.jsonl`
- 不確定候選：各 run 的 `uncertain_candidates.csv`
- 四個代表片段（4.9s、6.0s、14.9s、holdout frame 1606）及 PNG 遮罩：`output/geometry_video_v1/fresh_20261117/selected_review_clips/`
- 驗證結果：`output/geometry_video_v1/fresh_20261117/validation/`

完整影片依來源 MP4 的 60 fps PTS 編碼；`frame_index.csv` 另外保留實際 capture/acquired timestamps。Run 1 的 MP4 PTS 時長約 52.63 秒，capture timestamp 範圍約 124.20 秒，因此不要用 MP4 播放秒數取代擷取時鐘。

## 量測

以下為每個 run 量測後的中位數統計：先算每場各 stage 的 median，再取 8 場中位數。P95 欄為 8 場 P95 的平均值。

| Stage | 每場 median 的中位數 | 每場 P95 的平均值 | 解讀 |
|---|---:|---:|---|
| Decode | 2.516 ms | 3.476 ms | 來源影格解碼 |
| Segment + pixel evidence + temporal association | 315.531 ms | 432.598 ms | 主要瓶頸；遠高於 16.67 ms/影格的 60 fps 預算 |
| Geometry rendering | 37.067 ms | 48.051 ms | 幾何畫布與候選形狀 |
| Comparison compose + video writes | 20.809 ms | 27.233 ms | 對照影格合成及影片寫入 |
| Serialization | 3.119 ms | 7.390 ms | JSONL、CSV 與 review audit 資料 |

120 幀 cProfile 樣本（Run 1 source frame 264–383）中，`HoughLinesP` 花費 10.10 秒/120 次，約 84 ms/幀；`connectedComponentsWithStats` 花費 1.57 秒/600 次，約 13 ms/幀。主要瓶頸是每影格的水平邊緣 Hough 偵測，其次為連通元件及候選整理。完整 run 的 stage 結果見 `validation/performance_stage_metrics.csv`；樣本呼叫表見 `validation/profile_hotspots_run1_120frames_with_tracker.csv`。

已移除水平 edge pair 對每個小區域重複呼叫五組 `inRange` 的計算，改用該影格已建立的顏色遮罩；幾何 field mask 也按幾何設定快取。120 幀 profile 中 `inRange` 呼叫由 18,995 降至 600；對 5 個代表影格逐一比對後，候選型別、位置、面積及壓縮像素遮罩與全量輸出完全一致。這項局部節省不足以讓整體達到即時，Hough 仍是後續效能工作首要對象。

8 場全量影片是在這項不改判斷結果的計算重用改動前產生；改動後已對 5 個關鍵影格做候選/遮罩逐筆相等檢查並重跑完整測試，但沒有為這個局部運算改動重編碼 8 場影片。因此，全量 stage 時間是改動前的實測；目前程式碼不會改變輸出候選判斷，但此等價性尚未對全部 26,259 幀逐一重跑。

來源是原生 1280×720 影格；目前沒有逐影格影像 Normalize/Rectify warp，使用透視幾何座標映射。因此 Normalize/Rectify 沒有獨立影像處理耗時。HSV/Gray、mask 建立、component 統計、edge pairing 在全量摘要中尚未逐項拆開；Hough 與 connected components 的內層成本由 cProfile 樣本量測。

## 候選與驗收狀態

8 場合計有 2,380,922 筆逐影格候選，其中 UNKNOWN 1,969,477 筆（82.72%）。獨立水平邊緣審核列 111,632 筆，71,037 筆沒有重疊候選；它們只作為 review queue，不強行歸因為漏音符或特效。沒有人工作出的物理音符標註，故不能把這些數字說成 recall 或 false-positive rate。

獨立幾何校準以 Run 1–6 的來源影像估計七條軌道邊界，Run 7–8 保留作 holdout。Holdout Hough edge residual 的最大 P95 約 10.56 px（Run 7 左外邊界）和 9.76 px（Run 8 右外邊界）；其餘內部邊界約 2.0–3.0 px。這是自動線段一致性檢查，不是人工 rail ground truth。

目前保留 UNKNOWN 的情況包括判定線光效/文字重疊、跨 lane 或邊界不清、太薄的邊緣片段、被畫面/field crop 截斷的區域。Hold 的 screen-top Tail、screen-bottom Head 仍是暫定角色；無法由單張像素證據證明遊戲語義上的起點/終點歸屬。

## 驗證及限制

- 獨立機械驗證：8/8 runs PASS，來源與輸出都是 26,259/26,259 幀；source recordings 未修改。
- 自動測試：`pytest -q`，36 passed。
- 五個代表影格（Run 1 的 294、360、894、1579；Run 8 的 1606）在遮罩快取及計算重用後，像素候選逐筆一致。
- 不使用 Live、鍵盤、Scheduler，也沒有模擬送鍵結果。
- 尚未建立獨立人工物理音符真值；整體狀態維持 `REVIEW_REQUIRED`，不可接入正式 Active。
- 暫存清理只按每輪的逐檔 SHA/大小清單執行；iteration 0005 清理 5,324,490,248 bytes，總計清理 6,544,506,132 bytes，無 blocked path。來源與正式輸出雜湊在清理前後受保護。

## 重跑新輸出

請使用一個全新的空目錄，不要覆寫本報告對應的結果：

```powershell
$Out = "output/geometry_video_v1/fresh_YYYYMMDD"
python -B tools/geometry_v1_fresh/inventory.py --recording-root output/recording --output "$Out/source_inventory"
python -B tools/geometry_video_v1_fresh/calibrate_source_geometry.py --input-root output/recording --out $Out
python -B tools/geometry_video_v1_fresh/render_geometry_video.py --input-root output/recording --out $Out --all
python -B tools/geometry_video_v1_fresh/validate_geometry_video.py --root $Out --recording-root output/recording
```
