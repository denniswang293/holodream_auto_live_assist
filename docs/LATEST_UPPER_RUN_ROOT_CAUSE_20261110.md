# 最新 upper 實測：Hold 斷續與 Tap 流失根因

來源：`output/assist/run_20261109T154423_161807Z/`，7,945 幀、約 124.5 秒，`session.json` 確認模式為 **upper，y=202**。本輪分析原影片、逐幀 note、actions 與 video index，未修改演算法或原始資料，未執行 Git。所有時間皆為 host performance-counter 秒；沒有使用 frame/FPS 換算。

## 1. 圖中的左 Hold 273：不是按住後又放開，而是新一段根本沒按

- 273 自 frame 2790 出現，已確認為 Hold，但從未 accepted／pressed，沒有對它送過 key-down。
- frame 2893–2897（763432.904241–763432.975836）只追到左面板局部，最後 bbox `[321,231,30,13]`；之後 stale，進入 `hold_head_not_verified`，直到離場。
- 同一左側完整面板後來卻出現在 **282** 身上：frame 2911／763433.251232，bbox `[284,300,118,30]`，detection 是綠色 Hold head，但 note 仍是 Tap，理由為 `tap_face_not_visible`。
- 282 最初於 frame 2850／763432.104836 出生，是 bbox `[336,149,49,3]` 的**中性薄線 Tap**，不是已驗證的綠色 Hold。

因此有兩個相連的問題：真 Hold 的身分中斷；中性候選後來接走真綠色面板，卻沒有正確 Hold 身分。現有 Tracker 允許 neutral 與其他顏色相容，並以位置、重疊和中心距離競爭；upper 又禁止在下方建立恢復用頭部，及更改已確認 Tap 的類型。這個策略限制使錯配之後難以恢復。

**證據與推論分界**：面板在 282、273 失追是紀錄可確認的；raw live 沒有保存每個 association pair 的成本，尚不能確定當幀是 273 先被 gate 排除，還是 282 在兩者都合格時勝出。不能捏造某個 cost 數字。

前一段 Hold 的實際放鍵：259/J 在 **763433.138007**，265/S 在 **763433.178909**。新的右段 276/L 在 **763433.254926** 接上；新的左段 273 沒有接上。畫面因而像「中間鬆了一下」，但不能用延長舊段按住時間代替新段的起點動作。

## 2. 圖中的 Tap 513：身分先出生在光效，再追到真音符

frame 4154／763452.796082 的原圖很關鍵：

- 真正中央 cyan Tap 是 **498**，bbox `[315,137,89,11]`。
- 513 的出生位置是其右下方藍色光柱，bbox `[360,152,48,16]`，並非那顆完整 Tap。
- 後來真 Tap 的面板落到 513 軌跡中；498 在下方失追。到 frame 4194，513 也縮成 `[395,233,24,10]`，frame 4196 只剩 4px 邊線，後續 `tap_face_not_visible`。
- 498 與 513 在原實機都沒有送鍵。預期該 Tap 到達附近的時段，紀錄沒有新的 F／J key-down；不能只看到 513 沒送，就忽略另一個早期身分 498。

結論是**光效假候選與真 Tap 的身分競爭／分裂**。不是只因 ETA 太晚，也不是把 513 無條件補按就能正確解決。區域限制沒有擋住這個假候選，因為它在上半部 y=152 就已出生。

在壓縮來源的重播中，真 Tap 由 full 的 1069／upper 的 514 在 **763453.756531** 送 J；假光效分支則都沒有送。這也再次證明原實機 UID 513 不能等同於一顆穩定物理音符，壓縮回放與 raw live 不是逐候選完全一致。按原 UID 的最佳早期重疊配對會偏向假光效分支，必須結合影格和早期真面板 498 判讀。

## 3. 結尾 Hold：確實按預測期限放鍵，但不能把所有 MISS 歸因提前 key-up

全場 71 次 Hold up 的原因都是 `tail_release`，不是失焦、stale timeout、手動停用或 hard timeout。

### 1077：MISS 明確早於放鍵

- L down：**763505.505822**。
- frame 7340／**763506.193** 已可見 MISS、生命下降；當時畫面與紀錄都仍顯示 L 按住。
- L up：**763506.432436**，晚於該可見 MISS 約 239ms。

所以這個 MISS 不是由這一次 key-up 觸發。起點是否被正確遊戲接受、該判定的物理歸屬與按住過程中的遊戲條件，仍需獨立驗證，不能直接怪罪放鍵時間。

### 1151 與最後一段 1162：尾端追蹤失真，仍沿用早期期限

1151/J：

- down 763512.251345；up **763512.849607**。
- frame 7711 尾端 top y=217 時，以 crossing **763512.757545** 加 uncertainty **91.193ms**，建立 release **763512.848737**。
- 後來 cap 1154 跟成 y=230 的 `tap`，預測變成 outside horizon／stationary／stale，沒有新的有效尾端時間；舊期限仍會執行。

1162/K：

- down 763513.757222；up **763514.333776**。
- 早期 y=222 預測 crossing **763514.240699**，加 uncertainty **91.279ms**，得到 release **763514.331977**。
- 後來尾端是薄片／ambiguous／hold_head，後續更新也出現 `release_update_bound`。它不是到 key-up 當幀才確認尾端越線。
- frame 7856／763514.304983 可見綠色判定殘光，沒有清楚可辨的完整尾端；7859 仍有光效。這些綠光本身不能證明真色帶還沒結束。
- 末段抽查生命維持 320、Combo 增加到 34；最後 focus_lost 在 **763514.382128**，比 K up 晚約 48ms，不是該次放鍵原因。

**可確認的程式風險**：尾端追蹤已變質時，舊的粗略 release deadline 仍有效；目前更新受原本 per-step／total／freeze 限制，不會任意延長。**尚未確認的部分**：這幾次 up 到底比真正尾端早或晚幾毫秒。尾端被光效遮住，不能把預測 crossing 當作視覺真值，也不能聲稱每次 `tail_release` 都正確。

圖中的 276 同樣是早期預測期限放鍵：L 在 763433.254926 按下、763434.196995 放開；它沒有中途 up/down 重按紀錄。

## 4. 同一來源的 full／upper 對照

兩種模式都回放全部 7,945 幀，使用同一 capture／acquired／processed 時鐘與 MockActuator。

| 指標 | full | upper |
|---|---:|---:|
| Mock down／up | 409／409 | 340／340 |
| Tap down | 339 | 273 |
| Hold down | 70 | 67 |
| Hold hard timeout | 0 | 0 |
| 同 UID 重複 down | 0 | 0 |
| 遊戲命中率 | UNVERIFIED | UNVERIFIED |

以相同 capture、位置、顏色與多幀軌跡配對後：

- **273 的物理左 Hold**：full 在 763433.250919 按 F、763434.197489 放開；upper 沒有送。這項對照有 94／95 個共同位置觀測支持，顯示 upper 的恢復限制確實參與此次漏接。
- **276 的物理右 Hold**：兩模式都正常送 L，放鍵相同。
- **513 所涉真 Tap**：兩模式的壓縮回放都能由較早的真面板分支送 J，因此不能把 raw live 的失敗簡化成只有 upper 造成。
- 1077、1151、1162 的回放放鍵時間在兩模式相同；僅改出生區並沒有修復這些尾端追蹤風險。

全體可唯一配對 785 組，其中 10 組在 full 有動作、upper 無動作，均曾在上方確認。這是候選動作流失，不是 10 個遊戲 MISS；其餘不能唯一配對的資料保留 UNKNOWN。

## 5. 優先修正順序

1. **先處理假候選搶真音符**：273／282 是中性薄線接走綠色 Hold，498／513 是同色光效與真 Tap 分裂。針對具體競爭修復角色／外觀證據及身分延續，不一律放寬確認、顏色或時間容忍度。只修 neutral 通配也不足以解決同色光效。
2. **恢復已確認身分的下方觀測**：upper 需能靠嚴格影格／軌跡證據接回原身分，不能靠禁止一切下方恢復來減少 ID。短期使用一般 `launch_assist.cmd` 的 full；不要繼續以 upper 作為穩定版測試。
3. **建立可驗證的 Hold release 依據**：分開記錄初始粗估期限、最新可信尾端、角色變質與實際 key-up。先釐清哪些真的提前，再修尾端排程；不能把 stale tail 或綠色殘光直接當成延長按住的理由，也不能繞過安全停止。

本輪完成原因分析，尚未改變上述演算法、放鍵期限或安全限制。

## 證據與重播

- [原實機動作時間線](../output/analysis_latest_hold_tap_20261109/source_action_timeline.csv)
- [逐觀測與尾端決策](../output/analysis_latest_hold_tap_20261109/selected_decision_evidence.csv)
- [雙路 Hold 原始影格](../output/analysis_latest_hold_tap_20261109/paired_holds.jpg)
- [498 真面板與 513 光效出生位置](../output/analysis_latest_hold_tap_20261109/tap_birth_split.png)
- [Tap 接近判定區的原始影格](../output/analysis_latest_hold_tap_20261109/tap513.jpg)
- [1077 的 MISS 在 L up 之前](../output/analysis_latest_hold_tap_20261109/late_holds_0.jpg)
- [結尾 Hold 與最後殘光](../output/analysis_latest_hold_tap_20261109/end_more_1.jpg)
- [最後尾端區域連續影格](../output/analysis_latest_hold_tap_20261109/final_tail_crossing.jpg)
- [full／upper 軌跡對照 CSV](../output/analysis_latest_hold_tap_20261109/replay/trajectory_comparison.csv)

`selected_replay_pairs.csv` 是按來源 UID 的最佳重疊配對，其中 513 的結果代表假光效出生分支，不能單獨拿來計算該真 Tap 的送鍵率。真正的物理對應需依上述 498→513 身分錯置與影片判讀。

可重跑：

```powershell
python -B tools/replay_note_entry.py --run-dir output/assist/run_20261109T154423_161807Z --out output/analysis_latest_hold_tap_20261109/recheck --mode full
python -B tools/replay_note_entry.py --run-dir output/assist/run_20261109T154423_161807Z --out output/analysis_latest_hold_tap_20261109/recheck --mode upper
python -B tools/replay_note_entry.py --run-dir output/assist/run_20261109T154423_161807Z --out output/analysis_latest_hold_tap_20261109/recheck --mode compare
```
