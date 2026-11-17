# Geometry Scene V2 執行結果

**停止狀態：`REVIEW_REQUIRED`；不是 PASS。** 已完成 8/8 部原始影片的全長幾何重建、來源／幾何並排影片、逐影格時間映射、代表性影格遮罩與合成渲染測試。輸出能完整播放且時間軸對齊；但 Scene 中大量候選仍是 UNKNOWN，幾何校準與自動類型尚未經人工核准，物理音符 precision／recall 因沒有獨立真值而 `NOT_EVALUABLE`。不得據此推論命中率或 Live Ready。

## 完成的全長轉換

原始 `output/recording/` 保持唯讀。8 段來源共 **26,259 幀**。每場都有 `scene.json`、來源觀測 JSONL、track audit、效能摘要、`geometry.mp4`、`comparison.mp4` 及輸出 frame index，均位於 `output/geometry_scene_v2/runs/<run_id>/`。第三輪修正後共 19,581 個暫定視覺 tracks：2,702 個暫定 TAP、1,543 個暫定 HOLD、15,336 個 UNKNOWN；類型標籤不是人工真值。

| Run | 來源幀數 | 幾何輸出 | 並排影片 |
|---|---:|---|---|
| `run_20261106T164049_800126Z` | 3,159 | [geometry.mp4](../output/geometry_scene_v2/runs/run_20261106T164049_800126Z/geometry.mp4) | [comparison.mp4](../output/geometry_scene_v2/runs/run_20261106T164049_800126Z/comparison.mp4) |
| `run_20261106T164704_064294Z` | 3,171 | [geometry.mp4](../output/geometry_scene_v2/runs/run_20261106T164704_064294Z/geometry.mp4) | [comparison.mp4](../output/geometry_scene_v2/runs/run_20261106T164704_064294Z/comparison.mp4) |
| `run_20261106T164959_579760Z` | 3,013 | [geometry.mp4](../output/geometry_scene_v2/runs/run_20261106T164959_579760Z/geometry.mp4) | [comparison.mp4](../output/geometry_scene_v2/runs/run_20261106T164959_579760Z/comparison.mp4) |
| `run_20261106T170057_932173Z` | 3,513 | [geometry.mp4](../output/geometry_scene_v2/runs/run_20261106T170057_932173Z/geometry.mp4) | [comparison.mp4](../output/geometry_scene_v2/runs/run_20261106T170057_932173Z/comparison.mp4) |
| `run_20261106T170845_579909Z` | 3,472 | [geometry.mp4](../output/geometry_scene_v2/runs/run_20261106T170845_579909Z/geometry.mp4) | [comparison.mp4](../output/geometry_scene_v2/runs/run_20261106T170845_579909Z/comparison.mp4) |
| `run_20261106T171405_612600Z` | 3,156 | [geometry.mp4](../output/geometry_scene_v2/runs/run_20261106T171405_612600Z/geometry.mp4) | [comparison.mp4](../output/geometry_scene_v2/runs/run_20261106T171405_612600Z/comparison.mp4) |
| `run_20261106T172037_662313Z` | 3,563 | [geometry.mp4](../output/geometry_scene_v2/runs/run_20261106T172037_662313Z/geometry.mp4) | [comparison.mp4](../output/geometry_scene_v2/runs/run_20261106T172037_662313Z/comparison.mp4) |
| `run_20261106T172404_427324Z` | 3,212 | [geometry.mp4](../output/geometry_scene_v2/runs/run_20261106T172404_427324Z/geometry.mp4) | [comparison.mp4](../output/geometry_scene_v2/runs/run_20261106T172404_427324Z/comparison.mp4) |

`comparison.mp4` places the source on the left and the new geometry on the right. `geometry.mp4` is rendered from Scene JSON and frame index only; it does not read the source video.

## 時間軸與完整性驗證

- 每場來源解碼幀數、Scene 重建來源幀數、幾何輸出幀數、並排輸出幀數與 frame-index 列數一致；8/8 comparison 報告 `dropped_or_extra_frames=0`。
- 每個原始來源影片實際 SHA-256 與盤點、重建和比較摘要一致；輸出影片雜湊與各自摘要一致。原始影片沒有被改寫。
- 來源 MP4 的名義 60 fps PTS 時長為 50.217–59.383 秒；取得時間跨度為 120.824–139.417 秒，比例 2.330–2.406×。因此輸出採 index acquired timestamp 的 VFR 時間軸（1/90000 time base），而非把 `frame/60` 當作取得時間。幾何及並排輸出的最大時間映射絕對誤差約 **5.56 μs**。
- 全局逐影格索引為 [frame_index.csv](../output/geometry_scene_v2/frame_index.csv)，原始時間分析為 [timestamp_audit.csv](../output/geometry_scene_v2/timestamp_audit.csv)，來源雜湊清冊為 [source_manifest.json](../output/geometry_scene_v2/source_manifest.json)。
- 逐 Run 的機械驗證列於 [final_validation.csv](../output/geometry_scene_v2/validation/final_validation.csv)；每 Run `checksums.json` 記錄 22 個輸出檔案的 SHA-256，包含影片、Scene、時間索引及 review window 素材。

## 代表案例、實際修正與尚未確認事項

- 色彩分割現分開處理 Cyan 與 Green、限制在棋盤 ROI，並用形態學開運算去除孤立亮點；面板核心填充率低於 0.60 的單影格面板候選不再進入追蹤，但長綠色主體會保留為模糊 Hold 假設。固定面板輪廓／填充與多影格向下運動用來提出暫定 TAP，綠色連續主體及運動用來提出暫定 HOLD。三段優先窗口共移除 8 個低填充成分；8 Run 的 TAP/HOLD track 數未變，UNKNOWN 總數減少 11（其中一場 UNKNOWN track 增加 16），沒有將數量變化當作真值指標。
- 新增輪廓插值修正：舊 renderer 在相鄰觀測輪廓頂點數不同時退回 bbox。第一 Run 有 5,751 對相鄰多邊形頂點數不同；76 對 typed-HOLD 輪廓跨越缺影格，合計 105 個缺影格會畫成方框。現以等弧長輪廓取樣及循環對齊插值；直接觀測影格仍保留原始輪廓。代表例 `track_002041`（frame 2870–2873），新輸出中間影格維持輪廓而非 bbox，對照在 [iteration_0003_hold_interpolation.png](../output/geometry_scene_v2/review/iteration_0003_hold_interpolation.png)。
- 4.9 秒（來源 frame 294）可見綠色長帶及 Cyan 候選；不規則效果候選已受抑制，但綠色 HOLD 的尾端歸屬仍 UNKNOWN。
- 6.0 秒（來源 frame 360）可見連續綠色 HOLD；Cyan 元件仍有合併／面板邊界不清風險，Hold 尾端／Key-up 仍 UNKNOWN。
- 14.9 秒（來源 frame 894）是 Tap、Hold 與效果重疊的混合畫面；遮擋區及尾端歸屬 UNKNOWN，沒有把推測補成確定音符。
- 第一場代表影格的原畫、像素遮罩、overlay 與幾何輸出截圖位於 [review/run_20261106T164049_800126Z](../output/geometry_scene_v2/review/run_20261106T164049_800126Z/)。其餘 Run 的開頭／中段／結尾抽樣在各 run 的 `review_windows/`；全部是 `AUTO_VISUAL_REVIEWED_PROVISIONAL`，truth 保持 UNKNOWN。
- 8 場開頭／中段／結尾的遮罩總覽在 [cross_run_review_contact_sheet.png](../output/geometry_scene_v2/review/cross_run_review_contact_sheet.png)；frame 294、360、894 的連續短窗來源／重建抽樣在 [priority_windows_4_9_6_0_14_9.png](../output/geometry_scene_v2/review/priority_windows_4_9_6_0_14_9.png)。目視可見連續綠帶會進入幾何場景，但局部有分裂／邊界不穩；Cyan 面板和特效在密集區仍可能混淆，14.9 秒附近的綠色片段與尾端歸屬仍不確定。這只是自動候選的暫定檢視，不作為真值。
- 所有 tracks 的不確定原因列於 [uncertain_candidates.csv](../output/geometry_scene_v2/uncertain_candidates.csv)，另有每 Run 的 `uncertain_candidates.csv`；各 Run 抽樣索引為 `runs/<run_id>/review_windows/review_queue.csv`。來源／Scene 問題記錄在 [issue_log.csv](../output/geometry_scene_v2/validation/issue_log.csv)。開發範圍及保留範圍未形成乾淨獨立 holdout，見 [holdout_results.md](../output/geometry_scene_v2/validation/holdout_results.md)。

## 效能與測試

各 Run 的 `profile_stages.csv` 與根目錄 `processing_profile.csv` 分開記錄 decode、normalize/rectify、HSV、mask segmentation、connected components、candidate extraction、data conversion 和 temporal association；渲染與影片編碼則分別記在 `geometry_render_summary.json`、`comparison_summary.json`。8 Run 的每幀階段中位數（先計每 Run 統計，再跨 Run 取中位數）為：decode 平均 1.603ms／P95 1.779ms、HSV 0.453／0.592ms、mask 1.309／1.996ms、connected components 2.823／3.134ms、candidate extraction 4.700／7.308ms、data conversion 0.262／0.423ms。Normalize/rectify 是 no-op。Temporal association 每場只測一次全 Run 操作，中位數約 648.941ms，不能和每幀延遲直接相加。幾何 render 和 video encode/write 另計；第一 Run render P95 從 4.40ms 變為 5.02ms，encoder P95 約 6.75ms；處理延遲不以固定值偽裝，也不把編碼成本混進辨識階段。

執行：

```powershell
pytest -q tests/test_geometry_scene_renderer.py tests/test_geometry_scene_io.py tests/test_geometry_scene_segmentation.py tests/test_geometry_scene_association.py tests/test_geometry_scene_observe.py tests/test_geometry_scene_timeline.py tests/test_geometry_scene_video.py
```

結果：**28 passed**。涵蓋人工合成場景 renderer（含不同輪廓頂點數插值）、JSON/schema、分割、身份關聯、觀測重建和時間／影片處理；這不是來源音符標註驗收。

## 清理與限制

本輪先清理先前迭代的 **53 檔／71,128,892 bytes**；第三輪候選完整複製並驗證後，再逐檔比對路徑、大小及 SHA-256，清理 `_scratch/iteration_0003` 的 **88 檔／1,131,633,714 bytes**。累計清除 141 檔／1,202,762,606 bytes。第三輪清理前後重新核對 8 個原始影片 hash、104 個正式輸出 hash，均未變；第三輪 manifest 為 [cleanup_manifest.json](../output/geometry_scene_v2/iterations/iteration_0003/cleanup_manifest.json)，歷史摘要為 [cleanup_history.csv](../output/geometry_scene_v2/iterations/cleanup_history.csv)。保留正式 Scene、影片、來源資料、審核截圖、測試與文件。未使用 Git，未接入 Live/Scheduler/ETA，也未送出 OS 鍵盤輸入。

尚缺人工審核的音符類別、位置、Hold 頭尾、跨軌所有權與校準；沒有受控人工標註，因此物理音符召回率、假陽性率、Tap/Hold 混淆率皆 `NOT_EVALUABLE`。目前產物是可播放的幾何場景候選與來源審核材料，不是通過驗收的譜面。
