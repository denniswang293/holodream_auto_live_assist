# 設定與資料

## 設定來源

`src/assist_defaults.py` 是唯一內建 Assist 設定。`src/assist_config.py` 負責載入與安全驗證，可透過 `--config` 指定完整結構的局部 JSON 覆寫。

```json
{
  "live": {
    "capture_fps": 120
  }
}
```

沒有舊 profile、`--profile` 或 `--live-config` 選項。錄影和無紀錄使用同一組核心設定。

## 幾何

共用幾何在 `config/geometry_live_assist.json`，六鍵參考座標為 720×404。Detector、Tracker 與 Overlay 共用此模型。

目前幾何狀態仍是 `pending_calibration`，不能因專案結構整理而宣稱已完成獨立校準。鍵位證據綁定幾何 hash；修改幾何後需重新確認，不能繞過既有檢查。

## 資料

- `output/assist/`：保留的實機場次及後續新紀錄。
- `output/recording/`：原有人工演奏來源，不由 Assist 覆寫。

這些是本機執行資料，不是原始碼。測試套件、離線比對工具、開發報告及舊分析產物已移除。

CSV 可能因有界診斷佇列而缺列；先查看 `diagnostic_rows_dropped`、`diagnostic_errors` 與錄影丟失數。一般記錄不能直接換算遊戲命中率；未有遊戲判定真值時為 `UNKNOWN`。
