# 上半部建立音符：實作與兩場回放結果

已實作成正式執行參數 `--note-entry upper`，但**不取代目前 full 預設**。原因是回放已發現真 Tap 漏送，不能把較少 ID 當作改善。

## 使用方式

```powershell
.\tools\launch_assist_upper.cmd
```

試驗啟動器固定錄製來源及 overlay，輸入仍預設 OFF，需手動 `Ctrl+Shift+Alt+Q` 啟用，Esc/F12 停止。一般 `launch_assist.cmd` 與 clean 版仍走原本 `full`。

也可直接執行：

```powershell
python -m src.live --note-entry upper --record-overlay
python -m src.live --note-entry full --record-overlay
```

## 改了哪些行為

- 在正規化 720×404 座標中，以**面板中心 y<202** 定義上方，只有這裡能建立／確認新音符身分。
- 下方只允許已確認音符繼續關聯；上方未確認候選不能靠下方特效補成 confirmed。下方像素不能把既有 Tap 改成 Hold。
- 下方可量測屬於既有 confirmed Hold 的尾端；保留原本完整面板、歸屬與運動證據要求，端點候選不能變成新的頭部。
- 已確認排程不因單幀缺少觀測而取消。
- 仍讀取下方畫面以修正 ETA 與 Hold 放鍵，不是裁掉下半部後盲目倒數。Timing、幾何、Arm、Focus、stale frame、合法六鍵與 Scheduler 保護不變。
- `session.json` 與逐幀 `info_json` 會記錄模式和 y 邊界，方便下次辨別實際測的是哪一版。

實際修改 `src/tracking.py`、`src/engine.py`、`src/live.py`；新增試驗啟動器、回放工具和回歸測試，沒有新增另一套核心。

## 同來源兩種模式的比較

使用最新兩場原始影片、video index 與 frames 紀錄；讀取實際 capture／acquired／processed timestamp，2ms Mock 輪詢。兩種模式使用相同已處理影格與 Arm 狀態；不使用未來影格、人工答案或 frame/FPS 代替時鐘。沒有實際 Windows 送鍵。

| 場次 | 幀數 | 新 ID full→upper | Mock down full→upper | Hold hard timeout full→upper |
|---|---:|---:|---:|---:|
| `run_20261109T144952_721038Z` | 2,447 | 796→409 | 154→124 | 0→0 |
| `run_20261109T144607_490617Z` | 7,045 | 2,871→1,429 | 534→451 | 10→10 |

兩模式所有 down 都有配對 up，沒有同 UID 重複送鍵。完整場在 full 模式有 51 個 Hold down、upper 有 56 個，不能只靠數量認定真假或改善。這兩場與上一份 Hold 修正報告的舊 run 是不同素材，不能把舊場「逾時 3→0」推廣到它們。

依相同 capture 的 bbox／顏色／多幀軌跡進行雙向唯一配對，至少 5 個共同觀測，且與次佳配對保留數量差距，沒有使用整數 UID 相等。合併已證實 alias 後：

- 短場有 295 組可配對；其中 **3 組**在 full 有動作、upper 無動作，三組在上方已確認。
- 完整場有 959 組可配對；其中 **17 組**在 full 有動作、upper 無動作，17 組在上方已確認。
- 其餘無法唯一配對者保留 UNKNOWN，沒有強制當成假音符或 MISS。

上述流失不等於 20 次遊戲 MISS；必須區分候選動作與遊戲判定。但至少已視覺確認一個明確的普通 Tap 流失：短場 full `note:285`／upper `note:161`，共同觀測 88 幀；來源 frame 1288 的右側 cyan 面板是真音符。full 在 760139.452728 送鍵，upper 沒有送。其餘兩例包含文字／特效遮擋與密集 Hold，物理身分或判定仍需更多核對。

## 為什麼仍會漏

在下方遭遮擋或碎裂時，原模式可建立暫時碎片身分，再透過已有的證據接回原音符。上方模式禁止這條途徑；既有軌跡若先跟到邊線、或錯過最後可用的完整面板，尚未取得可靠 ETA 就會流失。上方有辨識到，不代表後續預測與身分一定保持正確。

上方也可能出現延伸特效與 Fever 文字，因此區域限制不是完整的特效分類器。這次試驗沒有降低 ETA uncertainty 或擅自擴大失追容忍度，來掩蓋被擋掉的動作。

**結論：可以測試，但目前證據不足以當正式預設，也沒有證明 Hold 逾時改善。** 下一步若繼續此方向，應針對已確認身分的下方恢復能力補證據與實作，不能只把出生區一路縮小。

## 測試與產物

完整現有 pytest：**46 passed**，包含 14 項新增區域策略測試：下方不得新建頭部、上方未確認不得在下方確認、既有 confirmed 可繼續、Hold 下方尾端接回、不受觀測缺失影響的原排程、類型固定與 full 回退。

- [短場配對 CSV](../output/analysis_note_entry/run_20261109T144952_721038Z/trajectory_comparison.csv)
- [短場流失案例原始影格](../output/analysis_note_entry/run_20261109T144952_721038Z/lost_candidates.jpg)
- [完整場配對 CSV](../output/analysis_note_entry/run_20261109T144607_490617Z/trajectory_comparison.csv)
- [修改 diff](../output/analysis_note_entry/active_fix.diff)
- 每場的 `full_*`／`upper_*` 保存動作、觀測、來源雜湊及摘要。這些紀錄是 Mock 行為，遊戲命中率一律 UNVERIFIED。

工具可重跑（將 run 路徑換成欲比較場次）：

```powershell
python -B tools/replay_note_entry.py --run-dir output/assist/run_20261109T144952_721038Z --out output/analysis_note_entry/recheck --mode full
python -B tools/replay_note_entry.py --run-dir output/assist/run_20261109T144952_721038Z --out output/analysis_note_entry/recheck --mode upper
python -B tools/replay_note_entry.py --run-dir output/assist/run_20261109T144952_721038Z --out output/analysis_note_entry/recheck --mode compare
```

CPU 欄位排除影片解碼，但本次前後回放在同機並行，不能當成受控效能 benchmark；也不宣稱只建立上方身分就省去下方 Detector 運算。A/B 後僅調整了非 PLAYING 的診斷計數及錯誤收尾 metadata，沒有改動送鍵邏輯。

原始 `output/assist/` 與 `output/recording/` 資料未修改，沒有執行任何 Git 命令。
