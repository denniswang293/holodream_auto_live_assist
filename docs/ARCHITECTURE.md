# 架構說明

## 即時資料流

```text
遊戲所在螢幕全畫面
        │
        ▼
等比例正規化至 720×404
        │
        ├── GameplayGate：判斷是否正在遊玩
        ├── HSV 與水平邊緣：建立音符候選
        ├── 幾何 lane assignment：映射 S/D/F/J/K/L
        ├── Tracker + Predictor：追蹤及預估命中時間
        ├── Assist 輸入鎖：等待快捷鍵及驗證安全條件
        └── Overlay、CSV 診斷及選用非同步錄影
```

`src.live_engine.LiveEngine` 串接偵測、幾何、追蹤、預測與事件決策。`src.windows_runtime.py` 負責視窗／焦點、全螢幕擷取控制、全域快捷鍵與 Win32 輸入。`src.live_input.py` 管理手動啟用鎖、排程、Hold 按住／釋放及故障解除。

## 影像與幾何

唯一執行座標為 720×404。全螢幕擷取先依 16:9 等比例縮放並置中補邊。`config/geometry_live_assist.json` 是目前 Assist 幾何，狀態仍為 `pending_calibration`。偵測器、lane assignment、追蹤、overlay 和 Hold 路徑使用相同幾何物件。

`config.json` 保持 `control.dry_run=true`；即時輸入只由 Assist 明確建立的 Win32 actuator 提供，且快捷鍵初始為關閉。離線分析與回放入口已從目前產品結構移除。

## 輸入安全

- 輸入啟動時關閉，必須由使用者按 `Ctrl+Shift+Alt+Q` 手動啟用。
- 必須有新鮮影格、遊戲前景焦點、有效畫面與 PLAYING 狀態。
- 失焦、暫停、擷取逾時、停止或緊急鍵會取消待送動作並釋放按鍵。
- 程式解除輸入後不會自動重新啟用。
- Assist 實戰辨識準確率仍未獨立驗證。

## 主要模組

| 模組 | 職責 |
|---|---|
| `src/detector.py` | HSV 外觀與水平邊緣候選偵測 |
| `src/geometry.py`、`src/calibration.py` | 幾何模型、載入、hash 與影格轉換 |
| `src/tracker.py`、`src/predictor.py` | 軌跡維護與命中時間預估 |
| `src/live_engine.py` | 即時決策與 overlay |
| `src/live_input.py` | 快捷鍵啟用鎖、輸入排程與安全檢查 |
| `src/live_capture.py` | Windows 畫面擷取、緩衝與正規化 |
| `src/live_async.py` | 選用 overlay／來源影片的有界非同步編碼 |
| `src/windows_runtime.py` | Windows 視窗、焦點、快捷鍵與輸入 API |
