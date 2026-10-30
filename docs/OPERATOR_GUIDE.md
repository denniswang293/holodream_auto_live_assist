# Assist 操作手冊

## 啟動

1. 確認 Windows 遊戲視窗標題是 `hololive-Dreams`，遊戲解析度接近 16:9。
2. 執行 `tools/launch_assist.cmd`。
3. 等待即時畫面狀態進入 PLAYING，並將遊戲視窗留在前景。
4. 按 `Ctrl+Shift+Alt+Q` 並放開以啟用 Assist；再按一次可關閉。
5. 按 `Esc` 或 `F12` 停止 Assist 並釋放程式按住的鍵。

輸入鎖在每次啟動時都是關閉狀態。Assist 解除後不會自動重新啟用。

## 擷取與座標

Assist 擷取遊戲所在顯示器的完整畫面，不提供 ROI 或辨識解析度選擇。影格依比例映射到 720×404，不會以 1920 座標進行辨識。全螢幕擷取使用 headless，避免程式 overlay 被再次擷取。接近 16:9 以外的畫面會被拒絕，避免拉伸變形。

## 啟用失敗或中途停止

`hotkey_rejected_not_ready` 表示快捷鍵有收到，但遊戲尚未符合啟用條件。確認遊戲在前景、正在遊玩，並查看最新 run 的 `live_key_actions.csv` 與 `live_diagnostics.md`，其中會記錄失焦、遊戲狀態或影格逾時等原因。恢復後需再次手動按快捷鍵。

## 輸出

每次執行在 `output/assist/run_*/` 建立新目錄。`live_run.json`、`live_events.csv`、`live_frames.csv`、`live_key_actions.csv` 和 `live_diagnostics.md` 記錄執行狀態。啟動時選擇錄影後，另會產生來源、overlay 與 `live_video_index.csv`。這些檔案是執行診斷紀錄，不是人工真值或命中率證明。
