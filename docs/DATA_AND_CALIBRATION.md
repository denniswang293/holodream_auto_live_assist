# Assist 設定與資料

## 目前使用設定

- `config.json`：六鍵順序與共用偵測／追蹤設定；`control.dry_run` 維持 `true`。
- `config/geometry_live_assist.json`：Assist 共用幾何，參考座標為 720×404，目前狀態是 `pending_calibration`。
- `config/live_assist_v5.json`：即時輸入時序、Hold 規則與使用者確認的操作資料。

幾何未完成獨立驗證，因此不能宣稱軌道或命中率已校準。修改幾何會改變其 hash；既有操作 profile 綁定 hash，避免錯用於不同幾何。

## 執行產物

`output/assist_720/` 儲存新的 Assist run、CSV 診斷資料，以及使用者選擇錄影時的來源／overlay 影片。大型輸出屬本機執行產物，不是程式來源。舊人工標註、評估資料和 Shadow run 已移出現行工作流程並封存於 `docs/archive/`，不會被 Assist 載入或覆寫。

## 指標解讀

Assist 可記錄處理 FPS、延遲、stale frames、事件、送鍵與取消數。以上都是執行指標，不能換算成音符精確率、召回率、錯鍵率或遊戲命中率。這些準確度目前未經獨立驗證。
