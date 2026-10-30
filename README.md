# HoloDream Live Assist

> **警告：**目前工具仍處於測試階段，測試結果尚不穩定，基本上還不能放心用於實戰。

目前只保留 C 模式 Tap 主路徑：Simple Tracker + Particle Filter。Hold 控制、即時擷取、幾何、人工啟用與輸入安全機制仍保留。執行指標不代表遊戲命中率。

## 安裝與啟動

需要 Windows 與 Python 3.10 或更新版本：

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-live.txt
.\tools\launch_assist.cmd
```

啟動後等待遊戲進入 PLAYING，並確認遊戲視窗在前景。Assist 初始為停用狀態；按下並放開 `Ctrl+Shift+Alt+Q` 才會啟用，再按一次可停用。`Esc` 或 `F12` 停止程式並釋放按住的鍵。失焦、暫停或影格過期時會解除輸入。

程式使用 720×404 座標、`S D F J K L` 六鍵及 `config/geometry_live_assist.json`。Tap 目標使用 y=295.5（判定線上移 30 px）；Hold 依可見尾端放鍵。

V7.1 flags 位於 `config/live_assist.json`：pending Tap deadline amendment 使用 30 ms freeze window 與 bounded revisions；judgment calibration 在有足夠遊戲判定標註前維持 shadow-only；Hold v2 使用短時間 head/body continuity，並保留既有的 bounded release 與失焦安全規則。

## 輸出與資料

每次執行在 `output/assist/run_*` 建立新資料夾。檢查 `live_key_actions.csv` 的送鍵紀錄及 `live_events.csv` 的排程狀態。錄影是選用功能，會增加磁碟用量。`output/` 已排除於 Git 追蹤之外。

## 核心測試

安裝測試依賴後執行：

```powershell
python -m pip install -r requirements-test.txt
python -m pytest
```

測試只能驗證程式行為，不能證明實機命中率。

## 核心檔案

- `src/simple_tracker.py`、`src/particle_predictor.py`：C 模式 Tap 位置追蹤與 Hit ETA 預測。
- `src/tap_planner.py`、`src/tap_intent.py`：Tap 排程與意圖。
- `src/live_input.py`、`src/live_engine.py`：人工啟用、安全限制、排程及 Hold 控制。
- `src/live_capture.py`、`src/geometry.py`、`src/detector.py`：即時擷取、幾何與音符偵測。
- `tools/launch_assist.cmd`：Assist 啟動器。

更多操作資訊見[操作手冊](docs/OPERATOR_GUIDE.md)、[架構說明](docs/ARCHITECTURE.md)與[資料及校正說明](docs/DATA_AND_CALIBRATION.md)。
