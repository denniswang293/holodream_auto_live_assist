@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
set "ROOT=%~dp0"
if /I not "%ROOT%"=="C:\Users\USER\Desktop\holodream\" goto :wrong_root
set "TARGET=%ROOT%output\geometry_scene_v2"
set "FAILED=0"
set "DELETED_COUNT=0"
echo Preflight: checking 1,408 listed files and their previewed sizes.
call :check "output\geometry_scene_v2\_scratch\round100_run6_pair_negative\source_geometry_pair_review.png" 747161
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\_scratch\round120_run6_note398\source_frames_492_498.png" 1269591
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\_scratch\round145_run6\native_tail_compare.png" 4294678
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\_scratch\round145_run6\run6_holds_tail_source_geometry.png" 4666782
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\_scratch\round146_run7\frame2142_full.png" 465754
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\_scratch\round146_run7\run7_candidate_window_2470_2512.png" 3347857
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\_scratch\round146_run7\run7_note2784_native_crop.png" 1607178
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\_scratch\round146_run7\run7_note2784_native_timeline.png" 7796786
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\_scratch\round174_renderer_replay\run_20261106T164049_800126Z.mp4" 30422079
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\_scratch\round174_renderer_replay\run_20261106T164704_064294Z.mp4" 31810957
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\_scratch\round174_renderer_replay\run_20261106T164959_579760Z.mp4" 23211316
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\_scratch\round174_renderer_replay\run_20261106T170057_932173Z.mp4" 46249989
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\_scratch\round174_renderer_replay\run_20261106T170845_579909Z.mp4" 40175167
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\_scratch\round174_renderer_replay\run_20261106T171405_612600Z.mp4" 47884327
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\_scratch\round174_renderer_replay\run_20261106T172037_662313Z.mp4" 52134175
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\_scratch\round174_renderer_replay\run_20261106T172404_427324Z.mp4" 34369993
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\cleanup_manifest_round_00.json" 3530
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\cleanup_manifest_round_01.json" 2189
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\cleanup_manifest_round_02.json" 4769
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\cleanup_manifest_round_03.json" 4331
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\cleanup_manifest_round_04.json" 9275
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\cleanup_manifest_round_05.json" 19620
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\cleanup_manifest_round_06.json" 25335
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\cleanup_manifest_round_07.json" 26517
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\cleanup_manifest_round_08.json" 30102
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\cleanup_manifest_round_09.json" 23484
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\cleanup_manifest_round_10.json" 23905
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\cleanup_manifest_round_11.json" 15521
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\cleanup_manifest_round_12.json" 15536
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\cleanup_manifest_round_13.json" 9046
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\cleanup_manifest_round_14.json" 28252
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\cleanup_manifest_round_15.json" 27088
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\cleanup_manifest_round_16.json" 28737
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round100_run4_note1897_color_context.png" 425645
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round100_run4_pair_color_correction.json" 42224
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round100_run4_pair_overlap_negative_review.json" 42630
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round100_run4_source_boxes_overlay.png" 111736
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round100_run4_trial_color_contact.png" 909010
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round101_run6_note1848_overlap_fragment_review.json" 8540
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round101_run6_source_frames.png" 1267532
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round101_run6_source_geometry_contact.png" 742102
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round102_run6_note398_source_geometry_contact.png" 3124667
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round102_run6_note398_tail_ambiguity_review.json" 8752
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round103_run1_frame746_zoom_boxes.png" 272552
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round103_run1_pair_source_geometry.png" 1188570
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round103_run1_same_lane_hold_overlap_review.json" 13959
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round103_run1_source_native_frames744_754.png" 1534823
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round104_run2_same_hold_boundary_duplicate_review.json" 34518
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round104_run2_source_geometry_contact.png" 1346148
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round104_run2_source_native_body_frames.png" 2278780
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round104_run2_source_native_heads.png" 1032837
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round105_run3_note2151_duplicate_review.json" 78215
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round105_run3_source_edge_boxes_2660_2675.png" 1484041
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round105_run3_source_geometry_contact.png" 2564065
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round105_run3_source_native_2660_2675.png" 1417971
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round105_run3_source_native_overlap_full_window.png" 3005277
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round106_synthetic_geometry.mp4" 146107
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round106_synthetic_renderer_contact.png" 228667
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round106_synthetic_renderer_validation.json" 2032
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round107_negative_missing_timestamp_index.csv" 123
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round107_negative_short_index.csv" 485
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round107_short_clip_estimator_smoke.json" 8616
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round107_synthetic_short_game_layout.mp4" 74874
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round107_synthetic_short_game_layout_index.csv" 501
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round107_synthetic_short_geometry.json" 6575
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round108_run7_note1011_hud_candidate_review.json" 5215
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round108_run7_note1011_source_zoom.png" 744270
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round108_run7_partial_scene_991_observation.json" 6707917
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round108_run7_source_geometry_contact_974_990.png" 2027741
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round109_run7_note1010_note1017_unresolved_review.json" 8578
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round109_run7_partial_scene_991_observation.json" 8690705
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round109_run7_plate_fragment_source_geometry_context.png" 567874
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round110_failed_converging_geometry_estimate.json" 6564
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round110_failed_converging_scene.json" 13593
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round110_generic_clip_pipeline_smoke.json" 6721
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round110_synthetic_clip_comparison.mp4" 98476
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round110_synthetic_clip_geometry.json" 7253
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round110_synthetic_clip_geometry.mp4" 30751
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round110_synthetic_clip_geometry_comparison_contact.png" 326645
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round110_synthetic_clip_run_manifest.json" 3432
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round110_synthetic_clip_scene.json" 13619
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round111_run5_judgment_band_candidate_zoom.png" 606175
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round111_run5_partial_scene_1518_observation.json" 10840175
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round111_run5_source_geometry_contact_1494_1517.png" 2787697
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round111_run5_static_plate_edge_review.json" 23512
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round112_run4_note1074_plate_edge_review.json" 28557
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round112_run4_note1094_partial_scene_1469.json" 9152262
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round112_run4_note1094_source_bbox_zoom.png" 1097610
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round112_run4_previous_geometry_source_contact_1454_1469.png" 2088900
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round112_run4_revision07_geometry_review.png" 166776
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round112_run4_source_detail_frames.png" 4578735
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round112_run4_source_frames_contact.png" 4895676
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round113_run4_note1071_hold_negative_review.json" 46502
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round113_run4_note1071_source_candidate_contact.png" 3391401
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round114_run4_note1056_source_contact.png" 1924936
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round114_run4_note1056_static_plate_edge_review.json" 11611
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round115_run4_note1094_judgment_band_review.json" 10935
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round115_run4_note1094_source_contact.png" 1532560
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round116_run5_hold_tail_source_review.json" 133985
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round116_run5_note641_note666_source_tail_contact_898_905.png" 1752126
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round116_run5_note641_note666_source_tail_contact_910_924.png" 1755844
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round117_run1_note1150_manual_source_measurement_review.png" 898196
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round117_run1_note1150_revision15_comparison_contact.png" 2710118
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round117_run1_note1150_source_1441_1446.png" 1658246
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round117_run1_note1150_source_bbox_zoom.png" 1396065
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round117_run1_note1150_source_candidate_contact.png" 2457686
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round117_run1_note1150_source_detail_1441_1445.png" 858971
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round117_run1_note1150_source_zoom_gap.png" 1258737
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round117_run1_note1150_visible_tap_gap_review.json" 34648
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round117_run1_revision15_geometry_detail.png" 124854
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round118_run6_note3104_note3100_source_tail_contact.png" 1753423
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round118_run6_note3104_tail_identity_review.json" 134848
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round119_run2_note606_note638_head_overlap_detail.png" 2876688
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round119_run2_note606_note638_overlap_review.json" 94536
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round119_run2_note606_note638_source_context.png" 2773370
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round120_run6_note398_source_frames_492_498.png" 1269591
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round120_run6_note398_source_review.json" 2086
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round121_longest_gap_source_geometry_contact.png" 2937041
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round121_run1_note349_gap_detail.png" 2142266
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round121_visibility_migration_audit.json" 9406
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round122_run1_bounded_rebuild_1600.json" 11252096
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round122_run1_bounded_rebuild_1600_trace_v3.json" 11301853
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round122_run1_note349_gap_contact.png" 1949565
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round122_run1_note349_gap_review.json" 17083
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round122_run1_source_rebuilt_scene.json" 23436575
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round122_run2_bounded_rebuild_850_v2.json" 6002598
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round122_run2_source_rebuilt_scene.json" 25347585
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round123_run3_bounded_rebuild_180.json" 494126
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round123_run3_frame150_source.png" 1147341
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round123_run3_note7_candidate_contact.png" 2145173
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round123_run3_note7_gap_review.json" 9843
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round123_run3_note7_gap_source_contact.png" 2198251
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round124_run3_bounded_rebuild_800.json" 4060491
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round124_run3_note368_candidate_contact.png" 2289302
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round124_run3_note368_early_gap_contact.png" 643418
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round124_run3_note368_gap_review.json" 10349
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round124_run3_note368_gap_source_contact.png" 2444576
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round124_run3_note368_gap_zoom.png" 804182
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round125_run3_bounded_rebuild_800.json" 4060491
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round125_run3_bounded_rebuild_800_v2.json" 4060491
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round125_run3_full_rebuild.json" 17113181
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round125_run3_link_debug2_180.json" 494222
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round125_run3_link_debug_180.json" 494222
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round125_run3_note1124_bridge_source_contact.png" 2466466
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round125_run3_note1124_candidate_contact.png" 2715818
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round125_run3_note1386_bridge_source_contact.png" 2025638
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round125_run3_note1386_candidate_contact.png" 2302889
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round125_run3_note368_candidate_contact.png" 2325818
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round125_run3_note7_candidate_contact.png" 2208572
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round125_run3_partial_bridge_180.json" 518919
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round125_run3_partial_bridge_800.json" 4092526
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round125_run3_partial_bridge_review.json" 4630
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round126_run1_bounded_240.json" 1139268
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round126_run1_bounded_800.json" 4709368
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round126_run1_cross_run_bridge_review.json" 3675
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round126_run1_full_rebuild.json" 23500824
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round126_run1_geo_2924.png" 111438
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round126_run1_geo_2928.png" 106435
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round126_run1_geo_2933.png" 116718
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round126_run1_note1494_candidate_contact.png" 4745421
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round126_run1_note1494_zoom.png" 364212
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round126_run1_note2767_candidate_contact.png" 4541905
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round126_run1_note2767_zoom.png" 444395
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round127_run3_note1124_candidate_contact.png" 2838885
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round127_run3_note1124_edge_source_contact.png" 3720873
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round127_run3_note1124_grid.png" 2822369
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round127_run3_note1386_candidate_contact.png" 893421
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round127_run3_note1386_grid.png" 529213
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round127_run3_note1386_missing_source_contact.png" 1559887
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round127_run3_visible_gap_review.json" 3560
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round128_fragment_geometry_review.json" 8633
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round128_run1_full_rebuild_v2.json" 23501300
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round128_run1_note1494_candidate_contact.png" 565438
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round128_run1_note2767_candidate_contact.png" 463146
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round128_run2_full_rebuild.json" 25493987
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round128_run2_full_rebuild_v2.json" 25494328
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round128_run2_note129_candidate_contact.png" 2380577
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round128_run2_note129_candidate_contact_v2.png" 2318200
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round128_run2_note129_grid.png" 1702455
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round128_run2_note129_source_contact.png" 3361920
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round128_run3_full_rebuild_v2.json" 17114828
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round128_run3_note1124_candidate_contact.png" 1820286
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round128_run3_note1386_candidate_contact.png" 1081159
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round128_run3_note368_candidate_contact.png" 2440050
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round129_run4_full_rebuild.json" 25161867
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round129_run4_note1464_candidate_contact.png" 3580223
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round129_run4_note1464_early_grid.png" 552993
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round129_run4_note1464_geometry_mismatch.json" 3512
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round129_run4_note1464_late_grid.png" 720150
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round129_run4_note1464_source_contact.png" 3134745
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round130_run5_effect_band_association_review.json" 2186
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round130_run5_full_rebuild.json" 24939805
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round130_run5_note2196_window.png" 3240336
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round130_run5_note2237_window.png" 3832843
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round131_run6_effect_band_association_review.json" 2341
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round131_run6_full_rebuild.json" 30727893
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round131_run6_note1080_window.png" 3164129
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round131_run6_note1813_window.png" 4367129
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round132_run7_full_rebuild.json" 30782579
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round132_run7_judgment_band_association_review.json" 2922
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round132_run7_note1173_window.png" 3276799
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round132_run7_note1344_window.png" 3257631
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round132_run7_note1937_window.png" 3408065
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round132_run7_note2855_window.png" 3329211
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round133_judgment_band_guard_validation.json" 3398
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round133_run7_guard_rebuild.json" 30781310
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round133_run7_note1173_candidate_contact.png" 3272430
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round134_run8_frozen_holdout_audit.json" 1507
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round134_run8_frozen_holdout_rebuild.json" 21527532
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round135_formal_delivery_integrity_audit.json" 6727
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round136_run4_native_f1820.png" 1281291
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round136_run4_native_f1823.png" 1310318
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round136_run4_native_f1824.png" 1243688
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round136_run4_native_f1826.png" 1271432
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round136_run4_native_f1833.png" 1233584
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round136_run4_native_f1834.png" 1235690
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round136_run4_native_f1835.png" 1237184
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round136_run4_note1464_candidate_contact.png" 2502485
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round136_run4_note1464_native_compare.png" 1675252
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round136_run4_note1464_native_review.json" 3567
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round137_run1_native_f1772.png" 1266545
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round137_run1_native_f1774.png" 1267870
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round137_run1_native_f1776.png" 1169215
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round137_run1_native_f1778.png" 1185450
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round137_run1_note1494_candidate_contact.png" 2894283
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round137_run1_note1494_native_contact.png" 2469164
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round137_run1_note1494_native_grid.png" 2803094
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round137_run1_note1494_native_review.json" 3053
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round137_run1_note1494_source_frames.png" 2543254
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round138_run1_native_f2924.png" 1182883
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round138_run1_native_f2933.png" 1168678
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round138_run1_native_f2933_left_zoom.png" 237472
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round138_run1_native_f2934.png" 1168402
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round138_run1_native_f2934_left_zoom.png" 204328
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round138_run1_native_f2935.png" 1189460
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round138_run1_native_f2935_left_zoom.png" 297383
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round138_run1_note2767_candidate_contact.png" 2605383
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round138_run1_note2767_contact.png" 5989695
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round138_run1_note2767_native_review.json" 2904
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round139_run5_full_rebuild.json" 24948186
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round139_run5_judgment_band_gate_validation.json" 5044
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round140_run6_full_rebuild.json" 30732740
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round140_run6_judgment_band_gate_validation.json" 8124
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round141_run3_note368_bounds_grid.png" 236939
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round141_run3_note368_candidate_contact.png" 562898
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round141_run3_note368_native_review.json" 2803
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round141_run3_note368_tail_native_crops.png" 363706
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round141_run3_note368_tail_native_source.png" 1646352
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round142_run2_note129_identity_review.json" 2667
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round142_run2_note129_native_timeline.png" 1844627
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round143_run2_note638_after_effect_contact.png" 1575908
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round143_run2_note638_post_overlap_contact.png" 1721473
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round143_run2_note638_post_overlap_review.json" 3001
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round144_run5_sample_review.json" 3522
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round144_run5_unreviewed_sample_contact.png" 3137743
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round145_run6_holds_tail_source_geometry.png" 4666782
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round145_run6_tail_attribution_review.json" 8344
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round145_run6_tail_native_compare.png" 4294678
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round146_run7_note2784_source_review.json" 11179
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round147_run7_note1955_candidate_source_review.png" 2031563
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round147_run7_note1955_source_review.json" 6434
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round148_final_delivery_index_before_run1_revision21.json" 114809
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round148_run1_revision21_acceptance.json" 5342
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round148_run1_revision21_target_windows.png" 4898311
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round149_final_delivery_index_before_run3_revision16.json" 116129
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round149_run3_revision16_acceptance.json" 4012
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round149_run3_revision16_note368_windows.png" 3092313
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round150_final_delivery_index_before_review.json" 117513
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round150_run7_note2784_post_effect_review.json" 3152
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round150_run7_note2784_post_effect_source_frames.png" 4254596
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round151_final_delivery_index_before_run4_revision13.json" 118828
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round151_run4_note1464_revision13_acceptance.json" 4751
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round151_run4_note1464_revision13_window.png" 3098881
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round152_final_delivery_index_before_review.json" 120400
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round152_run4_note1071_endpoint_extended.png" 4151280
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round152_run4_note1071_tail_endpoint_review.json" 3649
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round152_run4_note1071_tail_zoom.png" 1986369
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round153_final_delivery_index_before_run7_revision11.json" 121693
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round153_run7_frame1041_full.png" 1437960
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round153_run7_frame1042_full.png" 1434179
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round153_run7_frame1043_full.png" 1430890
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round153_run7_note1173_native_band_review.png" 899477
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round153_run7_note1173_revision10_window.png" 532574
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round153_run7_note1173_source_neighborhood.png" 855311
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round153_run7_note1266_tap_native_measurement.png" 356065
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round153_run7_revision11_note1173_note1266_acceptance.json" 5092
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round153_run7_revision11_note1173_note1266_window.png" 463102
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round154_run5_frame898_full.png" 1248006
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round154_run5_frame905_full.png" 1194226
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round154_run5_frame915_full.png" 1147216
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round154_run5_frame924_full.png" 1144348
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round154_run5_note641_native_ribbon_898_905.png" 2254305
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round154_run5_note641_note666_tail_identity_review.json" 4046
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round155_run5_geometry_judgment_approach_920_931.png" 343599
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round155_run5_judgment_approach_920_931.png" 2967721
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round155_run5_note641_judgment_boundary_review.json" 2923
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round156_run1_note433_note505_post_overlap_review.json" 3581
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round156_run1_overlap_native_1.png" 1066329
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round156_run1_overlap_native_2.png" 1082438
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round156_run1_overlap_reemergence_geometry_750_778.png" 168187
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round156_run1_overlap_reemergence_source_750_778.png" 2413254
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round157_run6_judgment_green_head_geometry_500_511.png" 184913
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round157_run6_judgment_green_head_source_500_511.png" 4286457
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round157_run6_note398_postflash_geometry_496_524.png" 216813
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round157_run6_note398_postflash_green_candidate_review.json" 4612
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round157_run6_note398_postflash_source_496_524.png" 2946985
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round157_run6_postflash_native_1.png" 1218910
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round157_run6_postflash_native_2.png" 1104361
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round157_run6_postflash_native_3.png" 1180625
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round158_final_delivery_index_before_run6_revision10.json" 238486
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round158_run6_hold_continuity_493_504_geometry.png" 127599
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round158_run6_hold_continuity_493_504_revision10_geometry.png" 294271
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round158_run6_hold_continuity_493_504_source.png" 2424081
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round158_run6_hold_endpoint_grid_499_504.png" 3298727
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round158_run6_hold_endpoints_zoom_499_504.png" 3162367
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round158_run6_hold_measured_timeline_499_504.png" 3111740
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round158_run6_native_boundary_1.png" 1212782
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round158_run6_native_boundary_2.png" 1218910
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round158_run6_native_boundary_3.png" 1226757
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round158_run6_native_boundary_4.png" 1104361
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round158_run6_native_boundary_5.png" 1142964
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round158_run6_native_boundary_6.png" 1149205
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round158_run6_note398_before_revision10.json" 56907
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round158_run6_note398_revision10_acceptance.json" 4811
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round158_run6_note398_source_geometry_window_493_504.png" 1338203
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round159_run6_note398_frame505_506_detail.png" 721403
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round159_run6_note398_release_boundary_grid_504_507.png" 3233297
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round159_run6_note398_release_boundary_review.json" 2531
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round160_run5_note641_postimpact_review.json" 2583
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round160_run5_note641_postimpact_source_932_960.png" 2480809
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round161_final_delivery_index_before_run8_revision05.json" 127582
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round161_run8_hold_frame270_approach_zoom.png" 1287270
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round161_run8_hold_frame270_early_timeline.png" 2195758
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round161_run8_hold_frame270_early_zoom.png" 2258776
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round161_run8_hold_frame270_late_timeline.png" 2494156
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round161_run8_hold_frame270_late_zoom.png" 2779746
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round161_run8_hold_frame270_release_zoom.png" 2746958
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round161_run8_hold_release_boundary_312_320.png" 583830
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round161_run8_hold_release_coordinate_grid_311_314.png" 334813
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round161_run8_hold_tail_anchors_234_313.png" 2655908
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round161_run8_hold_transition_frames232_240.png" 854456
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round161_run8_note7_before_revision05.json" 63176
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round161_run8_note7_revision05_acceptance.json" 6594
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round161_run8_revision05_note7_entry_comparison.png" 1030177
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round161_run8_revision05_note7_release_comparison.png" 1058508
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round161_run8_scene_before_revision05.json" 16598696
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round162_run8_note7_effect_clear_frames321_328.png" 448948
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round162_run8_note7_postflash_release_review.json" 2801
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round162_run8_note7_postflash_source_314_348.png" 1181433
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round163_run1_note2767_effect_clear_2935_2948.png" 1280284
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round163_run1_note2767_posthit_release_review.json" 2621
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round163_run1_note2767_posthit_source_2935_2970.png" 1263183
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round164_run3_note368_posthit_identity_review.json" 2188
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round164_run3_note368_posthit_source_784_820.png" 2702979
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round165_run7_note2855_postflash_identity_review.json" 2048
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round165_run7_note2855_postflash_source_2220_2260.png" 2869259
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round166_run2_note638_post_overlap_identity_review.json" 2281
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round166_run2_note638_post_overlap_source_863_900.png" 2816532
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round167_process_error.txt" 439
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round167_process_stdout.log" 1564
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round167_run4_native_segment_pipeline_audit.json" 7201
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round167_run4_segment_build\comparison.mp4" 7842974
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round167_run4_segment_build\geometry.json" 9590
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round167_run4_segment_build\geometry.mp4" 1170218
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round167_run4_segment_build\run_manifest.json" 3411
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round167_run4_segment_build\scene.json" 831942
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round167_run4_segment_index_1000_1119.csv" 11309
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round167_run4_segment_source_1000_1119.mp4" 6916689
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round167_run4_segment_source_geometry_review.png" 1329432
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round167_run4_segment_source_tap_1001_geometry_negative.png" 584432
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round168_final_delivery_index_before_run4_revision14.json" 141830
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round168_run4_cyan_face_999_1000.png" 1630096
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round168_run4_cyan_face_bounds_1001_1009.png" 2052679
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round168_run4_cyan_manual_bounds_proposal.png" 2524100
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round168_run4_cyan_plate_source_1000_1016.png" 2503359
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round168_run4_revision14_before_frame999_fix.json" 20038299
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round168_run4_revision14_cyan_tap_review.png" 1876274
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round168_run4_revision14_cyan_tap_review_after_frame999.png" 1875656
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round168_run4_revision14_full_validation.json" 1096
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round168_run4_revision14_note581_note662_acceptance.json" 7342
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round169_run4_note1071_endpoint_source_crop.png" 2250894
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round169_run4_note1071_postimpact_source_1484_1540.png" 4034177
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round169_run4_note1071_tail_endpoint_review.json" 2347
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round170_run6_notes3104_3100_source_after_endpoint.png" 2422775
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round170_run6_notes3104_3100_tail_review.json" 2416
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_generic_clip_native_cyan_fallback_validation.json" 9629
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_cyan_tap_source_geometry_review.png" 1138526
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_frame1008_candidate_vs_source_review.png" 241432
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_segment_build\comparison.mp4" 7851961
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_segment_build\geometry.json" 9595
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_segment_build\geometry.mp4" 1177661
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_segment_build\run_manifest.json" 3641
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_segment_build\scene.json" 830135
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_segment_build_final_candidate\comparison.mp4" 7851961
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_segment_build_final_candidate\geometry.json" 9611
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_segment_build_final_candidate\geometry.mp4" 1177661
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_segment_build_final_candidate\run_manifest.json" 3787
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_segment_build_final_candidate\scene.json" 824671
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_segment_build_final_candidate_r2\comparison.mp4" 7851961
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_segment_build_final_candidate_r2\geometry.json" 9604
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_segment_build_final_candidate_r2\geometry.mp4" 1177661
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_segment_build_final_candidate_r2\run_manifest.json" 3776
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_segment_build_final_candidate_r2\scene.json" 824660
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_segment_build_iter2\comparison.mp4" 7851961
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_segment_build_iter2\geometry.json" 9601
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_segment_build_iter2\geometry.mp4" 1177661
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_segment_build_iter2\run_manifest.json" 3659
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_segment_build_iter2\scene.json" 824681
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_segment_build_iter3\comparison.mp4" 7851961
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_segment_build_iter3\geometry.json" 9601
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_segment_build_iter3\geometry.mp4" 1177661
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_segment_build_iter3\run_manifest.json" 3659
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_segment_build_iter3\scene.json" 824121
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_segment_build_iter4\comparison.mp4" 7852954
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_segment_build_iter4\geometry.json" 9601
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_segment_build_iter4\geometry.mp4" 1179477
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_segment_build_iter4\run_manifest.json" 3757
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run4_segment_build_iter4\scene.json" 826681
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run8_holdout_build\comparison.mp4" 2542057
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run8_holdout_build\geometry.json" 7741
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run8_holdout_build\geometry.mp4" 381099
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run8_holdout_build\run_manifest.json" 3703
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run8_holdout_build\scene.json" 323616
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run8_holdout_build_r2\comparison.mp4" 2542057
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run8_holdout_build_r2\geometry.json" 7755
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run8_holdout_build_r2\geometry.mp4" 381099
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run8_holdout_build_r2\run_manifest.json" 3734
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run8_holdout_build_r2\scene.json" 323647
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run8_holdout_cyan_source_geometry_review.png" 2153509
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run8_holdout_index_360_399.csv" 3849
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run8_holdout_note100_source_geometry.png" 2826672
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round171_run8_holdout_source_360_399.mp4" 2214026
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run2_frozen_holdout_build\comparison.mp4" 2748438
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run2_frozen_holdout_build\geometry.json" 7789
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run2_frozen_holdout_build\geometry.mp4" 354976
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run2_frozen_holdout_build\run_manifest.json" 3745
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run2_frozen_holdout_build\scene.json" 279104
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run2_frozen_holdout_contact.png" 1504638
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run2_frozen_holdout_frame3039.png" 1378613
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run2_frozen_holdout_last4.png" 1640292
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run2_frozen_holdout_source_3000_3039.csv" 3886
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run2_frozen_holdout_source_3000_3039.mp4" 2457261
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run2_frozen_review_window.json" 6500
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run4_segment_build_r3\comparison.mp4" 7851961
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run4_segment_build_r3\geometry.json" 9598
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run4_segment_build_r3\geometry.mp4" 1177661
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run4_segment_build_r3\run_manifest.json" 3748
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run4_segment_build_r3\scene.json" 824632
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run4_segment_build_r4\comparison.mp4" 7851961
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run4_segment_build_r4\geometry.json" 9598
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run4_segment_build_r4\geometry.mp4" 1177661
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run4_segment_build_r4\run_manifest.json" 3748
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run4_segment_build_r4\scene.json" 824632
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run8_edge_pair_face_reconstruction.json" 8588
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run8_formal_edge_candidates_source_overlay.png" 1968021
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run8_holdout_build_r3\comparison.mp4" 2545114
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run8_holdout_build_r3\geometry.json" 7749
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run8_holdout_build_r3\geometry.mp4" 384316
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run8_holdout_build_r3\run_manifest.json" 3722
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run8_holdout_build_r3\scene.json" 326397
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run8_holdout_build_r4\comparison.mp4" 2560349
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run8_holdout_build_r4\geometry.json" 7749
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run8_holdout_build_r4\geometry.mp4" 400711
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run8_holdout_build_r4\run_manifest.json" 3722
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run8_holdout_build_r4\scene.json" 329860
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run8_lower_full_face_bounds_preview.png" 1344316
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run8_manual_full_face_bounds_preview.png" 2189842
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run8_native_frames_370_382_lane0.png" 4043762
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run8_native_zoom_373_379.png" 3812037
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run8_revision06_source_geometry_window.png" 1813419
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run8_revision07_source_geometry_window.png" 2026122
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round172_run8_source_geometry_effect_gap_review.png" 1919611
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round173_delivery_index_link_consistency.json" 3869
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round174_full_scene_renderer_replay_audit.json" 14273
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round175_run7_note3081_cross_lane_identity_review.json" 7831
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round175_run7_note3081_lane2_vs_lane4_contact.png" 2156152
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round175_run7_note3081_source_lane_overlay.png" 722022
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round176_run7_note3081_note3188_identity_review.json" 6515
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round176_run7_note3081_note3188_overlap_detail.png" 3267536
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round177_run7_note4166_cross_track_association_review.json" 9486
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round177_run7_note4166_horizon_detail.png" 1291275
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round177_run7_note4166_source_crop_contact.png" 1703572
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round177_run7_note4166_switch_frame_detail.png" 898208
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round178_run7_refined_geometry_jump_windows.png" 386585
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round178_run7_same_jump_patterns.png" 1116639
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round178_run7_tracker_discontinuity_refinement.json" 8177
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round179_run6_note398_hold_tail_release_review.json" 6311
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round179_run6_note398_source_498_520.png" 3614035
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round179_run6_note398_source_endpoint_overlay.png" 2395369
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round17_run5_direction_guard_contact.png" 2879240
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round17_run5_frame900_source.png" 1179877
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round17_run5_hold_tail_direction.json" 2393
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round180_run8_note7_release_tail_review.json" 3578
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round180_run8_note7_source_310_324.png" 4387145
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round181_run4_note1071_endpoint_overlay.png" 2485872
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round181_run4_note1071_pre_effect_tail_source_review.json" 2074
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round181_run4_note1071_source_1458_1465.png" 2469597
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round181_run4_note1071_source_post_effect.png" 4194301
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round182_run7_note4166_covisible_tracker_switch_review.json" 3058
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round182_run7_note4166_source_3096_3120.png" 5680183
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round183_run7_jump_3094_4273_source.png" 4371070
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round183_run7_jump_split_source_review.json" 3206
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round184_run2_note1689_note1709_same_lane_double_tap_review.json" 3386
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round184_run2_note1689_note1709_source_1625_1645.png" 4849107
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round184_run2_note1689_note1709_source_zoom.png" 757090
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round185_run4_note1331_frame1707_source_measurement.png" 543840
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round185_run4_note1331_frame1707_unannotated_zoom.png" 188510
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round185_run4_note1331_measure_frames_1707_1710.png" 842598
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round185_run4_note1331_neighbor_bounds.png" 821607
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round185_run4_note1331_note1410_source_1698_1714.png" 4092093
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round185_run4_note1331_note1410_source_bounds_review.json" 5150
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round185_run4_note1331_note1410_source_zoom.png" 1092166
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round185_run4_note1331_patch_source_geometry_check.png" 975236
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round185_run4_note1331_source_frames_1707_1712.png" 988011
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round186_run4_note1410_duplicate_suppression_review.json" 7224
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round186_run4_note1410_frame1704_boxes.png" 193508
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round186_run4_note1410_geometry_parent_new_check.png" 575484
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round186_run4_note1410_source_1704_1723.png" 1800552
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round186_run4_note1410_source_1704_1734.png" 3742911
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round186_run4_note1410_source_detail_1708_1719.png" 1623339
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round187_run6_notes3104_3100_source_2684_2715.png" 3504542
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round187_run6_notes3104_3100_source_scene_overlay.png" 1613197
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round187_run6_notes3104_3100_source_tail_zoom.png" 3132790
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round187_run6_notes3104_3100_source_zoom_2695_2711.png" 3193558
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round187_run6_notes3104_3100_tail_identity_review.json" 3992
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round188_run8_untuned_window_2100_2159_build\comparison.mp4" 4454799
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round188_run8_untuned_window_2100_2159_build\geometry.json" 9571
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round188_run8_untuned_window_2100_2159_build\geometry.mp4" 406607
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round188_run8_untuned_window_2100_2159_build\run_manifest.json" 3757
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round188_run8_untuned_window_2100_2159_build\scene.json" 429373
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round188_run8_untuned_window_2100_2159_index.csv" 5686
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round188_run8_untuned_window_2100_2159_source.mp4" 4148852
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round188_run8_untuned_window_evaluation.json" 5845
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round188_run8_untuned_window_source_contact.png" 4364112
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round188_run8_untuned_window_source_geometry_contact.png" 1425937
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round188_run8_untuned_window_source_geometry_keyframes.png" 1389520
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round189_run5_training_window_890_930_build\comparison.mp4" 2721967
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round189_run5_training_window_890_930_build\geometry.json" 7879
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round189_run5_training_window_890_930_build\geometry.mp4" 350251
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round189_run5_training_window_890_930_build\run_manifest.json" 3752
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round189_run5_training_window_890_930_build\scene.json" 362084
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round189_run5_training_window_890_930_index.csv" 3919
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round189_run5_training_window_890_930_source.mp4" 2443319
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round189_run5_training_window_repeatability.json" 4333
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round189_run5_training_window_source_geometry_contact.png" 1740586
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round18_component_anchor_training_and_frozen_holdout.json" 17651
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round18_run1_component_anchored_trial_scene.json" 18422255
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round18_run1_component_anchored_windowA.png" 3781946
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round18_run1_component_anchored_windowB.png" 4637328
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round18_run1_stationary_hold_candidate_alignment.json" 1699
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round18_run1_stationary_hold_candidate_alignment_review.png" 3074141
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round18_run8_frozen_holdout_frame_context.png" 5049637
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round18_run8_frozen_holdout_miss.json" 3580
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round190_run5_note641_note666_source_overlay_912_924.png" 2203312
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round190_run5_note641_note666_tail_window_review.json" 3732
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round191_run2_candidate_face_geometry_review.png" 1696167
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round191_run2_note1689_note1709_native_crop.png" 166173
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round191_run2_note1689_note1709_source_bounds_review.json" 28004
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round192_run1_note709_parallel_hold_native_detail.png" 8517558
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round192_run1_note709_parallel_hold_native_review.png" 2462790
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round192_run1_note709_parallel_hold_review.json" 11342
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round192_run1_note709_right_path_detail.png" 1513358
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round193_run4_note1897_note1910_overlap_review.png" 1463067
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round193_run4_note1910_candidate_review.png" 1192521
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round193_run4_note1910_continuation_review.png" 611749
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round193_run4_note1910_source_continuation.json" 12694
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round194_run7_note4444_alternating_hold_candidate.png" 2145433
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round194_run7_note4444_full_window_review.png" 2119082
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round194_run7_note4444_geometry_before_after.png" 258832
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round194_run7_note4444_review.json" 3412
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round195_run3_note443_tail_jump_review.png" 2241455
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round195_run3_note443_tail_review.json" 6567
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round196_run6_note3535_revision11_review.png" 682340
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round196_run6_note3535_tail_switch_review.json" 9966
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round196_run6_note3535_tail_switch_review.png" 1305851
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round197_run1_note1508_tail_review.json" 5348
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round197_run1_note1508_tail_transition.png" 1505921
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round198_run2_note965_tail_review.json" 5395
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round198_run2_note965_tail_switch_review.png" 1463446
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round199_run3_note1959_tail_jump_review.png" 1483657
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round199_run3_note1959_tail_review.json" 5283
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round19_observed_head_short_tail_failure.json" 1845
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round19_run1_observed_head_short_tail_trial_scene.json" 18449654
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round19_run1_observed_head_windowA.png" 2421246
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round19_run1_observed_head_windowB.png" 3288735
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round200_run4_note2308_full_tail_window_review.png" 3201104
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round200_run4_note2308_lane_tail_review.json" 22044
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round200_run4_note2308_postflash_tail_review.png" 2645662
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round200_run4_note2308_revision19_review.png" 3401720
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round201_run6_notes3100_3104_tail_review.json" 7473
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round201_run6_notes3100_3104_tail_switch_source_geometry.png" 3830823
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round201_run6_tail_candidates_native_2704_2710.png" 3883422
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round202_run3_note443_extended_tail_review.json" 5770
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round202_run3_note443_extended_tail_source_geometry.png" 4713734
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round203_run5_note619_source_geometry_895_904.png" 3717714
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round203_run5_note619_source_review.json" 2992
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round204_run4_note1071_post_effect_1460_1475_source_geometry.png" 4380697
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round204_run4_note1071_post_effect_review.json" 2380
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round20_run1_shared_component_ambiguity.json" 4617
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round21_run1_cut_mask_ambiguity.json" 3137
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round21_run1_cut_mask_frame961.png" 1362176
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round22_run1_cut_component_no_safe_anchor.json" 3063
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round23_run1_f955_970_source_contact.png" 5734948
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round23_run1_source_frame970.png" 1247051
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round23_run1_source_identity_unresolved.json" 3338
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round24_cross_run_hold_tail_direction.json" 3352
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round24_run2_revision04_frame1049.png" 1399710
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round24_run2_revision04_frame3147.png" 1316072
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round25_run3_direction_guard_audit.json" 2337
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round25_run3_revision04_frame1839.png" 1407354
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round26_run4_direction_guard_audit.json" 2719
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round26_run4_revision04_frame1524.png" 1537979
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round27_run6_direction_guard_audit.json" 2388
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round27_run6_revision04_frame1090.png" 1511723
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round28_run7_direction_guard_audit.json" 2391
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round28_run7_revision04_frame1039.png" 1581980
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round29_run8_frozen_holdout_miss.json" 2450
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round29_run8_revision04_frame270.png" 1250873
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round30_cross_run_lane_drift.json" 9576
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round30_run1_lane_drift_frame1380.png" 1181045
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round31_run1_head_only_filter_audit.json" 2759
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round31_run1_head_only_review.png" 1611781
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round32_run2_head_only_audit.json" 2033
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round32_run2_head_only_review.png" 912476
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round33_run3_head_only_audit.json" 1759
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round33_run3_head_only_review.png" 951210
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round34_run4_head_only_visible_tap_miss.json" 2395
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round34_run4_head_only_visible_tap_miss.png" 946933
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round35_run5_head_only_tap_gap.json" 2041
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round35_run5_head_only_tap_gap.png" 895486
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round36_run6_head_only_visible_tap_miss.json" 1604
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round36_run6_head_only_visible_tap_miss.png" 1039041
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round37_run7_head_only_visible_tap_miss.json" 1532
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round37_run7_head_only_visible_tap_miss.png" 1021460
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round38_run4_unresolved_cyan_tap.json" 5641
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round38_run4_unresolved_cyan_tap.png" 434936
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round39_run4_cyan_tap_ambiguous.json" 9117
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round39_run4_cyan_tap_ambiguous_source_contact.jpg" 100006
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round40_run7_recovery_tap_gap.json" 10836
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round41_run7_recovery_link_anchor_gate.json" 2479
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round42_run7_link_1039_contact.jpg" 428132
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round42_run7_link_1085_contact.jpg" 451935
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round42_run7_link_1093_contact.jpg" 480992
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round42_run7_link_1588_contact.jpg" 457608
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round42_run7_link_2207_contact.jpg" 440581
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round42_run7_recovery_link_review.json" 19379
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round43_run7_selected_recovery.json" 5836
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round43_run7_selected_recovery_review.jpg" 466875
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round44_run4_singleton_negative.json" 8537
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round45_run8_frozen_holdout.json" 2052
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round46_run6_frame1100_unresolved.json" 3347
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round47_run6_recovery_trace.json" 13245
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round47_run6_source_frames1093_1107.jpg" 530503
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round48_run6_line_overlap_contact.jpg" 858611
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round48_run6_line_overlap_diagnostic.json" 23310
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round49_recovery_width_gate.json" 4590
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round49_run7_positive_control_contact.jpg" 795144
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round50_run1_frame970_hold_observation.json" 4882
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round50_run1_frame970_hold_observation_contact.jpg" 1160451
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round51_run1_right_hold_candidate.json" 4402
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round51_run1_right_hold_contact.jpg" 834263
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round52_run5_frame898_902_contact.jpg" 806752
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round52_run5_frame900_hold_endpoint_review.json" 7941
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round53_run4_cyan_singleton_review.json" 1976
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round53_run4_frame1002_1010_contact.jpg" 1089751
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round54_run7_2206_2211_identity_review.jpg" 2155024
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round54_run7_2207_identity_ambiguity.json" 3995
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round55_generic_clip_pipeline.json" 3607
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round56_all_run_scene_media_structure.json" 5764
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round57_run1_frame1041_1049_hold_identity.jpg" 1646278
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round57_run1_frame1045_hold_identity.json" 9786
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round58_all_run_keyframe_timestamps.json" 2538
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round59_run1_left_hold_candidate.json" 3518
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round59_run1_left_hold_contact.jpg" 1456806
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round60_latest_all_run_validation.json" 2792
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round61_run1_component_continuity.json" 3885
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round61_run1_component_continuity_contact.jpg" 787621
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round62_latest_all_run_validation.json" 5128
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round63_run1_continuity_threshold.json" 2134
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round63_run1_continuity_threshold_contact.jpg" 1172482
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round64_latest_all_run_validation.json" 4398
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round65_run4_cyan_context_contact.jpg" 1255664
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round65_run4_cyan_temporal_motion.json" 1904
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round66_run1_candidate_provenance_audit.json" 999
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round67_run1_component_masks.jpg" 824144
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round67_run1_component_separation_review.json" 4460
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round68_run5_hold_context_contact.jpg" 507552
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round68_run5_hold_endpoint_review.json" 1390
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round69_run7_candidate_trial_revision06\comparison.mp4" 325933728
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round69_run7_candidate_trial_revision06\geometry.mp4" 52148869
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round69_run7_candidate_trial_revision06\run_manifest.json" 3599
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round69_run7_candidate_trial_revision06\scene.json" 24142716
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round69_run7_cyan_motion_association.json" 7585
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round70_run7_revision06_contact.jpg" 475672
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round70_run7_revision06_trial_rejected.json" 2103
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round71_run7_post_hit_effect_truncation.json" 2685
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round71_run7_revision07_contact.jpg" 451143
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round72_latest_all_run_validation.json" 5525
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round73_run1_wide_tap_candidate_review.json" 9115
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round73_run1_wide_tap_context_contact.jpg" 394789
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round74_run3_note204_association_contact.jpg" 432112
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round74_run3_note204_association_review.json" 12683
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round75_run1_note1540_width_contact.jpg" 374382
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round75_run1_note1540_width_review.json" 4933
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round76_run6_note438_duplicate_effect_contact.jpg" 487062
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round76_run6_note438_duplicate_effect_review.json" 11630
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round77_run4_note166_beam_fragment_contact.jpg" 388647
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round77_run4_note166_beam_fragment_review.json" 21444
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round78_run2_note274_lane_association_contact.jpg" 337048
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round78_run2_note274_lane_association_review.json" 24600
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round79_run2_blue_plate_source.jpg" 179694
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round79_run2_yellow_plate_context.jpg" 310080
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round79_run2_yellow_plate_reconstruction.json" 34808
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round79_run2_yellow_plate_source_detail.jpg" 282355
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round80_latest_all_run_validation.json" 6664
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round81_run5_hold_ending_contact.jpg" 659816
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round81_run5_hold_endpoint_review.json" 1712
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round82_run6_note475_endpoint_review.json" 1580
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round82_run6_note475_source_contact.jpg" 666567
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round83_run1_hold970_review.json" 2370
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round83_run1_hold970_source_context.jpg" 612063
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round83_run1_hold970_source_geometry_contact.jpg" 317241
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round84_run1_left_hold_reconstruction.json" 3203
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round84_run1_left_hold_reconstruction_contact.jpg" 424024
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round84_run1_left_hold_source_contact_1.jpg" 330170
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round84_run1_left_hold_source_contact_2.jpg" 326406
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round84_run1_left_hold_source_contact_3.jpg" 331384
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round84_run1_left_hold_source_contact_4.jpg" 273242
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round85_run1_hold_tail_contact.jpg" 419713
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round85_run1_hold_tail_extension.json" 2071
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round85_run1_hold_tail_source_contact.jpg" 512398
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round86_run4_note166_comparison_review.jpg" 780257
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round86_run4_note166_source_review.jpg" 314005
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round86_run4_note166_unbracketed_occlusion_metadata.json" 2620
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round87_run6_note475_tail_ambiguity.json" 1605
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round87_run6_note475_tail_ambiguity_contact.jpg" 463578
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round88_run3_note204_comparison_review.jpg" 951678
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round88_run3_note204_cross_lane_association.json" 22424
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round88_run3_note204_source_contact.jpg" 933687
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round89_run8_frozen_holdout_recheck.json" 1460
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round90_run3_tap_comparison_contact.jpg" 1220974
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round90_run3_tap_reconstruction.json" 7011
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round90_run3_tap_source_contact.jpg" 1253191
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round91_run3_comparison_detail.jpg" 1761853
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round91_run3_comparison_timeline.jpg" 711794
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round91_run3_scene_window_review.json" 3814
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round91_run3_source_context.jpg" 1317631
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round91_run3_source_timeline.jpg" 1417726
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round92_run1_hold_review.json" 2490
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round92_run1_hold_review_contact.jpg" 2453353
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round93_run5_note641_comparison_contact.jpg" 1249810
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round93_run5_note641_source_head_measurement_contact.jpg" 381780
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round93_run5_note641_visible_head_reconstruction.json" 4910
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round94_run5_note666_review.json" 2657
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round94_run5_note666_selected_source_frames.png" 819064
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round94_run5_note666_source_detail_frames.png" 2243583
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round94_run5_note666_source_geometry_contact.png" 743850
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round95_run5_note666_frames945_964_source.png" 1239553
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round95_run5_note666_frames965_984_source.png" 1245369
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round95_run5_note666_postflash_review.json" 2332
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round95_run5_note666_source_scene_frames950_982.png" 1134791
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round96_run7_note2855_endpoint_review.json" 2041
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round96_run7_note2855_source_frames2202_2220.png" 1328695
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round96_run7_note2855_source_scene_contact.png" 889968
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round97_run6_note475_duplicate_suppression.json" 24921
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round97_run6_note475_source_native_crops.png" 3407166
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round97_run6_note475_trial_source_geometry_contact.png" 1462418
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round98_run2_yellow_lane_guide_review.json" 3669
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round99_run4_cyan_frames1002_1012.png" 1171105
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round99_run4_cyan_judgement_zoom1003_1010.png" 796471
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round99_run4_cyan_singleton_review.json" 2167
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round_03_hold_component_role_ambiguity.json" 4540
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round_04_tap_shape_and_source_size_lost.json" 8240
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round_08_hold_component_endpoint_probe.json" 7516
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round_14_scene_build_summary_run_id_mismatch.json" 1319
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round_15_probe_setup_missing_cleaned_scratch.json" 1194
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round_16_run5_inferred_occlusion_frame_300.png" 1290288
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round_16_run5_inferred_occlusion_renderer_omission.json" 9309
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\round_16_run5_source_temporal_context_frames_270_330.jpg" 530095
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\run7_note2784_frame2142_full.png" 465754
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\failures\run7_note2784_native_crop.png" 1607178
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\geometries\run_20261106T164049_800126Z.json" 9195
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\geometries\run_20261106T164704_064294Z.json" 9221
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\geometries\run_20261106T164959_579760Z.json" 9246
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\geometries\run_20261106T170057_932173Z.json" 9217
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\geometries\run_20261106T170845_579909Z.json" 9233
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\geometries\run_20261106T171405_612600Z.json" 9246
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\geometries\run_20261106T172037_662313Z.json" 9239
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\geometries\run_20261106T172404_427324Z.json" 9240
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_100.json" 151111
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_101.json" 149293
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_102.json" 147551
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_103.json" 149202
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_104.json" 152738
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_105.json" 156070
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_106.json" 152415
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_107.json" 155877
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_108.json" 156332
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_109.json" 156503
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_110.json" 163729
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_111.json" 160301
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_112.json" 116527
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_113.json" 114681
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_114.json" 115951
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_115.json" 116797
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_116.json" 117788
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_117.json" 123318
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_118.json" 120353
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_119.json" 138555
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_120.json" 5974
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_121.json" 23720
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_122.json" 8791
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_123.json" 5786
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_124.json" 6769
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_125.json" 16154
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_126.json" 22275
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_127.json" 23089
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_128.json" 26990
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_129.json" 29305
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_130.json" 30253
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_131.json" 30923
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_132.json" 32029
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_133.json" 33510
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_134.json" 34063
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_135.json" 34192
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_136.json" 36510
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_137.json" 38591
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_138.json" 12660
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_139.json" 12692
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_140.json" 12659
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_141.json" 15251
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_142.json" 13173
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_143.json" 13954
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_144.json" 11961
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_145.json" 14152
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_146.json" 16577
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_147.json" 13773
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_148.json" 15173
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_149.json" 13868
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_150.json" 12997
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_151.json" 15094
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_152.json" 12832
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_153.json" 15867
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_154.json" 19854
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_155.json" 20509
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_156.json" 21634
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_157.json" 23216
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_158.json" 23723
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_159.json" 5374
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_160.json" 5717
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_161.json" 17949
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_162.json" 14357
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_163.json" 12234
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_164.json" 12045
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_165.json" 11997
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_166.json" 12010
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_167.json" 14002
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_168.json" 16393
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_169.json" 13776
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_17.json" 11207
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_170.json" 13771
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_171.json" 17382
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_172.json" 22839
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_173.json" 22598
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_174.json" 29863
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_175.json" 26454
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_176.json" 26847
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_177.json" 3711
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_178.json" 8996
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_179.json" 4128
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_18.json" 37180
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_180.json" 3725
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_181.json" 14346
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_182.json" 13733
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_183.json" 13621
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_184.json" 15909
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_185.json" 16241
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_186.json" 4917
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_187.json" 5013
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_188.json" 4954
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_189.json" 5166
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_19.json" 28708
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_190.json" 3981
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_191.json" 6132
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_192.json" 5951
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_193.json" 6429
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_194.json" 7449
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_195.json" 6793
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_196.json" 7773
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_197.json" 7515
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_198.json" 7511
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_199.json" 8152
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_20.json" 20629
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_200.json" 14734
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_201.json" 15600
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_202.json" 16034
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_203.json" 16530
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_204.json" 17126
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_21.json" 19268
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_22.json" 20454
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_23.json" 20596
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_24.json" 22245
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_25.json" 22770
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_26.json" 24076
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_27.json" 25382
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_28.json" 26688
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_29.json" 27988
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_30.json" 27559
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_31.json" 54723
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_32.json" 54452
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_33.json" 55410
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_34.json" 55405
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_35.json" 55293
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_36.json" 55327
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_37.json" 55344
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_38.json" 32837
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_39.json" 33565
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_40.json" 33194
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_41.json" 33204
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_42.json" 36139
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_43.json" 34403
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_44.json" 32553
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_45.json" 33329
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_46.json" 33311
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_47.json" 34055
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_48.json" 35911
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_49.json" 37673
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_50.json" 37936
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_51.json" 40064
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_52.json" 37434
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_53.json" 37528
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_54.json" 38029
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_55.json" 40462
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_56.json" 37774
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_57.json" 38792
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_58.json" 38320
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_59.json" 41259
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_60.json" 39580
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_61.json" 43529
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_62.json" 40838
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_63.json" 45096
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_64.json" 42114
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_65.json" 43205
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_66.json" 42959
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_67.json" 44012
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_68.json" 44441
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_69.json" 44495
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_70.json" 45854
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_71.json" 46435
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_72.json" 46253
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_73.json" 94449
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_74.json" 94833
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_75.json" 96951
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_76.json" 98924
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_77.json" 100866
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_78.json" 101301
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_79.json" 105975
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_80.json" 104818
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_81.json" 107505
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_82.json" 108796
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_83.json" 111957
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_84.json" 124630
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_85.json" 122289
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_86.json" 159641
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_87.json" 145273
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_88.json" 156988
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_89.json" 134383
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_90.json" 187480
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_91.json" 141126
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_92.json" 137928
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_93.json" 144618
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_94.json" 143894
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_95.json" 142817
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_96.json" 142951
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_97.json" 146549
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_98.json" 143678
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\cleanup_manifest_round_99.json" 145142
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\generalization_probe_640x360.json" 1965
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\generalization_probe_run2_derived_segment.json" 4431
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\indexed_clip_probe_run2_derived_segment.json" 1527
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round161_run8_note7_hsv_tail_candidate_observations.json" 21215
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round39_run4_queue_detail_run_manifest.json" 2503
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round39_run4_queue_detail_scene.json" 18577744
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round40_run7_baseline_run_manifest.json" 2503
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round40_run7_baseline_scene.json" 22868014
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round41_run7_pre_anchorfix_run_manifest.json" 2504
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round41_run7_pre_anchorfix_scene.json" 22868064
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round42_run7_recovery_link_run_manifest.json" 2504
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round42_run7_recovery_link_scene.json" 22883608
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round44_run4_singleton_negative_scene.json" 4587885
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round45_run8_frozen_holdout_scene.json" 15540625
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round46_run6_frame1100_diagnostic_scene.json" 7330118
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round47_run6_run6_frame1100_recovery_trace_scene.json" 7679224
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round48_run6_frame1099_1102_observations.json" 51119
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round49_run4_negative_scene.json" 4806528
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round49_run6_width_gate_scene.json" 7674343
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round49_run7_positive_control_observations.json" 8786
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round49_run7_positive_scene.json" 6900799
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round50_run1_frame970_perception_observations.json" 27069
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round51_run1_component_trace.json" 24025
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round52_run5_frame900_observations.json" 6470
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round53_run4_cyan_singleton_observation.json" 696
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round54_run7_2207_track_observation.json" 2804
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round57_run1_frame1045_hold_observations.json" 8718
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round59_run1_left_hold_component_trace.json" 9251
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round61_run1_component_continuity_trace.json" 16646
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round63_run1_continuity_threshold_trace.json" 2145
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round65_run4_cyan_temporal_trace.json" 663
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round66_run1_candidate_width_lineage.json" 2118
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round67_run1_component_separation_trace.json" 5054
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round68_run5_hold_point_mask_trace.json" 7357
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round69_run7_cyan_window_observations.json" 57298
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round_16_all_runs_frame_300_renderer_review.jpg" 943996
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\provenance\round_16_renderer_inferred_occlusion_check.json" 4492
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\renderer_smoke_v1_3.mp4" 147378
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\renderer_smoke_v1_3_scene.json" 2063
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\comparison.mp4" 231824180
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\geometry.mp4" 17926431
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_02\comparison.mp4" 244581427
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_02\geometry.mp4" 30849722
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_02\scene.json" 16980912
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_03\comparison.mp4" 246266634
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_03\geometry.mp4" 32582160
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_03\run_manifest.json" 2579
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_03\scene.json" 18430992
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_04\comparison.mp4" 251684731
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_04\geometry.mp4" 38050048
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_04\run_manifest.json" 3431
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_04\scene.json" 18430992
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_05\comparison.mp4" 252377798
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_05\geometry.mp4" 38815945
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_05\run_manifest.json" 3678
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_05\scene.json" 18449808
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_06\comparison.mp4" 244180004
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_06\geometry.mp4" 30382183
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_06\run_manifest.json" 2490
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_06\scene.json" 14033547
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_07\comparison.mp4" 244279978
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_07\geometry.mp4" 30489138
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_07\run_manifest.json" 3594
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_07\scene.json" 14052814
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_08\comparison.mp4" 244317704
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_08\geometry.mp4" 30530320
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_08\run_manifest.json" 4530
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_08\scene.json" 14064435
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_09\comparison.mp4" 244312948
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_09\geometry.mp4" 30524695
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_09\run_manifest.json" 5045
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_09\scene.json" 14061717
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_10\comparison.mp4" 244312948
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_10\geometry.mp4" 30524695
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_10\run_manifest.json" 5398
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_10\scene.json" 14062154
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_11\comparison.mp4" 244262440
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_11\geometry.mp4" 30473722
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_11\run_manifest.json" 5527
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_11\scene.json" 14055972
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_12\comparison.mp4" 244261941
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_12\geometry.mp4" 30472825
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_12\run_manifest.json" 5684
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_12\scene.json" 14057812
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_13\comparison.mp4" 244217047
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_13\geometry.mp4" 30427781
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_13\run_manifest.json" 7780
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_13\scene.json" 14065006
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_14\comparison.mp4" 244223383
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_14\geometry.mp4" 30432880
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_14\run_manifest.json" 8045
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_14\scene.json" 14066756
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_15\comparison.mp4" 244216025
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_15\geometry.mp4" 30424421
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_15\run_manifest.json" 1336
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_15\scene.json" 14068983
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_16\comparison.mp4" 238419052
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_16\geometry.mp4" 24420090
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_16\run_manifest.json" 3609
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_16\scene.json" 14130966
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_17\comparison.mp4" 238810065
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_17\geometry.mp4" 24802088
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_17\run_manifest.json" 2684
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_17\scene.json" 23501116
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_18\comparison.mp4" 238808018
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_18\geometry.mp4" 24800469
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_18\run_manifest.json" 2485
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_18\scene.json" 23501522
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_19\comparison.mp4" 238807813
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_19\geometry.mp4" 24802168
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_19\run_manifest.json" 2984
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_19\scene.json" 23505249
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_20\comparison.mp4" 238809090
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_20\geometry.mp4" 24803186
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_20\run_manifest.json" 2233
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_20\scene.json" 12685222
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\scene.json" 14948150
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_01\comparison.mp4" 254285961
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_01\geometry.mp4" 32479678
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_01\run_manifest.json" 1699
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_01\scene.json" 18640376
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_02\comparison.mp4" 256370135
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_02\geometry.mp4" 34627862
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_02\run_manifest.json" 2579
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_02\scene.json" 20322460
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_03\comparison.mp4" 262596591
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_03\geometry.mp4" 40941587
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_03\run_manifest.json" 3431
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_03\scene.json" 20322460
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_04\comparison.mp4" 262633013
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_04\geometry.mp4" 41076181
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_04\run_manifest.json" 2975
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_04\scene.json" 20285202
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_05\comparison.mp4" 253872635
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_05\geometry.mp4" 31984371
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_05\run_manifest.json" 2490
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_05\scene.json" 15428689
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_06\comparison.mp4" 253736268
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_06\geometry.mp4" 31844456
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_06\scene.json" 15409510
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_07\comparison.mp4" 253743729
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_07\geometry.mp4" 31852812
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_07\run_manifest.json" 3671
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_07\scene.json" 15409510
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_08\comparison.mp4" 253703058
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_08\geometry.mp4" 31810957
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_08\run_manifest.json" 4728
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_08\scene.json" 15393434
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_09\comparison.mp4" 247343265
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_09\geometry.mp4" 25227339
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_09\run_manifest.json" 3129
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_09\scene.json" 15447297
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_10\comparison.mp4" 248043770
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_10\geometry.mp4" 25969732
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_10\run_manifest.json" 2490
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_10\scene.json" 25495996
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_11\comparison.mp4" 248043228
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_11\geometry.mp4" 25971306
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_11\run_manifest.json" 2570
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_11\scene.json" 25496357
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_12\comparison.mp4" 253703058
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_12\geometry.mp4" 31810957
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_12\run_manifest.json" 1870
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_12\scene.json" 15396313
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_01\comparison.mp4" 198574394
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_01\geometry.mp4" 22688169
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_01\run_manifest.json" 1699
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_01\scene.json" 11270129
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_02\comparison.mp4" 200129918
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_02\geometry.mp4" 24295258
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_02\run_manifest.json" 2579
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_02\scene.json" 12499568
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_03\comparison.mp4" 203411297
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_03\geometry.mp4" 27642230
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_03\run_manifest.json" 3431
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_03\scene.json" 12499568
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_04\comparison.mp4" 204039957
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_04\geometry.mp4" 28343813
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_04\run_manifest.json" 2952
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_04\scene.json" 12557733
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_05\comparison.mp4" 199320071
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_05\geometry.mp4" 23435503
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_05\run_manifest.json" 2490
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_05\scene.json" 9828288
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_06\comparison.mp4" 199104703
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_06\geometry.mp4" 23209609
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_06\run_manifest.json" 3117
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_06\scene.json" 5608637
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_07\comparison.mp4" 199142118
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_07\geometry.mp4" 23243342
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_07\run_manifest.json" 3765
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_07\scene.json" 5617733
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_08\comparison.mp4" 199099325
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_08\geometry.mp4" 23200389
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_08\run_manifest.json" 4584
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_08\scene.json" 5610076
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_09\comparison.mp4" 195170236
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_09\geometry.mp4" 19072266
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_09\run_manifest.json" 3127
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_09\scene.json" 9840700
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_10\comparison.mp4" 195177061
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_10\geometry.mp4" 19078705
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_10\run_manifest.json" 4173
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_10\scene.json" 9851745
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_11\comparison.mp4" 195182567
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_11\geometry.mp4" 19085430
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_11\run_manifest.json" 2334
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_11\scene.json" 9861786
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_12\comparison.mp4" 195733292
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_12\geometry.mp4" 19691697
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_12\run_manifest.json" 3825
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_12\scene.json" 17113947
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_13\comparison.mp4" 195732654
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_13\geometry.mp4" 19689392
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_13\run_manifest.json" 2419
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_13\scene.json" 17116662
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_14\comparison.mp4" 195738154
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_14\geometry.mp4" 19694639
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_14\run_manifest.json" 2696
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_14\scene.json" 17118460
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_15\comparison.mp4" 195740140
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_15\geometry.mp4" 19696795
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_15\run_manifest.json" 2209
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_15\scene.json" 9210121
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_01\comparison.mp4" 279146520
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_01\geometry.mp4" 35509994
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_01\run_manifest.json" 1699
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_01\scene.json" 18156344
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_02\comparison.mp4" 281976345
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_02\geometry.mp4" 38438026
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_02\run_manifest.json" 2579
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_02\scene.json" 20066382
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_03\comparison.mp4" 289156293
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_03\geometry.mp4" 45803199
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_03\run_manifest.json" 3431
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_03\scene.json" 20066382
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_04\comparison.mp4" 289697172
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_04\geometry.mp4" 46442468
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_04\run_manifest.json" 2952
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_04\scene.json" 20065092
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_05\comparison.mp4" 289605957
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_05\geometry.mp4" 46348163
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_05\run_manifest.json" 4172
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_05\scene.json" 20045127
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_06\comparison.mp4" 289605957
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_06\geometry.mp4" 46348163
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_06\run_manifest.json" 4469
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_06\scene.json" 20044916
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_07\comparison.mp4" 289529811
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_07\geometry.mp4" 46258683
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_07\run_manifest.json" 1322
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_07\scene.json" 20023528
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_08\comparison.mp4" 289529811
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_08\geometry.mp4" 46258683
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_08\run_manifest.json" 1364
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_08\scene.json" 20024160
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_09\comparison.mp4" 289529811
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_09\geometry.mp4" 46258683
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_09\run_manifest.json" 1360
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_09\scene.json" 20024826
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_10\comparison.mp4" 282284483
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_10\geometry.mp4" 38810601
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_10\run_manifest.json" 3129
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_10\scene.json" 20079213
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_11\comparison.mp4" 273960598
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_11\geometry.mp4" 30180685
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_11\run_manifest.json" 2486
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_11\scene.json" 25163843
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_12\comparison.mp4" 273958603
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_12\geometry.mp4" 30181004
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_12\run_manifest.json" 2899
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_12\scene.json" 25165021
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_13\comparison.mp4" 289532522
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_13\geometry.mp4" 46260897
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_13\run_manifest.json" 2919
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_13\scene.json" 20026167
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_14\comparison.mp4" 289521030
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_14\geometry.mp4" 46249989
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_14\run_manifest.json" 1885
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_14\scene.json" 20040437
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_15\comparison.mp4" 289521030
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_15\geometry.mp4" 46249989
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_15\run_manifest.json" 1802
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_15\scene.json" 20043447
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_16\comparison.mp4" 289519504
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_16\geometry.mp4" 46248153
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_16\run_manifest.json" 1872
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_16\scene.json" 20048207
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_17\comparison.mp4" 289515081
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_17\geometry.mp4" 46243199
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_17\run_manifest.json" 1961
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_17\scene.json" 20050534
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_18\comparison.mp4" 289521507
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_18\geometry.mp4" 46249914
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_18\run_manifest.json" 1940
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_18\scene.json" 20064674
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_01\comparison.mp4" 254136028
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_01\geometry.mp4" 31707204
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_01\run_manifest.json" 1699
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_01\scene.json" 17793397
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_02\comparison.mp4" 256409944
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_02\geometry.mp4" 34114459
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_02\run_manifest.json" 2579
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_02\scene.json" 19639535
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_03\comparison.mp4" 261762990
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_03\geometry.mp4" 39599723
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_03\run_manifest.json" 3431
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_03\scene.json" 19639535
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_04\comparison.mp4" 262256918
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_04\geometry.mp4" 40157926
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_04\run_manifest.json" 3676
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_04\scene.json" 19603373
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_05\comparison.mp4" 262254200
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_05\geometry.mp4" 40153747
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_05\run_manifest.json" 4035
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_05\scene.json" 19606759
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_06\comparison.mp4" 262267523
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_06\geometry.mp4" 40175167
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_06\run_manifest.json" 4466
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_06\scene.json" 19618264
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_08\comparison.mp4" 256886792
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_08\geometry.mp4" 34650698
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_08\run_manifest.json" 3129
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_08\scene.json" 19670836
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_01\comparison.mp4" 278538608
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_01\geometry.mp4" 37874258
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_01\run_manifest.json" 1701
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_01\scene.json" 23252150
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_02\comparison.mp4" 279876670
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_02\geometry.mp4" 39289818
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_02\run_manifest.json" 2581
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_02\scene.json" 24680680
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_03\comparison.mp4" 287996386
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_03\geometry.mp4" 47546816
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_03\run_manifest.json" 3433
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_03\scene.json" 24680680
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_04\comparison.mp4" 288275267
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_04\geometry.mp4" 47887526
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_04\run_manifest.json" 2954
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_04\scene.json" 24642482
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_05\comparison.mp4" 288256937
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_05\geometry.mp4" 47866672
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_05\run_manifest.json" 3627
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_05\scene.json" 24640270
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_06\comparison.mp4" 288243028
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_06\geometry.mp4" 47853086
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_06\run_manifest.json" 4190
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_06\scene.json" 24632379
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_07\comparison.mp4" 288231393
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_07\geometry.mp4" 47841742
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_07\run_manifest.json" 4587
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_07\scene.json" 24632923
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_08\comparison.mp4" 288231393
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_08\geometry.mp4" 47841742
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_08\run_manifest.json" 4508
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_08\scene.json" 13826535
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_09\comparison.mp4" 280091072
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_09\geometry.mp4" 39557006
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_09\run_manifest.json" 3129
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_09\scene.json" 24705201
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_10\comparison.mp4" 288274322
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_10\geometry.mp4" 47884327
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_10\run_manifest.json" 4727
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_10\scene.json" 23778992
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_01\comparison.mp4" 313531767
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_01\geometry.mp4" 39403248
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_01\run_manifest.json" 1701
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_01\scene.json" 22327841
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_02\comparison.mp4" 316148179
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_02\geometry.mp4" 42084396
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_02\run_manifest.json" 2581
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_02\scene.json" 24161963
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_03\comparison.mp4" 325861053
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_03\geometry.mp4" 52020135
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_03\run_manifest.json" 3433
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_03\scene.json" 24161963
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_04\comparison.mp4" 325972916
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_04\geometry.mp4" 52196611
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_04\run_manifest.json" 2954
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_04\scene.json" 24139825
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_05\comparison.mp4" 325973882
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_05\geometry.mp4" 52194016
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_05\run_manifest.json" 3389
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_05\scene.json" 24142894
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_07\comparison.mp4" 325929051
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_07\geometry.mp4" 52144103
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_07\run_manifest.json" 3528
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_07\scene.json" 24139508
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_08\comparison.mp4" 316201107
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_08\geometry.mp4" 42174015
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_08\run_manifest.json" 3129
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_08\scene.json" 24214965
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_09\comparison.mp4" 316198730
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_09\geometry.mp4" 42171463
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_09\run_manifest.json" 2981
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_09\scene.json" 24215259
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_10\comparison.mp4" 325924799
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_10\geometry.mp4" 52142276
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_10\scene.json" 24139719
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_11\comparison.mp4" 325919035
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_11\geometry.mp4" 52134175
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_11\run_manifest.json" 3143
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_11\scene.json" 24141314
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_12\comparison.mp4" 325919035
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_12\geometry.mp4" 52134175
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_12\run_manifest.json" 5362
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_12\scene.json" 24152313
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_01\comparison.mp4" 223422874
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_01\geometry.mp4" 27874917
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_01\run_manifest.json" 1788
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_01\scene.json" 15270369
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_02\comparison.mp4" 224751556
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_02\geometry.mp4" 29267429
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_02\run_manifest.json" 2687
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_02\scene.json" 16634315
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_03\comparison.mp4" 229386533
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_03\geometry.mp4" 33995218
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_03\run_manifest.json" 3539
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_03\scene.json" 16634315
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_04\comparison.mp4" 229655371
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_04\geometry.mp4" 34283622
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_04\run_manifest.json" 2975
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_04\scene.json" 16598696
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_05\comparison.mp4" 229743280
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_05\geometry.mp4" 34376666
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_05\run_manifest.json" 4224
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_05\scene.json" 16696241
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_06\comparison.mp4" 229744877
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_06\geometry.mp4" 34379091
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_06\run_manifest.json" 2406
if errorlevel 1 goto :preflight_failed
call :check "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_06\scene.json" 16701992
if errorlevel 1 goto :preflight_failed
echo This will delete 1,408 non-final files under output\geometry_scene_v2.
echo Planned total: 33,215,185,519 bytes.
echo output\recording, latest formal revisions, offline code, report, index and source inventory are excluded.
echo Exact list: output\geometry_scene_v2\provenance\cleanup_manifest_final_compact.json
choice /C YN /M "Delete the listed files"
if errorlevel 2 goto :cancelled
call :delete "output\geometry_scene_v2\_scratch\round100_run6_pair_negative\source_geometry_pair_review.png"
call :delete "output\geometry_scene_v2\_scratch\round120_run6_note398\source_frames_492_498.png"
call :delete "output\geometry_scene_v2\_scratch\round145_run6\native_tail_compare.png"
call :delete "output\geometry_scene_v2\_scratch\round145_run6\run6_holds_tail_source_geometry.png"
call :delete "output\geometry_scene_v2\_scratch\round146_run7\frame2142_full.png"
call :delete "output\geometry_scene_v2\_scratch\round146_run7\run7_candidate_window_2470_2512.png"
call :delete "output\geometry_scene_v2\_scratch\round146_run7\run7_note2784_native_crop.png"
call :delete "output\geometry_scene_v2\_scratch\round146_run7\run7_note2784_native_timeline.png"
call :delete "output\geometry_scene_v2\_scratch\round174_renderer_replay\run_20261106T164049_800126Z.mp4"
call :delete "output\geometry_scene_v2\_scratch\round174_renderer_replay\run_20261106T164704_064294Z.mp4"
call :delete "output\geometry_scene_v2\_scratch\round174_renderer_replay\run_20261106T164959_579760Z.mp4"
call :delete "output\geometry_scene_v2\_scratch\round174_renderer_replay\run_20261106T170057_932173Z.mp4"
call :delete "output\geometry_scene_v2\_scratch\round174_renderer_replay\run_20261106T170845_579909Z.mp4"
call :delete "output\geometry_scene_v2\_scratch\round174_renderer_replay\run_20261106T171405_612600Z.mp4"
call :delete "output\geometry_scene_v2\_scratch\round174_renderer_replay\run_20261106T172037_662313Z.mp4"
call :delete "output\geometry_scene_v2\_scratch\round174_renderer_replay\run_20261106T172404_427324Z.mp4"
call :delete "output\geometry_scene_v2\cleanup_manifest_round_00.json"
call :delete "output\geometry_scene_v2\cleanup_manifest_round_01.json"
call :delete "output\geometry_scene_v2\cleanup_manifest_round_02.json"
call :delete "output\geometry_scene_v2\cleanup_manifest_round_03.json"
call :delete "output\geometry_scene_v2\cleanup_manifest_round_04.json"
call :delete "output\geometry_scene_v2\cleanup_manifest_round_05.json"
call :delete "output\geometry_scene_v2\cleanup_manifest_round_06.json"
call :delete "output\geometry_scene_v2\cleanup_manifest_round_07.json"
call :delete "output\geometry_scene_v2\cleanup_manifest_round_08.json"
call :delete "output\geometry_scene_v2\cleanup_manifest_round_09.json"
call :delete "output\geometry_scene_v2\cleanup_manifest_round_10.json"
call :delete "output\geometry_scene_v2\cleanup_manifest_round_11.json"
call :delete "output\geometry_scene_v2\cleanup_manifest_round_12.json"
call :delete "output\geometry_scene_v2\cleanup_manifest_round_13.json"
call :delete "output\geometry_scene_v2\cleanup_manifest_round_14.json"
call :delete "output\geometry_scene_v2\cleanup_manifest_round_15.json"
call :delete "output\geometry_scene_v2\cleanup_manifest_round_16.json"
call :delete "output\geometry_scene_v2\failures\round100_run4_note1897_color_context.png"
call :delete "output\geometry_scene_v2\failures\round100_run4_pair_color_correction.json"
call :delete "output\geometry_scene_v2\failures\round100_run4_pair_overlap_negative_review.json"
call :delete "output\geometry_scene_v2\failures\round100_run4_source_boxes_overlay.png"
call :delete "output\geometry_scene_v2\failures\round100_run4_trial_color_contact.png"
call :delete "output\geometry_scene_v2\failures\round101_run6_note1848_overlap_fragment_review.json"
call :delete "output\geometry_scene_v2\failures\round101_run6_source_frames.png"
call :delete "output\geometry_scene_v2\failures\round101_run6_source_geometry_contact.png"
call :delete "output\geometry_scene_v2\failures\round102_run6_note398_source_geometry_contact.png"
call :delete "output\geometry_scene_v2\failures\round102_run6_note398_tail_ambiguity_review.json"
call :delete "output\geometry_scene_v2\failures\round103_run1_frame746_zoom_boxes.png"
call :delete "output\geometry_scene_v2\failures\round103_run1_pair_source_geometry.png"
call :delete "output\geometry_scene_v2\failures\round103_run1_same_lane_hold_overlap_review.json"
call :delete "output\geometry_scene_v2\failures\round103_run1_source_native_frames744_754.png"
call :delete "output\geometry_scene_v2\failures\round104_run2_same_hold_boundary_duplicate_review.json"
call :delete "output\geometry_scene_v2\failures\round104_run2_source_geometry_contact.png"
call :delete "output\geometry_scene_v2\failures\round104_run2_source_native_body_frames.png"
call :delete "output\geometry_scene_v2\failures\round104_run2_source_native_heads.png"
call :delete "output\geometry_scene_v2\failures\round105_run3_note2151_duplicate_review.json"
call :delete "output\geometry_scene_v2\failures\round105_run3_source_edge_boxes_2660_2675.png"
call :delete "output\geometry_scene_v2\failures\round105_run3_source_geometry_contact.png"
call :delete "output\geometry_scene_v2\failures\round105_run3_source_native_2660_2675.png"
call :delete "output\geometry_scene_v2\failures\round105_run3_source_native_overlap_full_window.png"
call :delete "output\geometry_scene_v2\failures\round106_synthetic_geometry.mp4"
call :delete "output\geometry_scene_v2\failures\round106_synthetic_renderer_contact.png"
call :delete "output\geometry_scene_v2\failures\round106_synthetic_renderer_validation.json"
call :delete "output\geometry_scene_v2\failures\round107_negative_missing_timestamp_index.csv"
call :delete "output\geometry_scene_v2\failures\round107_negative_short_index.csv"
call :delete "output\geometry_scene_v2\failures\round107_short_clip_estimator_smoke.json"
call :delete "output\geometry_scene_v2\failures\round107_synthetic_short_game_layout.mp4"
call :delete "output\geometry_scene_v2\failures\round107_synthetic_short_game_layout_index.csv"
call :delete "output\geometry_scene_v2\failures\round107_synthetic_short_geometry.json"
call :delete "output\geometry_scene_v2\failures\round108_run7_note1011_hud_candidate_review.json"
call :delete "output\geometry_scene_v2\failures\round108_run7_note1011_source_zoom.png"
call :delete "output\geometry_scene_v2\failures\round108_run7_partial_scene_991_observation.json"
call :delete "output\geometry_scene_v2\failures\round108_run7_source_geometry_contact_974_990.png"
call :delete "output\geometry_scene_v2\failures\round109_run7_note1010_note1017_unresolved_review.json"
call :delete "output\geometry_scene_v2\failures\round109_run7_partial_scene_991_observation.json"
call :delete "output\geometry_scene_v2\failures\round109_run7_plate_fragment_source_geometry_context.png"
call :delete "output\geometry_scene_v2\failures\round110_failed_converging_geometry_estimate.json"
call :delete "output\geometry_scene_v2\failures\round110_failed_converging_scene.json"
call :delete "output\geometry_scene_v2\failures\round110_generic_clip_pipeline_smoke.json"
call :delete "output\geometry_scene_v2\failures\round110_synthetic_clip_comparison.mp4"
call :delete "output\geometry_scene_v2\failures\round110_synthetic_clip_geometry.json"
call :delete "output\geometry_scene_v2\failures\round110_synthetic_clip_geometry.mp4"
call :delete "output\geometry_scene_v2\failures\round110_synthetic_clip_geometry_comparison_contact.png"
call :delete "output\geometry_scene_v2\failures\round110_synthetic_clip_run_manifest.json"
call :delete "output\geometry_scene_v2\failures\round110_synthetic_clip_scene.json"
call :delete "output\geometry_scene_v2\failures\round111_run5_judgment_band_candidate_zoom.png"
call :delete "output\geometry_scene_v2\failures\round111_run5_partial_scene_1518_observation.json"
call :delete "output\geometry_scene_v2\failures\round111_run5_source_geometry_contact_1494_1517.png"
call :delete "output\geometry_scene_v2\failures\round111_run5_static_plate_edge_review.json"
call :delete "output\geometry_scene_v2\failures\round112_run4_note1074_plate_edge_review.json"
call :delete "output\geometry_scene_v2\failures\round112_run4_note1094_partial_scene_1469.json"
call :delete "output\geometry_scene_v2\failures\round112_run4_note1094_source_bbox_zoom.png"
call :delete "output\geometry_scene_v2\failures\round112_run4_previous_geometry_source_contact_1454_1469.png"
call :delete "output\geometry_scene_v2\failures\round112_run4_revision07_geometry_review.png"
call :delete "output\geometry_scene_v2\failures\round112_run4_source_detail_frames.png"
call :delete "output\geometry_scene_v2\failures\round112_run4_source_frames_contact.png"
call :delete "output\geometry_scene_v2\failures\round113_run4_note1071_hold_negative_review.json"
call :delete "output\geometry_scene_v2\failures\round113_run4_note1071_source_candidate_contact.png"
call :delete "output\geometry_scene_v2\failures\round114_run4_note1056_source_contact.png"
call :delete "output\geometry_scene_v2\failures\round114_run4_note1056_static_plate_edge_review.json"
call :delete "output\geometry_scene_v2\failures\round115_run4_note1094_judgment_band_review.json"
call :delete "output\geometry_scene_v2\failures\round115_run4_note1094_source_contact.png"
call :delete "output\geometry_scene_v2\failures\round116_run5_hold_tail_source_review.json"
call :delete "output\geometry_scene_v2\failures\round116_run5_note641_note666_source_tail_contact_898_905.png"
call :delete "output\geometry_scene_v2\failures\round116_run5_note641_note666_source_tail_contact_910_924.png"
call :delete "output\geometry_scene_v2\failures\round117_run1_note1150_manual_source_measurement_review.png"
call :delete "output\geometry_scene_v2\failures\round117_run1_note1150_revision15_comparison_contact.png"
call :delete "output\geometry_scene_v2\failures\round117_run1_note1150_source_1441_1446.png"
call :delete "output\geometry_scene_v2\failures\round117_run1_note1150_source_bbox_zoom.png"
call :delete "output\geometry_scene_v2\failures\round117_run1_note1150_source_candidate_contact.png"
call :delete "output\geometry_scene_v2\failures\round117_run1_note1150_source_detail_1441_1445.png"
call :delete "output\geometry_scene_v2\failures\round117_run1_note1150_source_zoom_gap.png"
call :delete "output\geometry_scene_v2\failures\round117_run1_note1150_visible_tap_gap_review.json"
call :delete "output\geometry_scene_v2\failures\round117_run1_revision15_geometry_detail.png"
call :delete "output\geometry_scene_v2\failures\round118_run6_note3104_note3100_source_tail_contact.png"
call :delete "output\geometry_scene_v2\failures\round118_run6_note3104_tail_identity_review.json"
call :delete "output\geometry_scene_v2\failures\round119_run2_note606_note638_head_overlap_detail.png"
call :delete "output\geometry_scene_v2\failures\round119_run2_note606_note638_overlap_review.json"
call :delete "output\geometry_scene_v2\failures\round119_run2_note606_note638_source_context.png"
call :delete "output\geometry_scene_v2\failures\round120_run6_note398_source_frames_492_498.png"
call :delete "output\geometry_scene_v2\failures\round120_run6_note398_source_review.json"
call :delete "output\geometry_scene_v2\failures\round121_longest_gap_source_geometry_contact.png"
call :delete "output\geometry_scene_v2\failures\round121_run1_note349_gap_detail.png"
call :delete "output\geometry_scene_v2\failures\round121_visibility_migration_audit.json"
call :delete "output\geometry_scene_v2\failures\round122_run1_bounded_rebuild_1600.json"
call :delete "output\geometry_scene_v2\failures\round122_run1_bounded_rebuild_1600_trace_v3.json"
call :delete "output\geometry_scene_v2\failures\round122_run1_note349_gap_contact.png"
call :delete "output\geometry_scene_v2\failures\round122_run1_note349_gap_review.json"
call :delete "output\geometry_scene_v2\failures\round122_run1_source_rebuilt_scene.json"
call :delete "output\geometry_scene_v2\failures\round122_run2_bounded_rebuild_850_v2.json"
call :delete "output\geometry_scene_v2\failures\round122_run2_source_rebuilt_scene.json"
call :delete "output\geometry_scene_v2\failures\round123_run3_bounded_rebuild_180.json"
call :delete "output\geometry_scene_v2\failures\round123_run3_frame150_source.png"
call :delete "output\geometry_scene_v2\failures\round123_run3_note7_candidate_contact.png"
call :delete "output\geometry_scene_v2\failures\round123_run3_note7_gap_review.json"
call :delete "output\geometry_scene_v2\failures\round123_run3_note7_gap_source_contact.png"
call :delete "output\geometry_scene_v2\failures\round124_run3_bounded_rebuild_800.json"
call :delete "output\geometry_scene_v2\failures\round124_run3_note368_candidate_contact.png"
call :delete "output\geometry_scene_v2\failures\round124_run3_note368_early_gap_contact.png"
call :delete "output\geometry_scene_v2\failures\round124_run3_note368_gap_review.json"
call :delete "output\geometry_scene_v2\failures\round124_run3_note368_gap_source_contact.png"
call :delete "output\geometry_scene_v2\failures\round124_run3_note368_gap_zoom.png"
call :delete "output\geometry_scene_v2\failures\round125_run3_bounded_rebuild_800.json"
call :delete "output\geometry_scene_v2\failures\round125_run3_bounded_rebuild_800_v2.json"
call :delete "output\geometry_scene_v2\failures\round125_run3_full_rebuild.json"
call :delete "output\geometry_scene_v2\failures\round125_run3_link_debug2_180.json"
call :delete "output\geometry_scene_v2\failures\round125_run3_link_debug_180.json"
call :delete "output\geometry_scene_v2\failures\round125_run3_note1124_bridge_source_contact.png"
call :delete "output\geometry_scene_v2\failures\round125_run3_note1124_candidate_contact.png"
call :delete "output\geometry_scene_v2\failures\round125_run3_note1386_bridge_source_contact.png"
call :delete "output\geometry_scene_v2\failures\round125_run3_note1386_candidate_contact.png"
call :delete "output\geometry_scene_v2\failures\round125_run3_note368_candidate_contact.png"
call :delete "output\geometry_scene_v2\failures\round125_run3_note7_candidate_contact.png"
call :delete "output\geometry_scene_v2\failures\round125_run3_partial_bridge_180.json"
call :delete "output\geometry_scene_v2\failures\round125_run3_partial_bridge_800.json"
call :delete "output\geometry_scene_v2\failures\round125_run3_partial_bridge_review.json"
call :delete "output\geometry_scene_v2\failures\round126_run1_bounded_240.json"
call :delete "output\geometry_scene_v2\failures\round126_run1_bounded_800.json"
call :delete "output\geometry_scene_v2\failures\round126_run1_cross_run_bridge_review.json"
call :delete "output\geometry_scene_v2\failures\round126_run1_full_rebuild.json"
call :delete "output\geometry_scene_v2\failures\round126_run1_geo_2924.png"
call :delete "output\geometry_scene_v2\failures\round126_run1_geo_2928.png"
call :delete "output\geometry_scene_v2\failures\round126_run1_geo_2933.png"
call :delete "output\geometry_scene_v2\failures\round126_run1_note1494_candidate_contact.png"
call :delete "output\geometry_scene_v2\failures\round126_run1_note1494_zoom.png"
call :delete "output\geometry_scene_v2\failures\round126_run1_note2767_candidate_contact.png"
call :delete "output\geometry_scene_v2\failures\round126_run1_note2767_zoom.png"
call :delete "output\geometry_scene_v2\failures\round127_run3_note1124_candidate_contact.png"
call :delete "output\geometry_scene_v2\failures\round127_run3_note1124_edge_source_contact.png"
call :delete "output\geometry_scene_v2\failures\round127_run3_note1124_grid.png"
call :delete "output\geometry_scene_v2\failures\round127_run3_note1386_candidate_contact.png"
call :delete "output\geometry_scene_v2\failures\round127_run3_note1386_grid.png"
call :delete "output\geometry_scene_v2\failures\round127_run3_note1386_missing_source_contact.png"
call :delete "output\geometry_scene_v2\failures\round127_run3_visible_gap_review.json"
call :delete "output\geometry_scene_v2\failures\round128_fragment_geometry_review.json"
call :delete "output\geometry_scene_v2\failures\round128_run1_full_rebuild_v2.json"
call :delete "output\geometry_scene_v2\failures\round128_run1_note1494_candidate_contact.png"
call :delete "output\geometry_scene_v2\failures\round128_run1_note2767_candidate_contact.png"
call :delete "output\geometry_scene_v2\failures\round128_run2_full_rebuild.json"
call :delete "output\geometry_scene_v2\failures\round128_run2_full_rebuild_v2.json"
call :delete "output\geometry_scene_v2\failures\round128_run2_note129_candidate_contact.png"
call :delete "output\geometry_scene_v2\failures\round128_run2_note129_candidate_contact_v2.png"
call :delete "output\geometry_scene_v2\failures\round128_run2_note129_grid.png"
call :delete "output\geometry_scene_v2\failures\round128_run2_note129_source_contact.png"
call :delete "output\geometry_scene_v2\failures\round128_run3_full_rebuild_v2.json"
call :delete "output\geometry_scene_v2\failures\round128_run3_note1124_candidate_contact.png"
call :delete "output\geometry_scene_v2\failures\round128_run3_note1386_candidate_contact.png"
call :delete "output\geometry_scene_v2\failures\round128_run3_note368_candidate_contact.png"
call :delete "output\geometry_scene_v2\failures\round129_run4_full_rebuild.json"
call :delete "output\geometry_scene_v2\failures\round129_run4_note1464_candidate_contact.png"
call :delete "output\geometry_scene_v2\failures\round129_run4_note1464_early_grid.png"
call :delete "output\geometry_scene_v2\failures\round129_run4_note1464_geometry_mismatch.json"
call :delete "output\geometry_scene_v2\failures\round129_run4_note1464_late_grid.png"
call :delete "output\geometry_scene_v2\failures\round129_run4_note1464_source_contact.png"
call :delete "output\geometry_scene_v2\failures\round130_run5_effect_band_association_review.json"
call :delete "output\geometry_scene_v2\failures\round130_run5_full_rebuild.json"
call :delete "output\geometry_scene_v2\failures\round130_run5_note2196_window.png"
call :delete "output\geometry_scene_v2\failures\round130_run5_note2237_window.png"
call :delete "output\geometry_scene_v2\failures\round131_run6_effect_band_association_review.json"
call :delete "output\geometry_scene_v2\failures\round131_run6_full_rebuild.json"
call :delete "output\geometry_scene_v2\failures\round131_run6_note1080_window.png"
call :delete "output\geometry_scene_v2\failures\round131_run6_note1813_window.png"
call :delete "output\geometry_scene_v2\failures\round132_run7_full_rebuild.json"
call :delete "output\geometry_scene_v2\failures\round132_run7_judgment_band_association_review.json"
call :delete "output\geometry_scene_v2\failures\round132_run7_note1173_window.png"
call :delete "output\geometry_scene_v2\failures\round132_run7_note1344_window.png"
call :delete "output\geometry_scene_v2\failures\round132_run7_note1937_window.png"
call :delete "output\geometry_scene_v2\failures\round132_run7_note2855_window.png"
call :delete "output\geometry_scene_v2\failures\round133_judgment_band_guard_validation.json"
call :delete "output\geometry_scene_v2\failures\round133_run7_guard_rebuild.json"
call :delete "output\geometry_scene_v2\failures\round133_run7_note1173_candidate_contact.png"
call :delete "output\geometry_scene_v2\failures\round134_run8_frozen_holdout_audit.json"
call :delete "output\geometry_scene_v2\failures\round134_run8_frozen_holdout_rebuild.json"
call :delete "output\geometry_scene_v2\failures\round135_formal_delivery_integrity_audit.json"
call :delete "output\geometry_scene_v2\failures\round136_run4_native_f1820.png"
call :delete "output\geometry_scene_v2\failures\round136_run4_native_f1823.png"
call :delete "output\geometry_scene_v2\failures\round136_run4_native_f1824.png"
call :delete "output\geometry_scene_v2\failures\round136_run4_native_f1826.png"
call :delete "output\geometry_scene_v2\failures\round136_run4_native_f1833.png"
call :delete "output\geometry_scene_v2\failures\round136_run4_native_f1834.png"
call :delete "output\geometry_scene_v2\failures\round136_run4_native_f1835.png"
call :delete "output\geometry_scene_v2\failures\round136_run4_note1464_candidate_contact.png"
call :delete "output\geometry_scene_v2\failures\round136_run4_note1464_native_compare.png"
call :delete "output\geometry_scene_v2\failures\round136_run4_note1464_native_review.json"
call :delete "output\geometry_scene_v2\failures\round137_run1_native_f1772.png"
call :delete "output\geometry_scene_v2\failures\round137_run1_native_f1774.png"
call :delete "output\geometry_scene_v2\failures\round137_run1_native_f1776.png"
call :delete "output\geometry_scene_v2\failures\round137_run1_native_f1778.png"
call :delete "output\geometry_scene_v2\failures\round137_run1_note1494_candidate_contact.png"
call :delete "output\geometry_scene_v2\failures\round137_run1_note1494_native_contact.png"
call :delete "output\geometry_scene_v2\failures\round137_run1_note1494_native_grid.png"
call :delete "output\geometry_scene_v2\failures\round137_run1_note1494_native_review.json"
call :delete "output\geometry_scene_v2\failures\round137_run1_note1494_source_frames.png"
call :delete "output\geometry_scene_v2\failures\round138_run1_native_f2924.png"
call :delete "output\geometry_scene_v2\failures\round138_run1_native_f2933.png"
call :delete "output\geometry_scene_v2\failures\round138_run1_native_f2933_left_zoom.png"
call :delete "output\geometry_scene_v2\failures\round138_run1_native_f2934.png"
call :delete "output\geometry_scene_v2\failures\round138_run1_native_f2934_left_zoom.png"
call :delete "output\geometry_scene_v2\failures\round138_run1_native_f2935.png"
call :delete "output\geometry_scene_v2\failures\round138_run1_native_f2935_left_zoom.png"
call :delete "output\geometry_scene_v2\failures\round138_run1_note2767_candidate_contact.png"
call :delete "output\geometry_scene_v2\failures\round138_run1_note2767_contact.png"
call :delete "output\geometry_scene_v2\failures\round138_run1_note2767_native_review.json"
call :delete "output\geometry_scene_v2\failures\round139_run5_full_rebuild.json"
call :delete "output\geometry_scene_v2\failures\round139_run5_judgment_band_gate_validation.json"
call :delete "output\geometry_scene_v2\failures\round140_run6_full_rebuild.json"
call :delete "output\geometry_scene_v2\failures\round140_run6_judgment_band_gate_validation.json"
call :delete "output\geometry_scene_v2\failures\round141_run3_note368_bounds_grid.png"
call :delete "output\geometry_scene_v2\failures\round141_run3_note368_candidate_contact.png"
call :delete "output\geometry_scene_v2\failures\round141_run3_note368_native_review.json"
call :delete "output\geometry_scene_v2\failures\round141_run3_note368_tail_native_crops.png"
call :delete "output\geometry_scene_v2\failures\round141_run3_note368_tail_native_source.png"
call :delete "output\geometry_scene_v2\failures\round142_run2_note129_identity_review.json"
call :delete "output\geometry_scene_v2\failures\round142_run2_note129_native_timeline.png"
call :delete "output\geometry_scene_v2\failures\round143_run2_note638_after_effect_contact.png"
call :delete "output\geometry_scene_v2\failures\round143_run2_note638_post_overlap_contact.png"
call :delete "output\geometry_scene_v2\failures\round143_run2_note638_post_overlap_review.json"
call :delete "output\geometry_scene_v2\failures\round144_run5_sample_review.json"
call :delete "output\geometry_scene_v2\failures\round144_run5_unreviewed_sample_contact.png"
call :delete "output\geometry_scene_v2\failures\round145_run6_holds_tail_source_geometry.png"
call :delete "output\geometry_scene_v2\failures\round145_run6_tail_attribution_review.json"
call :delete "output\geometry_scene_v2\failures\round145_run6_tail_native_compare.png"
call :delete "output\geometry_scene_v2\failures\round146_run7_note2784_source_review.json"
call :delete "output\geometry_scene_v2\failures\round147_run7_note1955_candidate_source_review.png"
call :delete "output\geometry_scene_v2\failures\round147_run7_note1955_source_review.json"
call :delete "output\geometry_scene_v2\failures\round148_final_delivery_index_before_run1_revision21.json"
call :delete "output\geometry_scene_v2\failures\round148_run1_revision21_acceptance.json"
call :delete "output\geometry_scene_v2\failures\round148_run1_revision21_target_windows.png"
call :delete "output\geometry_scene_v2\failures\round149_final_delivery_index_before_run3_revision16.json"
call :delete "output\geometry_scene_v2\failures\round149_run3_revision16_acceptance.json"
call :delete "output\geometry_scene_v2\failures\round149_run3_revision16_note368_windows.png"
call :delete "output\geometry_scene_v2\failures\round150_final_delivery_index_before_review.json"
call :delete "output\geometry_scene_v2\failures\round150_run7_note2784_post_effect_review.json"
call :delete "output\geometry_scene_v2\failures\round150_run7_note2784_post_effect_source_frames.png"
call :delete "output\geometry_scene_v2\failures\round151_final_delivery_index_before_run4_revision13.json"
call :delete "output\geometry_scene_v2\failures\round151_run4_note1464_revision13_acceptance.json"
call :delete "output\geometry_scene_v2\failures\round151_run4_note1464_revision13_window.png"
call :delete "output\geometry_scene_v2\failures\round152_final_delivery_index_before_review.json"
call :delete "output\geometry_scene_v2\failures\round152_run4_note1071_endpoint_extended.png"
call :delete "output\geometry_scene_v2\failures\round152_run4_note1071_tail_endpoint_review.json"
call :delete "output\geometry_scene_v2\failures\round152_run4_note1071_tail_zoom.png"
call :delete "output\geometry_scene_v2\failures\round153_final_delivery_index_before_run7_revision11.json"
call :delete "output\geometry_scene_v2\failures\round153_run7_frame1041_full.png"
call :delete "output\geometry_scene_v2\failures\round153_run7_frame1042_full.png"
call :delete "output\geometry_scene_v2\failures\round153_run7_frame1043_full.png"
call :delete "output\geometry_scene_v2\failures\round153_run7_note1173_native_band_review.png"
call :delete "output\geometry_scene_v2\failures\round153_run7_note1173_revision10_window.png"
call :delete "output\geometry_scene_v2\failures\round153_run7_note1173_source_neighborhood.png"
call :delete "output\geometry_scene_v2\failures\round153_run7_note1266_tap_native_measurement.png"
call :delete "output\geometry_scene_v2\failures\round153_run7_revision11_note1173_note1266_acceptance.json"
call :delete "output\geometry_scene_v2\failures\round153_run7_revision11_note1173_note1266_window.png"
call :delete "output\geometry_scene_v2\failures\round154_run5_frame898_full.png"
call :delete "output\geometry_scene_v2\failures\round154_run5_frame905_full.png"
call :delete "output\geometry_scene_v2\failures\round154_run5_frame915_full.png"
call :delete "output\geometry_scene_v2\failures\round154_run5_frame924_full.png"
call :delete "output\geometry_scene_v2\failures\round154_run5_note641_native_ribbon_898_905.png"
call :delete "output\geometry_scene_v2\failures\round154_run5_note641_note666_tail_identity_review.json"
call :delete "output\geometry_scene_v2\failures\round155_run5_geometry_judgment_approach_920_931.png"
call :delete "output\geometry_scene_v2\failures\round155_run5_judgment_approach_920_931.png"
call :delete "output\geometry_scene_v2\failures\round155_run5_note641_judgment_boundary_review.json"
call :delete "output\geometry_scene_v2\failures\round156_run1_note433_note505_post_overlap_review.json"
call :delete "output\geometry_scene_v2\failures\round156_run1_overlap_native_1.png"
call :delete "output\geometry_scene_v2\failures\round156_run1_overlap_native_2.png"
call :delete "output\geometry_scene_v2\failures\round156_run1_overlap_reemergence_geometry_750_778.png"
call :delete "output\geometry_scene_v2\failures\round156_run1_overlap_reemergence_source_750_778.png"
call :delete "output\geometry_scene_v2\failures\round157_run6_judgment_green_head_geometry_500_511.png"
call :delete "output\geometry_scene_v2\failures\round157_run6_judgment_green_head_source_500_511.png"
call :delete "output\geometry_scene_v2\failures\round157_run6_note398_postflash_geometry_496_524.png"
call :delete "output\geometry_scene_v2\failures\round157_run6_note398_postflash_green_candidate_review.json"
call :delete "output\geometry_scene_v2\failures\round157_run6_note398_postflash_source_496_524.png"
call :delete "output\geometry_scene_v2\failures\round157_run6_postflash_native_1.png"
call :delete "output\geometry_scene_v2\failures\round157_run6_postflash_native_2.png"
call :delete "output\geometry_scene_v2\failures\round157_run6_postflash_native_3.png"
call :delete "output\geometry_scene_v2\failures\round158_final_delivery_index_before_run6_revision10.json"
call :delete "output\geometry_scene_v2\failures\round158_run6_hold_continuity_493_504_geometry.png"
call :delete "output\geometry_scene_v2\failures\round158_run6_hold_continuity_493_504_revision10_geometry.png"
call :delete "output\geometry_scene_v2\failures\round158_run6_hold_continuity_493_504_source.png"
call :delete "output\geometry_scene_v2\failures\round158_run6_hold_endpoint_grid_499_504.png"
call :delete "output\geometry_scene_v2\failures\round158_run6_hold_endpoints_zoom_499_504.png"
call :delete "output\geometry_scene_v2\failures\round158_run6_hold_measured_timeline_499_504.png"
call :delete "output\geometry_scene_v2\failures\round158_run6_native_boundary_1.png"
call :delete "output\geometry_scene_v2\failures\round158_run6_native_boundary_2.png"
call :delete "output\geometry_scene_v2\failures\round158_run6_native_boundary_3.png"
call :delete "output\geometry_scene_v2\failures\round158_run6_native_boundary_4.png"
call :delete "output\geometry_scene_v2\failures\round158_run6_native_boundary_5.png"
call :delete "output\geometry_scene_v2\failures\round158_run6_native_boundary_6.png"
call :delete "output\geometry_scene_v2\failures\round158_run6_note398_before_revision10.json"
call :delete "output\geometry_scene_v2\failures\round158_run6_note398_revision10_acceptance.json"
call :delete "output\geometry_scene_v2\failures\round158_run6_note398_source_geometry_window_493_504.png"
call :delete "output\geometry_scene_v2\failures\round159_run6_note398_frame505_506_detail.png"
call :delete "output\geometry_scene_v2\failures\round159_run6_note398_release_boundary_grid_504_507.png"
call :delete "output\geometry_scene_v2\failures\round159_run6_note398_release_boundary_review.json"
call :delete "output\geometry_scene_v2\failures\round160_run5_note641_postimpact_review.json"
call :delete "output\geometry_scene_v2\failures\round160_run5_note641_postimpact_source_932_960.png"
call :delete "output\geometry_scene_v2\failures\round161_final_delivery_index_before_run8_revision05.json"
call :delete "output\geometry_scene_v2\failures\round161_run8_hold_frame270_approach_zoom.png"
call :delete "output\geometry_scene_v2\failures\round161_run8_hold_frame270_early_timeline.png"
call :delete "output\geometry_scene_v2\failures\round161_run8_hold_frame270_early_zoom.png"
call :delete "output\geometry_scene_v2\failures\round161_run8_hold_frame270_late_timeline.png"
call :delete "output\geometry_scene_v2\failures\round161_run8_hold_frame270_late_zoom.png"
call :delete "output\geometry_scene_v2\failures\round161_run8_hold_frame270_release_zoom.png"
call :delete "output\geometry_scene_v2\failures\round161_run8_hold_release_boundary_312_320.png"
call :delete "output\geometry_scene_v2\failures\round161_run8_hold_release_coordinate_grid_311_314.png"
call :delete "output\geometry_scene_v2\failures\round161_run8_hold_tail_anchors_234_313.png"
call :delete "output\geometry_scene_v2\failures\round161_run8_hold_transition_frames232_240.png"
call :delete "output\geometry_scene_v2\failures\round161_run8_note7_before_revision05.json"
call :delete "output\geometry_scene_v2\failures\round161_run8_note7_revision05_acceptance.json"
call :delete "output\geometry_scene_v2\failures\round161_run8_revision05_note7_entry_comparison.png"
call :delete "output\geometry_scene_v2\failures\round161_run8_revision05_note7_release_comparison.png"
call :delete "output\geometry_scene_v2\failures\round161_run8_scene_before_revision05.json"
call :delete "output\geometry_scene_v2\failures\round162_run8_note7_effect_clear_frames321_328.png"
call :delete "output\geometry_scene_v2\failures\round162_run8_note7_postflash_release_review.json"
call :delete "output\geometry_scene_v2\failures\round162_run8_note7_postflash_source_314_348.png"
call :delete "output\geometry_scene_v2\failures\round163_run1_note2767_effect_clear_2935_2948.png"
call :delete "output\geometry_scene_v2\failures\round163_run1_note2767_posthit_release_review.json"
call :delete "output\geometry_scene_v2\failures\round163_run1_note2767_posthit_source_2935_2970.png"
call :delete "output\geometry_scene_v2\failures\round164_run3_note368_posthit_identity_review.json"
call :delete "output\geometry_scene_v2\failures\round164_run3_note368_posthit_source_784_820.png"
call :delete "output\geometry_scene_v2\failures\round165_run7_note2855_postflash_identity_review.json"
call :delete "output\geometry_scene_v2\failures\round165_run7_note2855_postflash_source_2220_2260.png"
call :delete "output\geometry_scene_v2\failures\round166_run2_note638_post_overlap_identity_review.json"
call :delete "output\geometry_scene_v2\failures\round166_run2_note638_post_overlap_source_863_900.png"
call :delete "output\geometry_scene_v2\failures\round167_process_error.txt"
call :delete "output\geometry_scene_v2\failures\round167_process_stdout.log"
call :delete "output\geometry_scene_v2\failures\round167_run4_native_segment_pipeline_audit.json"
call :delete "output\geometry_scene_v2\failures\round167_run4_segment_build\comparison.mp4"
call :delete "output\geometry_scene_v2\failures\round167_run4_segment_build\geometry.json"
call :delete "output\geometry_scene_v2\failures\round167_run4_segment_build\geometry.mp4"
call :delete "output\geometry_scene_v2\failures\round167_run4_segment_build\run_manifest.json"
call :delete "output\geometry_scene_v2\failures\round167_run4_segment_build\scene.json"
call :delete "output\geometry_scene_v2\failures\round167_run4_segment_index_1000_1119.csv"
call :delete "output\geometry_scene_v2\failures\round167_run4_segment_source_1000_1119.mp4"
call :delete "output\geometry_scene_v2\failures\round167_run4_segment_source_geometry_review.png"
call :delete "output\geometry_scene_v2\failures\round167_run4_segment_source_tap_1001_geometry_negative.png"
call :delete "output\geometry_scene_v2\failures\round168_final_delivery_index_before_run4_revision14.json"
call :delete "output\geometry_scene_v2\failures\round168_run4_cyan_face_999_1000.png"
call :delete "output\geometry_scene_v2\failures\round168_run4_cyan_face_bounds_1001_1009.png"
call :delete "output\geometry_scene_v2\failures\round168_run4_cyan_manual_bounds_proposal.png"
call :delete "output\geometry_scene_v2\failures\round168_run4_cyan_plate_source_1000_1016.png"
call :delete "output\geometry_scene_v2\failures\round168_run4_revision14_before_frame999_fix.json"
call :delete "output\geometry_scene_v2\failures\round168_run4_revision14_cyan_tap_review.png"
call :delete "output\geometry_scene_v2\failures\round168_run4_revision14_cyan_tap_review_after_frame999.png"
call :delete "output\geometry_scene_v2\failures\round168_run4_revision14_full_validation.json"
call :delete "output\geometry_scene_v2\failures\round168_run4_revision14_note581_note662_acceptance.json"
call :delete "output\geometry_scene_v2\failures\round169_run4_note1071_endpoint_source_crop.png"
call :delete "output\geometry_scene_v2\failures\round169_run4_note1071_postimpact_source_1484_1540.png"
call :delete "output\geometry_scene_v2\failures\round169_run4_note1071_tail_endpoint_review.json"
call :delete "output\geometry_scene_v2\failures\round170_run6_notes3104_3100_source_after_endpoint.png"
call :delete "output\geometry_scene_v2\failures\round170_run6_notes3104_3100_tail_review.json"
call :delete "output\geometry_scene_v2\failures\round171_generic_clip_native_cyan_fallback_validation.json"
call :delete "output\geometry_scene_v2\failures\round171_run4_cyan_tap_source_geometry_review.png"
call :delete "output\geometry_scene_v2\failures\round171_run4_frame1008_candidate_vs_source_review.png"
call :delete "output\geometry_scene_v2\failures\round171_run4_segment_build\comparison.mp4"
call :delete "output\geometry_scene_v2\failures\round171_run4_segment_build\geometry.json"
call :delete "output\geometry_scene_v2\failures\round171_run4_segment_build\geometry.mp4"
call :delete "output\geometry_scene_v2\failures\round171_run4_segment_build\run_manifest.json"
call :delete "output\geometry_scene_v2\failures\round171_run4_segment_build\scene.json"
call :delete "output\geometry_scene_v2\failures\round171_run4_segment_build_final_candidate\comparison.mp4"
call :delete "output\geometry_scene_v2\failures\round171_run4_segment_build_final_candidate\geometry.json"
call :delete "output\geometry_scene_v2\failures\round171_run4_segment_build_final_candidate\geometry.mp4"
call :delete "output\geometry_scene_v2\failures\round171_run4_segment_build_final_candidate\run_manifest.json"
call :delete "output\geometry_scene_v2\failures\round171_run4_segment_build_final_candidate\scene.json"
call :delete "output\geometry_scene_v2\failures\round171_run4_segment_build_final_candidate_r2\comparison.mp4"
call :delete "output\geometry_scene_v2\failures\round171_run4_segment_build_final_candidate_r2\geometry.json"
call :delete "output\geometry_scene_v2\failures\round171_run4_segment_build_final_candidate_r2\geometry.mp4"
call :delete "output\geometry_scene_v2\failures\round171_run4_segment_build_final_candidate_r2\run_manifest.json"
call :delete "output\geometry_scene_v2\failures\round171_run4_segment_build_final_candidate_r2\scene.json"
call :delete "output\geometry_scene_v2\failures\round171_run4_segment_build_iter2\comparison.mp4"
call :delete "output\geometry_scene_v2\failures\round171_run4_segment_build_iter2\geometry.json"
call :delete "output\geometry_scene_v2\failures\round171_run4_segment_build_iter2\geometry.mp4"
call :delete "output\geometry_scene_v2\failures\round171_run4_segment_build_iter2\run_manifest.json"
call :delete "output\geometry_scene_v2\failures\round171_run4_segment_build_iter2\scene.json"
call :delete "output\geometry_scene_v2\failures\round171_run4_segment_build_iter3\comparison.mp4"
call :delete "output\geometry_scene_v2\failures\round171_run4_segment_build_iter3\geometry.json"
call :delete "output\geometry_scene_v2\failures\round171_run4_segment_build_iter3\geometry.mp4"
call :delete "output\geometry_scene_v2\failures\round171_run4_segment_build_iter3\run_manifest.json"
call :delete "output\geometry_scene_v2\failures\round171_run4_segment_build_iter3\scene.json"
call :delete "output\geometry_scene_v2\failures\round171_run4_segment_build_iter4\comparison.mp4"
call :delete "output\geometry_scene_v2\failures\round171_run4_segment_build_iter4\geometry.json"
call :delete "output\geometry_scene_v2\failures\round171_run4_segment_build_iter4\geometry.mp4"
call :delete "output\geometry_scene_v2\failures\round171_run4_segment_build_iter4\run_manifest.json"
call :delete "output\geometry_scene_v2\failures\round171_run4_segment_build_iter4\scene.json"
call :delete "output\geometry_scene_v2\failures\round171_run8_holdout_build\comparison.mp4"
call :delete "output\geometry_scene_v2\failures\round171_run8_holdout_build\geometry.json"
call :delete "output\geometry_scene_v2\failures\round171_run8_holdout_build\geometry.mp4"
call :delete "output\geometry_scene_v2\failures\round171_run8_holdout_build\run_manifest.json"
call :delete "output\geometry_scene_v2\failures\round171_run8_holdout_build\scene.json"
call :delete "output\geometry_scene_v2\failures\round171_run8_holdout_build_r2\comparison.mp4"
call :delete "output\geometry_scene_v2\failures\round171_run8_holdout_build_r2\geometry.json"
call :delete "output\geometry_scene_v2\failures\round171_run8_holdout_build_r2\geometry.mp4"
call :delete "output\geometry_scene_v2\failures\round171_run8_holdout_build_r2\run_manifest.json"
call :delete "output\geometry_scene_v2\failures\round171_run8_holdout_build_r2\scene.json"
call :delete "output\geometry_scene_v2\failures\round171_run8_holdout_cyan_source_geometry_review.png"
call :delete "output\geometry_scene_v2\failures\round171_run8_holdout_index_360_399.csv"
call :delete "output\geometry_scene_v2\failures\round171_run8_holdout_note100_source_geometry.png"
call :delete "output\geometry_scene_v2\failures\round171_run8_holdout_source_360_399.mp4"
call :delete "output\geometry_scene_v2\failures\round172_run2_frozen_holdout_build\comparison.mp4"
call :delete "output\geometry_scene_v2\failures\round172_run2_frozen_holdout_build\geometry.json"
call :delete "output\geometry_scene_v2\failures\round172_run2_frozen_holdout_build\geometry.mp4"
call :delete "output\geometry_scene_v2\failures\round172_run2_frozen_holdout_build\run_manifest.json"
call :delete "output\geometry_scene_v2\failures\round172_run2_frozen_holdout_build\scene.json"
call :delete "output\geometry_scene_v2\failures\round172_run2_frozen_holdout_contact.png"
call :delete "output\geometry_scene_v2\failures\round172_run2_frozen_holdout_frame3039.png"
call :delete "output\geometry_scene_v2\failures\round172_run2_frozen_holdout_last4.png"
call :delete "output\geometry_scene_v2\failures\round172_run2_frozen_holdout_source_3000_3039.csv"
call :delete "output\geometry_scene_v2\failures\round172_run2_frozen_holdout_source_3000_3039.mp4"
call :delete "output\geometry_scene_v2\failures\round172_run2_frozen_review_window.json"
call :delete "output\geometry_scene_v2\failures\round172_run4_segment_build_r3\comparison.mp4"
call :delete "output\geometry_scene_v2\failures\round172_run4_segment_build_r3\geometry.json"
call :delete "output\geometry_scene_v2\failures\round172_run4_segment_build_r3\geometry.mp4"
call :delete "output\geometry_scene_v2\failures\round172_run4_segment_build_r3\run_manifest.json"
call :delete "output\geometry_scene_v2\failures\round172_run4_segment_build_r3\scene.json"
call :delete "output\geometry_scene_v2\failures\round172_run4_segment_build_r4\comparison.mp4"
call :delete "output\geometry_scene_v2\failures\round172_run4_segment_build_r4\geometry.json"
call :delete "output\geometry_scene_v2\failures\round172_run4_segment_build_r4\geometry.mp4"
call :delete "output\geometry_scene_v2\failures\round172_run4_segment_build_r4\run_manifest.json"
call :delete "output\geometry_scene_v2\failures\round172_run4_segment_build_r4\scene.json"
call :delete "output\geometry_scene_v2\failures\round172_run8_edge_pair_face_reconstruction.json"
call :delete "output\geometry_scene_v2\failures\round172_run8_formal_edge_candidates_source_overlay.png"
call :delete "output\geometry_scene_v2\failures\round172_run8_holdout_build_r3\comparison.mp4"
call :delete "output\geometry_scene_v2\failures\round172_run8_holdout_build_r3\geometry.json"
call :delete "output\geometry_scene_v2\failures\round172_run8_holdout_build_r3\geometry.mp4"
call :delete "output\geometry_scene_v2\failures\round172_run8_holdout_build_r3\run_manifest.json"
call :delete "output\geometry_scene_v2\failures\round172_run8_holdout_build_r3\scene.json"
call :delete "output\geometry_scene_v2\failures\round172_run8_holdout_build_r4\comparison.mp4"
call :delete "output\geometry_scene_v2\failures\round172_run8_holdout_build_r4\geometry.json"
call :delete "output\geometry_scene_v2\failures\round172_run8_holdout_build_r4\geometry.mp4"
call :delete "output\geometry_scene_v2\failures\round172_run8_holdout_build_r4\run_manifest.json"
call :delete "output\geometry_scene_v2\failures\round172_run8_holdout_build_r4\scene.json"
call :delete "output\geometry_scene_v2\failures\round172_run8_lower_full_face_bounds_preview.png"
call :delete "output\geometry_scene_v2\failures\round172_run8_manual_full_face_bounds_preview.png"
call :delete "output\geometry_scene_v2\failures\round172_run8_native_frames_370_382_lane0.png"
call :delete "output\geometry_scene_v2\failures\round172_run8_native_zoom_373_379.png"
call :delete "output\geometry_scene_v2\failures\round172_run8_revision06_source_geometry_window.png"
call :delete "output\geometry_scene_v2\failures\round172_run8_revision07_source_geometry_window.png"
call :delete "output\geometry_scene_v2\failures\round172_run8_source_geometry_effect_gap_review.png"
call :delete "output\geometry_scene_v2\failures\round173_delivery_index_link_consistency.json"
call :delete "output\geometry_scene_v2\failures\round174_full_scene_renderer_replay_audit.json"
call :delete "output\geometry_scene_v2\failures\round175_run7_note3081_cross_lane_identity_review.json"
call :delete "output\geometry_scene_v2\failures\round175_run7_note3081_lane2_vs_lane4_contact.png"
call :delete "output\geometry_scene_v2\failures\round175_run7_note3081_source_lane_overlay.png"
call :delete "output\geometry_scene_v2\failures\round176_run7_note3081_note3188_identity_review.json"
call :delete "output\geometry_scene_v2\failures\round176_run7_note3081_note3188_overlap_detail.png"
call :delete "output\geometry_scene_v2\failures\round177_run7_note4166_cross_track_association_review.json"
call :delete "output\geometry_scene_v2\failures\round177_run7_note4166_horizon_detail.png"
call :delete "output\geometry_scene_v2\failures\round177_run7_note4166_source_crop_contact.png"
call :delete "output\geometry_scene_v2\failures\round177_run7_note4166_switch_frame_detail.png"
call :delete "output\geometry_scene_v2\failures\round178_run7_refined_geometry_jump_windows.png"
call :delete "output\geometry_scene_v2\failures\round178_run7_same_jump_patterns.png"
call :delete "output\geometry_scene_v2\failures\round178_run7_tracker_discontinuity_refinement.json"
call :delete "output\geometry_scene_v2\failures\round179_run6_note398_hold_tail_release_review.json"
call :delete "output\geometry_scene_v2\failures\round179_run6_note398_source_498_520.png"
call :delete "output\geometry_scene_v2\failures\round179_run6_note398_source_endpoint_overlay.png"
call :delete "output\geometry_scene_v2\failures\round17_run5_direction_guard_contact.png"
call :delete "output\geometry_scene_v2\failures\round17_run5_frame900_source.png"
call :delete "output\geometry_scene_v2\failures\round17_run5_hold_tail_direction.json"
call :delete "output\geometry_scene_v2\failures\round180_run8_note7_release_tail_review.json"
call :delete "output\geometry_scene_v2\failures\round180_run8_note7_source_310_324.png"
call :delete "output\geometry_scene_v2\failures\round181_run4_note1071_endpoint_overlay.png"
call :delete "output\geometry_scene_v2\failures\round181_run4_note1071_pre_effect_tail_source_review.json"
call :delete "output\geometry_scene_v2\failures\round181_run4_note1071_source_1458_1465.png"
call :delete "output\geometry_scene_v2\failures\round181_run4_note1071_source_post_effect.png"
call :delete "output\geometry_scene_v2\failures\round182_run7_note4166_covisible_tracker_switch_review.json"
call :delete "output\geometry_scene_v2\failures\round182_run7_note4166_source_3096_3120.png"
call :delete "output\geometry_scene_v2\failures\round183_run7_jump_3094_4273_source.png"
call :delete "output\geometry_scene_v2\failures\round183_run7_jump_split_source_review.json"
call :delete "output\geometry_scene_v2\failures\round184_run2_note1689_note1709_same_lane_double_tap_review.json"
call :delete "output\geometry_scene_v2\failures\round184_run2_note1689_note1709_source_1625_1645.png"
call :delete "output\geometry_scene_v2\failures\round184_run2_note1689_note1709_source_zoom.png"
call :delete "output\geometry_scene_v2\failures\round185_run4_note1331_frame1707_source_measurement.png"
call :delete "output\geometry_scene_v2\failures\round185_run4_note1331_frame1707_unannotated_zoom.png"
call :delete "output\geometry_scene_v2\failures\round185_run4_note1331_measure_frames_1707_1710.png"
call :delete "output\geometry_scene_v2\failures\round185_run4_note1331_neighbor_bounds.png"
call :delete "output\geometry_scene_v2\failures\round185_run4_note1331_note1410_source_1698_1714.png"
call :delete "output\geometry_scene_v2\failures\round185_run4_note1331_note1410_source_bounds_review.json"
call :delete "output\geometry_scene_v2\failures\round185_run4_note1331_note1410_source_zoom.png"
call :delete "output\geometry_scene_v2\failures\round185_run4_note1331_patch_source_geometry_check.png"
call :delete "output\geometry_scene_v2\failures\round185_run4_note1331_source_frames_1707_1712.png"
call :delete "output\geometry_scene_v2\failures\round186_run4_note1410_duplicate_suppression_review.json"
call :delete "output\geometry_scene_v2\failures\round186_run4_note1410_frame1704_boxes.png"
call :delete "output\geometry_scene_v2\failures\round186_run4_note1410_geometry_parent_new_check.png"
call :delete "output\geometry_scene_v2\failures\round186_run4_note1410_source_1704_1723.png"
call :delete "output\geometry_scene_v2\failures\round186_run4_note1410_source_1704_1734.png"
call :delete "output\geometry_scene_v2\failures\round186_run4_note1410_source_detail_1708_1719.png"
call :delete "output\geometry_scene_v2\failures\round187_run6_notes3104_3100_source_2684_2715.png"
call :delete "output\geometry_scene_v2\failures\round187_run6_notes3104_3100_source_scene_overlay.png"
call :delete "output\geometry_scene_v2\failures\round187_run6_notes3104_3100_source_tail_zoom.png"
call :delete "output\geometry_scene_v2\failures\round187_run6_notes3104_3100_source_zoom_2695_2711.png"
call :delete "output\geometry_scene_v2\failures\round187_run6_notes3104_3100_tail_identity_review.json"
call :delete "output\geometry_scene_v2\failures\round188_run8_untuned_window_2100_2159_build\comparison.mp4"
call :delete "output\geometry_scene_v2\failures\round188_run8_untuned_window_2100_2159_build\geometry.json"
call :delete "output\geometry_scene_v2\failures\round188_run8_untuned_window_2100_2159_build\geometry.mp4"
call :delete "output\geometry_scene_v2\failures\round188_run8_untuned_window_2100_2159_build\run_manifest.json"
call :delete "output\geometry_scene_v2\failures\round188_run8_untuned_window_2100_2159_build\scene.json"
call :delete "output\geometry_scene_v2\failures\round188_run8_untuned_window_2100_2159_index.csv"
call :delete "output\geometry_scene_v2\failures\round188_run8_untuned_window_2100_2159_source.mp4"
call :delete "output\geometry_scene_v2\failures\round188_run8_untuned_window_evaluation.json"
call :delete "output\geometry_scene_v2\failures\round188_run8_untuned_window_source_contact.png"
call :delete "output\geometry_scene_v2\failures\round188_run8_untuned_window_source_geometry_contact.png"
call :delete "output\geometry_scene_v2\failures\round188_run8_untuned_window_source_geometry_keyframes.png"
call :delete "output\geometry_scene_v2\failures\round189_run5_training_window_890_930_build\comparison.mp4"
call :delete "output\geometry_scene_v2\failures\round189_run5_training_window_890_930_build\geometry.json"
call :delete "output\geometry_scene_v2\failures\round189_run5_training_window_890_930_build\geometry.mp4"
call :delete "output\geometry_scene_v2\failures\round189_run5_training_window_890_930_build\run_manifest.json"
call :delete "output\geometry_scene_v2\failures\round189_run5_training_window_890_930_build\scene.json"
call :delete "output\geometry_scene_v2\failures\round189_run5_training_window_890_930_index.csv"
call :delete "output\geometry_scene_v2\failures\round189_run5_training_window_890_930_source.mp4"
call :delete "output\geometry_scene_v2\failures\round189_run5_training_window_repeatability.json"
call :delete "output\geometry_scene_v2\failures\round189_run5_training_window_source_geometry_contact.png"
call :delete "output\geometry_scene_v2\failures\round18_component_anchor_training_and_frozen_holdout.json"
call :delete "output\geometry_scene_v2\failures\round18_run1_component_anchored_trial_scene.json"
call :delete "output\geometry_scene_v2\failures\round18_run1_component_anchored_windowA.png"
call :delete "output\geometry_scene_v2\failures\round18_run1_component_anchored_windowB.png"
call :delete "output\geometry_scene_v2\failures\round18_run1_stationary_hold_candidate_alignment.json"
call :delete "output\geometry_scene_v2\failures\round18_run1_stationary_hold_candidate_alignment_review.png"
call :delete "output\geometry_scene_v2\failures\round18_run8_frozen_holdout_frame_context.png"
call :delete "output\geometry_scene_v2\failures\round18_run8_frozen_holdout_miss.json"
call :delete "output\geometry_scene_v2\failures\round190_run5_note641_note666_source_overlay_912_924.png"
call :delete "output\geometry_scene_v2\failures\round190_run5_note641_note666_tail_window_review.json"
call :delete "output\geometry_scene_v2\failures\round191_run2_candidate_face_geometry_review.png"
call :delete "output\geometry_scene_v2\failures\round191_run2_note1689_note1709_native_crop.png"
call :delete "output\geometry_scene_v2\failures\round191_run2_note1689_note1709_source_bounds_review.json"
call :delete "output\geometry_scene_v2\failures\round192_run1_note709_parallel_hold_native_detail.png"
call :delete "output\geometry_scene_v2\failures\round192_run1_note709_parallel_hold_native_review.png"
call :delete "output\geometry_scene_v2\failures\round192_run1_note709_parallel_hold_review.json"
call :delete "output\geometry_scene_v2\failures\round192_run1_note709_right_path_detail.png"
call :delete "output\geometry_scene_v2\failures\round193_run4_note1897_note1910_overlap_review.png"
call :delete "output\geometry_scene_v2\failures\round193_run4_note1910_candidate_review.png"
call :delete "output\geometry_scene_v2\failures\round193_run4_note1910_continuation_review.png"
call :delete "output\geometry_scene_v2\failures\round193_run4_note1910_source_continuation.json"
call :delete "output\geometry_scene_v2\failures\round194_run7_note4444_alternating_hold_candidate.png"
call :delete "output\geometry_scene_v2\failures\round194_run7_note4444_full_window_review.png"
call :delete "output\geometry_scene_v2\failures\round194_run7_note4444_geometry_before_after.png"
call :delete "output\geometry_scene_v2\failures\round194_run7_note4444_review.json"
call :delete "output\geometry_scene_v2\failures\round195_run3_note443_tail_jump_review.png"
call :delete "output\geometry_scene_v2\failures\round195_run3_note443_tail_review.json"
call :delete "output\geometry_scene_v2\failures\round196_run6_note3535_revision11_review.png"
call :delete "output\geometry_scene_v2\failures\round196_run6_note3535_tail_switch_review.json"
call :delete "output\geometry_scene_v2\failures\round196_run6_note3535_tail_switch_review.png"
call :delete "output\geometry_scene_v2\failures\round197_run1_note1508_tail_review.json"
call :delete "output\geometry_scene_v2\failures\round197_run1_note1508_tail_transition.png"
call :delete "output\geometry_scene_v2\failures\round198_run2_note965_tail_review.json"
call :delete "output\geometry_scene_v2\failures\round198_run2_note965_tail_switch_review.png"
call :delete "output\geometry_scene_v2\failures\round199_run3_note1959_tail_jump_review.png"
call :delete "output\geometry_scene_v2\failures\round199_run3_note1959_tail_review.json"
call :delete "output\geometry_scene_v2\failures\round19_observed_head_short_tail_failure.json"
call :delete "output\geometry_scene_v2\failures\round19_run1_observed_head_short_tail_trial_scene.json"
call :delete "output\geometry_scene_v2\failures\round19_run1_observed_head_windowA.png"
call :delete "output\geometry_scene_v2\failures\round19_run1_observed_head_windowB.png"
call :delete "output\geometry_scene_v2\failures\round200_run4_note2308_full_tail_window_review.png"
call :delete "output\geometry_scene_v2\failures\round200_run4_note2308_lane_tail_review.json"
call :delete "output\geometry_scene_v2\failures\round200_run4_note2308_postflash_tail_review.png"
call :delete "output\geometry_scene_v2\failures\round200_run4_note2308_revision19_review.png"
call :delete "output\geometry_scene_v2\failures\round201_run6_notes3100_3104_tail_review.json"
call :delete "output\geometry_scene_v2\failures\round201_run6_notes3100_3104_tail_switch_source_geometry.png"
call :delete "output\geometry_scene_v2\failures\round201_run6_tail_candidates_native_2704_2710.png"
call :delete "output\geometry_scene_v2\failures\round202_run3_note443_extended_tail_review.json"
call :delete "output\geometry_scene_v2\failures\round202_run3_note443_extended_tail_source_geometry.png"
call :delete "output\geometry_scene_v2\failures\round203_run5_note619_source_geometry_895_904.png"
call :delete "output\geometry_scene_v2\failures\round203_run5_note619_source_review.json"
call :delete "output\geometry_scene_v2\failures\round204_run4_note1071_post_effect_1460_1475_source_geometry.png"
call :delete "output\geometry_scene_v2\failures\round204_run4_note1071_post_effect_review.json"
call :delete "output\geometry_scene_v2\failures\round20_run1_shared_component_ambiguity.json"
call :delete "output\geometry_scene_v2\failures\round21_run1_cut_mask_ambiguity.json"
call :delete "output\geometry_scene_v2\failures\round21_run1_cut_mask_frame961.png"
call :delete "output\geometry_scene_v2\failures\round22_run1_cut_component_no_safe_anchor.json"
call :delete "output\geometry_scene_v2\failures\round23_run1_f955_970_source_contact.png"
call :delete "output\geometry_scene_v2\failures\round23_run1_source_frame970.png"
call :delete "output\geometry_scene_v2\failures\round23_run1_source_identity_unresolved.json"
call :delete "output\geometry_scene_v2\failures\round24_cross_run_hold_tail_direction.json"
call :delete "output\geometry_scene_v2\failures\round24_run2_revision04_frame1049.png"
call :delete "output\geometry_scene_v2\failures\round24_run2_revision04_frame3147.png"
call :delete "output\geometry_scene_v2\failures\round25_run3_direction_guard_audit.json"
call :delete "output\geometry_scene_v2\failures\round25_run3_revision04_frame1839.png"
call :delete "output\geometry_scene_v2\failures\round26_run4_direction_guard_audit.json"
call :delete "output\geometry_scene_v2\failures\round26_run4_revision04_frame1524.png"
call :delete "output\geometry_scene_v2\failures\round27_run6_direction_guard_audit.json"
call :delete "output\geometry_scene_v2\failures\round27_run6_revision04_frame1090.png"
call :delete "output\geometry_scene_v2\failures\round28_run7_direction_guard_audit.json"
call :delete "output\geometry_scene_v2\failures\round28_run7_revision04_frame1039.png"
call :delete "output\geometry_scene_v2\failures\round29_run8_frozen_holdout_miss.json"
call :delete "output\geometry_scene_v2\failures\round29_run8_revision04_frame270.png"
call :delete "output\geometry_scene_v2\failures\round30_cross_run_lane_drift.json"
call :delete "output\geometry_scene_v2\failures\round30_run1_lane_drift_frame1380.png"
call :delete "output\geometry_scene_v2\failures\round31_run1_head_only_filter_audit.json"
call :delete "output\geometry_scene_v2\failures\round31_run1_head_only_review.png"
call :delete "output\geometry_scene_v2\failures\round32_run2_head_only_audit.json"
call :delete "output\geometry_scene_v2\failures\round32_run2_head_only_review.png"
call :delete "output\geometry_scene_v2\failures\round33_run3_head_only_audit.json"
call :delete "output\geometry_scene_v2\failures\round33_run3_head_only_review.png"
call :delete "output\geometry_scene_v2\failures\round34_run4_head_only_visible_tap_miss.json"
call :delete "output\geometry_scene_v2\failures\round34_run4_head_only_visible_tap_miss.png"
call :delete "output\geometry_scene_v2\failures\round35_run5_head_only_tap_gap.json"
call :delete "output\geometry_scene_v2\failures\round35_run5_head_only_tap_gap.png"
call :delete "output\geometry_scene_v2\failures\round36_run6_head_only_visible_tap_miss.json"
call :delete "output\geometry_scene_v2\failures\round36_run6_head_only_visible_tap_miss.png"
call :delete "output\geometry_scene_v2\failures\round37_run7_head_only_visible_tap_miss.json"
call :delete "output\geometry_scene_v2\failures\round37_run7_head_only_visible_tap_miss.png"
call :delete "output\geometry_scene_v2\failures\round38_run4_unresolved_cyan_tap.json"
call :delete "output\geometry_scene_v2\failures\round38_run4_unresolved_cyan_tap.png"
call :delete "output\geometry_scene_v2\failures\round39_run4_cyan_tap_ambiguous.json"
call :delete "output\geometry_scene_v2\failures\round39_run4_cyan_tap_ambiguous_source_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round40_run7_recovery_tap_gap.json"
call :delete "output\geometry_scene_v2\failures\round41_run7_recovery_link_anchor_gate.json"
call :delete "output\geometry_scene_v2\failures\round42_run7_link_1039_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round42_run7_link_1085_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round42_run7_link_1093_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round42_run7_link_1588_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round42_run7_link_2207_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round42_run7_recovery_link_review.json"
call :delete "output\geometry_scene_v2\failures\round43_run7_selected_recovery.json"
call :delete "output\geometry_scene_v2\failures\round43_run7_selected_recovery_review.jpg"
call :delete "output\geometry_scene_v2\failures\round44_run4_singleton_negative.json"
call :delete "output\geometry_scene_v2\failures\round45_run8_frozen_holdout.json"
call :delete "output\geometry_scene_v2\failures\round46_run6_frame1100_unresolved.json"
call :delete "output\geometry_scene_v2\failures\round47_run6_recovery_trace.json"
call :delete "output\geometry_scene_v2\failures\round47_run6_source_frames1093_1107.jpg"
call :delete "output\geometry_scene_v2\failures\round48_run6_line_overlap_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round48_run6_line_overlap_diagnostic.json"
call :delete "output\geometry_scene_v2\failures\round49_recovery_width_gate.json"
call :delete "output\geometry_scene_v2\failures\round49_run7_positive_control_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round50_run1_frame970_hold_observation.json"
call :delete "output\geometry_scene_v2\failures\round50_run1_frame970_hold_observation_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round51_run1_right_hold_candidate.json"
call :delete "output\geometry_scene_v2\failures\round51_run1_right_hold_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round52_run5_frame898_902_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round52_run5_frame900_hold_endpoint_review.json"
call :delete "output\geometry_scene_v2\failures\round53_run4_cyan_singleton_review.json"
call :delete "output\geometry_scene_v2\failures\round53_run4_frame1002_1010_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round54_run7_2206_2211_identity_review.jpg"
call :delete "output\geometry_scene_v2\failures\round54_run7_2207_identity_ambiguity.json"
call :delete "output\geometry_scene_v2\failures\round55_generic_clip_pipeline.json"
call :delete "output\geometry_scene_v2\failures\round56_all_run_scene_media_structure.json"
call :delete "output\geometry_scene_v2\failures\round57_run1_frame1041_1049_hold_identity.jpg"
call :delete "output\geometry_scene_v2\failures\round57_run1_frame1045_hold_identity.json"
call :delete "output\geometry_scene_v2\failures\round58_all_run_keyframe_timestamps.json"
call :delete "output\geometry_scene_v2\failures\round59_run1_left_hold_candidate.json"
call :delete "output\geometry_scene_v2\failures\round59_run1_left_hold_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round60_latest_all_run_validation.json"
call :delete "output\geometry_scene_v2\failures\round61_run1_component_continuity.json"
call :delete "output\geometry_scene_v2\failures\round61_run1_component_continuity_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round62_latest_all_run_validation.json"
call :delete "output\geometry_scene_v2\failures\round63_run1_continuity_threshold.json"
call :delete "output\geometry_scene_v2\failures\round63_run1_continuity_threshold_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round64_latest_all_run_validation.json"
call :delete "output\geometry_scene_v2\failures\round65_run4_cyan_context_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round65_run4_cyan_temporal_motion.json"
call :delete "output\geometry_scene_v2\failures\round66_run1_candidate_provenance_audit.json"
call :delete "output\geometry_scene_v2\failures\round67_run1_component_masks.jpg"
call :delete "output\geometry_scene_v2\failures\round67_run1_component_separation_review.json"
call :delete "output\geometry_scene_v2\failures\round68_run5_hold_context_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round68_run5_hold_endpoint_review.json"
call :delete "output\geometry_scene_v2\failures\round69_run7_candidate_trial_revision06\comparison.mp4"
call :delete "output\geometry_scene_v2\failures\round69_run7_candidate_trial_revision06\geometry.mp4"
call :delete "output\geometry_scene_v2\failures\round69_run7_candidate_trial_revision06\run_manifest.json"
call :delete "output\geometry_scene_v2\failures\round69_run7_candidate_trial_revision06\scene.json"
call :delete "output\geometry_scene_v2\failures\round69_run7_cyan_motion_association.json"
call :delete "output\geometry_scene_v2\failures\round70_run7_revision06_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round70_run7_revision06_trial_rejected.json"
call :delete "output\geometry_scene_v2\failures\round71_run7_post_hit_effect_truncation.json"
call :delete "output\geometry_scene_v2\failures\round71_run7_revision07_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round72_latest_all_run_validation.json"
call :delete "output\geometry_scene_v2\failures\round73_run1_wide_tap_candidate_review.json"
call :delete "output\geometry_scene_v2\failures\round73_run1_wide_tap_context_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round74_run3_note204_association_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round74_run3_note204_association_review.json"
call :delete "output\geometry_scene_v2\failures\round75_run1_note1540_width_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round75_run1_note1540_width_review.json"
call :delete "output\geometry_scene_v2\failures\round76_run6_note438_duplicate_effect_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round76_run6_note438_duplicate_effect_review.json"
call :delete "output\geometry_scene_v2\failures\round77_run4_note166_beam_fragment_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round77_run4_note166_beam_fragment_review.json"
call :delete "output\geometry_scene_v2\failures\round78_run2_note274_lane_association_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round78_run2_note274_lane_association_review.json"
call :delete "output\geometry_scene_v2\failures\round79_run2_blue_plate_source.jpg"
call :delete "output\geometry_scene_v2\failures\round79_run2_yellow_plate_context.jpg"
call :delete "output\geometry_scene_v2\failures\round79_run2_yellow_plate_reconstruction.json"
call :delete "output\geometry_scene_v2\failures\round79_run2_yellow_plate_source_detail.jpg"
call :delete "output\geometry_scene_v2\failures\round80_latest_all_run_validation.json"
call :delete "output\geometry_scene_v2\failures\round81_run5_hold_ending_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round81_run5_hold_endpoint_review.json"
call :delete "output\geometry_scene_v2\failures\round82_run6_note475_endpoint_review.json"
call :delete "output\geometry_scene_v2\failures\round82_run6_note475_source_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round83_run1_hold970_review.json"
call :delete "output\geometry_scene_v2\failures\round83_run1_hold970_source_context.jpg"
call :delete "output\geometry_scene_v2\failures\round83_run1_hold970_source_geometry_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round84_run1_left_hold_reconstruction.json"
call :delete "output\geometry_scene_v2\failures\round84_run1_left_hold_reconstruction_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round84_run1_left_hold_source_contact_1.jpg"
call :delete "output\geometry_scene_v2\failures\round84_run1_left_hold_source_contact_2.jpg"
call :delete "output\geometry_scene_v2\failures\round84_run1_left_hold_source_contact_3.jpg"
call :delete "output\geometry_scene_v2\failures\round84_run1_left_hold_source_contact_4.jpg"
call :delete "output\geometry_scene_v2\failures\round85_run1_hold_tail_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round85_run1_hold_tail_extension.json"
call :delete "output\geometry_scene_v2\failures\round85_run1_hold_tail_source_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round86_run4_note166_comparison_review.jpg"
call :delete "output\geometry_scene_v2\failures\round86_run4_note166_source_review.jpg"
call :delete "output\geometry_scene_v2\failures\round86_run4_note166_unbracketed_occlusion_metadata.json"
call :delete "output\geometry_scene_v2\failures\round87_run6_note475_tail_ambiguity.json"
call :delete "output\geometry_scene_v2\failures\round87_run6_note475_tail_ambiguity_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round88_run3_note204_comparison_review.jpg"
call :delete "output\geometry_scene_v2\failures\round88_run3_note204_cross_lane_association.json"
call :delete "output\geometry_scene_v2\failures\round88_run3_note204_source_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round89_run8_frozen_holdout_recheck.json"
call :delete "output\geometry_scene_v2\failures\round90_run3_tap_comparison_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round90_run3_tap_reconstruction.json"
call :delete "output\geometry_scene_v2\failures\round90_run3_tap_source_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round91_run3_comparison_detail.jpg"
call :delete "output\geometry_scene_v2\failures\round91_run3_comparison_timeline.jpg"
call :delete "output\geometry_scene_v2\failures\round91_run3_scene_window_review.json"
call :delete "output\geometry_scene_v2\failures\round91_run3_source_context.jpg"
call :delete "output\geometry_scene_v2\failures\round91_run3_source_timeline.jpg"
call :delete "output\geometry_scene_v2\failures\round92_run1_hold_review.json"
call :delete "output\geometry_scene_v2\failures\round92_run1_hold_review_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round93_run5_note641_comparison_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round93_run5_note641_source_head_measurement_contact.jpg"
call :delete "output\geometry_scene_v2\failures\round93_run5_note641_visible_head_reconstruction.json"
call :delete "output\geometry_scene_v2\failures\round94_run5_note666_review.json"
call :delete "output\geometry_scene_v2\failures\round94_run5_note666_selected_source_frames.png"
call :delete "output\geometry_scene_v2\failures\round94_run5_note666_source_detail_frames.png"
call :delete "output\geometry_scene_v2\failures\round94_run5_note666_source_geometry_contact.png"
call :delete "output\geometry_scene_v2\failures\round95_run5_note666_frames945_964_source.png"
call :delete "output\geometry_scene_v2\failures\round95_run5_note666_frames965_984_source.png"
call :delete "output\geometry_scene_v2\failures\round95_run5_note666_postflash_review.json"
call :delete "output\geometry_scene_v2\failures\round95_run5_note666_source_scene_frames950_982.png"
call :delete "output\geometry_scene_v2\failures\round96_run7_note2855_endpoint_review.json"
call :delete "output\geometry_scene_v2\failures\round96_run7_note2855_source_frames2202_2220.png"
call :delete "output\geometry_scene_v2\failures\round96_run7_note2855_source_scene_contact.png"
call :delete "output\geometry_scene_v2\failures\round97_run6_note475_duplicate_suppression.json"
call :delete "output\geometry_scene_v2\failures\round97_run6_note475_source_native_crops.png"
call :delete "output\geometry_scene_v2\failures\round97_run6_note475_trial_source_geometry_contact.png"
call :delete "output\geometry_scene_v2\failures\round98_run2_yellow_lane_guide_review.json"
call :delete "output\geometry_scene_v2\failures\round99_run4_cyan_frames1002_1012.png"
call :delete "output\geometry_scene_v2\failures\round99_run4_cyan_judgement_zoom1003_1010.png"
call :delete "output\geometry_scene_v2\failures\round99_run4_cyan_singleton_review.json"
call :delete "output\geometry_scene_v2\failures\round_03_hold_component_role_ambiguity.json"
call :delete "output\geometry_scene_v2\failures\round_04_tap_shape_and_source_size_lost.json"
call :delete "output\geometry_scene_v2\failures\round_08_hold_component_endpoint_probe.json"
call :delete "output\geometry_scene_v2\failures\round_14_scene_build_summary_run_id_mismatch.json"
call :delete "output\geometry_scene_v2\failures\round_15_probe_setup_missing_cleaned_scratch.json"
call :delete "output\geometry_scene_v2\failures\round_16_run5_inferred_occlusion_frame_300.png"
call :delete "output\geometry_scene_v2\failures\round_16_run5_inferred_occlusion_renderer_omission.json"
call :delete "output\geometry_scene_v2\failures\round_16_run5_source_temporal_context_frames_270_330.jpg"
call :delete "output\geometry_scene_v2\failures\run7_note2784_frame2142_full.png"
call :delete "output\geometry_scene_v2\failures\run7_note2784_native_crop.png"
call :delete "output\geometry_scene_v2\geometries\run_20261106T164049_800126Z.json"
call :delete "output\geometry_scene_v2\geometries\run_20261106T164704_064294Z.json"
call :delete "output\geometry_scene_v2\geometries\run_20261106T164959_579760Z.json"
call :delete "output\geometry_scene_v2\geometries\run_20261106T170057_932173Z.json"
call :delete "output\geometry_scene_v2\geometries\run_20261106T170845_579909Z.json"
call :delete "output\geometry_scene_v2\geometries\run_20261106T171405_612600Z.json"
call :delete "output\geometry_scene_v2\geometries\run_20261106T172037_662313Z.json"
call :delete "output\geometry_scene_v2\geometries\run_20261106T172404_427324Z.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_100.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_101.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_102.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_103.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_104.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_105.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_106.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_107.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_108.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_109.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_110.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_111.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_112.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_113.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_114.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_115.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_116.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_117.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_118.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_119.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_120.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_121.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_122.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_123.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_124.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_125.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_126.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_127.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_128.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_129.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_130.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_131.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_132.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_133.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_134.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_135.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_136.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_137.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_138.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_139.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_140.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_141.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_142.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_143.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_144.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_145.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_146.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_147.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_148.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_149.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_150.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_151.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_152.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_153.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_154.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_155.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_156.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_157.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_158.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_159.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_160.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_161.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_162.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_163.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_164.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_165.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_166.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_167.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_168.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_169.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_17.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_170.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_171.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_172.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_173.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_174.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_175.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_176.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_177.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_178.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_179.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_18.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_180.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_181.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_182.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_183.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_184.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_185.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_186.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_187.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_188.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_189.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_19.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_190.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_191.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_192.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_193.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_194.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_195.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_196.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_197.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_198.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_199.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_20.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_200.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_201.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_202.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_203.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_204.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_21.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_22.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_23.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_24.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_25.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_26.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_27.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_28.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_29.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_30.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_31.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_32.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_33.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_34.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_35.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_36.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_37.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_38.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_39.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_40.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_41.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_42.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_43.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_44.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_45.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_46.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_47.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_48.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_49.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_50.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_51.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_52.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_53.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_54.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_55.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_56.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_57.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_58.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_59.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_60.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_61.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_62.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_63.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_64.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_65.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_66.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_67.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_68.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_69.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_70.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_71.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_72.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_73.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_74.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_75.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_76.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_77.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_78.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_79.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_80.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_81.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_82.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_83.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_84.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_85.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_86.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_87.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_88.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_89.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_90.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_91.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_92.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_93.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_94.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_95.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_96.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_97.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_98.json"
call :delete "output\geometry_scene_v2\provenance\cleanup_manifest_round_99.json"
call :delete "output\geometry_scene_v2\provenance\generalization_probe_640x360.json"
call :delete "output\geometry_scene_v2\provenance\generalization_probe_run2_derived_segment.json"
call :delete "output\geometry_scene_v2\provenance\indexed_clip_probe_run2_derived_segment.json"
call :delete "output\geometry_scene_v2\provenance\round161_run8_note7_hsv_tail_candidate_observations.json"
call :delete "output\geometry_scene_v2\provenance\round39_run4_queue_detail_run_manifest.json"
call :delete "output\geometry_scene_v2\provenance\round39_run4_queue_detail_scene.json"
call :delete "output\geometry_scene_v2\provenance\round40_run7_baseline_run_manifest.json"
call :delete "output\geometry_scene_v2\provenance\round40_run7_baseline_scene.json"
call :delete "output\geometry_scene_v2\provenance\round41_run7_pre_anchorfix_run_manifest.json"
call :delete "output\geometry_scene_v2\provenance\round41_run7_pre_anchorfix_scene.json"
call :delete "output\geometry_scene_v2\provenance\round42_run7_recovery_link_run_manifest.json"
call :delete "output\geometry_scene_v2\provenance\round42_run7_recovery_link_scene.json"
call :delete "output\geometry_scene_v2\provenance\round44_run4_singleton_negative_scene.json"
call :delete "output\geometry_scene_v2\provenance\round45_run8_frozen_holdout_scene.json"
call :delete "output\geometry_scene_v2\provenance\round46_run6_frame1100_diagnostic_scene.json"
call :delete "output\geometry_scene_v2\provenance\round47_run6_run6_frame1100_recovery_trace_scene.json"
call :delete "output\geometry_scene_v2\provenance\round48_run6_frame1099_1102_observations.json"
call :delete "output\geometry_scene_v2\provenance\round49_run4_negative_scene.json"
call :delete "output\geometry_scene_v2\provenance\round49_run6_width_gate_scene.json"
call :delete "output\geometry_scene_v2\provenance\round49_run7_positive_control_observations.json"
call :delete "output\geometry_scene_v2\provenance\round49_run7_positive_scene.json"
call :delete "output\geometry_scene_v2\provenance\round50_run1_frame970_perception_observations.json"
call :delete "output\geometry_scene_v2\provenance\round51_run1_component_trace.json"
call :delete "output\geometry_scene_v2\provenance\round52_run5_frame900_observations.json"
call :delete "output\geometry_scene_v2\provenance\round53_run4_cyan_singleton_observation.json"
call :delete "output\geometry_scene_v2\provenance\round54_run7_2207_track_observation.json"
call :delete "output\geometry_scene_v2\provenance\round57_run1_frame1045_hold_observations.json"
call :delete "output\geometry_scene_v2\provenance\round59_run1_left_hold_component_trace.json"
call :delete "output\geometry_scene_v2\provenance\round61_run1_component_continuity_trace.json"
call :delete "output\geometry_scene_v2\provenance\round63_run1_continuity_threshold_trace.json"
call :delete "output\geometry_scene_v2\provenance\round65_run4_cyan_temporal_trace.json"
call :delete "output\geometry_scene_v2\provenance\round66_run1_candidate_width_lineage.json"
call :delete "output\geometry_scene_v2\provenance\round67_run1_component_separation_trace.json"
call :delete "output\geometry_scene_v2\provenance\round68_run5_hold_point_mask_trace.json"
call :delete "output\geometry_scene_v2\provenance\round69_run7_cyan_window_observations.json"
call :delete "output\geometry_scene_v2\provenance\round_16_all_runs_frame_300_renderer_review.jpg"
call :delete "output\geometry_scene_v2\provenance\round_16_renderer_inferred_occlusion_check.json"
call :delete "output\geometry_scene_v2\renderer_smoke_v1_3.mp4"
call :delete "output\geometry_scene_v2\renderer_smoke_v1_3_scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_02\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_02\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_02\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_03\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_03\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_03\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_03\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_04\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_04\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_04\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_04\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_05\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_05\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_05\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_05\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_06\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_06\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_06\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_06\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_07\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_07\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_07\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_07\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_08\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_08\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_08\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_08\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_09\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_09\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_09\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_09\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_10\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_10\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_10\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_10\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_11\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_11\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_11\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_11\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_12\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_12\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_12\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_12\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_13\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_13\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_13\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_13\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_14\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_14\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_14\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_14\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_15\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_15\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_15\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_15\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_16\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_16\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_16\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_16\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_17\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_17\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_17\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_17\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_18\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_18\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_18\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_18\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_19\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_19\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_19\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_19\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_20\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_20\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_20\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\revision_20\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164049_800126Z\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_01\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_01\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_01\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_01\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_02\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_02\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_02\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_02\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_03\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_03\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_03\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_03\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_04\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_04\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_04\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_04\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_05\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_05\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_05\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_05\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_06\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_06\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_06\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_07\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_07\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_07\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_07\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_08\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_08\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_08\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_08\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_09\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_09\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_09\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_09\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_10\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_10\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_10\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_10\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_11\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_11\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_11\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_11\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_12\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_12\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_12\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164704_064294Z\revision_12\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_01\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_01\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_01\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_01\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_02\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_02\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_02\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_02\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_03\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_03\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_03\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_03\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_04\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_04\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_04\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_04\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_05\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_05\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_05\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_05\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_06\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_06\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_06\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_06\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_07\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_07\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_07\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_07\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_08\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_08\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_08\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_08\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_09\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_09\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_09\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_09\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_10\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_10\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_10\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_10\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_11\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_11\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_11\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_11\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_12\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_12\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_12\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_12\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_13\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_13\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_13\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_13\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_14\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_14\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_14\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_14\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_15\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_15\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_15\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T164959_579760Z\revision_15\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_01\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_01\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_01\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_01\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_02\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_02\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_02\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_02\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_03\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_03\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_03\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_03\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_04\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_04\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_04\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_04\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_05\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_05\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_05\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_05\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_06\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_06\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_06\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_06\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_07\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_07\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_07\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_07\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_08\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_08\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_08\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_08\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_09\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_09\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_09\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_09\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_10\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_10\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_10\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_10\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_11\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_11\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_11\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_11\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_12\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_12\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_12\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_12\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_13\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_13\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_13\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_13\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_14\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_14\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_14\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_14\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_15\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_15\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_15\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_15\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_16\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_16\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_16\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_16\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_17\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_17\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_17\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_17\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_18\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_18\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_18\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170057_932173Z\revision_18\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_01\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_01\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_01\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_01\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_02\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_02\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_02\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_02\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_03\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_03\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_03\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_03\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_04\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_04\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_04\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_04\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_05\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_05\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_05\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_05\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_06\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_06\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_06\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_06\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_08\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_08\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_08\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T170845_579909Z\revision_08\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_01\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_01\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_01\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_01\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_02\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_02\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_02\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_02\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_03\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_03\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_03\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_03\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_04\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_04\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_04\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_04\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_05\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_05\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_05\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_05\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_06\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_06\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_06\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_06\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_07\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_07\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_07\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_07\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_08\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_08\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_08\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_08\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_09\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_09\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_09\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_09\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_10\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_10\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_10\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T171405_612600Z\revision_10\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_01\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_01\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_01\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_01\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_02\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_02\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_02\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_02\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_03\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_03\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_03\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_03\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_04\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_04\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_04\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_04\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_05\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_05\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_05\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_05\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_07\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_07\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_07\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_07\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_08\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_08\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_08\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_08\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_09\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_09\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_09\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_09\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_10\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_10\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_10\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_11\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_11\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_11\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_11\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_12\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_12\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_12\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172037_662313Z\revision_12\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_01\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_01\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_01\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_01\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_02\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_02\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_02\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_02\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_03\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_03\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_03\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_03\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_04\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_04\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_04\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_04\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_05\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_05\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_05\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_05\scene.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_06\comparison.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_06\geometry.mp4"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_06\run_manifest.json"
call :delete "output\geometry_scene_v2\scenes\run_20261106T172404_427324Z\revision_06\scene.json"
for /f "delims=" %%D in ('dir /ad /b /s "%TARGET%" ^| sort /r') do rd "%%D" 2>nul
if "%FAILED%"=="1" goto :partial
echo Cleanup complete. Deleted %DELETED_COUNT% files; final results and code were not targeted.
goto :end
:check
if not exist "%ROOT%%~1" (echo MISSING: %~1& exit /b 1)
for %%F in ("%ROOT%%~1") do if not "%%~zF"=="%~2" (echo CHANGED: %~1& exit /b 1)
exit /b 0
:delete
if not exist "%ROOT%%~1" (echo MISSING DURING DELETE: %~1& set "FAILED=1"& exit /b 0)
del /f /q "%ROOT%%~1" >nul 2>&1
if exist "%ROOT%%~1" (echo FAILED: %~1& set "FAILED=1") else set /a DELETED_COUNT+=1
exit /b 0
:preflight_failed
echo Preflight failed. No files were deleted. Compare this script with its manifest.
exit /b 3
:wrong_root
echo Refusing to run: this file must be located in C:\Users\USER\Desktop\holodream.
exit /b 2
:cancelled
echo Cancelled; no files were deleted.
goto :end
:partial
echo Some files could not be deleted. Check the FAILED lines above.
:end
endlocal
