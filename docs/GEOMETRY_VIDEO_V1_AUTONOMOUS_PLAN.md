# HoloDream Geometry Video V1 — 從原始錄影重新建立純幾何音符影片

> **交付給 Codex 的完整自主執行計畫**  
> 修訂：V1.1（每輪結束執行安全清理；舊離線實驗已放棄，不納入新流程）  
> 狀態：待執行（本文件不是已完成報告）  
> 範圍：`output/recording/` 唯讀輸入 → 純幾何影片、來源對照影片及可追溯逐影格資料。**不做自動按鍵、命中時機、速度預測、Tracker→Scheduler 整合、舊版離線 A/B**。

## 0. 最終目標：先把「看見了什麼」轉換正確

在保留的所有完整 `output/recording/run_*/live_source.mp4`（或逐一盤點後確認的其他來源影片）上，將每個來源影格轉換成一張乾淨的「幾何場景」，並輸出與來源影格順序／時間可對齊的完整影片：

- **六條固定透視軌道**：僅畫軌道界線／區域，依現有設定由左到右 S、D、F、J、K、L；輸出可不顯示字母，字母只供診斷對照。軌道位置須與原片對應，不得憑感覺畫等寬直線。
- **Tap**：每個真正在當前來源畫面可見的 Tap，畫成一個位置、寬度、跨軌範圍都與原圖一致的扁平幾何面板。不同顏色可使用穩定的有限色盤，但**顏色不能單獨決定 Tap/Hold 類型**。
- **Hold**：用連續的幾何色帶表達可見主體，區分可辨認的 Head、Body、Tail；同時存在的 Hold 必須個別保持空間歸屬，不能跨其他顏色或光效憑空連接；原影格部分被遮住時不能憑空補出可見像素。
- **終點線／判定線**：固定畫在與來源相同的投影位置，作為畫面參照；**不等於要計算鍵盤觸發時機**。
- **除了上述內容，乾淨的幾何影片不得出現任何 HUD、角色、文字、背景、命中光效、按鍵 Overlay、預測軌跡、除錯框或來源影像殘留。**

嚴格區分兩種影片：
1. `geometry.mp4`：**最終產品**，黑／深色純背景、軌道、Tap、Hold、判定線，無額外內容。
2. `comparison.mp4`：**僅供檢查**，來源與幾何影片並排（可加一個疊合／差異視圖），保留時間戳、frame ID、疑似錯誤標記。不要把除錯資訊混進 `geometry.mp4`。

### 特別提醒

本階段的輸出是一種**視覺重建**，不是未來「應該出現的譜面」，不應把看不見的音符提前生成；也不應等音符靠近判定線才第一次畫出來。對「影片目前可見」的範圍力求忠實。當畫面受遮擋，允許短暫使用歷史／離線時序資訊判斷類型與身份，但**不可把沒有觀測到的區域描繪為已觀測的幾何音符**。如果使用離線未來影格輔助分類，必須在 manifest 標示為 `OFFLINE_RETROSPECTIVE`，不得誤稱即時因果能力。

## 1. 專案現狀與約束（全新離線專案；不承接歷史實驗）

截至 2026-11-16 的 GitHub `8.6` 版：

- 過去的離線實驗**已刪除且正式放棄**，本次沒有要與舊實驗共存或避免混淆的需求。直接將新任務視為獨立新專案流程，**不恢復／不比較／不引用舊實驗成果或工具**；現有 Live Runtime 只作為必須保護的既有程式。
- `docs/PROJECT_CLEANUP_MANIFEST.md` 紀錄 `output/recording/` 被保留（清理時盤點為 40 個檔案、約 1.88 GB）；這是歷史盤點，Codex 必須以本機目前實際檔案重新列清單。
- `config/geometry_live_assist.json`：參考解析度 720×404、六軌 SDFJKL、`model_type=linear`、`status=pending_calibration`。**這不是人工確認過的準確幾何**。
- `src/model.py` 已有 `Geometry.normalize()`、`Geometry.rectify()`、`Geometry.boundaries(y)`、`hit_y` 和視角映射可供參考；`src/perception.py` 是 Live Legacy 偵測器，**可閱讀／借用概念，但其輸出不是幾何真值，也不能作為唯一驗收標準**。
- `.gitignore` 排除 `/output`。全部生成影片放在新輸出資料夾，與來源隔離。

**不准 Codex 執行任何 Git 指令（包含 read-only 的 status/diff/log）。** 不准 commit、push。**允許且要求每輪結束清理本輪可重建的暫存／失敗中間輸出**，詳見第 7.1 節；除此之外，禁止刪除或修改任何 `output/recording/` 原始影片、index、CSV、其他既有資料。不要改 `src/live.py`、`src/scheduler.py`、實機鍵盤輸入、既有 Live 預設、`config/reference_timing.json` 或 Live 幾何設定作為本計畫的一部分。新校準結果應寫到**獨立** `config/geometry_video_v1.json` 或輸出資料夾內的配置，不能偷偷覆蓋 Live 設定。

## 2. 先盤點資料，不要先寫一套假設性的偵測器

Codex 自行探索本機 `output/recording/`：

1. 列出每個 Run 的錄影路徑、Video Codec、寬高、影格數、時長、FPS 或時間戳資訊、是否能完整 Decode、是否有 `live_video_index.csv`、index 是否一一對應。紀錄 SHA-256、內容可用性和損壞處。
2. 列出每個來源影片的顯示差異：畫面比例、遊戲場景、軌道透視、判定線、顏色／主題、是否包含選單或非遊玩畫面；異常要記錄，不能擅自用單一 Geometry 套所有影片。
3. 將可用完整 Run 分成**開發組**與**保留驗收組（holdout）**。例如若至少有 4 個不同 Run，就保留至少 1–2 個不供微調；若來源少，保留時間上完全不重疊的區間並明確註記限制。不可看了 holdout 的錯誤就直接修改而又把同一批資料宣稱「獨立通過」；修改後要重設 holdout 或清楚寫成再訓練驗證。
4. 自動生成一份 `inventory.csv` 與 `inventory.md`。如果檔案不存在則寫 `UNAVAILABLE`；不可下載或推測不存在的舊分析檔案。
5. 對每個 Run 擷取代表影格，不只取漂亮畫面：出生區、畫面中央、判定線附近、同一高度多鍵、灰色／中性色音符、青色／黃色 Tap、綠色／黃色 Hold、連續長帶、Hold 起尾、兩條 Hold 重疊、特效最重、遮擋／裁切、最後幀。樣本不足時明確記錄沒有該類案例。

**來源時間規則**：若 `live_video_index.csv` 可用，以 index 的 `video_frame`、`source_frame`、`capture_timestamp`、`acquired_timestamp` 為真實對應；不要用預覽秒數或 `frame / 60` 假裝是真實 capture time。保留來源影格序號。若只有影片 PTS，保留 PTS 和 timebase；若是 VFR 而輸出 MP4 轉 CFR 會失真，須採用保時戳方式或清楚輸出 frame+PTS 映射與誤差報告，不得默默丟幀／複製幀。

## 3. 第一個里程碑：先把軌道和判定線畫準

先建立 `blank_geometry_preview.mp4`（暫時不畫音符），驗證：

- 不同 y 高度的六軌界線與真實遊戲軌道投影一致：上方窄、下方寬；不得只用等寬垂直線代替。
- 判定線與畫面中的真實判定線高度、斜率／形狀吻合；不要把 HUD 上的鍵帽中心誤當軌道中心。
- 正規化與 rectification 必須擁有可逆／可稽核座標轉換：source 像素 ↔ 720×404 native reference ↔ 360px lane plane。
- 至少在多個 Run 的上、中、下三段做源影格疊合檢查。`pending_calibration` 不是通過證據；如果幾何偏移就建立隔離的 Geometry V1 參數，保存調整前／後對比，不改 Live config。
- 只要位置未校準，就不准宣布 `GEOMETRY_VISUAL_PASS`，也不准用後續音符的落點補償錯誤基準。

此里程碑交付 `geometry_alignment_review/`：不同 Run 的 source、純軌道、50% alpha 疊合三圖、座標誤差記錄、可讀的修正建議。顯示錯誤必須在開發集修正後再進下一步。

## 4. 第二個里程碑：新建只負責「當前影格所見」的像素→幾何轉換器

### 4.1 模組邊界

建立**獨立離線程式**（可自行拆分模組），建議的啟動介面：

```powershell
# 列來源和驗證幾何：不改來源，不啟用 Live
python tools/render_geometry_video.py --input-root output/recording --out output/geometry_video_v1 --inventory
python tools/render_geometry_video.py --input-root output/recording --out output/geometry_video_v1 --preview

# 全部來源完整轉換（Codex 應實作等價 CLI）
python tools/render_geometry_video.py --input-root output/recording --out output/geometry_video_v1 --all

# 只重新驗證已生成結果，避免不必要的整段重編碼
python tools/validate_geometry_video.py --root output/geometry_video_v1
```

API 名稱可因實作需要調整，但必須存在易懂且可重跑的單 Run、全 Run、預覽、僅驗證入口，並在 README 寫實際命令。

一條簡單清楚的管線即可：

`source decode → Geometry normalize/rectify → current pixel evidence → Tap/Hold/body/tail instances → native polygons → geometry frame → MP4 + per-frame JSONL/CSV`。

不要將舊 Live 的 `Tracker`、ETA、Engine、Scheduler 或按鍵決策串接進來；也不要為了恢復 V8.5 舊離線架構重建一大堆依賴。

### 4.2 來源像素證據（不能把背景當音符）

- 每個候選實例都要有當前影格像素支持，記錄 mask／bbox／polygon／來源顏色證據／所屬軌道區間／類型／信心／不確定原因。幾何輸出依實例生成，不是用預先固定的「會有幾顆音符」模版補出來。
- Tap 側重完整橫向面板的上／下邊、填色、幾何厚度、局部支撐及時間連續性。
- Hold 側重真正連通的長條及其兩個端點；Head/Body/Tail 可各有幾何元件，但必須能歸屬於同一個來源實例。不能把兩條交錯的 Hold 連在一起；不同顏色的跨越、命中光柱、殘影、碎片、HUD 不得當作 Hold Body。
- 青色／黃色／綠色／粉色／中性色只作為觀測線索。**黃色可能是 Tap 或 Hold；灰色／中性色面板不能預設是背景；綠色長帶可能部分被遮蔽。** 類型須根據當前外觀、連接關係及時序判斷，不是依 HSV 單一條件武斷分類。
- 兩個同一 y 的相鄰 Tap 必須畫兩個幾何物件，不能合併為一個；同一時間 Tap＋Hold 也要分別保留。
- 判定光效與音符面板重疊時，保留來源看得到的音符像素證據；不得把閃光補成完整 Tap。遮擋下能合理確定的類型可在診斷資料標註，但**乾淨影片不可假裝隱藏區域被觀測到**。
- 不允許把 `src/perception.py` 的 Legacy Detection 當成唯一真值；可以拿它作診斷對照，但最後的 source-vs-geometry 審核必須回到來源像素／連續影片。

### 4.3 乾淨影片的幾何語言（請維持固定一致）

固定一個圖例，在任何 Run 都不改語意：

- 背景：單一深色；軌道：六個半透明等透視多邊形或細邊界線；判定線：一條醒目的幾何線段。
- `TAP`：有可觀測面板位置與寬度的實心橫向四邊形／梯形；不得使用角色／原圖貼圖、Emoji、文字。
- `HOLD_HEAD`：實心端面幾何；`HOLD_BODY`：對應可見面積的長條／色帶；`HOLD_TAIL`：另一端面；同一條 Hold 使用一致的主色。不同重疊實例要可區分，至少有不同邊界或圖層順序，不能把它們合成一條。
- 畫面**只**允許這些幾何類別。`UNKNOWN`、低信心、特效、可能的 Note ID 不要畫成確定的音符；請改放到 `uncertain_candidates.csv`、`diagnostic_overlay.mp4`。不准以隱藏所有難辨的候選來假裝沒有誤報；審核要特別檢查缺失區域。
- 保持**源影片畫面座標對齊**，不要為求「整齊」把音符強制吸到軌道中心或沿 y 軸重排。至少保留來源所見寬度、中心、各相鄰音符分隔、頭尾空間位置。若使用 rectified 內部座標，輸出時需轉回同一 native 視角。
- 不畫沒有真實像素的未來預測 note；不畫按鍵、數字倒數、ETA、準確率 HUD。

### 4.4 音符出現與消失

- 畫面剛進入視野時就要能出現在幾何影片中，不可只在靠近判定線才畫；近判定線強光下不應突然多畫重複 Note。
- 同一個真正連續的 Hold 在相鄰影格不能無證據地 Tap↔Hold 切換；短暫遮擋需要記錄而不是產生一整條假色帶。
- 同一個 Tap 不能在一個畫面被複製兩次或合併兩個相鄰面板；新舊身份以來源空間證據協助保持穩定，但不必建立實機可用的 Track ID/鍵盤排程。
- 畫面外進出、片段首尾、遊戲暫停／選單需明確處理；不要在非遊玩畫面繼續畫幽靈音符。

## 5. 第三個里程碑：所有 Run 的完整影片，不只挑幾張成功截圖

每個完整 Run 建立**獨立輸出資料夾**：

```text
output/geometry_video_v1/
  inventory.csv
  inventory.md
  config_snapshot.json
  run_<原本run_id>/
    geometry.mp4                 # 乾淨產品
    comparison.mp4               # source / geometry 並排，比對專用
    diagnostic_overlay.mp4       # 可選，含類別、uncertainty、來源 bbox/ID
    frame_index.csv              # output frame ↔ source frame ↔ PTS/capture time
    instances.jsonl              # 每幀的 Tap/Hold/head/body/tail 座標和來源像素證據
    uncertain_candidates.csv
    qc_summary.json
    checksums.json
    review_windows/
      *.png / *.mp4              # 高風險段落與前後連續影格
  validation/
    validation_results.csv
    issue_log.csv
    holdout_report.md
  iterations/
    iteration_0001.md         # 保留簡短實驗紀錄，非大型中間資料
    iteration_0002.md
    cleanup_history.csv       # 每一輪要有一筆可驗證清理紀錄
  _scratch/                   # 只在執行時存在；每輪結束清空過期工作物
    iteration_XXXX/           # 試作影片、frame cache、debug dump、失敗輸出
  final/
    result.md
    verification_manifest.json
    cleanup_summary.json
```

不得覆寫已接受的完整驗收基準而不記錄來源／程式雜湊；**每一輪只留有用的摘要、已驗證案例和真正需要對照的影片**。失敗試作 MP4、重複全片轉碼、影格 cache 都放 `_scratch/iteration_XXXX/`，每輪依第 7.1 節清理。正式保留第一個基準（若有明確用途）、最新已接受候選及最終版；沒有比較價值的舊版本不要無限累積。錄影量多時逐個 Run 處理，以固定上限記憶體串流，不把整段影片全部載入 RAM。必要時分段編碼、再按來源順序拼接並檢查對齊。

至少檢查：每個完整來源都有輸出、影格數與 PTS/index 一致、影片可以重新解碼、來源 hash 未變、幀序未跳／重排、不把 4.9 秒等「預覽時間」誤當 capture time；如果來源本身缺影格就明確記錄。

## 6. 第四個里程碑：Codex 必須真的「看原片與幾何結果」驗證

**嚴禁使用「模型自己輸出的 mask 與自己輸出的幾何影片一致」作為成功驗收**：這只能證明渲染器沒有漏畫其**已偵測到**的候選，無法證明候選正確或沒有漏偵。

請建立**分開的三層檢驗**：

### L1 — 機械性硬門檻（可客觀 100% 檢驗）

- 來源檔案 hash 與輸出 manifest 配對；來源影片/index 無修改。
- 完整可用 Run：輸出可 decode；frame join 100%；幀數一致；順序單調；時間戳明確可追溯；如有 VFR 特殊處理明確記錄。
- 純幾何影片只能由幾何 primitives 繪製，禁止源影片 compositing、HUD／人像／文字；每個繪製的 Tap/Hold 都有對應 `instances.jsonl` 記錄與來源 pixel evidence。
- 所有座標在合理範圍、六軌且幾何投影不自相交；判定線位置與配置一致；Hold body 不與不同來源 group 無證據合併；同幀物件重疊或同 y 不因資料結構限制強迫合併。
- 在用純解析／固定人工合成影格建立的單元測試中，Tap 的分離、跨軌、Hold 頭尾、兩條不同 Hold 交錯、近判定線光效、相似顏色、音符進出畫面、空白幀都通過。

### L2 — 來源導向的自動／視覺檢查（獨立於主要候選規則）

- 建立可由程式重新產生的 `source|geometry|overlay` 對照，至少涵蓋：每個 Run 的開頭／中間／結尾、音符剛出現、判定線附近、快速連點、同 y 雙 Tap、Tap+Hold、灰色中性色、黃色 Hold、兩個 Hold 重疊、光效遮擋、被裁切 Hold。**所有缺漏／低信心的案例也要入選**，不可只抽好看的幀。
- 檢驗員若能直接視覺讀圖／影片，就必須逐段觀看連續前後影格；若工具沒有可靠視覺分析能力，使用 contact sheet、來源對齊截圖及客觀像素檢查；仍不能檢驗的應回報 `REVIEW_REQUIRED`，而不是宣稱看過。
- 以來源中的獨立「橫向面板／色帶存在」候選搜尋（不能只是重跑同一個偵測器）檢測可能漏音符，對照渲染後的實例；稽核**音符有無、類型、數量、橫向分隔、座標、顏色／連接歸屬、首次可見、持續時間和消失時間**。
- 每個「轉換錯誤」都記錄 `run_id`, `source_frame`, `capture_timestamp` / PTS, `issue_type`, `source_crop`, `geometry_crop`, `confidence`, `root_cause`, `fix`, `rerun_status`。不需要使用者介入才能修正的就自行修。
- 即使完全沒有獨立人工真值，也要對最重要的案例做**明確來源視覺審查記錄**，但只能標 `AUTO_VISUAL_REVIEWED` 或 `PROVISIONAL`，**不能標 `HUMAN_REVIEWED`**。

### L3 — 保留集與外部真值

- 上述改進必須在沒有用來調閾值的 holdout Run 或區間重測；新增／減少的幾何實例都列成 case-level delta，絕不能只看「總音符數變多了」。
- 如果有真正獨立、人工作出的音符框／類型／軌道／Hold 歸屬標註，才可以報物理音符 precision/recall/type accuracy；沒有就寫 `NOT_EVALUABLE`。使用者後續可透過 6–12 個高風險案例做最終人工確認，不應讓 Codex 無限等待人工標註才進行所有自主工作。
- 不允許把 `src/perception.py`、人工按鍵事件或幾何輸出的結果當成物理音符真值。

## 7. 自主修正迴圈（Codex / Goal 自己跑，避免一小步一停）

每一輪：

1. **發現問題**：完整來源抽樣 + 上輪 `issue_log.csv`，先排序最有影響的**具體可重現**錯誤（例如 4.9s 上方 Hold 漏畫、灰色板不見、兩條 Hold 被合併、青色 Tap 被特效吃掉）。
2. **提出單一主假設**：準確指出來源幀和像素證據、預期改善、可能傷害的負例。不要一次改五種不相關門檻。
3. **實作與快速檢驗**：先只重跑失敗前後的連續 0.5–2 秒窗口和負例窗口；每輪保留前／後對照圖及個別 instance 差異。
4. **反例掃描**：擴展到同場景其他時間、其他顏色、Tap 與 Hold 並存、重疊與光效區域。若修掉一處卻讓其他案例退步，直接撤回本輪改動，保留反例。
5. **全片驗證**：快速檢查通過才跑所有開發 Run 完整輸出、L1/L2；重大架構調整或候選最終版再跑 holdout L3。
6. **接受／回退**：只有在可見來源對齊、幾何完整性和覆蓋率的多目標檢驗下改善才保留；不要為了讓數字好看而默默把難題都標 UNKNOWN／不畫。
7. **記錄**：先寫 iteration report、issue status、來源 hash、改動摘要、測試命令和驗收結果，將要保留的證據正式落盤並校驗。
8. **每輪結束必須清理**：按第 7.1 節執行 `preview → 保護清單核對 → 只刪可重建暫存 → 重新檢查`，記錄刪除與保留項。**接受或回退、成功或失敗、甚至本輪發生例外，都必須執行安全清理步驟**；若清理受權限限制則記錄未完成，不繞過限制。
9. **繼續自主迭代**：除非真的被工具／資料阻斷，**不必每輪等待使用者，也不需要 Git / Push**。

建議先設定每一類實質問題的修正嘗試上限 8 次，若**連續 4 輪有足夠測試但沒有可重現的可見改善，也沒有新找到的根本原因**，應停止反覆調閾值並整理未解問題；這是停損而非成功。若有新的客觀 root cause，允許再開一輪並記錄原因。不可用無限迴圈硬撐到「全部 OK」。

### 7.1 每輪自動清理規範（必做，不只是最終清理）

**目標：每次迭代結束，工作目錄只留下「繼續迭代、驗證結果、使用者看影片」真正需要的檔案。** 清理是管線的標準尾端步驟，不應累積幾十輪巨大影片。請建立 `tools/cleanup_geometry_iteration.py`（或等價安全函式），由迭代 orchestrator 自動呼叫；提供 `--preview`、`--execute`、`--iteration`、`--manifest`，預設 preview。每輪允許對**明確授權且白名單內**的目標執行清理，不需要每輪向使用者請示。不得藉此繞過環境的執行政策。

**A. 可以刪（均須由本輪新流程產生、可重建、範圍明確）：**

- `_scratch/iteration_XXXX/` 中用於調參的短片、失敗轉碼 MP4、`.tmp`、解碼影格 cache、暫存遮罩、重複的 contact sheet、臨時 profiling CSV/JSON、重複的 debug dump、崩潰殘檔。
- 未被採用、已完成回退且存在可核對小型 before/after 證據的**重複候選**輸出（若是唯一本輪錯誤證據，先保留一份精簡片段／數據再清）。
- 對同一來源、同一設定、同一版本 hash 完全相同的重複影片／中間資料；先核對 SHA-256 與用途，不因檔名類似就刪。
- 迭代時生成但不再被任何報告／驗證引用的中間快取；首選直接串流處理，避免產生大量影格暫存。

**B. 絕對不能刪／覆寫：**

- 整個 `output/recording/`、原影片、原始 index／CSV、使用者提供的標註、其他既有目錄；任何目前不屬於新幾何工作區的東西。
- `src/`、`config/`、`tests/`、`docs/`、`tools/` 等程式／設定來源（清理工具不可刪程式碼）；Live／Scheduler／既有 Geometry 和校準檔。
- `inventory.csv`、幾何校準版本、source/config SHA-256、穩定 frame/PTS 對齊表、當前被接受的 `geometry.mp4`、`comparison.mp4`、當前 `instances.jsonl`、正式 validation、issue log、必要回歸案例及最後報告。
- 仍未解決的問題所需**唯一**證據、不可再重現的輸出、holdout 對照、最終交付檔案。

**C. 清理操作的防呆要求：**

1. 寫入每輪 `cleanup_manifest.json`，列出 `path`、檔案大小、來源迭代、用途、`reason`、是否可重建、是否仍被引用、SHA-256（適用時）、`KEEP`／`DELETE_CANDIDATE`／`BLOCKED`。
2. **先完成報告與完整性檢查**（正式輸出／唯一證據可讀且雜湊固定），再 preview 清理；不得先清掉失敗定位資料才發現無從重建。讓 iteration report、validation manifest 引用**正式保留路徑**，不可指向將要刪除的 `_scratch`。
3. 清理只允許 workspace 根目錄內的 `output/geometry_video_v1/_scratch/` 和**經明確登記的本任務產生、未採用的重複工作輸出**；先解析絕對路徑與 symlink／junction，拒絕逃逸、未知目錄、符號連結跳轉、父目錄／整個 `output/` 的遞迴刪除。嚴禁泛用 `rmtree(output)`、萬用字元誤刪或掃描所有大型檔案刪除。
4. 保留當前正式版、最新可重現通過的基準與至少一份關鍵反例；其他不需留存的中間檔優先不生成，其次刪除。刪除應該是可預測、明確 allowlist、驗證後的操作。
5. 執行後重新確認 `output/recording/` 的檔案清單／hash **未變**、正式輸出仍存在且可開啟、清理候選已不在；若某項驗證不通過則停止後續刪除並回報錯誤。
6. 在 `iterations/cleanup_history.csv` 追加一筆：`iteration_id,bytes_before,bytes_deleted,files_deleted,files_kept,blocked_paths,validation_status,manifest_path`；在迭代報告同時列出累積回收空間與未清原因。若沒有可刪檔案也記 `NO_SAFE_CLEANUP`，不得省略。
7. 發生例外／測試失敗時，在 `finally` 中仍**嘗試**安全清理，但先留住 failure report 與唯一重現片段；若尚未確定資料安全，只產生 preview 與 `BLOCKED`，不強行刪。清理失敗不可被當成演算法成功，也不可阻止回報真正測試失敗。

**每輪結束應看到的是：短而可追溯的迭代報告 + 關鍵案例 + 當前可檢查成果，而不是堆積一大批已被淘汰的 MP4。**



## 8. 完成／停止條件（重要）

### `GEOMETRY_VIDEO_PROVISIONAL_PASS`（可以交給使用者觀看的離線候選）

必須**全部**成立：

1. 所有完整可用 `output/recording` Run 都有完整 `geometry.mp4`、`comparison.mp4`、同步 index、instances 和 manifest；不完整來源列出例外，不宣稱完整。
2. L1 全部通過：來源 hash 不變、decode 可用、幀序與時間對齊、幾何合法、無 HUD／背景／來源貼圖、無輸入／Scheduler／Live 變更。
3. 六軌與判定線有獨立原片對齊檢查；`pending_calibration` 已經透過新獨立幾何參數校正，或若沒有足夠依據則明白宣告 `GEOMETRY_ALIGNMENT_UNVERIFIED` 並**不可通過**。
4. 所有在開發／holdout **已確定為可見高信心音符**的重大漏畫、無端重複、Tap/Hold 錯類型、不同 Hold 合併、跨軌錯位，都已修復或給出可直接審核的證據；不以單一「總音符數增加」替代。
5. L2 審核分層覆蓋所有存在的高風險情境，至少每個可用 Run 都包含前／中／後完整窗口、光效與判定線窗口；holdout 不出現未解決的重大確定性錯誤。若沒有足夠圖像證據，結果應是 `REVIEW_REQUIRED`，而非 `PASS`。
6. 機械性錯誤全為 0，單元測試全部通過；使用者可直接開啟幾何影片觀看。結果報告**清楚標 `PROVISIONAL`**，不宣稱音符召回率 100% 或實機零 Miss。
7. **所有迭代均有 cleanup manifest 和 cleanup history**，沒有因清理造成不可重現的證據損失，來源 hash 與正式交付未被破壞；除合法 `BLOCKED` 外，已完成可執行的逐輪清理。

### `GEOMETRY_VIDEO_NOT_PASSED`

仍有可重現的漏畫、混淆、軌道／判定線錯位、畫面同步錯誤，或已達停損條件但無法修正。保留目前最好的候選和逐案證據，而不是宣稱 OK。

### `REVIEW_REQUIRED` / `BLOCKED_WITH_EVIDENCE`

來源含無法判明的物件、嚴重遮擋、缺少必要影格或視覺比對能力、無法確認軌道／判定線、Codec 工具不可用，且確實無法再自主驗證。列出**最少量**需要使用者確認的具體 `run/frame/crop/問題`；如果有其他可做的工作則先完成。

**沒有 `ZERO_MISS_PROVEN`、`LIVE_READY`、`PERFECT_NOTE_RECALL` 這類本階段狀態。**

## 9. 最終交付和 Codex 的回覆格式

程式與文檔（Codex 自行實作並驗證）：

- `tools/render_geometry_video.py`（或等價的清楚 CLI）與必要的 `src/geometry_video/` 隔離模組。
- `tools/validate_geometry_video.py`、`tools/cleanup_geometry_iteration.py`，以及使用 synthetic + 少量來源影格的回歸測試；測試不得依賴歷史離線工具。
- `docs/GEOMETRY_VIDEO_V1_RESULT.md`：一頁式結論、Run 數／總影格數、通過／失敗條件、音符來源分類最常見的問題、重跑命令、暫定／未確認的界限。
- `docs/GEOMETRY_VIDEO_V1_REVIEW.md`：疑難窗口、審核依據、視覺連續性和幾何對齊結果；只記實際已檢查的來源案例。
- `output/geometry_video_v1/` 中所有來源的 `geometry.mp4`、`comparison.mp4`、`instances.jsonl`、來源時間對齊表、issue log、必要短片、manifest 與最終摘要。另須交付逐輪 `cleanup_history.csv` 及最終 `cleanup_summary.json`，證明無需保留的暫存已清理。
- `README.md` 更新一段「如何觀看幾何影片／如何重跑」，指向新的離線 CLI。不要修改 Live 啟動流程。

最後請用**繁體中文**簡潔回答：

1. 完成了幾部完整來源影片的幾何轉換，影片與對照檔在哪裡？
2. 哪些具體 Tap／Hold／判定線問題已修正？至少提供 3 組真實來源前後對照證據（如該類情境不存在，講清楚）。
3. 哪些可見音符或歸屬還是有疑問？是 `GEOMETRY_VIDEO_PROVISIONAL_PASS`、`NOT_PASSED`，還是 `REVIEW_REQUIRED`？
4. 使用者現在只需要打開哪個資料夾、看哪幾段影片，才可以快速做最後確認？
5. 總共執行幾輪清理、刪了哪些類型的可重建檔案／回收多少空間、哪些檔案保留及為什麼、有無安全或權限阻礙？

---

## 給 Codex 的最重要原則（不需要每次問使用者）

> **不要重建舊 V8.x 離線實驗；只做忠實的「原片 → 乾淨幾何影片」。你可以自己選擇演算法、自行看片與修正，但所有聲稱正確的結果都要能回到原始影格驗證。若無法確認，不要硬猜為 Tap 或 Hold，更不要把不確定當成已通過。禁止任何 Git 指令；每輪結束安全清理可重建暫存，但禁止修改原始錄影、正式證據、Live、鍵盤輸入或 Scheduler。**
