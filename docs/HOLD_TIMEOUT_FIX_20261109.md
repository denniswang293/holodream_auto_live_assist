# 三個 Hold 逾時案例的修正

來源：`output/assist/run_20261109T125822_972619Z/`。原始錄影與紀錄未修改；沒有執行 Git 或實際 Windows 輸入。

## 原因與 Active 修正

原實機的三例是 `note:8`、`note:522`、`note:971`，都按住直到 9 秒 hard timeout。這是尾端身分／完整面板證據流失，不是需要再延長按住時間。

- **8**：綠色帶內的 3px 橫線被先綁成 `cap:9`，後來跟到的是色帶內線。真正尾端是上方附有色帶的黃色面板。白色判定光效又把原本寬色帶的 anchor 縮成 11px 小片，之後不再更新，真尾端沒有接回。
- **522**：彎曲頭部在下方碎裂；稍後取得的尾端是短邊線，沒有足夠完整尾端觀測，最終只能等 hard timeout。
- **971**：雙路彎曲 Hold 的右側先綁到 3px 假端點，該端點只有很少完整觀測，成為 ambiguous 後失追；真正尾端沒有取代它。

直接修改：

1. `src/tracking.py`：新綁定／轉移尾端，必須有至少兩次完整尾端觀測，且目前高度至少 6px；起點也須有至少兩次完整頭部觀測。薄內線不能先占住尾端，未驗證的晚生頭部碎片也不能搶走真正尾端。已驗證尾端之後短暫只剩薄邊，仍保留其身分與既有放鍵排程。
2. `src/tracking.py`：已按住的色帶若只露出少量當前色塊，保留原有範圍作為 anchor，不把整條色帶縮成幾個像素；仍需要當前像素支持才能更新觀測時間，沒有像素不能續命。
3. `src/engine.py`：另查出同一完整 Hold 被晚生身分重複預約。一個身分有尾端，另一個沒有，造成第二次按下後逾時。新增嚴格的恢復合併條件：早期完整面板軌跡、專屬且驗證過的尾端、至少三次後續完整範圍觀測，以及投影邊緣落在當前面板內。第一個雜訊碎片不再否決全部後續證據。既有排程的鍵與期限保留，不允許已使用 ID 重約。

**未修改** 9 秒上限、Timing、40ms uncertainty、60ms freshness、15ms lateness、幾何、Arm、焦點與安全釋放機制。沒有加入看不到尾端就任意放鍵、延長期限或補按。

## 完整回放結果

讀取同一影片全部 **7,517 幀**。以紀錄中的 capture／acquired／processed timestamp 模擬處理及 2ms Scheduler 輪詢；只使用已取得影格，全部使用 MockActuator。

| 指標 | 修正前 | 最終修正後 |
|---|---:|---:|
| Hold hard timeout | 3 | **0** |
| Hold down／up 組數 | 74 | 72 |
| Hold 尾端排程放鍵 | 71 | 72 |
| 全部 key-down／key-up | 392／392 | 396／396 |
| 同 UID 重複 down | 0 | 0 |
| 遊戲命中率 | UNVERIFIED | UNVERIFIED |

Hold 數量減少包含重複身分合併；解除卡鍵也讓其他原受衝突阻擋的動作可執行。這些動作數不是 Perfect／MISS 真值。尚無全譜人工逐音符標註，不能據此斷言全曲完全沒有跨 UID 錯配或重複。

### 三個原實機案例的對應

依相同 capture 的位置、顏色與連續運動配對，沒有用整數 UID 相等當身分。

| 原實機 ID | 修正前的解碼回放 | 最終解碼回放 |
|---|---|---|
| 8 | J：753437.113891 → 753446.115733，9 秒逾時 | 同一按下時間 → **753440.235456**，按住約 **3.122 秒**，接回黃色真尾端 |
| 522 | J：753465.030981 → 753465.812188，已能正常釋放 | 鍵位、按下與放開時間相同 |
| 971 | J：753488.115028 → 753488.718774，已能正常釋放 | 鍵位、按下與放開時間相同 |

**限制必須區分**：原實機三例都逾時；壓縮 MP4 的修正前回放只有 8 仍重現原問題，另外兩次回放逾時屬於不同的身分問題（基線 replay IDs 648、2166），不能稱為原實機 522、971。最終版本解掉了該影片回放內的全部三次逾時，也禁止了原實機所見的薄碎片搶尾端條件；522、971 的實機改善仍需新 run 驗證。

最後那個重複 Hold 的局部回歸：frame 2516 的第一個碎片偏在舊面板外，後來 frame 2522–2525 已恢復成同一完整面板。修正前局部 replay 55 與 87 分別按 K／L；修正後在送鍵前合併為一個帶有真尾端的 Hold，僅按 L，於 753471.050911 放開。這項合併不是只靠兩個期限很接近。

## 測試及證據

完整現有 pytest：**32 passed**。涵蓋原有 Tap 修正，加上薄尾端拒絕、真尾端綁定、未驗證頭部不得搶尾端、光效下 anchor 保留、無像素不得更新、雙路歸屬歧義、既有尾端薄邊保留，以及真實回放狀態的身分合併／反例／排程鍵與期限保留。

- [逐案例原實機、基線與修正後動作](../output/analysis_hold_timeouts_20261109/case_actions.csv)
- [完整動作時間線](../output/analysis_hold_timeouts_20261109/action_timeline.csv)
- [驗證指標與來源雜湊](../output/analysis_hold_timeouts_20261109/validation.json)
- [Active diff](../output/analysis_hold_timeouts_20261109/active_fix.diff)
- 原始影格：[8](../output/analysis_hold_timeouts_20261109/case_8.jpg)、[522](../output/analysis_hold_timeouts_20261109/case_522.jpg)、[971](../output/analysis_hold_timeouts_20261109/case_971.jpg)。

可重跑：

```powershell
python -B -m pytest -q -p no:cacheprovider
$env:PYTHONPATH = (Get-Location).Path
python -B output/analysis_hold_timeouts_20261109/replay_holds.py baseline
python -B output/analysis_hold_timeouts_20261109/replay_holds.py final
```

`baseline_sources.json` 僅供離線工具在記憶體重現修改前核心；Active 不載入它。`candidate_*` 與 `inspect*` 是中間診斷，完整驗收以 `baseline_*`／`final_*` 為準。

下一次啟動 `tools/launch_assist.cmd`、錄影選 **Y**，跑同首同難度，手動 Arm。檢查原三個 Hold 的實際尾端與 key-up、是否中途 MISS，以及同時 Tap 是否被長按占鍵。兩個啟動器均使用這套修改後的 src；clean 版不留紀錄，不適合這次驗證。
