# HoloDream Assist

> **警告：目前工具仍在測試階段，結果不穩定，Tap 與 Hold 仍可能漏按、早按、晚按或放鍵不準，尚不適合完全無人看管使用。**

Windows 六鍵遊戲 Assist。從遊戲畫面辨識音符，追蹤實體音符與 Hold 頭尾，預測時間並規劃按鍵；輸入預設關閉，必須由使用者手動啟用。

## 安裝與啟動

需要 Python 3.10 以上版本。在專案根目錄執行：

```powershell
python -m pip install -r requirements-live.txt
.\tools\launch_assist.cmd
```

錄影選 **Y** 時會保存原始影片與 Overlay，方便分析漏按。只要功能、不產生任何紀錄：

```powershell
.\tools\launch_assist_clean.cmd
```

兩個啟動器都使用同一套 `src.live`。遊戲視窗標題預設為 `hololive-Dreams`；遊戲應以約 16:9 顯示，並覆蓋擷取螢幕至少 90% 的面積。

- `Ctrl+Shift+Alt+Q`：切換 Assist，放開組合鍵後才啟用。
- `Esc` 或 `F12`：停止並釋放按鍵。
- 合法按鍵為 `S D F J K L`；失焦、畫面過期及錯誤仍會觸發安全保護。
- Hold 按住起點選定的鍵，中途不換鍵，依尾端證據放開。

其他啟動方式：

```powershell
python -m src.live --record-overlay
python -m src.live --no-logs
python -m src.live --list-windows
```

## 專案內容

|位置|用途|
|---|---|
|`src/`|唯一正式核心；擷取、辨識、追蹤、時間預測、規劃、輸入及診斷|
|`config/`|軌道幾何與時間參考設定|
|`tools/`|一般啟動器及無紀錄啟動器|
|`tests/`|核心與安全回歸測試；`fixtures/` 保存小型真實影格案例及來源資訊|
|`docs/`|架構、資料／時間參考來源及最新修補說明|
|`output/assist/run_*/`|實機紀錄，供後續分析|
|`output/recording/run_*/`|原始人工演奏資料|

目前使用逐音符的對數位置運動擬合，沒有 Particle Filter 或 Shadow Planner 執行路徑。設定檔 `config/reference_timing.json` 是成功人工操作的時間參考，不代表遊戲判定窗口的理想中心。

紀錄中的按下／放開代表程式送鍵，不能直接算作遊戲命中。影片時間以 `live_video_index.csv` 為準，不能用影格編號除以標稱 FPS 代替。實際遊戲命中率尚未驗證。

## 測試與文件

```powershell
python -m pip install -r requirements-dev.txt
python -B -m pytest -q
```

測試使用 Mock 輸入及小型 fixture，不需要歷史分析輸出，也不會自動操作遊戲。舊候選核心、重複回放及已停用工具的驗證程式已移除。

- [目前架構](docs/REBUILD_ARCHITECTURE.md)
- [人工錄製資料品質](docs/REBUILD_DATA_AUDIT.md)
- [時間參考與限制](docs/REBUILD_GROUND_TRUTH.md)
- [最新 Hold 身分延續修補](docs/CURVED_HOLD_IDENTITY_FIX_20261109.md)
