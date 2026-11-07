# HoloDream Assist

> **目前仍有漏按與 Hold 判斷問題，尚不能視為可靠的自動演奏工具。專案已統一為單一 Assist 流程，這不代表遊戲命中率已驗證。**

Windows 六鍵節奏遊戲 Assist。擷取遊戲所在顯示器，將畫面轉為 720×404 進行辨識；Tap 使用 Global y-profile ETA，Particle Filter 負責位置追蹤；Hold 按住起點鍵，依可見尾端控制放開。

## 安裝

需要 Windows、Python 3.10 以上，遊戲顯示比例接近 16:9。

```powershell
python -m pip install -r requirements-live.txt
```

## 啟動

```powershell
.\tools\launch_assist.cmd
```

啟動時選擇是否儲存來源與 Overlay 錄影。若完全不需要紀錄：

```powershell
.\tools\launch_assist_clean.cmd
```

兩個啟動器使用相同演算法與設定，差別只有是否輸出紀錄。

1. 開啟遊戲 `hololive-Dreams`，將遊戲留在前景。
2. 遊玩畫面就緒後，按下並放開 `Ctrl+Shift+Alt+Q` 啟用；再按一次停用。
3. `Esc` 或 `F12` 停止程式並釋放按鍵。

每次啟動均為輸入關閉狀態。失焦、遊戲狀態不符、無效畫面或影格過期時，保留安全停止／放鍵機制。合法鍵位只有 `S D F J K L`。

命令列啟動方式：

```powershell
python -m src.live
python -m src.live --record-overlay
python -m src.live --no-logs
```

## 設定

- `src/assist_defaults.py`：唯一內建設定，包含黃色軌道補辨識、Hold 尾端放鍵、60ms Tap lead 與 60ms 畫面新鮮度限制。
- `config/geometry_live_assist.json`：共用軌道幾何。
- `--config <JSON>`：選用設定覆寫；仍必須通過設定安全檢查。

不再提供舊版 profile 或回退設定選單。這次整理保留了目前核心的延遲改善與演算法。

## 執行紀錄

一般啟動在 `output/assist/run_*/` 建立紀錄；錄影時另有 `live_source.mp4`、`live_overlay.mp4`、`live_video_index.csv`。

CSV、Overlay 繪製與影片編碼採背景處理。`live_run.json` 記錄診斷資料丟失數、輸出錯誤與錄影階段耗時；分析前須確認資料完整。關鍵按鍵紀錄失敗會安全停用輸入。`--no-logs` 不建立紀錄目錄，且不能同時錄影。

原有人工錄製資料保留於 `output/recording/`。`key_down`、候選數或 Tracker UID 都不等於遊戲命中；缺乏遊戲判定資料時，命中率為 `UNKNOWN`。

## 專案結構

```text
config/       軌道幾何
docs/         架構、操作與設定說明
src/          Assist 核心與執行入口
tools/        一般與無紀錄啟動器
output/       本機實機紀錄與人工錄影
```

詳見 [操作手冊](docs/OPERATOR_GUIDE.md)、[架構](docs/ARCHITECTURE.md)及[設定與資料](docs/DATA_AND_CALIBRATION.md)。
