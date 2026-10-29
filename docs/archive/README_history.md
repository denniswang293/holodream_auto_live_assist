# HoloDream V6 — 即時效能剖析與獨立審查

> 歷史封存文件：以下記載的是舊版功能、命令和當時狀態，不是目前專案操作指示。目前只支援全螢幕、需手動啟用的 Live Assist；離線分析、標註／評估工作流及 Shadow 入口已移除。

最新 `run_20261029T113341_807713Z` 在啟用約 86.35 秒後輸入保護停用，辨識仍繼續產生 24 筆事件而沒有送鍵。前一份判斷的來源剛超過 50ms 時，新影格已開始處理，但舊程式要等正規化及遊戲狀態檢查結束才登記 in-flight。現在在接受有效時間、焦點及 ROI 的新影格後，於正規化前先登記；這段期間只保留已啟用的鎖並暫停新按鍵，等待狀態驗證後才繼續。沒有延長 50ms 影格新鮮度或原動作期限，也不自動重新啟用。按錄影時間邊界建立的測試覆蓋正規化、狀態檢查、真正失焦、來源逾時、非遊玩狀態與緊急停止；完整測試 376 項通過。新增 `input_not_ready` 日誌保存具體失效原因與兩份影格的年齡。詳見該 run 的 `input_handoff_review.json` 及 `input_shutdown_frames.jpg`；實戰持續輸入仍待新一輪確認。

新歌普通 Tap 漏按中已確認排程逾時：黃色短條已排程 K，但喚醒後晚約 15.8ms，超過既有 15ms 容許而取消。同機量測 `Event.wait(.002)` 的等待中位數約 15.6ms，`time.sleep(.002)` 約 2.2ms；排程執行緒改用後者，醒來先檢查停止旗標，再執行原有焦點／新鮮度／期限檢查。160 次 Mock 執行緒排程對照，逾時未送出 6→0 次，送鍵延遲 P95 約 14.6→2.4ms。這是排程基準測試，不是遊戲命中率；15px 提前量、15ms 遲到容許與 Hold 規則維持原設定。紀錄見 `output/assist_v5/run_20261029T110804_503378Z/tap_scheduler_review.json`，實際 MISS 畫面見同目錄 `tap_deadline_miss.jpg`。

清理後保留目前 Assist 實測的錄影、CSV、metadata 與診斷摘要；舊 Mock 回放明細、臨時截圖、一次性幾何產生器及獨立六鍵測試工具已移除。Windows 送鍵封包測試保存在 `tests/test_windows_runtime.py`；追蹤、時間預測、Hold、快捷鍵、Shadow 零輸入、人工標註及幾何回歸測試保留。下方歷史輸出路徑僅說明產物格式，未必仍存在。

最新短測試直接存於 `output/assist_v5` 根目錄，前次黃色 Tap 已正常送 K；啟用後約 13.7 秒的第一個可見 MISS 轉為綠色 Hold。已排程的 D／F 在期限前約 11ms 因頭部跨過提前送鍵線而被刪除，根因是時間預測目標與追蹤完成線共用 y=310.5。現在預測仍以 y=310.5 為目標，追蹤直到幾何的真正判定線 y=325.5；已固定原鍵／期限的動作可在這段區域繼續等候，不能在已過預測目標後建立新動作。完整普通頭部內的細邊不因仍被分類為 Tap 而失去原動作保留資格。Mock 的 `--recorded-timing` 可使用逐幀實際處理時間；26 秒 1554 幀對照中原有 46 動作全部保留，另送出 2 次 Tap。離線基線已送到實戰漏掉的部分 Hold，因此不能宣稱實戰 Hold 已通過驗收；跨線保留與真正越線取消另以 Mock 單元測試驗證。詳見 `output/assist_v5/lifecycle_review.json`。人工檢查入口亦支援 run 直接存在輸出根目錄的情況。

`run_20261029T100618_222545Z` 的首個可見 MISS（啟用後約 8.23 秒）已用乾淨來源重現：黃色短條已排程 K，完整頭部變成仍位於原頭部內的 1px 上緣片段後，原動作在截止前約 12ms 被取消。近線固定動作現在保存原頭部 bbox／類型；只有仍被原完整頭部包住、同色且水平範圍相符的薄片段，才能維持原鍵與原期限。不同顏色、不相交或位於原頭部上方的片段仍拒絕，不能從片段建立新動作。整段 2841 幀、相同擷取時間與啟用時點的 Mock 對照：Tap 72→76、Hold 9→9；原有送鍵沒有消失或改鍵。這不是整首命中率，詳見該 run 的 `committed_head_review.json` 與 `first_miss_before/after`。保留來源做離線定位，實戰驗證以固定短片段為主，避免同時改動 ROI 和送鍵高度。

黃色 Hold 修正：`run_20261029T095003_274640Z` 的乾淨來源確認黃色長按先前只送成 Tap，因舊路徑判斷僅處理綠色。Assist profile 現啟用綠色與黃色路徑；必須在頭部後方量得至少 40px 的連續同色路徑才升級為 Hold。每個 Hold 保存自己的路徑顏色，只按起點鍵，等該色尾端離開判定列後放開。黃色半透明路徑的色相容許範圍獨立於黃色頭部，避免改動一般音符外觀分類。該次來源相同 12 秒／719 幀的 Mock 對照中，黃色 Hold 0→2，D／K 原本各按 25ms，現在分別按約 1.436s／1.424s；普通黃色 Tap 的另一段控制回放仍為短按。這是錄影重播的輸入行為驗證，不是實際遊戲命中率。

最新完整實戰 `run_20261029T035427_764077Z` 的輸入持續啟用約 89 秒，沒有再出現後段誤停用。剩餘問題中已找到預約時間錯誤：待按音符更新時間後，衝突表仍留著首次預測時間；取消但未送鍵的預約也可能繼續擋鍵。現在預約會隨動作期限更新，未按即取消／逾時的預約會移除，已送出的去重紀錄仍保留。偵測器另排除被完整同色 Tap 頭部包住的內部亮邊／暗紋片段，避免一顆橫條產生額外候選。原影片 600–1799 幀對照中移除 175 個內部片段，建立的追蹤 ID 1773→1714；這是碎片診斷，不能當成召回率。詳見該 run 的 `tap_fragment_review.json`。

Assist 啟動時選 Y 錄影，現在會產生 `live_source.mp4`（乾淨畫面）、`live_overlay.mp4` 和 `live_video_index.csv`，共用現有的有界編碼執行緒。編碼跟不上只替換尚未讀取的錄影影格，不阻塞 CV；丟棄數與名義 FPS 保存於 `live_run.json`。人工檢查工具會優先開乾淨來源；Mock 工具也支援新的 Assist run，舊版僅 overlay 的錄影仍可人工檢查，但不能當成 detector 回放來源。錄影名義 FPS 不代表實際擷取時間，必須用獨立索引對應主機時間。

最新錄影 `run_20261029T031340_137193Z` 在啟用約 10.16 秒時發生輸入自動停用：上一個已驗證畫面已過 62.44ms，但當時正在處理的新影格只有 31.35ms，約 0.45ms 後便完成辨識。排程器現在會在這種交接期間暫停新按鍵，保留原本已啟用的狀態；新結果確認後才繼續，已錯過容許時間的動作仍略過。新影格本身過期、失焦、ROI／遊戲狀態失效時仍關閉輸入，需要快捷鍵重新啟用。日誌增加 `decision_wait`／`decision_resumed`，不會自動重新啟用。該次時間點的 Mock 重現與來源 CSV hash 存在 `output/assist_v5/run_20261029T031340_137193Z/decision_handoff_review.json`；這項修正不代表錄影中更早的辨識漏按已全部解決。

2026-10-29 色塊辨識試跑後，使用者回報效果沒有改善；目前已恢復原本的水平邊緣加 HSV 外觀辨識。V6 Shadow、Assist 與離線分析共用此偵測器；15px 提前送鍵、Hold 與快捷鍵鎖維持原設定。

最新 Assist 實戰回報普通 Tap 漏按較多；`run_20261028T182756_871708Z` 的日誌顯示 35 個事件首次因擊中時間穩定性不足而略過，其中青／黃外觀有 21 個。`config/live_assist_v5.json` 只對青／黃候選使用兩次一致的擊中時間估計，並以最近三次估計判斷舊的時間離群值是否已恢復；綠色 Hold、粉紅及灰白候選仍用原門檻。時間不確定度、漂移上限、送鍵鍵位、15px 目標及輸入鎖不變。用 `holodream.mp4` 前 40 秒做相同時間軸的離線 Mock 回放，Tap 送鍵 47→53 次、Hold 2→2 次、取消 136→136 次；這不是實際命中率。

錄影試跑 `run_20261029T025248_638020Z` 仍見漏按：正常青／黃頭部在 y≈252、距原預定時間約 244ms 時失追，被取消；另有青／黃殘邊已貼近判定帶，首次有效時間估計只剩約 10–20ms。Assist 現只對已確認並排程的青／黃 Tap，在 y≥250 且原期限≤250ms 時保留原鍵與原截止時間；其他 unknown／Hold 仍用先前 200ms／y≥265 規則。貼近送鍵線 25px、預測時間≤50ms、不確定度≤20ms 的青／黃 unknown 可用單次有效估計補最後一次機會。失焦、失效影格及遊戲狀態關閉仍立即取消。相同 `holodream.mp4` 前 40 秒的離線 Mock 對照：Tap 53→72、Hold 2→2、取消 136→119；多送鍵不等於多命中，仍需新實戰及人工核對誤按。

最新漏按修正：範圍內任意一鍵模式使用「目前候選鍵 ∩ 跨幀穩定鍵」，不因另一個邊緣候選暫時改變而全部拒絕；首次在同一啟用期間出現但尚未就緒的事件，後續可變成可執行，關閉時出現或舊啟用期間事件仍不能復活。已固定的 Tap 可由同一頭部的藍／黃殘邊維持至原截止時間，不會把新的殘邊或綠／粉／灰白候選當成 Tap。建立與保留近線排程使用一致的既有位置抖動範圍。固定截止時間以辨識完成時間判斷 100 ms 內可否建立，失效時刻為該次預定按下時間加既有 15 ms 遲到容許，避免在預定按下前就過期；不更新或延長原預測時間。取消原因記錄於 `live_key_actions.csv` 的 `track_gate_rejected`／`commit_invalidated`。

Windows 送鍵預設改為標準 SendInput scan-code 模式：`wVk=0`、`wScan=MapVirtualKeyW(...)`、按下旗標 `KEYEVENTF_SCANCODE`、釋放再加 `KEYEVENTF_KEYUP`；定義見 [Microsoft KEYBDINPUT 文件](https://learn.microsoft.com/windows/win32/api/winuser/ns-winuser-keybdinput)。仍保留手動選用的 `--input-mode virtual_key` 供獨立測試比較；不會自動切換模式、提高權限或處理遊戲保護。實戰的選擇記錄在 `live_run.json.keyboard_input_mode`。

實戰終端送出 Tap 顯示 `TAP sent: S`，送出視覺長按顯示 `HOLD sent: S`（鍵位依音符而定）。已固定的近線排程會保留原先驗證過的單鍵與截止時間，跨過判定帶造成的短暫追蹤降級；不會因新的暫時無效擬合覆蓋該時間。保留 100 ms 上限及目前畫面、焦點、PLAYING、外觀、鍵位和 ROI 檢查。若取消，`live_key_actions.csv` 的 `commit_invalidated` 會記錄當時追蹤狀態、預測原因與高度。

全螢幕實戰入口為 `tools\launch_assist.cmd`：載入 `config/live_assist_v5.json` 與獨立的 `config/geometry_live_assist.json`。使用者已確認「範圍內任意一鍵；左至右 S D F J K L」，也確認長按按住起點鍵直到尾端、滑動途中不換鍵。每個候選只選一鍵，優先覆蓋較大的格；同時音符以一對一配對分配不同鍵，既有排程選鍵固定。有連續綠色路徑的已確認音符會送出 Hold，路徑尾端離開判定列後放鍵；其他有移動軌跡、可用到達時間與候選軌道的 unknown／不確定候選送出一次 Tap。粉紅 Flick 仍無專屬操作。原始 `key_candidates` 保留，推測送鍵的 `resolution_basis` 記錄為 `speculative_visible_candidate`，不把操作規則當成辨識準確率證據。啟動先關閉輸入，確認 ROI 並進入歌曲後按 Ctrl+Shift+Alt+Q，放開組合鍵才啟用；再按一次關閉，Esc／F12 停止。預設不顯示持續 overlay、不錄影，可在啟動時選 Y 錄影。沒有可用時間／軌道、鍵位衝突或影格失效時仍略過。V6 保持 Shadow/replay。

實戰錄影中的判定帶中心由 81 張原生 720×404 影格量得 y=325.5，與原影片校正的 y=352 不同。新 live 幾何只改判定位置並截取原投影；上、中、下外框與持續軌道色彩的擬合差異均小於 1.5 像素。新檔仍為 `pending_calibration`、全部控制點標為機器推算；原始 v4 校正與人工資料不覆寫。當已確認 Tap 頭部進入量得的判定帶上緣 y=313，且距預測判定不超過 100 ms，允許固定該次單鍵與時間，跨過判定帶遮擋。持續要求最新擷取、PLAYING、焦點與 ROI 有效；觀測到特殊音符或重疊仍取消。判定帶外短暫漏抓會取消待按動作，同一啟用期間重新取得有效觀測後可重排；停止／重新啟用不能復活舊事件。

幾何查詢快取已預設啟用。照常執行 `tools\launch_shadow_v6.cmd`，無須另外設定；啟動時顯示 `Geometry lookup cache: ON`，新紀錄的 `live_run_v6.json` 內有 `geometry_cache` 與命中次數。快取只重用相同高度的軌道邊界及寬度，不取整座標，也不改校正檔、偵測門檻或輸入模式。每份幾何物件各自保存有上限的快取；校正工具修改控制點後建立新物件，舊快取不會套到新幾何。開發比較時可用 `CalibratedGeometry(document, cache_enabled=False)` 建立原始計算基準。

目前 `output` 只保留 `assist_v5` 的實測錄影、時間索引、CSV、metadata 與診斷摘要。根目錄原始影片、目前程式、設定及人工標註資料保留。

V6 優先完成 PR1：擷取、CV、顯示、編碼及 CSV 寫入分開執行，所有待處理佇列都有上限；慢顯示／錄影只替換展示影格，不把舊影格塞進辨識。未改 detector／tracker／predictor 的演算法或閾值，幾何維持 `f1aae599...`／`pending_calibration`。V6 入口只有 shadow／replay，永遠不建立鍵盤輸入後端；既有 V5 Assist 和其快捷鍵鎖維持原樣，不會自動開啟。

雙擊 `tools/launch_shadow_v6.cmd`，視窗標題直接預設為 `hololive-Dreams`，不再詢問；選 A／B／C，再填同一譜面標籤。Assist 啟動器和兩個 Python CLI 也採用同一預設，需要其他視窗時可明確指定 `--window-title`。沿用現有 16:9 方框確認範圍。**玩家手動按鍵，程式仍然 Shadow**；Esc／F12 停止。請把 overlay 移出擷取範圍並把焦點切回遊戲。

遊戲接近全螢幕時沒有空間放 overlay，舊紀錄因此有 527 個 ROI_BLOCKED。V6 啟動器會詢問是否顯示持續預覽，預設 N：B／C 仍在背景畫 overlay，C 仍錄影，但不會用預覽視窗遮住遊戲。這相當於 `--headless`；一次性的 16:9 範圍確認仍會開啟。選 Y 才量測真正 UI display，且需第二螢幕或縮小遊戲視窗留空間；未顯示時 UI 耗時標 NOT_MEASURED，不假裝測過。

- A：只 capture + CV，不畫、不顯示、不錄影。
- B：畫及顯示 overlay，不錄影。
- C：畫及顯示 overlay，另用有界 encoder 錄影；啟動器會同時錄乾淨的 720×404 來源畫面，供人工獨立標記。

同一首簡單譜面用 A、B、C 各跑一次。之後再跑 easy／normal／特殊音符較多三個短場景。每次實際輸出資料夾會顯示在 console；已有結果時自動新增 run 子目錄，不覆寫 V5／V4.1。命令列也可直接指定：

```powershell
python -m src.live_v6 --mode shadow --window-title "hololive-Dreams" --presentation-mode C --session-label easy-chart --select-region --record-source --out output/live_v6
```

輸出 `live_events_v6.csv`、`live_frames_v6.csv`、`live_acquisitions_v6.csv`、`live_performance_by_state.csv`、`live_segments_v6.csv`、`stage_latency.csv`、`live_video_index_v6.csv`、`live_run_v6.json`、`live_diagnostics_v6.md`；C 另有 `live_overlay_v6.mp4`，加 `--record-source` 時另存 `live_source_v6.mp4`。每階段列 P50／P95／P99；tracking 不重複計入 predictor 耗時。video_encoding 包含 OpenCV 寫入／編碼／mux 與影片 I/O，不假裝是純編碼 CPU 時間；disk_write 是另外量測的批次 CSV 寫入。

PLAYING 統計單獨計算 acquired／processed／dropped／stale、延遲及最長連續空隙。未處理影格的遊戲狀態只能依相鄰已觀測狀態推估，CSV 會明確標記；V5 沒有逐筆 acquisition 記錄時只報來源序號跨度估計，不把最後的滑動 FPS 當來源幀率。CPU backlog、overlay／encoder queue wait 和各種 dropped 分開列出。Telemetry 佇列飽和會停止，不靜默遺失事件。

影片的固定播放 FPS **不是**即時擷取時間軸。請用 `live_video_index_v6.csv` 精確連結 encoded frame、source frame、capture timestamp、processing timestamp 及 event IDs；被顯示／編碼丟棄的 CV 事件仍保存在事件 CSV。過期 ETA 記為 `eta_expired=true`／`predicted_hit_not_future` 並排除執行，不因 uncertainty 小而放行。

比較已錄好的 A／B／C 時，核對各次 `live_run_v6.json` 的來源、譜面標籤、幾何與設定，再查看每個 run 的 `live_performance_by_state.csv` 及 `stage_latency.csv`。

沒有遊戲時可重播相同來源時段作開發量測，但不能當 Windows 實測；`--headless` 不量測 UI display：

```powershell
python -m src.live_v6 --mode replay --presentation-mode C --record-source --source-seconds 10 --headless --video holodream.mp4 --session-label original-first-10s --out output/replay_v6
```

先前四組 Windows V5 紀錄的唯讀審查與開發用重播比較已按清理要求刪除。重新錄製後可用相同工具重建；舊版未量測的階段仍不可由掉幀比例反推瓶頸。

人工審查：雙擊 `tools/launch_live_review.cmd` 會自動開啟最新且有 overlay 的 Assist run，依 run 名稱另建人工標註檔；若有 `live_source.mp4`，會優先開乾淨畫面。舊 run 只有 overlay 時，辨識框可能遮擋實際音符。V6 C 紀錄可用以下命令開啟。工具不會把模型文字複製為真值。

```powershell
python -m tools.review_live --run "V6 C的輸出資料夾" --annotations annotations/live_v6_easy.json
```

逐個 recorded frame 觀察真實判定，填實際鍵位、類型、reviewer；不確定用 uncertain、未知鍵留空，綠色軌跡可只標 green_path 而不推斷 Hold／Slide。按「儲存目前可見判定」。可人工註記模型是否漏判。只有範圍內所有真實音符都標齊，才儲存並勾選完整審查範圍。時間使用對應 host capture timestamp 和相鄰觀測區間，不使用 video_frame/FPS。

```powershell
python -m tools.review_live --run "V6 C的輸出資料夾" --annotations annotations/live_v6_easy.json --evaluate output/live_v6/live_quality_v6.json
```

獨立一對一時間配對會列出 Tap／Unknown／green_path_candidate 的混淆與漏判。至少 100 個完整審查範圍內的 confirmed Tap 才公布 precision／recall；wrong-key 只比較非空的實際 resolved_keys 與人工鍵位，至少需 100 組可比較配對，絕不把 D|F 當 D+F。時間誤差至少需 100 組不含配對歧義、觀測間隔 ≤35ms 的可比較判定；它仍是相對可見擷取判定，不是引擎內部時間。未滿足時數值是 null／UNVERIFIED。計分和測試均不會解除輸入鎖。

目前新人工資料仍為 0；不宣稱辨識準確率或命中率已達標。歷史 V6 交付報告已依清理要求移除，需新實測資料才能重新評估。

---

# V5 即時 Shadow／快捷鍵控制（保留離線辨識）

V5 沿用目前 V4.1 幾何快照，不要求重新校正。幾何仍未完成獨立驗證，辨識準確率仍為 `UNVERIFIED`。原本的離線 CLI、v3 標註／評估及校正工具維持原用法。

V5 規格預設 shadow 零輸入；依使用者這次額外要求，另提供實驗性 `assist` 模式和 **Ctrl + Shift + Alt + Q** 開關。shadow／replay 不會建立鍵盤輸入後端；assist 啟動也一律關閉，必須在遊戲視窗取得焦點且正在遊玩時按組合鍵，放開修飾鍵後才啟用。再按一次關閉，Esc／F12 停止並釋放程式持有的鍵。失焦、暫停／結算、ROI 被預覽視窗遮住、移動／縮放視窗或影格過期都停止輸入；恢復後需要重新按快捷鍵。

安裝 Windows 即時擷取的可選依賴（離線辨識不需要）：

```powershell
cd "C:\Users\USER\Desktop\holodream"
python -m pip install -r requirements-live.txt
```

雙擊 `tools/launch_shadow_v6.cmd` 或 `tools/launch_assist.cmd` 時會直接擷取遊戲視窗所在螢幕的完整實體顯示範圍，不再顯示 ROI 選取框。辨識回到原有 720×404 座標；全螢幕影格會等比例縮放與置中補邊，不會直接用 1920×1080 做 CV。遊戲須以接近 16:9 顯示；啟動器使用 headless，避免把 overlay 擷取回遊戲畫面，Shadow C 模式仍保存 overlay 與乾淨來源錄影。DXcam 優先，次螢幕等 DXcam 不支援的範圍自動改用 MSS。

預設即時 Assist 與 V6 Shadow 擷取遊戲所在螢幕完整畫面，再適配到 720×404 原有辨識座標。`--full-screen` 需要 `--headless`，且不可與 `--crop`／`--select-region` 同用。另有 `config/*1920*` 的直接高解析度設定可供手動選用；目前啟動器不使用它們。所有既有 v3/v4 標註與離線影片工作流保持 720×404。實際縮放與補邊參數保存於 `live_run.json.normalization_transform`。

命令列用法：

```powershell
python -m src.live --list-windows
python -m src.live --mode shadow --window-title "你的遊戲視窗完整標題" --config config.json --geometry config/geometry_holodream_v4.json --out output/live_v5 --select-region --record-overlay
```

也可用 `--crop X Y WIDTH HEIGHT` 指定相對視窗內容區的遊戲矩形；不含標題列，並使用實際螢幕像素。相同標題有多個符合視窗時會要求改用明確標題，不自選。錄影畫面放在獨立 overlay 視窗，請移到遊戲擷取區之外；沒有空間時可加 `--headless` 只記錄檔案。視窗移動／縮放後，重新啟動並確認範圍。

要使用快捷鍵控制的實驗模式，雙擊 `tools/launch_assist.cmd`，或：

```powershell
python -m src.live --mode assist --config config.json --live-config config/live_assist_v5.json --geometry config/geometry_live_assist.json --full-screen --headless --out output/assist_720
```

Shadow 的對應命令為 `python -m src.live_v6 --mode shadow --config config.json --live-config config/live_v5.json --geometry config/geometry_live_assist.json --full-screen --headless --record-source --out output/live_v6_720`。Shadow 使用 `NoInputActuator`，不會送鍵。若需重播舊 720×404 影片，沿用原本的 720 設定與幾何檔。

**快捷鍵只開啟執行許可，不會驗證辨識結果。** 在這次明確選用的 Assist profile 下，`D|F` 是同一音符的可選鍵，動作只選 D 或 F，不會按成 D+F。`speculative_taps.enabled=true` 會將有移動軌跡、未來擊中時間和候選軌道的 unknown／不確定候選也納入；時間不確定度上限 0.10 秒、跨幀擊中時間漂移上限 0.15 秒。經使用者確認後，`hold_visual.enabled=true` 對至少 40px 連續綠色路徑的候選按住起點鍵，尾端離開 y≈304 的偵測列超過 80ms 後放鍵，最長 6 秒；失焦、暫停、停用快捷鍵或 F12／Esc 立即放鍵。這仍是未經人工真值驗證的視覺啟發式；可能誤判或漏判 Hold／Slide，Flick 尚未實作專屬操作。使用普通 Win32 SendInput，不處理遊戲記憶體或保護機制。

若兩個即時追蹤同色、候選鍵範圍相同、擊中預測相差小於 35ms，且水平音符範圍重疊至少 90%，Assist 會視為同一實體音符，只保留一個鍵位，避免碎片輪廓被選成兩鍵。

最新實戰 `run_20261029T124829_727209Z` 在仍為 PLAYING、視窗有焦點時，因決策影格年齡短暫達 51.89ms、超過 50ms 上限而解除 Assist。720 Assist profile 現將 `max_frame_age_ms` 調為 60；遊戲視窗失焦、狀態不符或超過新上限仍會停止送鍵並解除啟用。

依 2026-10-28 實機回饋，Assist 的提前量為 **15 個 720×404 座標像素**，預測目標由 y=325.5 上移至 y=310.5。這只改送鍵時機，不移動校正幾何、六鍵分界或畫面判定線。Assist overlay 以橘線標出提前送鍵目標，右側列出像素量；左上角顯示實際輸入啟用狀態。先前的離線對照報告已按清理要求刪除。

2026-10-29 實戰回饋顯示 y=310.5 的時機合適，但有已排程音符在 y≈267–292 短暫失追而取消。Assist profile 因此加入 `dropout_grace_ms=200`、`dropout_min_y=265`：只有已確認且已排程、最近在 y≥265 看見、預定送鍵在 200ms 內的原選鍵與原期限可於短暫失追時保留。過期、新的衝突觀測、遊戲狀態或焦點失效仍取消；不會從失追音符建立新送鍵。這是依實機日誌的針對性調整，尚待下一次實戰驗證漏按與誤按變化。

下一次實戰顯示 Tap 增至 55 次，但綠色候選仍只有 24–41ms 的單次按鍵。長按控制已依使用者確認的規則加入；對保留的乾淨來源影格做 10 秒離線 Mock 回放，得到 20 次 Tap、3 次 Hold，其中一段可見綠色長路徑維持約 3.0 秒後於尾端離開判定列時放鍵。這些是模擬輸入與畫面追蹤結果，實際遊戲判定仍需下一次實戰確認。詳見 `output/assist_v5/hold_audit_20261029_final/audit.json`。

再一次實戰 `run_20261028T171725_399125Z` 中，Hold 17 次均有可見尾端放鍵紀錄；Tap 108 次，使用者確認長按成功、漏按減少。仍有若干已排程音符因單幀 `latest_position_outlier` 在目標線附近取消。Assist 現在允許這種觀測在原本的 200ms 失追上限內維持原選鍵與原截止時間，但必須仍是同色、同鍵、橫向範圍重疊且靠近目標線的同一條音符；新候選不因此獲得送鍵資格。對未排程的 `unstable_hit_time` 不直接放寬，因錄影中的光效與同音符碎片會產生大量假候選。同一段乾淨來源的 10 秒離線 Mock 回放由 20 Tap／3 Hold 變為 22 Tap／3 Hold；額外送鍵不等於命中，這項調整仍待實戰確認。

舊 `config/live_v5.json` 的 `verified_key_mapping` 仍留空，不捏造逐音符人工驗證資料。實戰啟動器改用獨立的 `config/live_assist_v5.json`，記錄使用者的操作規則原文、日期與幾何 SHA256；不同幾何不能沿用該 profile。未指定此 profile 的舊路徑仍僅接受原本具人工證據的單鍵候選。`config.json.control.dry_run=true`、離線分析、v3 人工標註和評估均保留；辨識、鍵位與命中時間準確率仍為 UNVERIFIED。實戰輸入記錄在新資料夾的 `live_key_actions.csv`，不可用候選事件數當成實際送鍵次數。

以真實錄影測試選鍵與排程，但不接觸鍵盤：

```powershell
$sourceRun = Read-Host "含有 live_source.mp4 或 live_source_v6.mp4 的實測資料夾"
python -m tools.audit_assist_taps --run $sourceRun --out output/assist_mock_recheck --seconds 30
```

此工具只使用 MockActuator 與錄影索引中的主機時間，模擬固定 2 ms 處理延遲；不量測真實遊戲判定或 Win32 送鍵。

在沒有即時遊戲影像時，可用**相同 LiveEngine** 重播原影片，永遠零輸入：

```powershell
python -m src.live --mode replay --video holodream.mp4 --record-overlay --headless --out output/replay_v5
```

重播使用模擬的 monotonic 來源時間，加上本機量測的擷取／處理時間；若處理落後便跳到最新來源幀，不累積佇列。這是 recorded replay，不是實際桌面擷取速度或遊戲驗證。

每次執行輸出 `live_events.csv`、`live_frames.csv`、`live_key_actions.csv`、`live_diagnostics.md`、`live_run.json`，可選 `live_overlay.mp4`，以及正常單鍵候選、多候選、未知特殊音符的三張樣本圖（若實際出現）。每個事件記錄候選鍵、未解析／已驗證鍵、預測時間、不確定度及 abstain 原因；confidence_label 明確是啟發式分數。所有時間欄位都是該次單調時鐘，不是 Unix 時間。影片影格與原始來源的對應見 `live_frames.csv.video_frame`；重播被丟棄的時段以最後 overlay 畫面補幀。已有結果時自動新增 UTC run 子目錄，不覆寫舊輸出。

即時擷取僅保留一張待處理影格，記錄實際擷取 FPS、處理 FPS、frame age、擷取至決策 P50／P95、dropped／stale。host capture-start 時間不是經驗證的 GPU 顯示時間；也不能用這些數字取代音符 timing accuracy。擷取資源、全域快捷鍵、排程器都有明確停止及釋放流程。

本輪沒有實際遊戲的三段測試或 100 筆人工 Tap 真值。請先用 shadow 記錄慢速／普通／特殊音符較多三個短場景，並人工確認至少 100 個實際判定與按鍵。規格的 precision/recall ≥95%、錯鍵 ≤1%、時間 P95 ≤35ms、實際持續 ≥60 FPS 仍是待驗證目標，不能把測試通過當成達標。

實作參考：[DXcam 官方 API](https://github.com/ra1nty/DXcam)、[MSS 官方範例](https://python-mss.readthedocs.io/stable/examples.html)、[RegisterHotKey](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey)、[SendInput](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput)。

---

# v4 軌道幾何校正（保留 v3 標註與評估）

本輪先交付幾何診斷與校正工作流。**目前真實 Spawn／Middle／Hit 分界仍為 UNVERIFIED**；新設定中的座標是明確標記的舊估計初值，並非已修正座標。未取得獨立三高度人工點前，不宣稱 Homography 或其他模型能改善配準。

## v4：選幀 → 點選 → 預覽 → 存檔 → 驗證 → 分析

原始影片是 720×404、60 FPS、3,553 幀。所有控制點保存為原生影片像素；預覽放大、crop、letterbox 只影響顯示，點選使用顯式逆轉換。

使用者另外提供的固定軌道座標可記為 `origin=human_manual`、`frame=null`、`frame_scope=static_video_geometry`，不虛填來源幀。這些是校正控制點；獨立驗證點及音符判定標註仍須記錄實際影格。未實測的 ROI 外框若為容納新分界而擴張，標為 `derived_estimate` 且維持未確認。

啟動校正 GUI（也可雙擊 `tools/launch_calibrator.cmd`）：

```powershell
python -m tools.calibrate_geometry --video holodream.mp4 --config config.json --output config/geometry_holodream_v4.json --validation geometry_validation_points.json --time 11
```

1. 用幀號、秒數、±1／±60 或滑桿選清楚原始幀。已輸出 0、5、11、22.8、30、54 秒對照；不要從縮放截圖抄像素座標。
2. 選 spawn / middle / hit 列，填 native `row y` 並按「移動目前列 y」；移動後舊測量會取消確認。必要時增加內部高度列。
3. 選 `boundary`，依序點七條六鍵投影分界 0..6。畫面顯示水平 y 引導線，點選需在 1 個原生像素內；儲存 raw click 與約束後 row y。右鍵定位放大中心，再選 2／4／8 倍。六個鍵區不一定等寬。
4. 另外選 `outer_left / outer_right` 標可見物理外界；它們和六鍵分界是不同控制資料。`hit_left / hit_right` 標判定線端點。不要用背景裝飾或音符當成已確認外界。
5. 只有確實看清時勾「已人工確認」並填 reviewer；灰色 + 是未確認初值，綠色 + 是實測，圓圈是模型預測，紫色菱形是獨立驗證點。可切換外界、七界、六中心線、spawn 區域、hit line、原點、預測點、文字及像素座標。
6. 換另一原始幀，選 `validation_boundary` / `validation_center` 等，手動點獨立證據並選正確高度組。分界 index=0..6、中心=0..5、outer index=0、hit endpoint=0..1。同幀控制點不能重複當獨立真值；不能把模型預測抄成標籤。可刪所選驗證點及復原。
7. 比較 `linear`（C）、`homography`（A）、`piecewise`（B）。先選最簡且能通過獨立三高度點的模型；同四角 Homography 和原直線可能相同。控制點訓練擬合誤差不能代替獨立驗證。
8. 儲存會驗證缺失、交叉、排序、有限數值與可逆性；錯誤時保留上一份有效檔案。未完成草稿會明確標示顯示「上一份有效模型」。獨立驗證另存不可變的 hash snapshot，避免編輯新驗證資料破壞舊校正證據。

在沒有 GUI 的環境產生原生預覽、上中下對照與完整幾何影片：

```powershell
python -m tools.calibrate_geometry --video holodream.mp4 --config config.json --output config/geometry_holodream_v4.json --validation geometry_validation_points.json --time 11 --preview output/geometry_v4/calibration_preview.png --report output/geometry_v4 --debug-video
```

省略 `--debug-video` 可快速重產報告。`--frame` 與 `--time` 互斥；`--init-only` 只建立／檢查可編輯初值，不開 GUI。三高度各至少三個獨立確認點，最大誤差 ≤2 native px 且 ≤0.25 lane width；全部控制點人工確認、判定線水平且對應底列後，才會標記 `validated`。這只是目前校正驗收門檻，不能代表遊戲辨識準確率。

第二階段離線分析命令已接好，**pending 設定會先被拒絕**：

```powershell
python -m src.main analyze --video holodream.mp4 --config config.json --geometry config/geometry_holodream_v4.json --version v4 --out output
```

只有使用者人工校正並通過獨立 Spawn／Middle／Hit 驗證後才產生 `overlay_v4.mp4`、`detections_v4.csv`、`note_events_v4.csv` 與 `geometry_rejections_v4.csv`。tracker、predictor、特殊音符語意保持原有邏輯；仍為 dry-run，resolved_keys 空白，executable=false。傾斜判定線可存作診斷，但目前單一 hit_y 的時機流程不會被標為可接入。

使用者指定的 **V4.1 離線試跑**採用目前 spawn 左右界及六等分設定。若尚未完成獨立驗證，可明確指定下列試跑選項；程式仍檢查幾何完整性、來源影片及 `dry_run=true`，不會改寫設定的驗證狀態。影片標示 `V4.1 / geometry:UNVERIFIED`，執行紀錄保存完整幾何快照與 hash。

```powershell
python -m src.main analyze --video holodream.mp4 --config config.json --geometry config/geometry_holodream_v4.json --version v4.1 --allow-unverified-geometry --out output
```

輸出使用 `v4_1` 檔名：`overlay_v4_1.mp4`、`detections_v4_1.csv`、`note_events_v4_1.csv`、`tracks_v4_1.csv`、`frame_states_v4_1.csv`、`geometry_rejections_v4_1.csv`、`run_v4_1.json` 及 `debug_v4_1/`。這是未驗證幾何的辨識實驗，不能當作準確率改善的證據。標準 `--version v4` 的獨立驗證要求維持不變。

新幾何下的音符標註必須使用**新檔名**，不自動解讀或遷移 v3 的舊 u：

```powershell
python -m tools.annotate --video holodream.mp4 --geometry config/geometry_holodream_v4.json --annotations annotations/holodream_v4.json
```

JSON 保存 geometry schema/hash 與模型快照；既有標註 hash 不同會顯示 migration error，保留原檔。評估器同樣檢查幾何版本，包含較早僅保存 playfield 的 v3 資料。日後評估 v4 請另設 `--out output/evaluation_v4`，保留舊評估報告。

v4 產物：`config/geometry_holodream_v4.json`、獨立 `geometry_validation_points.json`、`output/geometry_v4/before_after_spawn.png`／`middle.png`／`hit.png`、六張完整原幀對照、`geometry_debug_overlay.mp4`、`geometry_validation.md/.json`、`changes_v4.md`、`changes_v4.patch` 及測試紀錄。沒有獨立標籤的誤差顯示 UNVERIFIED；候選多值、ROI 外框及 u 漂移只用同一批 v3 bbox 重投影作診斷，不假裝重新量測 track fragmentation。

幾何 API：`screen_to_uv`、`uv_to_screen`、`lane_bounds_at_y`、`lane_centers_at_y`、`playfield_polygon`、`is_inside_playfield`、`safe_lane`、`safe_bbox_interval`、`safe_candidate_lanes`。外部點回傳 None／空候選；legacy 的 `lane()` 保留舊 clamp 相容性，但 pipeline 使用安全 API。detector mask、局部 lane width、候選分配及 overlay 都由同一物件提供，不另寫簡化線條公式。

---

## 保留的 v3 人工標註與獨立評估

本輪完成人工標註工具、基於真值的獨立評估器，以及候選 lane／已驗證輸入鍵的欄位隔離。沿用 v2 的 OpenCV 讀片 → detect → track → predict → overlay 架構，保留舊輸出與診斷資料。`detector.py` / `tracker.py` 演算法未調整；設定維持 `control.dry_run=true`。

**未驗證準確率**：目前 `annotations/holodream.json` 沒有人工標籤。新的 evaluation 報告會顯示未評估，不會把 124 筆候選當成真值或 124 個 FP。

## 安裝

Python 3.11+，GUI 使用 Python 的 tkinter，CV 與測試沿用現有依賴：

```powershell
python -m pip install -r requirements.txt
python -m pytest -q
```

## 1. 使用人工標註工具

執行下列命令，或雙擊 `tools/launch_annotator.cmd`：

```powershell
python -m tools.annotate --video holodream.mp4 --annotations annotations/holodream.json
```

若只建立空白資料／匯出 CSV、不開啟介面：

```powershell
python -m tools.annotate --video holodream.mp4 --init-only --export-csv annotations/holodream.csv
```

- 影片幀號由 0 起算，可用左右鍵、±1／±10 按鈕、幀號／秒數跳轉及時間滑桿。
- 到判定影格，按「本幀設為判定」，再點音符中心填位置 u。亦可手動填 `u:0.45` 或零起算 `lane:2`；寬條可補 `u_min/u_max`。
- `hit_reference` 記錄前緣、中心或判定特效；不確定時保留 `certainty=uncertain`，不要猜測實際判定幀。黃／紅線是設定幾何，不是人工真值。
- 確認標籤需填 reviewer；`verified_keys` 未證實時留空，不能從候選 lane 推導。`S|D` 表示人工證實兩鍵的輸入語意，請勿用來填一個寬條可能接受的兩個鍵。
- 追蹤同一音符時，在不同幀點主體中心並按「加入軌跡觀測」；間隔建議 ≤6 幀。這些後續點不會改寫原先判定幀的位置。
- 背景負樣本選 `label=background`，點背景位置（u、background_v），並填實際觀察的起末幀。負樣本不會將整條 lane 都排除。
- 按儲存才寫入 JSON；可編輯、刪除、復原與匯出 CSV。切換尚未儲存的表單會提醒。JSON 原子替換寫入，驗證失敗不覆寫舊資料。
- 右側 review window 可新增／修改區間，**只有全部真實音符已標齊時**才勾選 complete 並儲存。三個初始區間均為未完成。

詳細取樣目標見 [annotations/REVIEW_PLAN.md](annotations/REVIEW_PLAN.md)。先標 30–50 筆跨場景音符及數筆背景負樣本。JSON 保存影片 SHA256、FPS、幀數、固定幾何與完整標註區間；CSV 與 `.metadata.json` 方便人工檢閱，評估入口使用 JSON。

## 2. 產生 v3 離線輸出

```powershell
python -m src.main analyze --video holodream.mp4 --out output --version v3
```

CLI 預設輸出 v3；Python `analyze()` API 預設 v2 以保留原測試相容性。新版不覆寫 `events.csv`、`overlay.mp4` 或 `*_v2.*`。仍可顯式指定 `--version v2` 重跑舊格式路徑。

| 欄位 | 語意 |
|---|---|
| `candidate_lanes` | 零起算的可能 lane 集合，例如 `0|1`；不是 chord |
| `key_candidates` / detections 的 `candidate_keys` | 舊欄位相容名稱，同樣只是幾何候選 |
| `resolved_keys` | 已驗證實際輸入鍵；本輪全部留空 |
| `u_min/u_max` | 觀測主體的正規化橫向範圍，用於獨立位置比對 |
| `source_v` | 事件來源主體的垂直中心 / 參考高度，用於背景負樣本核對 |
| `confidence` / `heuristic_score` | 形狀啟發式分數，並非正確率或機率 |
| `status / executable` | 事件仍為 `pending_review / false` |

這一節描述 v3 離線事件欄位：粉色、綠色與灰白候選維持 `unknown`，原始 PR3 的完整 flick／hold／slide 分類仍未建立。現行 Assist 另以使用者確認的操作規則和可見綠色路徑試做 Hold 送鍵；其事件類型與遊戲判定尚未經人工真值驗證。

## 3. 使用同一份真值評估 v2 / v3

```powershell
python -m tools.evaluate --annotations annotations/holodream.json --events output/note_events_v3.csv --detections output/detections_v3.csv --baseline-events output/note_events_v2.csv --baseline-detections output/detections_v2.csv --out output
```

也可單獨評估 v2：將 `--events`／`--detections` 指向 v2 檔案並省略 baseline 選項。資料搬移後可加 `--video` 指向同 SHA256 的原影片。

評估固定影片 SHA256／FPS／幀數；比較版本使用相同 JSON SHA256 與相同門檻。可用 `--time-tolerance-ms`（預設 100）及 `--u-tolerance`（預設 .09）調整配對容許範圍，報告會記錄設定。

Hungarian 配對先最大化合法的一對一配對數，再最小化時間及位置成本；已知類型必須一致。同一人工音符不能重複算 TP。事件來源 detection 的幾何優先；缺少幾何時，候選鍵僅能當粗略位置範圍，不能當已解析輸入鍵。

未配對事件只在完整標註區間或明確背景負樣本內才可算 FP。其他區間為 UNSCORED；不確定標籤附近為 IGNORED。背景核對還需來源幀、u、垂直位置一致。30 個完整區間 confirmed 音符前不公布 TP/FP/FN、precision/recall；命中時間 MAE/P95/偏差與已解析鍵位正確率，各自至少需 30 組有效配對。

時間誤差直接比較 `prediction.hit_time − frame_hit/FPS`，不是 ETA 漂移。鍵位評分只比較明確的 `resolved_keys` 與人工 `verified_keys`；未知輸入鍵記為 abstention。追蹤診斷使用人工短間隔主體軌跡，記錄 ID switch、fragment break 及缺失觀測，不用 track ID 總數代替碎片率。

## 產物

| 檔案 | 用途 |
|---|---|
| `output/review_summary_v3.md` | 本次審查重點與已完成／待人工驗證項目 |
| `output/overlay_v3.mp4` | 原演算法的完整新版 schema 對照影片 |
| `output/detections_v3.csv` / `note_events_v3.csv` | 逐幀觀測與待確認候選事件 |
| `output/evaluation_v3.md` / `.json` | 同一真值集的 v2/v3 評估、來源雜湊與不確定性 |
| `output/mismatches_v3_v2.csv` / `mismatches_v3_v3.csv` | 逐項配對、未配對、忽略及未評分，附原影片時間 |
| `output/evaluation_examples_v3/` | 真值足夠時才輸出真正 FP/FN 的原始影片畫面；目前未產生 |
| `output/failures_v3.md` | 11s、22.8s、54s 診斷入口；未經真值確認不冒稱 FP/FN |
| `output/metrics_v3.json` | 原有 raw 診斷指標，與準確率分開 |
| `output/run_v3.json` | 影片、解碼時間戳、設定、來源 SHA256；reference_resolution 為唯一分析座標來源 |
| `output/revision_v3/` | 修改前來源 ZIP、完整文字 diff、pytest 報告、舊輸出雜湊檢查與行號對照 |

原有 v1/v2 影片、CSV、failures、metrics 及截圖均保留。OpenCV CLI 預設 mp4v；本次交付另可轉為 H.264/yuv420p/faststart，編碼資訊放在 `media_v3.json`。

## 下一步

先由人工完成標註與重跑評估，再分開處理 detector 假候選及 tracker 的 ID 碎片；每次只改一個模組，沿用同一份真值與固定門檻。現階段沒有建立 30–50 筆人工真值，因此不宣稱命中率、漏檢率或真實時間誤差已有改善。
