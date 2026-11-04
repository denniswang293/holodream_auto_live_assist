# Assist 架構

```text
全螢幕擷取 → 720×404 正規化 → 遊戲狀態檢查 → 色塊候選
                                       ├→ Tap：SimpleTracker／PF 空間追蹤
                                       │        → Global y-profile ETA
                                       │        → Planner／Intent／Scheduler
                                       └→ Hold：可見路徑與音符頭追蹤
                                                → Scheduler 起按／可見尾端放鍵
```

所有送鍵都要經過手動啟用、PLAYING、前景焦點、有效畫面與影格新鮮度檢查。Tap 與 Hold 共用六鍵幾何；PF 只處理 Tap 空間追蹤，不決定 Tap 送鍵時間。Hold 入口會合併同一路徑旁的薄邊緣碎片，但不合併不同鍵位或不同音符頭。
