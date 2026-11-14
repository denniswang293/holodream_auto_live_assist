# HoloDream Assist

> **警告：目前工具仍在測試階段，結果不穩定，Tap／Hold 仍可能漏按、早按、晚按或放鍵不準，尚不適合完全無人看管使用。**

Windows 六鍵節奏遊戲 Assist。從畫面辨識音符、追蹤面板與 Hold 頭尾、預測到達時間，再由獨立排程器送鍵。輸入預設關閉，必須手動啟用。

## 安裝

需要 Windows 與 Python 3.10 以上版本。在專案根目錄執行：

```powershell
python -m pip install -r requirements-live.txt
```

## 使用

一般啟動，可選擇保存原始影片與 Overlay：

```powershell
.\tools\launch_assist.cmd
```

純功能啟動，不建立任何輸出紀錄：

```powershell
.\tools\launch_assist_clean.cmd
```

兩個啟動器共用同一套核心。遊戲視窗標題預設為 `hololive-Dreams`；遊戲應以約 16:9 顯示，並覆蓋所在螢幕至少 90% 的面積。

| 快捷鍵 | 功能 |
|---|---|
| `Ctrl+Shift+Alt+Q` | 切換 Assist，放開組合鍵後才啟用 |
| `Esc`／`F12` | 停止並釋放所有按鍵 |

左至右鍵位為 `S D F J K L`。Hold 按住起點選定的鍵，中途不換鍵，依尾端證據放開。失焦、無效遊戲區域、畫面過期及錯誤仍會停止送鍵或安全放鍵；持續過期或安全停用後須再次手動啟用。

命令列亦可直接使用：

```powershell
python -m src.live --record-overlay
python -m src.live --no-logs
python -m src.live --list-windows
python -m src.live --help
```

## 設定與紀錄

| 位置 | 用途 |
|---|---|
| `config/geometry_live_assist.json` | 軌道幾何與判定線 |
| `config/reference_timing.json` | 與幾何相符的時間參考 |
| `output/assist/run_*/` | 每次獨立的實機紀錄 |
| `output/recording/` | 人工演奏原始資料，供人工比對 |

幾何與時間設定具有雜湊對應，不應任意混用。時間參考源自人工成功操作，不能視為遊戲判定窗口的理想中心。

一般紀錄包含 `actions.csv`、`frames.csv`、`note_decisions.csv`、`session.json` 與 `summary.json`；開啟錄影時另保存 `live_source.mp4`、`live_overlay.mp4` 及 `live_video_index.csv`。影片時間以 index 中的 capture timestamp 為準，不能以影格編號除以標稱 FPS 代替。

需要額外的原始候選與色帶量測時：

```powershell
python -m src.live --record-overlay --identity-trace
```

Trace 由背景執行緒編碼，會增加紀錄量；一般啟動器不預設開啟。`--no-logs` 會停用所有檔案輸出。程式送出 key-down／key-up 不等於遊戲成功命中，命中率需以可確認的遊戲判定驗證。

## 專案結構

```text
config/       幾何與時間設定
src/          唯一 Assist 核心
tests/        Tap、Hold、診斷格式與安全回歸測試
tools/        一般與無紀錄啟動器
output/       本機錄影、執行紀錄與既有分析資料
```

核心流程：`live → capture → perception → tracking → timing → engine → scheduler → Windows input`。`diagnostics` 在背景保存可選紀錄；幾何及共享資料型別由 `model` 管理。

## 開發驗證

```powershell
python -m pip install -r requirements-dev.txt
python -B -m pytest -q -p no:cacheprovider
```

測試使用 Mock 輸入及小型真實影格 fixture，不會操作遊戲，也不依賴 `output/` 中的歷史資料。

## V8.5 離線候選評估

V8.5 EarlyPixelProvider 僅供離線實驗，Live 預設仍使用 Legacy Perception。完整結果、未知案例與限制見 `docs/V85_IMPLEMENTATION_RESULT.md` 和 `docs/V85_EVALUATION.md`。固定模擬延遲與實測即時處理是兩個不同實驗：

```powershell
python tools/replay_lane_filter.py --run-dir output/recording/run_20261106T164049_800126Z --out output/analysis_v85_early_identity/fixed_14ms --mode compare --latency-ms 14 --simulated-arm-window 1 124 --birth-zone-end-y 176.75
python tools/replay_lane_filter_measured.py --run-dir output/recording/run_20261106T164049_800126Z --out output/analysis_v85_early_identity/measured_realtime --mode compare --simulated-arm-window 1 124 --birth-zone-end-y 176.75
```

候選影片與遮罩只保存像素結果；`review_queue.csv` 尚未由真人審核的標籤均為 UNKNOWN。80ms 人工按鍵鄰近度僅為事後輔助診斷，不是遊戲命中率或物理音符召回率。
