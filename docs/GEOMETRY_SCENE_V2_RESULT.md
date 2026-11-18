# Geometry Scene v2 離線重建結果

更新日期：2026-11-19

## 狀態

八部來源影片均保留最新正式 Scene、空白畫布幾何影片及同步 comparison。視覺審核為 `AUTO_VISUAL_REVIEWED / PROVISIONAL`。G3/G5 未通過；本交付不宣稱所有真實音符均已正確重建。工作依四輪連續來源覆核沒有可重現修正的停止條件結束。

## 完整影片交付

每部 comparison 以編碼影格一對一並排原片與 Scene-only 幾何；geometry 不含來源背景或來源像素。完整解碼驗收資訊見交付索引。

| Run | 正式版本 | Comparison | Geometry | Scene Timeline |
|---|---|---|---|---|
| run_20261106T164049_800126Z | revision_21 | [comparison.mp4](../output/geometry_scene_v2/scenes/run_20261106T164049_800126Z/revision_21/comparison.mp4) | [geometry.mp4](../output/geometry_scene_v2/scenes/run_20261106T164049_800126Z/revision_21/geometry.mp4) | [scene.json](../output/geometry_scene_v2/scenes/run_20261106T164049_800126Z/revision_21/scene.json) |
| run_20261106T164704_064294Z | revision_13 | [comparison.mp4](../output/geometry_scene_v2/scenes/run_20261106T164704_064294Z/revision_13/comparison.mp4) | [geometry.mp4](../output/geometry_scene_v2/scenes/run_20261106T164704_064294Z/revision_13/geometry.mp4) | [scene.json](../output/geometry_scene_v2/scenes/run_20261106T164704_064294Z/revision_13/scene.json) |
| run_20261106T164959_579760Z | revision_16 | [comparison.mp4](../output/geometry_scene_v2/scenes/run_20261106T164959_579760Z/revision_16/comparison.mp4) | [geometry.mp4](../output/geometry_scene_v2/scenes/run_20261106T164959_579760Z/revision_16/geometry.mp4) | [scene.json](../output/geometry_scene_v2/scenes/run_20261106T164959_579760Z/revision_16/scene.json) |
| run_20261106T170057_932173Z | revision_19 | [comparison.mp4](../output/geometry_scene_v2/scenes/run_20261106T170057_932173Z/revision_19/comparison.mp4) | [geometry.mp4](../output/geometry_scene_v2/scenes/run_20261106T170057_932173Z/revision_19/geometry.mp4) | [scene.json](../output/geometry_scene_v2/scenes/run_20261106T170057_932173Z/revision_19/scene.json) |
| run_20261106T170845_579909Z | revision_07 | [comparison.mp4](../output/geometry_scene_v2/scenes/run_20261106T170845_579909Z/revision_07/comparison.mp4) | [geometry.mp4](../output/geometry_scene_v2/scenes/run_20261106T170845_579909Z/revision_07/geometry.mp4) | [scene.json](../output/geometry_scene_v2/scenes/run_20261106T170845_579909Z/revision_07/scene.json) |
| run_20261106T171405_612600Z | revision_11 | [comparison.mp4](../output/geometry_scene_v2/scenes/run_20261106T171405_612600Z/revision_11/comparison.mp4) | [geometry.mp4](../output/geometry_scene_v2/scenes/run_20261106T171405_612600Z/revision_11/geometry.mp4) | [scene.json](../output/geometry_scene_v2/scenes/run_20261106T171405_612600Z/revision_11/scene.json) |
| run_20261106T172037_662313Z | revision_13 | [comparison.mp4](../output/geometry_scene_v2/scenes/run_20261106T172037_662313Z/revision_13/comparison.mp4) | [geometry.mp4](../output/geometry_scene_v2/scenes/run_20261106T172037_662313Z/revision_13/geometry.mp4) | [scene.json](../output/geometry_scene_v2/scenes/run_20261106T172037_662313Z/revision_13/scene.json) |
| run_20261106T172404_427324Z | revision_07 | [comparison.mp4](../output/geometry_scene_v2/scenes/run_20261106T172404_427324Z/revision_07/comparison.mp4) | [geometry.mp4](../output/geometry_scene_v2/scenes/run_20261106T172404_427324Z/revision_07/geometry.mp4) | [scene.json](../output/geometry_scene_v2/scenes/run_20261106T172404_427324Z/revision_07/scene.json) |

來源雜湊與盤點：[source_inventory.json](../output/geometry_scene_v2/provenance/source_inventory.json)。完整交付索引：[final_delivery_index.json](../output/geometry_scene_v2/provenance/final_delivery_index.json)。離線工具：[tools/geometry_scene_v2](../tools/geometry_scene_v2)。

## 尚未解決的疑點

- Run1：note709／note707 的身份與 Hold 尾端連續性、note1508 尾端。
- Run2：note638 身份／尾端、note965 尾端；note1689／note1709 身份仍屬 provisional。
- Run3：note443／note492 重疊 Hold 歸屬、note1959 尾端。
- Run4：note1071 特效後延續不明；note2308 自 frame2695 起不渲染，frame2706 候選未關聯；note4444 保留為 excluded candidate。
- Run5：note641／note666 尾端歸屬；note619 完整 Tap 邊界被特效遮蔽。
- Run6：note3100／note3104 merged-ribbon 尾端歸屬；note3535 的短區間明確標為 retrospective inferred；note398 release 不明。
- Run7：note4444 可能全遮擋，身份未定；note4166 路徑身份仍 provisional。
- Run8：note7 特效後 release 不明；短 Tap 推測區段維持明確標示。

## 清理狀態

已完成清理預覽：1,408 個非最終檔案，共 33,215,185,519 bytes。刪除命令在啟動前遭執行政策拒絕，因此未刪除任何檔案；舊 revisions、診斷／失敗覆核產物、暫存與歷輪清理日誌仍在。`output/recording/` 的來源影片與來源 index 未納入清單並保持唯讀。預覽及拒絕狀態記錄於 [cleanup_manifest_final_compact.json](../output/geometry_scene_v2/provenance/cleanup_manifest_final_compact.json)。可人工確認後執行的批次檔：[cleanup_geometry_scene_v2_nonfinal.bat](../cleanup_geometry_scene_v2_nonfinal.bat)。
