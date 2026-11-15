# HoloDream V8.4 — 自主閉環修復、影片回放與離線驗收計畫

> **交給 Codex 執行的工作指令。這不是一份「做完一個小修正就交差」的清單。**
>
> 你的任務是在目前工作區內，**自己讀取影片及原始記錄 → 定位問題 → 修改實作 → 測試 → 重播影片 → 分析失敗 → 繼續修正**，持續到下列離線驗收條件成立，或確實遇到無法在現有資料／權限／環境下克服的阻礙。不要每做完一輪就停下來請使用者 Push 或問下一步。
>
> **嚴禁自行執行任何 `git` 指令，包括 status、diff、add、commit、push、pull、checkout、reset、clean。** 使用檔案讀寫、比較與測試工具即可。使用者自己負責 Git。不可自行操作真實遊戲、OS 鍵盤注入或啟用 Active。

## 0. 既有事實與工作起點

Repository: `denniswang293/holodream_auto_live_assist`。本計畫是根據 2026-11-15 已檢查的 `main` 版本（提交 `1e68b710ba5ccccbcc56fccdecaf5419a87ec2ab`，commit 訊息為 `8.4 beta 3`）以及上次提供的 V8.4／V8.5 Mask、Overlay、三段視覺比較影片和 V8.5 評估文件制定。**執行時以工作區實際檔案及可重現量測為準；若內容不同，必須記錄差異而非盲信數字。**

參考文件：

- `docs/V85_IMPLEMENTATION_RESULT.md`
- `docs/V85_EVALUATION.md`
- `docs/V85_EARLY_IDENTITY_DESIGN.md`
- `docs/V85_CLEANUP_MANIFEST.md`
- `docs/V84_REGRESSION_ROOT_CAUSE.md`
- `README.md`

主要程式：

- `src/early_perception.py`、`src/lane_segmentation.py`、`src/lane_filter.py`
- `src/tracking.py`、`src/engine.py`、`src/timing.py`、`src/scheduler.py`
- `src/perception.py`、`src/model.py`、`src/live.py`
- `tools/replay_lane_filter.py`、`tools/replay_lane_filter_measured.py`
- `tools/attribute_lane_action_losses.py`、`tools/profile_v85_birth.py`
- `tools/render_lane_filter.py`、`tools/render_v85_review_set.py`
- `tools/summarize_v85_replay.py`、`tests/`

原始資料（若本機存在）：

- `output/recording/run_20261106T164049_800126Z/`
- `output/recording/run_20261106T171405_612600Z/`
- `output/assist/run_20261109T143554_007912Z/`
- `output/assist/run_20261109T144952_721038Z/`

這些是已記錄的分析來源，**不要認為 GitHub 上必然有檔案**：目前 `.gitignore` 排除大多數 `/output`。若某一個 Run 缺少影片、index 或必要 CSV，將它記成 `UNAVAILABLE`，自動使用其他完整 Run，不可捏造結果，不可把不同 Run 的 UID 或時間戳直接硬湊。

已報告的基準（僅供一致性檢查，非遊戲命中真值）：

| 模式 | Legacy | V8.4 Segmented | V8.5 |
|---|---:|---:|---:|
| 固定 14ms Mock key-down | 343 | 213 | 199 |
| 優化後 measured-time Mock key-down | 339 | 141 | 39 |
| measured-time 丟棄影格（3159 幀） | 3 | 45 | 111 |
| measured-time 平均耗時 | 17.01ms | 30.54ms | 35.28ms |
| measured-time P90 耗時 | 24.15ms | 41.95ms | 46.89ms |

上述固定模式的 14ms 是**合成邏輯延遲**；measured-time 才是實際 `Engine.observe + Engine.decide` 的 Wall Time、以 latest-frame-slot 模擬丟幀；兩者不得混為一談。Host 速度、操作環境會造成差異，必須做有條件的重跑。

現有 Legacy-action 對照 V8.5 的分類：116 same-key、29 wrong-key、49 Engine eligibility、8 Timing、13 tracker confirmation、5 pixel UNKNOWN、123 unresolved，共 343。**Legacy 動作也可能是誤判，這是診斷基線，不是 343 個真音符。**

觀察到 V8.4 與 V8.5 在 4.9s／6.0s／14.9s 的 Mask 幾乎相同，V8.5 的 Overlay 文字變乾淨，**不能當成 pixel precision 提升的證據**。現有四段自動掃描得到 13,128 candidate tracks、2,966 confirmed tracks；這是演算法產生的 Track，**不是** 13,128 個真實音符。黃 Hold 尚未成功建立已驗證確認群，灰色板多停留在 `pending`。

## 1. 真正目標與自主權

### 1.1 核心目標

讓 **實際來源影格上的物理音符** 能以低誤判、低 ID 中斷、正確鍵位與時間估計，從出生一路追蹤到 Mock 按下／Hold 釋放，且在可負擔的運算延遲下運作。改善結果必須包含**視覺辨識、跨影格 Identity、類型判定、時序、按鍵選擇、效能、安全**，不能只優化其中一項。

你可以自主決定問題的優先順序與修法，必要時修改多個模組、移除沒有收益的複雜分支、改寫低效資料流程、建立工具及測試。**不要為保留 V8.5 的既有設計而保留已證明有害的機制**。如果某個新功能（例如 Hungarian assignment、`pending` 路徑、neutral component 掃描）是主要退步來源，可以實證後重構或回退其局部做法。

但須維持這些邊界：

1. **不修改 `src/live.py` 的 Live 預設 Perception / Active 選擇；不進行真實 OS 輸入。** 只做離線 Replay 與 `MockActuator`。
2. **不放寬 Scheduler 安全規則**（focus/ROI、stale capture、lateness、同鍵衝突、6 key 限制、Hold timeout、release freeze 等），更不能繞過拒絕原因來增加按鍵數。
3. 不修改原始 `output/recording/run_*/`、`output/assist/run_*/`、人工標註、原始影片、原始 index、幾何與 timing calibration 作為「改善」手段。
4. 保持因果性：只能用**當前／過去**影格做決策；不可用未來影格、人工按鍵事件或 Ground Truth 偷看後安排按鍵。Ground Truth 僅用於事後驗收。
5. 若系統目前有 **每首歌 Global 固定速度 ETA、PF 僅負責追蹤** 的架構，不要把 PF ETA 或影格局部速度再接回預按鍵，除非先有獨立實證與清楚說明；不要假設不同歌一定同速。先查實作再作判斷。
6. 不自行執行任何 Git 指令；不刪除原始資料，也不透過其他工具繞過已存在的刪除／權限封鎖。

### 1.2 你不需要等待的事情

遇到可以從 Repo 與影片回答的問題，自己查、自己試。不要詢問「要不要先優化 Tracking」、「要不要跑 Replay」、「要不要修改參數」、「要不要下一輪」；自行決策並留下理由。**只有當真實阻礙讓工作無法繼續時**，才在最終報告明列所缺的材料或操作。

## 2. 自動化迭代機制：先建立可自我驗證的工具

這是本計畫第一個交付：**建立可重複執行的完整驗證流程**，不要靠人工翻三張 Overlay 推測好壞。

請在 `tools/` 加入或擴充合理數量的工具（名稱可調整，例如 `tools/v86_autoloop.py`、`tools/v86_evaluate.py`、`tools/v86_case_report.py`），以 Python CLI 呼叫既有工具與同一份 fixture/config。可採 shell/bat 搭配，但不要引入難以維護的框架或新的大依賴。

驗證至少覆蓋：

- **資產完整性**：哪個 Run 的 MP4、`live_video_index.csv`、事件、原始 SHA 等可用；按 `video_frame` 連續解碼並以 index 驗證時間與來源。過去 MP4 random seek 曾造成 frame/index mismatch，必須防止復發。
- **逐幀的生命週期記錄**：每個 pixel component → detection → cap → physical-note candidate → track UID → `birth_info` → state/visibility → type/lock → Timing estimate → Engine eligibility → Scheduler offer/reject → Mock down/up。追蹤未發生動作時必須有具體、可定位的最後失敗點。
- **身份追蹤稽核**：同一個物理候選疑似 split、duplicate、ID switch、兩個候選 false merge、跟丟、重生、長時間 pending、stale、lane/key 切換；不得用 provider 內部 UID 當跨版本真實身份。
- **效果與保護**：按音符分類（cyan/yellow/neutral、Tap/Hold、獨立/重疊、判定線附近、遮擋）彙整的 TP/FP/FN 只可在有可信標註的 case 上報告；沒標註的改為 `UNVERIFIED` 與描述性診斷。
- **時間**：capture/acquired/processed/press/release 時間軸、ETA 值、uncertainty、計算時間、frame drop、scheduler pause/rejection，分清早按／晚按／未入列／被取消。
- **視覺**：對失敗案例生成短連續影片（來源、rectified、mask、overlay、時間線、各版本並排），不是僅截單張。畫面不要被 UNKNOWN 標籤遮到無法閱讀；完整 UNKNOWN 資料仍保存在 CSV。
- **性能**：record per-stage mean/P50/P90/P99 和最慢 frames，尤其 mask/component classification、Tap recovery、Tracker association/Hungarian、Engine decision；把 **運算時間** 與渲染輸出／MP4 encoding 時間分開。

每輪輸出到 `output/analysis_v86_autoloop/iteration_XXXX/`；留小型、可追蹤的失敗案例與 aggregate metrics。不要每輪都保存一份數 GB 完整 MP4；完整影片只在基準／最終驗收等必要節點保存。維護一份易讀的 `iteration_history.csv`／`iteration_history.md`，包含修改假設、版本狀態、指標、是否改善、下一輪方向與原因；不能只有「tests passed」。

## 3. 建立真正能揭露錯誤的案例庫

### 3.1 必查的來源區間

在可用的 Assist Run `run_20261109T143554_007912Z` 上，以 source/index 對齊下列**預覽時刻**，不要把畫面顯示 4.9s 當成絕對 capture timestamp：

- 約 **4.9s／frame 294**：早期色塊、完整 Tap 面板、背景與 UNKNOWN 干擾。
- 約 **6.0s／frame 360**：長條 Hold 的連續 Body、Head、Tail／按下資格。
- 約 **14.9s／frame 894**：同時存在多個 Hold、Tap、彎曲 ribbon、不同 lane 的重疊及 head/tail ownership。
- 如資料仍存在，補上 V8.4 回歸報告提到的 **recording frame 77** Hold endpoint，以及 **frame 97** 已追蹤但 stale 的案例。
- 另外自動挑出**原先 123 unresolved、29 wrong-key、長時間 pending、最高 P99 延遲、最多 frame drop**的代表窗口，依不同 root cause 分層抽樣，不能只選看起來成功的案例。

對每個窗口至少保存前後約 0.5–1.0 秒的連續影格、來源來源/索引對照、偵測/身份/事件時間線，以及 `review_queue.csv`。如果展示工具能直接逐幀分析來源，則自己對照來源畫面，產生**暫定的機器／模型審核標記**；**不可把這種自我審核寫成 HUMAN_REVIEWED**。

### 3.2 Ground Truth 的正確做法

先看是否已有**真正人工完成**、來源可信的標註。存在的就以 source hash、run_id、frame index、class、lane、note ID、Hold endpoint owner 做嚴格匹配；不存在就採用兩層評估：

- `PROVISIONAL_VISUAL_AUDIT`：可由 Codex 自主看片、按時間連續檢查，適合找線索、寫回歸案例、發現系統性假陽性與明顯漏判，但**不是**獨立真值。
- `TRUSTED_ANNOTATION`：需由來源獨立審核且可追溯的標記支援，才可以計算 physical-note recall、precision、IDF1、Hold owner accuracy 和遊戲類別的漏判率。

**不要透過 V8.5 自己輸出的 Mask 作為正確答案，再拿 V8.5 測它自己。** 不要用 Legacy 的每一次 Mock down 當真音符，也不要用人工 `player_key_events.csv` 直接當音符 Ground Truth；它們只能當事後輔助線索。

如沒有可信真值，可以繼續自主修復、做代理指標與視覺審核，但最終只能報 `OFFLINE_CANDIDATE_PASS`／`OFFLINE_NOT_PASSED`，不可報「已證明實際不會 Miss」。

## 4. 優先定位問題，而不是先調一堆參數

第一輪必須**重新產生足以解釋全部重大損失的 action attribution**。基準報告 343 例之中有 123 unresolved，這個分類太粗，尚不足以指導開發。對每個與 Legacy action 幾何近似的軌跡，查詢真正的最後實證事件，盡可能細分：

1. `NO_PIXEL_CANDIDATE`：來源影格有疑似音符，但沒有 pixel candidate；若來源未人工標註，只能列為疑似。
2. `MASK_ROLE_OR_ADAPTER_DROP`：像素有了，但被分類為 UNKNOWN／artifacts／body only，或轉換時漏掉。
3. `TRACK_NOT_BORN`／`TRACK_SPLIT`／`ID_SWITCH`／`AMBIGUOUS_ASSOCIATION`／`FALSE_MERGE`。
4. `TYPE_PENDING_NEVER_RESOLVED`、Tap vs Hold 衝突、黃色 Hold head/gray panel 無法取得足夠正向證據。
5. `CONFIRMATION_TOO_LATE`／`INSUFFICIENT_MOTION`／`OCCLUDED`／`OBSERVATION_STALE`。
6. `WRONG_KEY_OR_LANE_SPAN`、同 y 軸 chord 中 Tap+Hold 互相衝突。
7. `TIMING_NOT_READY`／`UNCERTAINTY`／`PREDICTION_LATE`／`OUTSIDE_COMMIT_HORIZON`。
8. `SCHEDULER_REJECTED`／`CONFLICT`／`CAPTURE_TOO_OLD`／`FRAME_DROPPED`。
9. `UNRESOLVED_WITH_EVIDENCE`：若無法可靠歸因，**保留 UNRESOLVED**，不可猜原因湊滿百分比。

加入**動作對照之外的漏音符發現機制**：在有可信標註的窗口評估所有物理音符；沒有可信標註則掃描上方出生區域的可重複運動實體，標記疑似未產生動作的片段並生成影片審核候選。不能只從 Legacy pressed actions 反推所有錯誤，因為兩版都漏的音符不會出現在那裡。

依實際量測結果排序修正；以下只是待檢查假說，不是預設根因：

- `src/tracking.py` 的 Hungarian 全域配對有未配對欄位，成本在 fragment 很多的畫面可能過高，且 close-cost ambiguity 過度拒絕可能害既有 note 失去 observation。
- `src/early_perception.py` 的 `plate_fragment/pending` 對灰色音符可能永遠沒有形成可執行的類型，尤其 `type_pending` gate。
- `src/lane_segmentation.py` 的 neutral/UNKNOWN 大量元件分類造成 CPU 成本，但不一定增加有效候選。
- 完整面板和 Hold endpoint 類型證據可能被過於嚴格的 `full_face`、`connected_ribbon`、lock/confirmation 條件擋住。
- 同一個連續 Hold 的 Head、Body、Tail 在跨影格會失去唯一 owner；不能只從 Mask 看起來連續就判定修好。
- 若解決時間問題需要調整 Global ETA，必須區分**每首歌曲的速度與校準**，不可隨意把 PF 預測速度接回。

## 5. 每輪自主改善流程（必須真正執行）

1. **Baseline**：先在未修改或當前工作樹現況跑 `pytest`、compile、固定延遲 Replay、measured Replay、case videos、per-action attribution；記錄來源檔 hash、依賴、CPU 環境、config、執行參數與完整結果。
2. **排序問題**：列出目前最大三個能由實證支持的 root causes；選對「錯誤案例覆蓋最大，且不會犧牲安全性」的一項先修。
3. **小幅、可回退的實作**：修真正根因，先加最小可重現失敗測試（真實 fixture 或合成已知真值），再修程式。可自由重構，但一輪盡量讓因果歸屬明確。
4. **快速迴圈**：跑單元測試、少數關鍵窗口、短區段 fixed replay、失敗案例影格對照。失敗就直接分析和再修，不要交差。
5. **完整迴圈**：小測通過後跑**完整相同來源** fixed 14ms A/B，接著 measured-time A/B；性能變動明顯時要重跑對照 baseline（避免將不同負載誤認算法提升），必要時跨 Run 驗證。
6. **反事實檢查**：對「修好的案例」展示修前／修後同來源影格與生命週期、最後按鍵原因；同時搜尋新增的誤判、錯鍵、ID merge、Hold Release、stale/rejection。若只是讓所有按鍵數上升但錯誤增加，要回退該策略。
7. **記錄與選擇**：保存這輪的 `hypothesis → modification → measured evidence → failures → decision`。若不改善或安全回歸，**局部還原那次修改**（用工作區檔案備份，不用 Git）。再選下一個問題繼續。
8. **持續迭代**：直到第 6 節的離線門檻成立，或所有合理的低風險方案都被證據否決／環境阻擋。不要因為跑過一次 `pytest`、改進一張圖或有多幾次 Mock down 就提前終止。

**為避免無界循環**：不是固定做 3 輪就結束；但每一輪要設定可判斷的 hypothesis、成功／失敗與回退條件。連續多輪沒有可重現收益時，不要盲目不停放寬 gate，改做最小失敗案例、性能剖析或記錄真正 blocker。遇到運算預算或執行環境的實際上限時，輸出截至目前完成的結果及阻礙，不得宣稱「已完成」或假設還能在背景繼續。

## 6. 離線驗收門檻（同時成立才可宣告通過）

### A. 安全性與因果性（硬性，零容忍）

- 既有所有單元／整合測試通過；新修案例有可重跑 regression tests。
- 0 illegal key、0 duplicate press UID、0 press without release、0 release failure、0 same-key illegal overlap、0 未授權 OS 注入。
- 不使用未來影格、人工事件及 Ground Truth 作為線上候選決策；不放寬現有 Scheduler safety bounds。
- 不把被遮擋的幀偽裝成新 observation，不用 predicted pixel 偽裝來源真像素。
- 獨立 Hold + Tap、多 Hold、錯誤歸屬、尾端遮擋、按下/放開轉移均有可重現安全測試。

### B. 視覺與身份連續性（以來源影格為依據）

- 4.9s、6.0s、14.9s 及新抽到的代表性失敗窗口，逐幀對照顯示改進且沒有新增明顯的「真音符當雜訊／效果當音符／跨 lane 合併／Head-Tail 錯配」。
- 至少提供一個灰色板、一個黃色 Hold、一個多 Hold+Tap 重疊的**連續追蹤證據鏈**，無法取得真實素材或正向證據則標 `NOT_EVALUABLE`，不得以合成測試取代真實驗收。
- 若存在可信真值，報 per-class recall / precision、ID switch、false merge、Hold endpoint owner accuracy，並以 baseline 比較，禁止有未解釋的嚴重回歸。
- 若無可信真值，報 `PROVISIONAL_VISUAL_AUDIT` 與 `NOT_HUMAN_REVIEWED`，**不能聲稱物理音符召回率或已消除 Miss**。

### C. 固定延遲的因果 Replay（品質硬門檻）

- 同一組 indexed frames、same geometry/timing/key map、same clock/Arm/Poll 設定完成 full Legacy、V8.4、當前候選 A/B。全部 3159 幀（若來源可用）均入列；完整事件流不受 Scheduler 512 event snapshot 截斷。
- 顯示疑似漏判與錯鍵的**逐案證據**，不只比較 total press。重點是已配對且鍵位正確的已驗證案例增加、錯鍵/重複/幻影事件沒有惡化。
- 先前的 123 `unresolved` 必須獲得明顯更細的可追查分類或伴隨足夠獨立來源證據說明為何無法分類；不得僅改名稱、改閾值或用 Legacy 當假真值。
- 若同來源 V8.4/Legacy 對照有全面惡化的清楚訊號，不能標通過；必須修正或把結果列為 failure。

### D. Measured-time 的實用性（品質硬門檻）

- 用真實量到的 `Engine.observe + Engine.decide` 耗時、latest-frame-slot、相同來源與同等 host 條件，完整重跑每個 Provider；至少兩次獨立重播以辨識主機波動。
- 新候選的 frame drop、P90/P99、capture freshness、stale pause、Mock action sustainability 必須**相較現有 V8.5 有明顯而且可重現的改善**，並與 Legacy / V8.4 同時計算；若仍有大量 dropped frames，不能通過。
- 以 `live_video_index.csv` 實際影格間隔估算合理計算預算，不憑空假設全段恆為 60fps；回報高分位耗時 vs frame interval、CPU bound 與硬體資訊。不要靠把 frame drop 計數隱藏、跳過昂貴場景、或延後 Scheduler gate 來美化表格。
- 最終模式至少不應出現「視覺顯示大量有效候選，但因自身運算過慢只剩極少 Mock presses」的 V8.5 退步型態；若性能瓶頸無法排除，必須 `OFFLINE_NOT_PASSED`。

### E. 結果分級（不可越權命名）

- `OFFLINE_CANDIDATE_PASS`：A/C/D 通過，B 的視覺案例有獨立來源證據且未假稱真值；所有已知高風險案例有報告。代表可供**後續人工與實機單獨驗收**，**不代表實機不會 Miss**。
- `OFFLINE_NOT_PASSED`：任何硬門檻失敗，或尚有重大 unresolved/性能回歸。請明確指出卡在哪個子系統。
- `BLOCKED`：必要素材、工具能力、執行權限、硬體、或可驗收真值確實不存在，並記下已做過的排除手段。不得偽造成功。
- **本任務不存在 `LIVE_READY` 或 `ZERO_MISS_PROVEN` 狀態。** 這些需另外取得可信的實機結果後才能討論。

## 7. 允許的性能優化方向（測出來才採用）

不要先一口氣實作以下全部；它們是可測試假說：

- 在 Geometry 有效 Lane／birth-to-hit 區域中做當前幀 ROI 與候選篩選，避免對大量 HUD/background neutral 元件逐一建立可執行候選；完整 mask 可保留給診斷，但跟蹤輸入只保留有足夠證據的 components。
- 避免反覆 full-frame connectedComponents/contour；對局部 ROI 與大面積雜訊建立廉價的 gate，效能改善前後要驗證不會漏掉實際彩色／灰色音符。
- 將 Hungarian 全域匹配縮到同 lane、同時間、同類型的稀疏競爭群；或證明某種局部配對在測試集上更正確且更快。注意不能為提升效能而引入 false merge、ID switch。
- 分離「記錄來源像素 Mask」與「用來發動作的可信 Candidate」；UNKNOWN 是資料狀態，不是必須讓所有 UNKNOWN 參與重型 Tracking 的理由。
- 資料事件追蹤只在分析模式記錄必要資訊，減少熱路徑大量 Python dict/string 生成；但不能以刪除關鍵證據換效能。
- 把 Hold endpoint 的 connected ribbon evidence、birth provenance、顏色、lane span 與幀間 identity 放在可測的簡單接口；過多互相矛盾的閾值／狀態應優先精簡。

## 8. 建議重現命令（先執行 `--help` 確認 CLI）

依現有 `README.md`／V8.5 文件，若指定 Run 在本機可用，使用：

```powershell
python -B -m pytest -q -p no:cacheprovider
python -m compileall -q src tools tests

python tools/replay_lane_filter.py --run-dir output/recording/run_20261106T164049_800126Z --out output/analysis_v86_autoloop/baseline_fixed --mode compare --latency-ms 14 --simulated-arm-window 1 124 --birth-zone-end-y 176.75

python tools/replay_lane_filter_measured.py --run-dir output/recording/run_20261106T164049_800126Z --out output/analysis_v86_autoloop/baseline_measured --mode compare --simulated-arm-window 1 124 --birth-zone-end-y 176.75
```

以上 `birth-zone-end-y=176.75` 是為了**保持與既有基準可比**，不是已驗證的最佳出生邊界。可在另外的實驗掃描候選值，但不得偷改正式 A/B 的共同條件、據此宣告通過。

新自動化工具應能用一條命令跑一輪「測試 → Replay → 視覺/事件檢驗 → 報告」，並有 `--quick`／`--full`、可用 Run 自動發現、輸出目錄、seed/config/hash、fail-fast/安全中斷。避免工具本身一直重複重算完整影片造成無意義成本。

## 9. 清理與工作區規範

上次 `docs/V85_CLEANUP_MANIFEST.md` 記錄了 10 個待刪除路徑，並說有 `tools/cleanup_v85_candidates.bat`，但已檢查的 GitHub `main` 內容沒有這個檔案。先核對**本機實際是否存在**，文件與程式碼不一致就修正文檔或提供經審查的 preview 工具；不要為清理而中斷本次的核心性能／品質修復。

- 先只整理**自身生成且可重建**的過期中間輸出，必須有 manifest 和 preview；不可刪 recording、assist、人工標註、fixtures、config、可重現的 canonical A/B 或 baseline。
- 如果權限／執行政策阻止刪除，尊重限制並報告，**不得改用其他方式繞過**。
- `.gitignore` 大多數忽略 `/output`，不要假設使用者 Push 後會在 GitHub 看到報告。最後在受版本控制的 `docs/` 產生精簡摘要、命令、相對資料路徑與 hash；並告知需要一同提供的最小證據檔案。不要直接改 `.gitignore` 使大量影片上傳。
- 不安裝非必要大型依賴，不增加過度設計的框架，不為了漂亮的 Overlay 改變檢測邏輯。

## 10. 最終交付（一次性，而不是每輪讓使用者 Push）

完成自主迭代後，留下：

1. `docs/V86_AUTONOMOUS_RESULT.md`：一頁先寫結論 `OFFLINE_CANDIDATE_PASS`／`OFFLINE_NOT_PASSED`／`BLOCKED`，再寫達成與未達成的 Gate、真正 root causes、採納／回退過的修法、重要剩餘風險。
2. `docs/V86_EVALUATION.md`：固定延遲與 measured-time 分開的 Legacy/V8.4/候選比較；多次實測 variance、per-stage latency、drop、pause、Mock event、錯鍵/identity/hold 失敗列表、Ground Truth 分級與方法限制。
3. `output/analysis_v86_autoloop/iteration_history.csv` 和 `iteration_history.md`：每一輪的假說、差異、前後測、接受／回退決策，不能只留最後最好的版本。
4. `output/analysis_v86_autoloop/final/`：必要的來源對齊短片、Frame/UID/Event 時間線、失敗證據、摘要 JSON/CSV、測試輸出、兩次 measured-time 全長 Replay；請保持可重跑。
5. 必要的 regression tests、性能工具及說明，讓下次執行不需重新設計評估。
6. 說明哪些路徑被保留、哪些清理未完成，以及 `output/` 是否被 `.gitignore` 排除；提供使用者手動 Push 前應檢查的清單，但**你不能執行 Git**。

結束時用簡潔的繁體中文說清楚：**(a) 現在是否真的通過離線驗收；(b) 比 V8.5 改善多少、哪些數據仍不可解讀成遊戲命中率；(c) 還有哪些音符類型、視覺案例或效能問題沒解決；(d) 使用者接下來只需要做什麼。**

---

## 給 Codex 的最後提醒

**你的目標不是「完成這份計畫」或「讓測試變綠」，而是讓來源影片中的音符更可靠地走完從辨識到 Mock 動作的整條流程。你有權自主定位與修復，也有責任在證據不支持時承認沒有修好。請持續自己跑影片與 Replay、分析並修正，直到有可重現的驗收證據，或發現無法自己克服的真阻礙；不需要每輪請使用者 Push。**
