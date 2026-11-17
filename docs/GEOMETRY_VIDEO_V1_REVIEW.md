# Geometry Video V1 — visual review queue

## 審核邊界

這是以來源像素轉換出的幾何候選，不是遊戲譜面或送鍵建議。遮罩顏色代表候選類型：青色為 provisional Tap、綠色為 provisional Hold、紫色為 UNKNOWN。紫色表示像素/所有權無法安全分類，不應算成已確認音符。

目前沒有人工標註，因此本文件不指定「真音符」、「命中」或「recall」。本文列出的 spot check 是 Codex 對來源/輸出影格的檢視記錄，不是獨立人工標註。mechanical PASS 只證明資料映射、影格數、遮罩可解碼、影片可播放及 checksum 正確。

## 優先連續片段

所有片段各 60 幀，來自全量 replay 的 `comparison.mp4`，不是另一次來源辨識：

| 片段 | 來源位置 | 審核重點 | 目前判讀 |
|---|---|---|---|
| `frame_4_9s_around_294.mp4` | Run 1，264–323，中心 frame 294 | 綠色連續帶、青色 Tap、周圍光效 | 主體幾何可見；Hold 起/尾語義仍未驗證 |
| `frame_6_0s_around_360.mp4` | Run 1，330–389，中心 frame 360 | 同時存在多條綠色帶及 Tap | 各可見元件有分離候選；跨影格身份及尾端歸屬未經人工確認 |
| `frame_14_9s_around_894.mp4` | Run 1，864–923，中心 frame 894 | Tap/Hold 重疊、判定特效、遮擋 | 混合場景；紫色 UNKNOWN 區域不可強行歸到音符 |
| `holdout_frame_1606.mp4` | Run 8 holdout，1576–1635 | 不參與幾何擬合的 holdout 影片 | 軌道對齊可檢查；候選分類仍屬 provisional |

每段有同名 `_comparison.png` 和 `_pixel_mask.png`。`index.json` 列出來源 run 與精確影格範圍。全量影片可在各 run 子目錄查看 `comparison.mp4` 和 `geometry.mp4`。

## 已確認的資料問題與未解問題

1. 全量輸出逐行保存像素遮罩，但候選大量落在 UNKNOWN：全體逐影格候選中 82.72% 是 UNKNOWN；獨立水平邊緣掃描中 63.63% 沒找到重疊候選。這表示目前候選/待審量仍高，不能只憑畫面看起來對齊就當成通過。
2. 代表片段中的 Hold 主體能形成像素支持的連續形狀；Hold 頭尾所有權仍依螢幕上下暫定，無法證明是遊戲判定的 head/tail。
3. 14.9 秒附近的效果與音符重疊。無法分清的內容保留 UNKNOWN。這是合適的安全狀態，但也表示視覺辨識尚未達到完成驗收。
4. 幾何校準是來源 Hough 自動擬合；holdout 最大外側邊界 P95 殘差約 10 px。需要在代表影格上人工核對 rail 邊界是否可接受。
5. 效能不達即時：分割/像素候選/時序關聯的 per-run median 中位數 315.531 ms/幀；60 fps 預算為 16.67 ms/幀。主要內層熱點為每幀 HoughLinesP，其後為 connected components。

## 建議人工審核順序

先看上表 4 段及其紫色遮罩區；逐段記錄可確認的 Tap、Hold 可見主體、被遮擋區和特效。Hold 起點/尾端只有在連續片段證據足夠時才填；其餘保持 UNKNOWN。這些人工標註完成前，不計算物理音符召回率、precision 或命中率，也不接入 Active。

## 安全與完整性

- 8 場各自輸出影格數與來源解碼影格數一致，source PTS 與 capture/acquired timestamps 有逐影格索引。
- `validation/issue_log.csv` 保留獨立水平邊緣審核列；它是審核佇列，不是已確認漏檢列表。
- `output/recording/` 保持唯讀；Live、鍵盤與 Scheduler 未使用。
- 目前整體驗收：`REVIEW_REQUIRED`。
