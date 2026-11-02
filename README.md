# HoloDream Live Assist

> **警告：目前工具仍處於測試階段，測試結果仍可能不穩定，基本上還不能視為完全可靠的防守使用。**

HoloDream 是 Windows 上的安全優先 Live Assist：使用六鍵軌道偵測、Particle Filter 進行 Tap 空間追蹤，並由 Global Fixed-Speed ETA 提供普通 Tap 的唯一送鍵時間；Hold 維持視覺尾端控制。PF 不再決定 Tap ETA 或 hit_at。

## 安裝

需要 Windows 與 Python 3.10+：

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-live.txt
```

## 啟動

```powershell
.\tools\launch_assist.cmd
```

Assist 初始為停用狀態。切回遊戲視窗後，按下並放開 `Ctrl+Shift+Alt+Q` 才會啟用，再按一次停用；`Esc` 或 `F12` 會停止程式並釋放按住的鍵。失焦、ROI 不合法、影格過期或安全條件失效時，輸入會自動停止。

預設使用完整遊戲顯示區、720×404 內部座標、六鍵 `S D F J K L`，視窗標題為 `hololive-Dreams`。Tap 使用 PF 空間追蹤與 Global Fixed-Speed ETA；Hold 使用視覺尾端離開判定區控制放鍵。

## 診斷設定

`config.json` 保留安全預設：

- `pf_assisted_reassociation.enabled=false`：PF-assisted 只做 Shadow/offline 診斷，不可送鍵。
- `live.global_tap_timing`：多軌固定速度 ETA 為普通 Tap 的 Active 時間來源；`allow_active=true` 只代表通過 Global gate 的 proposal 可送鍵，PF 僅提供空間追蹤與關聯。
- `diagnostics.trace_snapshot.enabled=true`：以有限佇列寫入逐影格追蹤摘要，僅供事後分析，不參與決策。
- `control.dry_run`、人工啟用、失焦／stale／ESC／F12 停止保護保持不變。

Snapshot 會寫入每次 `output/assist/run_*` 的 `live_trace_snapshots.csv`。它不會建立 synthetic observation、改變 Planner/Scheduler、取得 Hold 所有權或呼叫 Actuator。

## 輸出

每次執行會在 `output/assist/run_*` 建立紀錄。主要檔案包括：

- `live_events.csv`：事件與排程狀態。
- `live_key_actions.csv`：軟體送鍵動作紀錄；不等於遊戲命中。
- `live_trace_snapshots.csv`：可選診斷 snapshot。
- `global_tap_timing_shadow.csv`：全域固定速度 ETA 的逐 track 診斷；不代表遊戲命中。
- `live_overlay.mp4`、`live_source.mp4`：只有啟用錄影時才會產生。

沒有遊戲判定來源時，遊戲命中率一律視為 `UNKNOWN`；`FIRED`、`key_down` 或 UID 持續都不能直接解讀為 Perfect、Good 或 Miss。

## 核心測試

```powershell
python -m pip install -r requirements-test.txt
python -m pytest -q
```

測試驗證程式安全與演算法行為，不代表實機命中率。

## 核心結構

- `src/live.py`、`src/live_engine.py`：Assist 執行、安全停止與流程整合。
- `src/simple_tracker.py`、`src/particle_predictor.py`：Tap 空間追蹤、關聯與 PF 品質。
- `src/global_tap_timing.py`：普通 Tap 唯一 Global Fixed-Speed ETA / hit_at 模型。
- `src/tap_planner.py`、`src/tap_intent.py`：Tap 意圖與排程。
- `src/hold_tracker.py`、`src/hold_visual.py`：Hold 視覺追蹤與放鍵。
- `src/detector.py`、`src/geometry.py`：色塊偵測與六鍵幾何。
- `src/live_input.py`、`src/windows_runtime.py`：人工啟用與 Windows 輸入安全。
- `tools/launch_assist.cmd`：正式 Assist 啟動器。
- `docs/`：操作、架構與校正說明。
