# HoloDream 原始碼審查與 Codex 第二輪修改指令

> 審查基準：使用者提供的 `holodream.zip`，來源為 `src/*.py`、`config.json`、`output/events.csv`、`output/failures.md` 和故障截圖。此報告是原始碼分析與修正建議；未修改、重跑完整影片，也未進行即時鍵盤輸入。

## 一、目前的實作

現有處理路徑為：`src/main.py` 逐幀讀取影片 → `src/detector.py` 用 HSV 門檻、水平形態學閉運算找候選框 → `src/geometry.py` 以梯形軌道估計候選鍵位 → `src/tracker.py` 使用貪婪最近距離追蹤 → 使用**相鄰兩次**觀測計算 ETA → 寫入 `output/events.csv`（逐幀紀錄），以及 `output/overlay.mp4`。

**目前輸出不是可執行的譜面／按鍵事件表。** README 也明確定義此專案為離線、dry-run 的 M1 基線。

## 二、根據實際輸出的基線指標

- 9,343 筆逐幀候選紀錄、1,418 個不同追蹤 ID；同一音符可能有多筆紀錄，ID 也不等於真實音符數。
- 430 個 ID 只出現一幀；833 個 ID 出現少於四幀。大量短暫追蹤代表雜訊或追蹤碎片。
- 6,971 / 9,343 筆（74.6%）沒有 `hit_time_estimate`。
- 662 個 ID 在不同幀的 `candidate_keys` 值不同；其中可能有合法滑動音符，但也可能是框抖動／錯配，必須人工檢查。
- 時間預估在同一個 ID 下不穩定，不能據此產生鍵盤指令。
- `note_id=2` 在約 0.05～2.83 秒出現 152 次，絕大多數 Y 位置停在 250 附近，疑似靜態特效遭長期追蹤。
- `note_id=1404` 在約 57.25～59.20 秒出現 118 次，Y 座標只變動約 3 像素，屬於強烈可疑的靜態物件候選；影片末段並非有效遊玩區間。
- 現有 `pytest` 只有 `tests/test_geometry.py` 的 3 個測試，全部通過，但完全沒有測 detector、tracker、ETA 和輸出事件去重。

## 三、逐檔修正要求（優先順序）

### P0 — `src/detector.py`（第 44–50、55–67、83–97、98–115 行）

**問題：** HSV 分類完全依顏色，灰白 `neutral` 混入 tap；tap 與 hold 的 hue 範圍在 78–83 重疊；粉紅色就直接稱 flick（並未驗證箭頭）；`MORPH_CLOSE` 水平核可能串接相鄰音符；`confidence` 是手動公式，不是經驗證的正確率。

**修改：**
1. 將 `color_class` / `appearance` 與已驗證的 `note_type` 分開。沒有箭頭的粉色只能叫 `pink_candidate`，不得自動產生 `flick`。
2. 把 `bbox`、原始 mask、候選色別、主體（音符頭）與延伸路徑分離；不要將整段 hold path 當成一個普通音符框。
3. 在判定區附近加入動畫光效的排除機制；至少使用時間連續性 + 合理下移動作驗證，不能只調低 HSV 門檻。
4. 將形態學閉運算的 kernel 配合目前 Y 位置及投影寬度調整，避免跨軌合併。對疑似重疊的候選提供可視化與數據。
5. 追蹤信心分數只視為 heuristic score，不能誤稱為機率。

### P0 — `src/tracker.py`（第 19–35、44–75 行）

**問題：**
- `eta()` 第 28–35 行只用最後兩筆位置估算速度，極易被框抖動放大；雖然有保存最近 8 筆 history，卻未利用。
- 第 35 行 `max(0.0, eta)` 將已過判定線的負 ETA 夾成 0，會誤導後續的事件輸出。
- 第 57–67 行逐 track 貪婪匹配；距離門檻 90 像素在遠方窄軌道上太寬，且只憑相同 `kind`，不檢查合理速度、Y 方向、橫向 u / 軌道重疊或尺寸變化。
- 背景中的常駐亮條可能被當成生命週期很長的音符追蹤。

**修改：**
1. 依 normalized X（u）、Y、音符寬度、時間間隔、預測位置、軌道相容性建立配對成本與硬門檻；只允許物理上合理的位移。
2. 將逐 ID 處理的貪婪比對改成**全域一對一配對**（例如 Hungarian assignment，或先排序合法 pair 再以唯一 ID 配對），避免舊 track 搶走別人的 candidate。
3. 速度使用最近至少 5 筆以上的穩健估計，例如 median slope 或 robust linear fit；只有滿足連續正向移動和足夠觀測數才輸出 ETA。
4. `eta < 0` 表示已過判定線，不能夾成 0。加入 ETA 穩定性門檻；不穩定的預測保留 `None`。
5. 加入 track 生命週期：`tentative`、`confirmed`、`lost`、`completed`；只有 confirmed 才可輸出經驗證的單次事件，且要有去重機制。
6. 對 hold / slide 採獨立「頭、尾、路徑」資料模型，避免同一條延伸軌跡產生多個無關 ID。

### P1 — `src/main.py`（第 36–43、58–74 行）

**問題：**
- 第 41 行每一幀都呼叫 detect，沒有 gameplay/non-gameplay gate；結算畫面仍被掃成音符。
- 第 69–73 行輸出的 `events.csv` 是每幀一列，不是一次擊打一列；不應拿去直接觸發鍵盤。
- 第 64–73 行直接使用不穩定 ETA；未產生可審查的 `note_events.csv`。

**修改：**
1. 加入遊玩狀態判斷（`PLAYING / NOT_PLAYING / UNCERTAIN`），非 `PLAYING` 狀態不得建立新 note event，並在 overlay 標示狀態。
2. 保留原逐幀資料，但改名 `detections.csv`，包含 track status、velocity、ETA 及拒絕原因。
3. 新增 `note_events.csv`，每個確認音符一筆：`note_id, type, key_candidates, hit_time, confidence, status, source_frame, notes`。**未通過驗證的特殊音符不得標為可執行。**
4. Overlay 使用不同顏色區分 tentative、confirmed、rejected、completed；清楚標出 track ID、預估 hit time 和拒絕原因。
5. 使用影片實際解碼時間戳（可取得時），或明確記錄 `frame/fps` 假設；不得把處理時間等同遊戲時間。

### P2 — `src/geometry.py` 與 `config.json`

**問題：**幾何映射只採用簡化梯形，`src/detector.py` 和 `src/main.py` 直接寫死參考 720×404，沒有統一使用 `config.json` 的 `reference_resolution`。用框的微小重疊來決定候選鍵位，在邊界閃爍時會不穩定。

**修改：**把 `reference_resolution` 當唯一來源，加入 lane overlap fraction / center distance；保留相鄰鍵位的候選可能性，但是不要因為 bbox 邊界晃動就立刻更改音符鍵位。先在 720×404 上固定基線，不用急著做任意解析度。

## 四、建議分三次 PR，不要一次重寫

1. **PR1：基礎監測與假音符過濾**——gameplay gate、confirmed track、背景常駐光效剔除、detections.csv、加入測試與 debug overlay。仍不產生任何鍵盤輸入。
2. **PR2：穩定跨幀追蹤與 ETA**——以 u + y + 時間做全域配對、robust 多幀速度預測、拒絕離群點；建立 note_events.csv，但僅對已驗證的 tap 類型產生待確認事件。
3. **PR3：特殊音符**——人工標註與驗證 flick 箭頭、hold 起止點、slide 連續路徑；未驗證時輸出 `unknown`，不可假裝知道遊戲的按鍵規則。

## 五、驗收標準（需要人工標註 ground truth）

- 建立至少 30–50 筆跨場景的人工標註音符，涵蓋光效強、長按與密集粉紅音符；包括音符類型、軌道、判定幀（或可觀測誤差）及是否處於 gameplay。
- 追蹤不可在結算畫面輸出有效 note event；特別檢查 58 秒後。
- 對每個 confirmed tap，只能產生一筆事件；同時間多顆音符可各自有事件，不要錯誤合併。
- ETA 應與人工標記的判定幀比較 MAE/中位數/95% 分位數，並報告漏檢率和誤報率；**沒有人工標籤時不要宣稱已達到某個準確率**。
- `pytest` 新增：靜止亮條被拒絕、相鄰音符不可換 ID、暫時遮擋可恢復、相鄰兩幀 bbox 抖動不應造成 ETA 飛躍、超過判定線不得夾為 0、結算畫面不輸出事件、同一音符只能輸出一次。
- 保持 `dry_run: true`；第二輪不要呼叫鍵盤 API。

## 六、可以直接交給 Codex 的任務

請以這份審查文件為準，**在目前 `holodream` 專案上漸進修改，不要推倒重寫**。先實作 PR1 和 PR2，優先修正 `src/detector.py` / `src/tracker.py` / `src/main.py` 指定問題。原始 CSV 是 noisy candidates，禁止將其當成鍵盤觸發表。保留 offline dry-run，不接入鍵盤。提供改動前後的 `pytest` 結果、實際影片的三個失敗時間點 11s、22.8s、54s 的 overlay 對照，並產出 `detections_v2.csv`、`note_events_v2.csv`、`metrics_v2.md`、`failures_v2.md`。如沒有人工標註 ground truth，必須註明「未驗證準確率」，不得捏造數據。每個修改說明對應到程式碼行數與測試結果。
