# HoloDream Live Assist

> **警告：**目前工具仍處於測試階段，測試結果尚不穩定，基本上還不能放心用於實戰。

HoloDream 目前只保留 Windows 全螢幕即時 Assist：以 720×404 座標辨識六鍵軌道，按 `S D F J K L` 對應遊戲鍵。輸入啟動時關閉，只有使用者在遊戲前景按下 `Ctrl+Shift+Alt+Q` 並放開組合鍵後才會啟用。



## 安裝

需要 Windows 與 Python 3.10 或更新版本：

```powershell
cd C:\Users\USER\Desktop\holodream
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -r requirements-live.txt
```

若 PowerShell 不允許啟用虛擬環境，可直接使用 `\.venv\Scripts\python.exe` 執行後續命令。

## 啟動 Assist

```powershell
.\tools\launch_assist.cmd
```

啟動器預設尋找標題為 `hololive-Dreams` 的遊戲視窗，擷取該視窗所在螢幕的完整畫面，等比例正規化到 720×404，並使用 `config/geometry_live_assist.json` 與 `config/live_assist_v5.json`。不會跳出 ROI 或解析度選擇器。錄影為選用項目，會保存乾淨來源、overlay 和時間索引，並增加磁碟用量。

進入遊戲並確認遊戲視窗在前景後，按 `Ctrl+Shift+Alt+Q`、放開組合鍵以啟用，再按一次關閉。`Esc` 或 `F12` 停止 Assist 並釋放按住的鍵。失焦、暫停、ROI／遊戲狀態無效或影格逾時都會解除輸入；恢復後要再次手動啟用。

每次執行都會在 `output/assist/` 建立新的 run 資料夾，包含 `live_run.json`、`live_diagnostics.md`、事件／影格／送鍵 CSV，以及選擇錄影時的影片檔。

## 目前保留的測試

安裝開發測試依賴後可執行核心辨識、幾何、追蹤、時間預測及 Assist 輸入安全測試：

```powershell
python -m pip install -r requirements-test.txt
python -m pytest
```

測試不等於實戰命中率驗證。

## 專案結構

```text
config.json                      共用基礎設定，control.dry_run 保持 true
config/geometry_live_assist.json Assist 使用的 720×404 幾何
config/live_assist_v5.json       Assist 即時設定及使用者確認的操作規則
src/                             偵測、幾何、追蹤、預測、即時擷取和安全輸入
tools/launch_assist.cmd          唯一的使用者啟動器
tests/                           Assist 核心自動測試
 output/                          本機 run、CSV 與選用錄影
 docs/archive/                    舊資料與開發歷史封存，不是現行工作流程
```

參閱 [操作手冊](docs/OPERATOR_GUIDE.md)、[架構說明](docs/ARCHITECTURE.md) 與[資料說明](docs/DATA_AND_CALIBRATION.md)。
