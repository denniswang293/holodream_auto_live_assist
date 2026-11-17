# HoloDream Geometry Scene V2 — 原始影片推斷音符場景，從零渲染純幾何動畫

> **交付給 Codex 的完整自主執行計畫（取代 Geometry Video V1 / V1.1）**  
> 日期：2026-11-17；狀態：待執行，非驗收報告  
> **唯一核心任務：讀取 `output/recording/` 原片 → 重建結構化音符／軌道場景 → 從空白畫布渲染新影片 → 自動查錯修正。**  
> 舊離線實驗已刪除且放棄；不得恢復、比較或依賴舊 V8.x 離線程式與結果。絕不進入按鍵、ETA、Live Active、Scheduler。

## 0. 設計決定：不「過濾原片」，而是建立場景後重新生成影片

原始影片僅是**觀測輸入**，不是要被套濾鏡、抹背景或在原圖上畫彩色 Mask 的最終畫布。採用四個明確分離的階段：

```
原始 source MP4（唯讀）
   │
   ├─ 來源座標／時間校準
   │
   └─ 視覺觀測：擷取候選 Tap、Hold 頭／身／尾，記錄來源像素證據
            │
            ▼
      跨影格重建 Scene Timeline
      六軌幾何＋判定線＋獨立音符物件＋連續運動＋不確定性
            │
            ▼
      全新幾何渲染器（純背景；絕不貼來源像素）
            │
            ├─ geometry.mp4  ← 最終乾淨影片
            └─ comparison.mp4 ← 來源／重建並排，僅供審核
            │
            ▼
      逐段來源驗證 → issue log → 修正 → 重建 → 每輪安全清理
```

**不是「直接用程式假想一首譜面」**。場景裡的每顆音符仍必須有原片可追溯的觀測或有充分前後影格支持的短暫遮擋推論。不能從音樂、玩家按鍵、舊 Legacy 輸出、遊戲自動按鍵的需求或看似合理的節奏憑空生成音符。

**釐清效益與限制：** 使用全新畫布，讓輸出完全不含光效、HUD、背景和碎片，並大幅簡化畫面生成；但原片中「真音符 vs 光效」仍是來源辨識問題，光靠重畫無法解決。重點是依時序一致的物件／軌跡降低單影格干擾。

## 1. 執行範圍與專案保護

### 1.1 本機可依據的現狀

- GitHub 2026-11-16 的清理版已移除舊離線實驗程式、輸出與報告；保留 Live 核心及 `output/recording/`。不要重建舊架構。
- `config/geometry_live_assist.json` 的參考大小為 **720×404**、六軌 **S D F J K L**、`model_type=linear`、`status=pending_calibration`。這只是**未經獨立確認的參考**，不能直接當成無誤座標。
- `src/model.py` 的 `Geometry` 可**唯讀參考**正規化／透視映射；`src/perception.py` 的 Legacy 辨識不是 Ground Truth，不可作為成功標準。
- 真正的來源數量、大小、FPS、時間戳、是否包含非遊玩片段，由本機盤點確認，不直接假設歷史盤點仍準確。

### 1.2 嚴格禁止

1. **任何 Git 指令**（包括 `git status`、`git diff`、`git log`、commit、push）。Codex 不用 Git；需要基準時保存內容雜湊與經允許的新工作檔快照。
2. 修改、刪除或覆寫 `output/recording/`、使用者標註、原始 index 或其他既有資料；不得用清理程序掃描整個 `output/` 刪檔。
3. 修改 `src/live.py`、`src/perception.py`、`src/tracking.py`、`src/engine.py`、`src/scheduler.py`、`src/timing.py`、Live 的幾何與時間設定或實際鍵盤控制。
4. 將新 Scene 渲染器接到 Live、Scheduler、ETA 或遊戲輸入。此專案沒有音符按鍵輸出，也沒有 OS keyboard injection。
5. 把既有音符預測、自己輸出的 Scene／Mask、玩家人工鍵擊、遊戲節奏假設當成來源實體真值。

### 1.3 隔離的實作／輸出

新程式建議放 `tools/geometry_scene/` 和 `tools/geometry_scene_cli.py`，測試放 `tests/test_geometry_scene_*.py`，配置放 `output/geometry_scene_v2/config/` 或 `config/geometry_scene_v2.json`（新檔，不覆蓋既有 Live config）。所有衍生影片／實驗／審核結果只放 `output/geometry_scene_v2/`。

## 2. 第一里程碑：來源盤點、影格時間和場景座標

1. 遞迴列出 `output/recording/` 內的完整來源影片，優先識別 `run_*/live_source.mp4`，接受經盤點確認的其他來源檔名。記錄 source SHA-256、寬高、Codec、影格數、可解碼性、FPS／PTS、是否有 `live_video_index.csv`、是否為 VFR、非遊玩畫面與來源毀損情形。
2. 若有 index，以 `video_frame`／`source_frame`／`capture_timestamp`／`acquired_timestamp` 精確關聯；若沒有則使用實際 PTS。不可用 `frame/60` 假造真實 capture time。來源與輸出必須有逐影格索引可追溯。
3. 隔離建立**渲染用**六軌幾何：來源 native 座標、六條透視邊界、判定線、出生／視野邊界。先做只含軌道和判定線的空場景 `blank_scene_preview.mp4`，人工可看、程式可對齊；錯位就修正獨立 Scene config，不改 Live。
4. 同一個 Scene 可選擇透視投影，**正式 `geometry.mp4` 預設用與原片相同的畫面座標系**方便左右對照；不可強制把所有實體音符吸到假設的等距軌道中心。
5. 選定開發來源與真正獨立的 holdout 來源或不重疊的時段，登記清楚。不要在 holdout 找錯後仍把它說成未使用的獨立測試。

交付：`inventory.csv`、`source_manifest.json`、`scene_calibration.json`、多 Run 的軌道／判定線對照圖。**場景基準未校準，不得宣告完整品質通過。**

## 3. 第二里程碑：先實作「不用原片」也能工作的空白場景渲染器

**先做 Renderer，再接偵測器**。在完全人造的 Scene JSON 上測試以下情境：

- 六條軌道與判定線固定不變；Tap 用單一橫向幾何板（可跨軌），同時兩個 Tap 仍保持兩個實例。
- Hold 用**單一物件**表示 Head、Body、Tail 的連續幾何關係；同時兩條 Hold、不同顏色、Tap+Hold、跨軌重疊都能渲染而不強制合併。
- 按來源時間座標輸入 `scene_state_at(t)`，渲染指定時刻的所有物件；時間連續、位置單調且遵循來源觀測，不忽然瞬移／重複出生。
- 遮擋狀態與不確定性只存於 Scene Metadata，正式影片中不畫原片特效；審核影片可以另加觀測／推測分色圖層。
- 非遊玩畫面輸出空場景或清楚登記的遊玩狀態，不能出現上輪殘留音符。

渲染方式可用 OpenCV、NumPy 或其他本機可重現的 2D primitives。**禁止以任何方式直接貼、混合、擦除、模糊、過濾、風格轉換原影片像素來生成 `geometry.mp4`**。原影格只允許進入來源分析器與 `comparison.mp4` 的來源那一側。

先通過 renderer 單元測試，再開始從原片擷取音符；如此能明確區分「辨識錯」與「繪製錯」。

## 4. 第三里程碑：以多影格證據建立結構化 Tap／Hold 音符場景

### 4.1 Scene Data Model 是唯一渲染輸入

每顆來源音符建立跨影格持久 Scene ID（只在這支影片內有效），例如：

```json
{
  "scene_note_id": "n_000127",
  "kind": "HOLD",
  "lane_span": [1, 2],
  "source_color": "green",
  "first_observed_frame": 318,
  "last_observed_frame": 367,
  "motion": {"model": "observed_trajectory_with_piecewise_fit", "timebase": "source_pts"},
  "head": {"observations": [{"frame": 318, "bbox": [90, 60, 48, 12]}]},
  "body": {"observed_intervals": [[318, 367]]},
  "tail": {"observations": [], "status": "UNKNOWN"},
  "confidence": 0.87,
  "status": "PARTIALLY_OBSERVED",
  "evidence_refs": ["frame_000318/region_03"]
}
```

這只是 Schema 示範，**示例數字不是真實來源結果**。須用可版本化 JSON Schema／Python model 定義欄位和限制；不是從每幀各生成一張圖片後再硬湊影片。

場景至少記錄：`run_id`、`scene_note_id`、`kind`（`TAP`／`HOLD`／`UNKNOWN`）、`lane_span` 或來源座標／多邊形、觀測區間與證據、速度／位置曲線、Head／Body／Tail 可見／未知狀態、追蹤身份衝突、物件存續、信心、推論來源、缺失／遮擋標記。`track` 只是**離線視覺身份**，不是可接 Scheduler 的即時追蹤器。

### 4.2 觀測與物件識別

1. 來源畫面擷取**候選**面板、長帶、頭尾輪廓與判定線。允許使用 HSV、邊緣、分割、光流、實體形狀等來**量測輸入證據**；但這些不是最終影片濾鏡，也不能把一個 Mask 複製到輸出畫面。
2. 按多影格的 y-方向運動、形狀、寬度／跨軌、相對位置、顏色、連接關係判斷哪些觀測屬於同一 Tap 或 Hold。保留相互競爭的假設，不得因相同 y 就合併。
3. Tap 是短面板；Hold 是**有同一身份的頭、連續主體和可辨認尾部**。不能僅憑顏色斷言類型：黃色可能是 Tap 或 Hold，中性／灰色可能是音符，光效可能具有相似色彩。
4. 使用來源影片估算每段音符的移動：先從實際觀測擬合時間—位置曲線，可允許變速／曲線，**不要假設所有歌曲共用固定速度**；同一個可確認的音符不能在軌跡上跳接到別人。
5. 音符從畫面頂部第一次出現就建立 Scene，直到真正離開視野或有可靠消失證據。遇到遮擋／命中光效時，優先利用物件存續和周邊前後影格，而非每影格都當成全新的音符；保留欠缺證據的部分。
6. 這是**純離線重建**，允許由後續影格回看先前數幀（雙向關聯、後驗平滑、短區間內插）幫助處理光效遮擋；必須在資料標 `OFFLINE_RETROSPECTIVE`，不得宣稱能直接即時操作遊戲。不能任意在長時間缺失區域補出音符，也不能把未見過、缺乏前後佐證的 Tail 當成已觀測。
7. 光效、爆炸、碎片、HUD、手動按鍵效果不進 Scene 物件清單。當判斷不穩定時放入 `uncertain_candidates.csv`／`review_queue.csv`；不能用 `UNKNOWN` 抹去明顯可能的音符並藉此美化品質報告。

### 4.3 觀測 vs 推測必須可區別

- `OBSERVED`：該影格直接有可核對的原片局部像素證據。
- `INFERRED_OCCLUSION`：同一 Scene ID 在前後有可靠觀測，僅短暫被特效遮擋，通過已驗證的運動連續性和身份唯一性條件；保留推測影格範圍與來源邊界。
- `AMBIGUOUS`／`UNKNOWN`：多音符重疊、類型或頭尾歸屬無法唯一判斷；不可以在正式影片畫成「確定的」新增音符。另在診斷層提示，也要列入疑似漏偵審核，而非視為負例。
- 推測長度上限請根據來源的實際時間間隔和已驗證速度設定**保守可調的毫秒窗口**，不硬編碼為幾幀；超出就保留缺口／UNKNOWN。正式影片可畫具證據支持的短暫補償，但必須在 metadata 列明為 `INFERRED_OCCLUSION`，不能說來源影格直接看到了。

### 4.4 場景產生器、渲染器完全解耦

API 建議：

```python
observations = analyze_source_frames(source_video, source_index, scene_calibration)
scene = reconstruct_scene_timeline(observations, source_timestamps)
render_geometry_video(scene, source_timestamps, output_video)
render_comparison_video(source_video, scene, source_timestamps, output_video)
```

- `render_geometry_video(scene,...)` **不得開啟原始影片、不得呼叫任何辨識器**。可用人造 JSON 做百分之百可重現的單元測試。
- 來源辨識器修改時，只要 Scene JSON 沒變，渲染結果應一致；渲染器修改時，只要 Scene JSON 沒變，觀測不應受影響。
- `geometry.mp4` 只包含背景、六軌、Tap、Hold 的 Head／Body／Tail 和判定線；**無原片像素、文字、HUD、光效、Mask、debug 符號**。`comparison.mp4`、`diagnostic.mp4` 可以有原片與標註。

## 5. 第四里程碑：輸出完整影片與可重播的場景資料

建議 CLI（Codex 實作並在 README 記載）：

```powershell
python tools/geometry_scene_cli.py inventory --input-root output/recording --out output/geometry_scene_v2
python tools/geometry_scene_cli.py preview --input-root output/recording --out output/geometry_scene_v2
python tools/geometry_scene_cli.py render --all --input-root output/recording --out output/geometry_scene_v2
python tools/geometry_scene_cli.py validate --root output/geometry_scene_v2
```

支援單 Run、單窗口、只重建 Scene、只重新渲染、全 Run、只驗證，避免每次為了一幀 Bug 重新編碼所有來源。命令以 Codex 真正實作的參數為準，不可僅在文件宣稱 CLI 存在。

每個 Run 至少有：

```
output/geometry_scene_v2/
  inventory.csv
  config/scene_calibration.json
  run_<run_id>/
    geometry.mp4                 # 全新畫布生成；正式產品
    comparison.mp4               # source | geometry；供人目視
    scene.json                   # 整段、跨影格 Tap/Hold 物件＋運動資訊
    observations.jsonl           # 來源原始候選（可壓縮且需可讀回）
    frame_index.csv              # 來源↔場景↔輸出影格/PTS 對齊
    uncertain_candidates.csv
    review_queue.csv
    qc_summary.json
    checksums.json
    review_windows/              # 僅必要的可重現短片、截圖
  validation/
    issue_log.csv
    holdout_results.md
  iterations/
    iteration_history.csv
    iteration_0001.md
    cleanup_history.csv
  _scratch/                      # 每輪結束清理已失效快取
  final/
    result.md
    evidence_manifest.json
    cleanup_summary.json
```

- 源影片完整可解碼者必須完整轉換；不同歌曲／Run 不要共享未證實的速度或幾何配置。
- 輸出 `geometry.mp4` 須能單獨播放，**從第一個至最後一個來源影格都有畫面**；遊玩前後段即使沒有音符也要有空場景。依 PTS/index 保留幀對應，VFR 必須明確保持時間或記錄精確映射與誤差，不能悄悄以標稱 FPS 丟幀。
- 必須區分「觀測原始 JSON」、「重建 Scene JSON」、「渲染結果」，避免一個程式同時負責所有工作而難以驗證。
- `comparison.mp4` 的原片一側**只是審核用途**，不算直接修改原影片；`geometry.mp4` 絕不需要原片像素輸入。

## 6. 第五里程碑：讓 Codex 自動對照原片，查出真正錯誤

### L1 — Renderer／Scene 結構機械門檻（硬性）

- 來源 hash、來源 frame/index/PTS 對照可靠；能 decode 輸出且每個來源幀都有對應幾何幀；無源影片修改。
- 渲染器的輸入僅有 `scene.json`、配置和來源時間索引，不得存取原片；在 synthetic fixture 上所有 primitive／Tap、Hold、同 y 雙 Tap、混合譜、長 Hold、重疊、進出畫面、空白場景的測試通過。
- Scene 的 ID 穩定、跨影格位置不瞬移、每顆確定物件有證據引用、Hold Head/Body/Tail 各自可區分但同一物件歸屬一致，沒有無證據的交叉合併。
- `geometry.mp4` 中禁止原始影像、原片轉移像素、特效、HUD、來源字幕、Mask／診斷框／按鍵輸出。
- 精確列出空場景、推測補償、UNKNOWN、可信物件的每 Run 影格數與持續時間，不能靠跳幀或忽略候選減少錯誤統計。

### L2 — **獨立於渲染器**的來源證據驗證

**不能只比 Scene → Render 一致性就說轉換成功！** 這樣只能證明畫圖程式正常，不能證明辨識到所有真實音符。

1. 建立來源／幾何／診斷三聯視圖；Codex 實際檢查連續窗口，而不是僅看 6 張成功截圖。若執行環境無法可靠看影像／影片，明確回報能力限制與 `REVIEW_REQUIRED`。
2. 用**獨立的候選稽核**找出來源中可能有橫向面板／長帶、但 Scene 未收錄的位置；審核不能只重跑同一個 Scene extractor 或拿自己渲染的 Mask 當真值。
3. 優先抽樣：首次進入畫面、消失前、灰色／青色／黃色面板、綠色／黃色 Hold、同高雙 Tap、Tap+Hold、兩 Hold 重疊、強命中光效、完全或部分遮擋、離判定線最近、非遊玩幀。每個可用 Run 的開頭／中間／結尾都要覆蓋。
4. 每個案例對照**是否真有音符、數量、類型、跨軌、Head/Tail 歸屬、各觀測的空間位置、Scene 的連續移動、何處是 OFFLINE_RETROSPECTIVE 補償**。將問題分為 `MISSING_NOTE`、`FALSE_NOTE`、`WRONG_TYPE`、`WRONG_LANE`、`MERGE_SPLIT`、`HOLD_ENDPOINT`、`TEMPORAL_DISCONTINUITY`、`ALIGNMENT`、`UNCERTAIN`。
5. 將每個錯誤寫 `issue_log.csv`：run ID、來源幀與 PTS、來源 crop、預期／實際 Scene 片段、root cause、修正、前後對比、驗證狀態、來源證據。可以確定的錯誤自行修正；不能唯一判定就留審核佇列。
6. 所有 Codex 自己看片得到的標記只能是 `AUTO_VISUAL_REVIEWED`／`PROVISIONAL`，**不得冒充人類 Ground Truth**。Source 的音符 precision／recall 若無獨立標註必須寫 `NOT_EVALUABLE`。

### L3 — Holdout 與負例回歸

- 拆分不同 Run 或互不重疊區間；針對開發集找到的問題修正，再在未調過的保留集驗證；被用於調參的保留集須重標，不可繼續稱為 holdout。
- 必須保留「光效但沒有音符」「兩顆相鄰 Tap」「兩條 Hold 交錯」「黃 Tap 非 Hold」等負例，防止改善召回時引入大量虛構音符。
- 任何新的檢出，都要回看原片；音符數量變多、Scene 更連續、MP4 看起來乾淨，都**不是**準確率通過證據。

## 7. Codex 自主修正迭代與每輪安全清理

每輪：

1. 由來源稽核與 `issue_log.csv` 挑**一個最重要、可重現**的錯誤，給定精確 frame/PTS、預期錯誤型態及負例。
2. 決定問題屬 `SOURCE_OBSERVATION`、`SCENE_ASSOCIATION`、`MOTION_OCCLUSION`、`SCENE_GEOMETRY`、`RENDERER`、`TIMESTAMP_ALIGNMENT` 哪個模組。只修改必要模組，避免靠輸出裝飾隱藏辨識錯。
3. 先重跑失敗前後 0.5–2 秒、正例及負例；要檢查單顆 Scene ID、來源證據、時間線、前後渲染。失敗就回退該修法，保留短證據。
4. 小範圍過關後再重建開發 Run；主要候選通過後完整重跑所有可用 Run 和 L1/L2/L3；負例若退步必須回退。
5. 先寫本輪報告、問題處理決定、源檔 hash、驗收結果；保留**最新接受的正式** `geometry.mp4`、`comparison.mp4`、`scene.json`、最小失敗反例及必要測試資料。
6. **每輪結束（包括失敗、回退、例外）做安全清理**：先 preview 由本輪產生的 `_scratch/iteration_XXXX/` 快取、試片、重複 encoded MP4、debug dump；確認清單及保留集；刪除可重建且不被引用的檔案；回讀原始與正式輸出 SHA-256；把刪除檔案／位元組數、被阻擋路徑寫進 `iterations/cleanup_history.csv`。無可刪列 `NO_SAFE_CLEANUP`。如權限不允許，記 `BLOCKED`，不可繞過。
7. 不等使用者每輪 Push、不執行 Git、不修改原始資料。新假說有實證才進下一輪。

**安全清理邊界：** 只允許刪除 `output/geometry_scene_v2/_scratch/` 與本任務明確列出的已淘汰可重建衍生檔；**絕不碰** `output/recording/`、任何 Live 程式／設定、`docs/`、`tests/`、其他既有資料、正式場景／影片、不可重現的唯一錯誤證據。路徑要解析 realpath，拒絕 symlink／junction 逃出工作區；不得掃描所有大型檔案亂刪。所有清理先生成保護／刪除 manifest，只有符合允許清單才執行。不能把原始資料保護當作「不可清理本輪暫存」的藉口。

**停損：** 每類問題最多 8 次有內容的修正嘗試；連續 **4 輪**有效迭代沒有可重現改善且找不到新的根本原因即停止；建議總迭代上限 **30 輪**，超過必須整理證據及待審核問題，不可無限空轉。若來源／權限／視覺能力不足也可停止，但必須完成已能進行的工作，不能一遇到一個 UNKNOWN 就不做其餘 Run。

## 8. 完成／停止條件

### `GEOMETRY_SCENE_PROVISIONAL_PASS`

必須**全部**成立：

1. 所有完整可用 `output/recording/` 影片有完整 `geometry.mp4`、`comparison.mp4`、`scene.json`、來源對齊表、manifest；不能只交短窗口或挑漂亮案例。
2. 100% 對齊且來源 hash 未變，輸出可解碼，無跳幀／莫名重複／影格錯序；如果來源 VFR 有格式轉換，PTS 映射及可能的誤差須明確且在既定容許範圍。
3. Renderer 完全純幾何、與原片處理程式隔離，synthetic tests、空白場景、Tap/Hold、Hold 重疊、混合 chord、非遊玩幀測試全通過；**無特效殘留**。
4. 六軌與判定線的對齊有來源稽核；不得把 `pending_calibration` 當通過。
5. 在開發集與未受汙染保留集的**已確定來源可見**音符案例，沒有未修復的重大漏畫、假音符、Tap/Hold 錯類型、跨軌、分裂／合併、Hold 頭尾歸屬或時間不連續。推測遮擋有來源前後支持且沒有長區間任意補全。
6. 高風險抽樣與疑似漏偵審核完整，`UNKNOWN` 的數量／影格區間與嚴重程度逐案列出；不得只把難題標 UNKNOWN 就宣告已證明正確。重要不確定情形若阻礙判斷，結論應為 `REVIEW_REQUIRED` 而不是 PASS。
7. 每輪清理紀錄完整、正式交付可重讀、源檔與使用者既有資料未被修改；未執行 Git／OS 輸入／Live 修改。

此 PASS **僅代表可交給使用者最後目視核對的純幾何影片候選**，絕非音符真值召回率 100%、實機零 Miss 或 Live Ready。

### `GEOMETRY_SCENE_NOT_PASSED`

已知有重大、可重現的來源→Scene 錯誤未修復，或達 4 輪停損／30 輪上限。保留最佳候選、完整問題清單及可重現的短片，不得假稱通過。

### `REVIEW_REQUIRED` / `BLOCKED_WITH_EVIDENCE`

原片嚴重遮擋、類型／尾部不可辨、幾何無法確認、無可靠音符真值或環境限制使部分驗收無法完成。列出**最少必要**的 `run_id + source_frame/PTS + source crop + Scene crop + 具體問題`；先做完所有可以自主完成的工作。不因缺人工標註就放棄整體建構，也不以 Codex 的自我審核冒充人工確認。

**本階段絕不輸出 `ZERO_MISS_PROVEN`、`LIVE_READY`、`PHYSICAL_NOTE_RECALL_100`。**

## 9. 最終交付

- `tools/geometry_scene_cli.py`、`tools/geometry_scene/` 的來源觀測／Scene 重建／渲染分層實作；有真正可用的命令列與 README 操作說明。
- `tests/test_geometry_scene_*.py`：Renderer synthetic fixtures、解析／時間戳、Scene 身份／Hold 頭尾、光效／重疊負例；非互相驗證同一錯誤演算法。
- `docs/GEOMETRY_SCENE_V2_RESULT.md`：先寫結論、實際處理 Run/影格、成功與未過關 Gate、代表性修正、尚未確認的案例、重跑方式、清理統計。
- `output/geometry_scene_v2/`：所有來源的完整 geometry/comparison 影片、各 Run Scene JSON、來源觀測／時間表、可信度與審核佇列、必要差異視圖、最終 manifests、逐輪清理記錄。

最後用繁體中文簡述：**轉換了幾部完整影片／要看哪個 geometry.mp4；具體哪幾個來源案例修對了；哪些 Tap/Hold／Hold 尾端仍不可確認；停止狀態；多少迭代／刪掉多少無用衍生資料。** 不要回報 Mock 按鍵數、遊戲命中率或 Live 效能，因為本階段沒有評估那些事。
