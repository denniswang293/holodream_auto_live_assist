# 最新實機 Tap／Hold 核對與修正

後續 Hold 逾時修正與驗收已完成，見 [Hold timeout 後續報告](HOLD_TIMEOUT_FIX_20261109.md)。本文件保留當時的基線結果。

資料：`output/assist/run_20261109T125822_972619Z/`。原始資料只讀，未執行 Git 命令。

## 結論

截圖中的 8 個 Tap ID（801、915、921、1219、1800、1817、1914、2126）在這次實機 `actions.csv` 都沒有 `pressed`。這不是「沒有畫出音符」，而是已建立音符之後，完整面板分類或有效預測窗口流失。另查的控制案例 1300 有送出 J，不能算成未送鍵。

黃色判定特效會被色帶追蹤誤認為 Hold ribbon，讓已確認的普通 Tap 在下方變成 `body`、`hold_head` 或 `hold_tail`。前兩者被 Planner 的 `tap_face_not_visible` 擋住；後者還可能被 Tracker 當成尾端，拒絕與原 Tap 關聯。此時較高位置的 ETA 不確定性仍超過 40ms；等面板恢復時，ETA 經常已過期。因此只看 overlay 上曾有 `tap` 標籤，不能判斷它是否曾有可執行排程。

`note:2010` 不能歸類成提早放鍵：它的 L 按下為 **753534.363534**，放開為 **753535.297857**。frame 6517／capture **753534.982880** 已可見 MISS，當時 L 仍按住，尾端 top y=272；frame 6528／capture **753535.183755** 也仍按住。這個較早出現的 MISS 不可能由之後的這次 key-up 觸發。單憑此畫面，仍無法確定 MISS 屬於 Hold 中斷、起點問題或同期另一顆音符，不能用一律延後放鍵掩蓋它。

## 已直接修改的 Active Code

- `src/tracking.py`：普通 Tap 已有早期完整面板、持續運動及確認身分，且沒有真正 Hold 起點／尾端證據時，保留它在黃色特效中的完整面板 Tap 語義。仍須通過原有一對一空間與運動關聯；不能憑預測位置產生候選。真正的早期 Hold 起點證據會否決此修正。
- `src/tracking.py`：下方新出現、厚度不足 8px 的黃色薄邊，只保留候選 cap，不預先建立音符身分。若之後看到完整面板，以那一刻的實際位置建立新身分。既有音符與 Spawn 區的薄面板不受此限制。這修掉了候選版本在 1800 面板左側碎片上造成第二次預約的可重現錯誤。
- `src/perception.py`：把已有的「完整色塊面板恢復」延伸到 cyan。恢復候選只能接回已確認的既有 Tap，不得自己建立新音符；不把黃色光效強行當成被蓋住的 cyan。

未修改 Timing、Planner、Scheduler、Hold 控制或安全停止；幾何與時間設定檔雜湊和該 run 的 `session.json` 完全一致。40ms 不確定性上限、60ms 影格新鮮度及 15ms 送鍵逾時上限不變。

## 同一影片的因果 Mock 回放

讀取 7,517 個有 index 的來源影格。逐幀使用 `frames.csv` 的 capture、acquired、processed timestamp，並以 2ms 輪詢模擬 Scheduler。未使用 frame/FPS 當時鐘、未讀取未來畫面或人工按鍵答案。Arm 狀態依實測記錄套用；沒有實際 Windows 送鍵。

MP4 壓縮與診斷略過的影格會使候選及 UID 和原始 live 不同。因此以相同 capture 的 bbox、color、連續影格重合建立對應，不使用整數 UID 相等。這是「相同來源影片的修正前後比較」，不是 bit-exact 重現原始未壓縮擷取。

| 指標 | 修正前 | 最終修正後 |
|---|---:|---:|
| Mock key-down | 376 | 392 |
| Mock key-up | 376 | 392 |
| Hold key-down／key-up 組數 | 74 | 74 |
| Hold 按下、放開的鍵位與時間 | 基線 | 74 組逐項完全一致 |
| Hold hard timeout | 3 | 3 |
| 同 UID 重複 key-down | 0 | 0 |
| 遊戲命中率 | UNVERIFIED | UNVERIFIED |

915、921、1219 在修正前的完整回放沒有送鍵，最終版本各送出一次。1800 在修正前的局部對照與最終完整回放都送一次；修正過程發現並排除的雙重預約版本不得當成最終結果。其餘指定 Tap 在壓縮影片基線已可送鍵，不能據此聲稱它們的實機漏按已解決。最終回放的 8 個指定物理 Tap 各對應一次送鍵，但這不是遊戲命中真值，也不能推廣成全譜沒有跨 UID 重複。

## 逐案例證據

| 原實機 ID | 原影格與問題 | 最終狀態／限制 |
|---|---|---|
| 801 | frames 2961–3034；晚出現、少量完整觀測、motion uncertainty／stale／crossing in past | 基線回放已會送；仍需實機驗證 |
| 915 | frame 3459 body、3460 hold_head；有效面板／ETA 窗口流失 | 完整回放 0→1 次，K |
| 921 | frame 3474 body，後續碎片與不穩定觀測 | 完整回放 0→1 次，S |
| 1219 | frame 4228 面板縮成 3px 碎片，4233 後不再通過可見性 gate | 完整回放 0→1 次，L |
| 1800 | 下方黃色面板身分分裂；中間候選版本曾造成 F/J 雙預約 | 已排除該候選缺陷；最終完整回放一次 J |
| 1817 | frame 5991 body、5994 hold_head；完整面板被光效與碎片取代 | 基線回放已會送；仍需實機驗證 |
| 1914 | frame 6281 僅剩 cyan／neutral 邊緣，之後真面板被黃色特效蓋住 | 顏色完全不可見時不憑空補候選；基線回放已會送，仍需實機驗證 |
| 2126 | frame 6683 hold_head，後續 crossing in past | 基線回放已會送；仍需實機驗證 |
| 2010 Hold | frame 6517 已可見 MISS，但 L 未放；實際放鍵約在 frame 6534–6535 | 放鍵時間未改；MISS 的物理歸屬仍未確認 |

完整 capture timestamp、配對 UID、理由統計與動作時間在 [case_comparison.csv](../output/analysis_latest_misses_20261109/case_comparison.csv)。

## 測試與產物

`python -B -m pytest -q -p no:cacheprovider`：**16 passed**。目前 tests 原有內容已不存在；這是本次新增回歸測試的完整結果，不能稱作先前數百項歷史測試均已重跑。

包含黃色特效中的三種錯誤角色、真正 Hold 的否決、晚生薄邊與 Spawn 薄面板的區別、空間 gate、恢復候選不得創造新音符、重複 UID、Arm／失焦放鍵，以及原始影片影格的黃色與 cyan 面板測試。`python -B -m src.live --help` 通過；未在本機自動啟動遊戲輸入。

- [同一影格的分類對照](../output/analysis_latest_misses_20261109/tap_classification_comparison.jpg)
- [Hold 6517 的原始畫面與鄰近影格](../output/analysis_latest_misses_20261109/cases_2.jpg)
- [實際 Active diff](../output/analysis_latest_misses_20261109/active_fix.diff)
- `baseline_mapped_*`：修改前完整回放。
- `final_mapped_*`：最終完整回放；`final_1800_*` 為碎片重複問題的局部回歸。
- `fixed_*`、`after_*` 為中間候選驗證，**不是最終版本**。
- `baseline_sources.json` 僅供分析腳本在記憶體中重現舊 Detector／Tracker，Active 不會載入它。

重跑離線對照（PowerShell，專案根目錄）：

```powershell
$env:PYTHONPATH = (Get-Location).Path
python -B output/analysis_latest_misses_20261109/replay_cases.py baseline_mapped
python -B output/analysis_latest_misses_20261109/replay_cases.py final_mapped
```

## 尚未證實解決的問題與下一次測試

原實機仍有 3 個 Hold hard timeout：8、522、971；本次未修改它們，也未將它們算成正常尾端放鍵。2010 的 MISS 也沒有可靠物理歸屬。這些問題不能宣稱已修復。

下一次用 `tools/launch_assist.cmd`，錄影選 Y，跑同一首同一難度，進入遊戲後手動 Arm。用新 run 核對 8 顆 Tap 是否有唯一動作、畫面判定／生命／Combo，以及 Hold 的完整 down/up 區間。不要使用 clean 啟動器做這次診斷，因為它不保留證據。實機可見判定確認前，新增 Mock 動作只代表排程／追蹤可達性改變。
