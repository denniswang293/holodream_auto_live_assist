# Assist 操作手冊

## 一般啟動

1. 在 Windows 開啟 `hololive-Dreams`，使用接近 16:9 的完整遊戲顯示區。
2. 執行 `tools/launch_assist.cmd`，選擇是否錄影。
3. 切回遊戲，等待正在遊玩的畫面就緒。
4. 按下並放開 `Ctrl+Shift+Alt+Q` 啟用；再按一次停用。
5. `Esc` 或 `F12` 停止並放開程式持有的鍵。

無紀錄版本使用 `tools/launch_assist_clean.cmd`，演算法與一般版一致。

## 擷取與座標

擷取遊戲所在顯示器的完整畫面，依比例轉換為 720×404。沒有 ROI 選取或 1920 辨識模式。視窗標題預設為 `hololive-Dreams`，可使用 `--window-title` 指定其他標題。

## 啟用與停止訊息

- `hotkey_rejected_not_ready`：快捷鍵收到，但遊戲狀態、焦點或畫面尚未符合啟用條件。
- `validated_capture_expired`：最後可安全使用的畫面超過新鮮度限制；持有鍵會安全釋放。
- `stale_context_timeout`：新鮮畫面遲遲未恢復，已解除啟用。
- `game_state_or_focus_or_roi_loss`：遊戲狀態、前景焦點或有效擷取條件失效。

解除啟用後需要再次手動啟用。短暫安全放鍵不會盲目重新按住原 Hold。

## 錄影與排查

一般紀錄位於 `output/assist/run_*/`。錄影和日誌必須使用同一場次的 `live_video_index.csv` 對應時間，不能直接用影格編號除以名義 FPS。

檢查 `live_diagnostics.md`、`live_key_actions.csv` 與 `live_run.json`；先看輸出錯誤、資料丟失及安全放鍵，再與 MISS／Combo／生命及畫面核對。軟體送鍵不代表遊戲成功命中。
