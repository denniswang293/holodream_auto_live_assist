import cv2
import numpy as np
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from src.diagnostics import raw_identity_trace, pack_identity_trace, trace_planes
from src.lane_segmentation import LanePixelSegmenter, _bool_region_row_bounds
from src.model import Geometry
from src.early_perception import EarlyPixelProvider


def color(h, s=220, v=230):
    return tuple(int(x) for x in cv2.cvtColor(
        np.uint8([[[h, s, v]]]), cv2.COLOR_HSV2BGR)[0, 0])


def geometry():
    return Geometry("config/geometry_live_assist.json", plane_width=360)


def test_vectorized_boolean_row_bounds_match_scalar_argmax_for_all_row_shapes():
    region = np.zeros((6, 11), dtype=bool)
    region[1, 0] = True
    region[2, 10] = True
    region[3, 1:3] = True
    region[3, 8:10] = True
    region[4, :] = True
    # Row 0 remains empty; rows may contain separated spans as ribbon
    # curvature/aliasing can create more than one run at a given y.
    first, last = _bool_region_row_bounds(region)
    expected_first = np.asarray([int(np.argmax(row)) for row in region])
    expected_last = np.asarray([region.shape[1] - 1 - int(np.argmax(row[::-1]))
                                for row in region])
    assert np.array_equal(first, expected_first)
    assert np.array_equal(last, expected_last)


def test_hsv_channel_views_match_split_values_and_keep_interleaved_strides():
    bgr = np.arange(7 * 11 * 3, dtype=np.uint8).reshape(7, 11, 3)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    channels = tuple(hsv[:, :, channel] for channel in range(3))

    for view, split in zip(channels, cv2.split(hsv)):
        assert view.shape == split.shape == hsv.shape[:2]
        assert np.array_equal(view, split)
        assert view.strides == (hsv.strides[0], hsv.strides[1])
        assert np.shares_memory(view, hsv)


def test_bool_roi_uint8_view_preserves_connected_component_labels_and_stats():
    source = np.zeros((24, 36), dtype=bool)
    source[2:8, 3:12] = True
    source[10:19, 22:28] = True
    source[14:16, 11:23] = True  # joins the second region under 8-connectivity

    # Include both a normal ROI and a non-contiguous row slice with a larger
    # row stride. A bool pixel is one byte, with foreground represented as 1.
    for roi in (source, source[::2]):
        view = roi.view(np.uint8)
        copied = roi.astype(np.uint8)
        assert view.dtype == np.uint8
        assert np.array_equal(view, copied)

        expected = cv2.connectedComponentsWithStats(copied, 8)
        actual = cv2.connectedComponentsWithStats(view, 8)
        assert actual[0] == expected[0]
        assert np.array_equal(actual[1], expected[1])
        assert np.array_equal(actual[2], expected[2])
        assert np.array_equal(actual[3], expected[3])


def test_class_semantic_masks_stay_zero_outside_lane_y_domain():
    g = geometry()
    image = np.zeros((g.height, g.plane_width, 3), dtype=np.uint8)
    top = max(0, int(np.floor(g.top_y)))
    bottom = min(g.height - 1, int(np.ceil(g.hit_y + 34))) + 1
    # Place class-colored pixels above and below the exact class ROI. These
    # rows must not seed components or enter any exported note/unknown mask.
    if top:
        image[:top, :] = color(27)
    if bottom < g.height:
        image[bottom:, :] = color(62)

    result = LanePixelSegmenter().segment(image, g)
    assert all(mask.shape == (g.height, g.plane_width) and mask.dtype == np.uint8
               for mask in result.masks.values())
    for name in ("tap_face", "hold_head", "hold_body", "hold_tail", "unknown"):
        assert np.count_nonzero(result[name][:top]) == 0
        assert np.count_nonzero(result[name][bottom:]) == 0


def test_tap_recovery_padding_at_top_of_class_roi_keeps_observed_panel():
    g = geometry()
    image = np.zeros((g.height, g.plane_width, 3), dtype=np.uint8)
    roi_top = max(0, int(np.floor(g.top_y)))
    yellow = color(27)
    # A 24px-tall panel is too tall for the direct plate gate, so it is
    # recovered by the morphology path. Its top-edge padding extends above
    # class_roi_top, where the original full-frame mask contained zeros.
    cv2.rectangle(image, (120, roi_top), (236, roi_top + 23), yellow, -1)

    result = LanePixelSegmenter().segment(image, g, frame_index=655)

    taps = [c for c in result.components if c.role == "tap_face" and
            c.bbox[0] == 120 and c.bbox[1] == roi_top]
    assert taps, "top-edge panel recovery must survive ROI-local mask indexing"
    assert np.all(result["tap_face"][roi_top:roi_top + 24, 120:237] == 255)


def test_tap_and_curved_hold_masks_are_observed_pixels():
    g = geometry()
    image = np.zeros((g.height, g.plane_width, 3), dtype=np.uint8)
    image[40:390, 2:358] = color(98, 90, 85)  # observed lane background
    yellow = color(27)
    cv2.rectangle(image, (18, 250), (57, 263), yellow, -1)
    green = color(62)
    curve = np.array([[120, 100], [126, 130], [138, 150], [151, 166], [156, 185]], np.int32)
    cv2.polylines(image, [curve], False, green, 6)
    cv2.rectangle(image, (143, 181), (173, 190), green, -1)

    segmenter = LanePixelSegmenter()
    result = segmenter.segment(image, g, frame_index=294)
    assert result.frame_index == 294
    profile = segmenter.last_profile
    assert {"class_mask_setup_ms", "class_component_loop_ms", "effect_mask_ms",
            "effect_connected_components_ms", "effect_component_loop_ms"} <= profile.keys()
    assert all(profile[name] >= 0 for name in (
        "class_mask_setup_ms", "class_component_loop_ms", "effect_mask_ms",
        "effect_connected_components_ms", "effect_component_loop_ms"))
    assert result.masks.keys() >= {
        "lane", "tap_face", "hold_head", "hold_body", "hold_tail",
        "effect_or_artifact", "unknown", "judgment_line",
    }
    assert np.count_nonzero(result["tap_face"]) > 100
    assert np.count_nonzero(result["hold_body"]) > 100
    assert np.count_nonzero(result["hold_head"]) > 20
    # No rectangle filling: semantic masks can only retain measured source
    # pixels of their color, including the curved ribbon's actual outline.
    green_pixels = np.all(image == np.asarray(green, np.uint8), axis=2)
    yellow_pixels = np.all(image == np.asarray(yellow, np.uint8), axis=2)
    assert np.all(result["hold_body"][~green_pixels] == 0)
    assert np.all(result["hold_head"][~green_pixels] == 0)
    assert np.all(result["tap_face"][~yellow_pixels] == 0)
    assert result["hold_body"][150, 138] == 255
    assert result["hold_body"][130, 126] == 255
    assert result["hold_body"][120, 138] == 0
    assert any(c.role == "hold_head" for c in result.components)
    assert any(c.role == "tap_face" and c.frame_index == 294 for c in result.components)


def test_uncertain_thin_fragment_and_hit_effect_are_not_promoted_to_notes():
    g = geometry()
    image = np.zeros((g.height, g.plane_width, 3), dtype=np.uint8)
    image[40:390, 2:358] = color(98, 90, 85)
    green = color(62)
    cv2.line(image, (85, 160), (112, 160), green, 1)
    cy = int(round(g.hit_y))
    cyan = color(96, 190, 230)
    cv2.line(image, (30, cy), (329, cy), cyan, 2)
    cv2.circle(image, (290, cy - 8), 7, (255, 255, 255), -1)

    result = LanePixelSegmenter().segment(image, g)
    assert np.count_nonzero(result["unknown"]) > 0
    assert np.count_nonzero(result["effect_or_artifact"]) > 0
    assert np.count_nonzero(result["judgment_line"]) > 0
    assert np.count_nonzero(result["tap_face"]) == 0
    assert np.count_nonzero(result["hold_head"]) == 0
    assert np.count_nonzero(result["hold_tail"]) == 0
    assert np.count_nonzero(result["hold_body"]) == 0


def test_extracted_hold_frames_keep_green_ribbon_pixels_separate():
    g = geometry()
    segmenter = LanePixelSegmenter()
    base = Path(__file__).parent / "fixtures" / "v85"
    for filename, index, minimum in (("assist_6_0s_frame_360.png", 360, 5000),
                                     ("assist_4_9s_frame_294.png", 294, 1)):
        source = cv2.imread(str(base / filename))
        assert source is not None
        rectified = g.rectify(g.normalize(source))
        result = segmenter.segment(rectified, g, frame_index=index)
        assert np.count_nonzero(result["hold_body"]) >= minimum
        hsv = cv2.cvtColor(rectified, cv2.COLOR_BGR2HSV)
        observed_green = ((hsv[:, :, 0] >= 40) & (hsv[:, :, 0] <= 83) &
                          (hsv[:, :, 1] >= 55) & (hsv[:, :, 2] >= 105))
        assert np.all(result["hold_body"][~observed_green] == 0)
        bodies = [c for c in result.components if c.role == "hold_body"]
        assert bodies and all(c.frame_index == index for c in bodies)
        # A large, uncertain head/tail is not invented from the component box.
        for end_mask in (result["hold_head"], result["hold_tail"]):
            assert np.all(end_mask[~observed_green] == 0)


def test_recorded_connected_hold_emits_observed_head_plate():
    # Regression frame 77 was a Legacy action candidate with a visible green
    # face attached to a curved ribbon. The earlier width-only endpoint rule
    # labeled the ribbon as body but emitted no Hold head, so Tracker could
    # never confirm that note. The source run is read-only.
    source_path = Path(__file__).parent / "fixtures" / "v85" / "recording_hold_frame_77.png"
    source = cv2.imread(str(source_path))
    assert source is not None
    g = geometry()
    rectified = g.rectify(g.normalize(source))
    result = LanePixelSegmenter().segment(rectified, g, frame_index=77)
    heads = [c for c in result.components if c.role == "hold_head" and c.color == "green"]
    assert heads, "visible green face attached to a curved Hold must create a head candidate"
    face = max(heads, key=lambda c: c.area)
    assert face.bbox[1] >= 250 and face.bbox[3] >= 8
    hsv = cv2.cvtColor(rectified, cv2.COLOR_BGR2HSV)
    observed_green = ((hsv[:, :, 0] >= 40) & (hsv[:, :, 0] <= 83) &
                      (hsv[:, :, 1] >= 55) & (hsv[:, :, 2] >= 105))
    assert np.all(result["hold_head"][~observed_green] == 0)


def test_tap_face_survives_thin_connection_without_filling_pixels():
    g=geometry();image=np.zeros((g.height,g.plane_width,3),np.uint8)
    cyan=color(96,220,230)
    # A true panel is linked to a large cyan HUD/effect region by a thin
    # current-frame stroke. The panel core can be separated by its horizontal
    # shape; the stroke itself must not be filled into the Tap mask.
    cv2.rectangle(image,(220,280),(300,294),cyan,-1)
    cv2.line(image,(0,287),(220,287),cyan,1)
    result=LanePixelSegmenter().segment(image,g,frame_index=97)
    faces=[c for c in result.components if c.role=="tap_face" and c.bbox[0]>=200]
    assert faces
    face=max(faces,key=lambda c:c.area)
    assert face.bbox[2]>=60 and face.bbox[3]>=8
    assert result["tap_face"][287,250]==255
    assert result["tap_face"][287,100]==0
    assert np.all(result["tap_face"][image[:,:,0]==0]==0)


def test_tap_recovery_diagnostics_do_not_change_masks_or_ordered_components():
    g=geometry();image=np.zeros((g.height,g.plane_width,3),np.uint8)
    cyan=color(96,220,230);yellow=color(27)
    cv2.rectangle(image,(220,280),(300,294),cyan,-1)
    cv2.line(image,(0,287),(220,287),cyan,1)
    cv2.rectangle(image,(30,145),(87,158),yellow,-1)

    ordinary=LanePixelSegmenter()
    diagnostic=LanePixelSegmenter()
    ordinary_result=ordinary.segment(image,g,frame_index=500)
    diagnostic.profile_tap_recovery=True
    diagnostic_result=diagnostic.segment(image,g,frame_index=500)

    assert ordinary_result.components==diagnostic_result.components
    assert ordinary_result.frame_index==diagnostic_result.frame_index
    assert ordinary_result.lane_bounds==diagnostic_result.lane_bounds
    assert all(np.array_equal(ordinary_result.masks[name],diagnostic_result.masks[name])
               for name in ordinary_result.masks)
    detail_keys={
        f"tap_recovery_{pass_name}_{field}"
        for pass_name in ("yellow","cyan_global","cyan_tiled")
        for field in ("ms","connected_component_proposals","geometry_qualified_proposals",
                      "accepted_faces","duplicate_rejections")
    }
    detail_keys.add("tap_recovery_cyan_tiled_early_duplicate_prunes")
    assert not (detail_keys & ordinary.last_profile.keys())
    assert detail_keys <= diagnostic.last_profile.keys()
    assert all(diagnostic.last_profile[key]>=0 for key in detail_keys)


def test_cyan_tiled_prunes_global_duplicates_and_keeps_independent_panels():
    g=geometry();image=np.zeros((g.height,g.plane_width,3),np.uint8)
    cyan=color(96,220,230)
    # The thin bridge lets cyan-global recover the broad face. The separate
    # upper-left and right-edge panels must remain independently observable.
    cv2.rectangle(image,(220,280),(300,294),cyan,-1)
    cv2.line(image,(0,287),(220,287),cyan,1)
    cv2.rectangle(image,(28,242),(80,256),cyan,-1)
    cv2.rectangle(image,(306,260),(359,274),cyan,-1)

    ordinary=LanePixelSegmenter()
    diagnostic=LanePixelSegmenter();diagnostic.profile_tap_recovery=True
    ordinary_result=ordinary.segment(image,g,frame_index=503)
    diagnostic_result=diagnostic.segment(image,g,frame_index=503)

    assert ordinary_result.components==diagnostic_result.components
    assert all(np.array_equal(ordinary_result.masks[name],diagnostic_result.masks[name])
               for name in ordinary_result.masks)
    profile=diagnostic.last_profile
    assert profile["tap_recovery_cyan_global_accepted_faces"]>=1
    assert profile["tap_recovery_cyan_tiled_early_duplicate_prunes"]>=1
    assert profile["tap_recovery_cyan_tiled_accepted_faces"]==0
    for x0,x1,y0,y1 in ((220,301,280,295),(28,81,242,257),(306,360,260,275)):
        assert np.count_nonzero(ordinary_result["tap_face"][y0:y1,x0:x1])>0


def test_polygon_opt_out_preserves_segmentation_and_provider_observations():
    g=geometry();image=np.zeros((g.height,g.plane_width,3),dtype=np.uint8)
    green=color(62);cyan=color(96,220,230)
    cv2.line(image,(82,80),(88,212),green,9)
    cv2.rectangle(image,(72,204),(108,226),green,-1)
    cv2.rectangle(image,(185,255),(252,272),cyan,-1)

    polygon_result=LanePixelSegmenter().segment(image,g,frame_index=71)
    compact_result=LanePixelSegmenter().segment(
        image,g,frame_index=71,include_polygons=False)
    assert any(component.polygon for component in polygon_result.components)
    assert all(not component.polygon for component in compact_result.components)
    assert compact_result.components==[
        replace(component,polygon=()) for component in polygon_result.components]
    assert all(np.array_equal(polygon_result.masks[name],compact_result.masks[name])
               for name in polygon_result.masks)

    default_provider=EarlyPixelProvider(g)
    compact_provider=EarlyPixelProvider(g,include_polygons=False)
    assert default_provider.detect(image)==compact_provider.detect(image)
    assert any(component.polygon for component in default_provider.last_result.components)
    assert all(not component.polygon for component in compact_provider.last_result.components)


def test_recorded_connected_cyan_tap_is_recovered_but_hit_glow_is_not():
    # Source video_frame=186 from the immutable recording. Provisional visual
    # pixel ROIs are used only to pin this regression; they are not note GT.
    source_path = Path(__file__).parent / "fixtures" / "v85" / "recording_tap_frame_186.png"
    source = cv2.imread(str(source_path))
    assert source is not None
    g = geometry()
    rectified = g.rectify(g.normalize(source))
    result = LanePixelSegmenter().segment(rectified, g, frame_index=186)
    # The complete visible cyan panel is at x=32..123, y=282..309 after
    # rectification. Cyan mask evidence is joined to a screen-wide component,
    # so the regression is specifically about recovering its local panel core.
    panel = result["tap_face"][282:310, 32:123]
    assert np.count_nonzero(panel) > 700
    hsv = cv2.cvtColor(rectified, cv2.COLOR_BGR2HSV)
    observed_cyan = ((hsv[:, :, 0] >= 84) & (hsv[:, :, 0] <= 112) &
                     (hsv[:, :, 1] >= 65) & (hsv[:, :, 2] >= 135))
    assert np.all(result["tap_face"][~observed_cyan] == 0)
    # The bright, clipped judgment glint at the right edge is intentionally
    # left out of Tap ownership because a complete panel is not visible there.
    assert np.count_nonzero(result["tap_face"][311:324, 292:360]) == 0


def test_thin_color_fragments_remain_unknown_until_full_panel_height():
    g=geometry();cyan=color(96,220,230);segmenter=LanePixelSegmenter()
    for panel_height, expected_role in ((7,"unknown"),(11,"unknown"),(12,"tap_face")):
        image=np.zeros((g.height,g.plane_width,3),np.uint8)
        top=int(g.hit_y-34)
        cv2.rectangle(image,(126,top),(177,top+panel_height-1),cyan,-1)
        result=segmenter.segment(image,g,frame_index=panel_height)
        if expected_role=="unknown":
            assert np.count_nonzero(result["tap_face"])==0
            assert np.count_nonzero(result["unknown"])>=52*panel_height
            fragment=[c for c in result.components
                      if c.role=="unknown" and "partial_color_panel_candidate" in c.positive]
            assert fragment and "visible_panel_height_below_12px" in fragment[0].negative
        else:
            assert np.count_nonzero(result["tap_face"])>=52*panel_height


def test_partial_color_panel_is_preserved_as_pending_not_actionable(monkeypatch):
    g=geometry();cyan=color(96,220,230)
    # Supply a rectified image directly so this test isolates the perception
    # adapter's semantic conversion from the geometric warp.
    monkeypatch.setattr(g,"rectify",lambda image:image)
    image=np.zeros((g.height,g.plane_width,3),np.uint8)
    top=int(g.hit_y-34)
    cv2.rectangle(image,(126,top),(177,top+6),cyan,-1)
    provider=EarlyPixelProvider(g)
    detections=provider.detect(image)
    partial=[d for d in detections if d.color=="cyan" and d.kind=="plate_fragment"]
    assert partial
    assert all(d.semantic_candidate=="pending" and not d.full_face for d in partial)
    assert np.count_nonzero(provider.last_result["tap_face"])==0
    assert np.count_nonzero(provider.last_result["unknown"])>300


def test_recorded_cyan_panel_survives_provider_adapter_as_full_tap():
    source_path=Path(__file__).parent/"fixtures"/"v85"/"recording_tap_frame_186.png"
    source=cv2.imread(str(source_path));assert source is not None
    g=geometry();provider=EarlyPixelProvider(g,birth_zone_end_y=176.75)
    detections=provider.detect(g.normalize(source))
    target=[d for d in detections if d.color=="cyan" and d.bbox[0]==32 and
            d.bbox[1]==282 and d.bbox[2]>=80 and d.bbox[3]>=12]
    assert target,"the recovered source panel must survive segmentation-to-detection conversion"
    assert target[0].kind=="tap" and target[0].semantic_candidate=="tap"
    assert target[0].full_face


def test_conversion_trace_is_opt_in_and_does_not_change_observations(monkeypatch):
    g=geometry();monkeypatch.setattr(g,"rectify",lambda image:image)
    image=np.zeros((g.height,g.plane_width,3),np.uint8)
    green=color(62);cyan=color(96,220,230)
    cv2.line(image,(82,80),(88,212),green,9)
    cv2.rectangle(image,(72,204),(108,226),green,-1)
    cv2.rectangle(image,(185,255),(252,272),cyan,-1)

    realtime=EarlyPixelProvider(g,birth_zone_end_y=176.75)
    diagnostic=EarlyPixelProvider(g,birth_zone_end_y=176.75,record_conversion_trace=True)
    realtime_detections=realtime.detect(image)
    diagnostic_detections=diagnostic.detect(image)

    assert realtime_detections==diagnostic_detections
    assert np.array_equal(realtime.last_path,diagnostic.last_path)
    assert set(np.unique(realtime.last_path)).issubset({0,255})
    assert realtime.last_labels is None
    assert diagnostic.last_labels is None
    expected_count,expected_labels=cv2.connectedComponents(
        (realtime.last_path>0).astype(np.uint8),8)
    realtime_labels=realtime.ensure_last_labels()
    diagnostic_labels=diagnostic.ensure_last_labels()
    assert realtime.ensure_last_labels() is realtime_labels
    assert expected_count==int(realtime_labels.max())+1
    assert np.array_equal(expected_labels,realtime_labels)
    assert np.array_equal(realtime_labels,diagnostic_labels)
    assert realtime.last_result.components==diagnostic.last_result.components
    assert all(np.array_equal(realtime.last_result.masks[name],diagnostic.last_result.masks[name])
               for name in realtime.last_result.masks)
    assert realtime.conversion_trace==[]
    assert diagnostic.conversion_trace
    assert realtime.last_profile["dropped_component_count"]==diagnostic.last_profile["dropped_component_count"]
    assert "drop_reasons" not in realtime.last_profile
    assert "drop_reasons" in diagnostic.last_profile


def test_raw_identity_trace_materializes_exact_lazy_labels(monkeypatch):
    g=geometry();monkeypatch.setattr(g,"rectify",lambda image:image)
    image=np.zeros((g.height,g.plane_width,3),np.uint8)
    provider=EarlyPixelProvider(g,birth_zone_end_y=176.75)
    provider.detect(image)
    assert provider.last_labels is None

    engine=SimpleNamespace(perception=provider,tracker=SimpleNamespace(audit=[]))
    raw=raw_identity_trace(engine,{'detections':[]})
    assert provider.last_labels is not None
    packed=pack_identity_trace(raw)
    planes=trace_planes(packed,provider.last_path.shape)
    expected_count,expected=cv2.connectedComponents(provider.last_path,8)
    assert expected_count==int(planes['labels'].max())+1
    assert np.array_equal(planes['labels'],expected)
    assert np.array_equal(planes['path'],provider.last_path)


def test_neutral_icon_inside_complete_tap_stays_unknown_without_duplicate_observation():
    # Source recording frame 182: a 12x8 neutral icon inside a full cyan Tap
    # face was turned into a second pending observation. In the fixed replay
    # this fragment became a competing confirmed track and made the exact Tap
    # observation ambiguous at frame 186. Keep those pixels UNKNOWN, but do not
    # seed a second track while the same-frame colored face fully contains it.
    path=Path(__file__).parent/"fixtures"/"v85"/"recording_tap_neutral_overlay_frame_182.png"
    source=cv2.imread(str(path));assert source is not None
    g=geometry();provider=EarlyPixelProvider(g,birth_zone_end_y=176.75,record_conversion_trace=True)
    detections=provider.detect(g.normalize(source))

    icon_bbox=(71,257,12,8)
    icon=next(c for c in provider.last_result.components if c.bbox==icon_bbox and
              c.color=="neutral" and "partial_neutral_panel_candidate" in c.positive)
    assert icon.role=="unknown"
    assert np.count_nonzero(provider.last_result["unknown"][257:265,71:83])>0
    assert any(d.color=="cyan" and d.bbox==(32,251,91,28) and
               d.semantic_candidate=="tap" for d in detections)
    assert not any(d.bbox==icon_bbox for d in detections)
    trace=next(row for row in provider.conversion_trace if row.get("bbox")==icon_bbox)
    assert trace["conversion"]=="suppressed_occluded_fragment"
    assert trace["reason"]=="partial_neutral_pixels_occluded_by_complete_tap_face"


def test_neutral_fragment_suppression_requires_small_contained_fragment():
    contained=(71,257,12,8);face=(32,251,91,28)
    assert EarlyPixelProvider._occluded_neutral_fragment(contained,[face])
    # Keep nearby fragments as UNKNOWN tracker evidence; only the visually
    # verified 12x8 glyph signature is suppressed by this adapter rule.
    assert not EarlyPixelProvider._occluded_neutral_fragment((71,257,11,7),[face])
    assert not EarlyPixelProvider._occluded_neutral_fragment((124,257,12,8),[face])
    assert not EarlyPixelProvider._occluded_neutral_fragment((40,254,80,20),[face])


def test_thin_neutral_rail_stays_pending_without_full_face_claim(monkeypatch):
    g=geometry();neutral=color(0,0,210)
    monkeypatch.setattr(g,"rectify",lambda image:image)
    image=np.zeros((g.height,g.plane_width,3),np.uint8)
    y=int(g.hit_y-24)
    cv2.rectangle(image,(126,y),(177,y+2),neutral,-1)
    provider=EarlyPixelProvider(g)
    detections=provider.detect(image)
    partial=[d for d in detections if d.color=="neutral" and d.kind=="plate_fragment"]
    assert partial
    assert all(d.semantic_candidate=="pending" and not d.full_face for d in partial)
    assert np.count_nonzero(provider.last_result["unknown"])>100


def test_yellow_hold_keeps_connected_head_body_and_tail_separate():
    g=geometry();image=np.zeros((g.height,g.plane_width,3),np.uint8);yellow=color(27)
    curve=np.array([[110,70],[112,110],[116,150],[121,190],[125,230]],np.int32)
    cv2.polylines(image,[curve],False,yellow,9)
    cv2.rectangle(image,(108,220),(145,238),yellow,-1)  # moving head
    cv2.rectangle(image,(99,61),(137,80),yellow,-1)     # observed tail
    result=LanePixelSegmenter().segment(image,g,frame_index=12)
    assert np.count_nonzero(result['hold_head'])>100
    assert np.count_nonzero(result['hold_body'])>100
    assert np.count_nonzero(result['hold_tail'])>100
    hold_parts=[c for c in result.components if c.role in ('hold_body','hold_head','hold_tail')]
    groups={c.connection_group_id for c in hold_parts}
    assert len(groups)==1 and None not in groups
    hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV)
    observed_yellow=(hsv[:,:,0]>=16)&(hsv[:,:,0]<40)&(hsv[:,:,1]>=65)&(hsv[:,:,2]>=125)
    for name in ('hold_head','hold_body','hold_tail'):
        assert np.all(result[name][~observed_yellow]==0)


def test_neutral_panel_is_evidence_but_remains_unknown():
    g=geometry();image=np.zeros((g.height,g.plane_width,3),np.uint8)
    neutral=color(0,0,210);cv2.rectangle(image,(180,90),(254,106),neutral,-1)
    result=LanePixelSegmenter().segment(image,g,frame_index=33)
    candidates=[c for c in result.components if 'neutral_full_face_candidate' in c.positive]
    assert len(candidates)==1
    assert candidates[0].role=='unknown'
    assert np.count_nonzero(result['unknown'])>=candidates[0].area
    assert np.count_nonzero(result['tap_face'])==0


def test_two_holds_and_adjacent_tap_keep_independent_pixel_ownership():
    g=geometry();image=np.zeros((g.height,g.plane_width,3),np.uint8)
    green=color(62);cyan=color(96,220,230)
    for x,shift in ((72,0),(238,8)):
        cv2.line(image,(x,85),(x+shift,224),green,9)
        cv2.rectangle(image,(x-15,216),(x+shift+19,238),green,-1)
    cv2.rectangle(image,(155,270),(215,286),cyan,-1)
    result=LanePixelSegmenter().segment(image,g,frame_index=410)
    bodies=[c for c in result.components if c.role=='hold_body' and c.color=='green']
    heads=[c for c in result.components if c.role=='hold_head' and c.color=='green']
    assert len(bodies)==2 and len(heads)==2
    assert len({c.connection_group_id for c in bodies})==2
    for body in bodies:
        same_group=[c for c in bodies+heads if c.connection_group_id==body.connection_group_id]
        assert {c.role for c in same_group}=={'hold_body','hold_head'}
    assert {c.connection_group_id for c in heads}=={c.connection_group_id for c in bodies}
    assert np.count_nonzero(result['tap_face'])>100
    assert all(c.frame_index==410 for c in bodies+heads)
    assert np.count_nonzero(result['hold_body'][:, :130])>0
    assert np.count_nonzero(result['hold_body'][:, 220:])>0
    assert np.count_nonzero(result['hold_body'][:,130:220])==0
    hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV)
    observed_green=(hsv[:,:,0]>=40)&(hsv[:,:,0]<=83)&(hsv[:,:,1]>=55)&(hsv[:,:,2]>=105)
    assert np.all(result['hold_body'][~observed_green]==0)


def test_connection_group_id_survives_lane_observation_and_both_provider_traces():
    from src.lane_filter import LaneFilter
    from tools.replay_lane_filter import SegmentedProvider

    g=geometry();image=np.zeros((g.height,g.plane_width,3),np.uint8);yellow=color(27)
    curve=np.array([[110,70],[112,110],[116,150],[121,190],[125,230]],np.int32)
    cv2.polylines(image,[curve],False,yellow,9)
    cv2.rectangle(image,(108,220),(145,238),yellow,-1)
    cv2.rectangle(image,(99,61),(137,80),yellow,-1)
    g.rectify=lambda frame:frame
    segmented=SegmentedProvider(g)
    segmented.detect(image)
    seg_groups={row['role']:row['connection_group_id'] for row in segmented.conversion_trace
                if row['role'] in ('hold_body','hold_head','hold_tail')}
    assert set(seg_groups)=={'hold_body','hold_head','hold_tail'}
    assert len(set(seg_groups.values()))==1

    early=EarlyPixelProvider(g,record_conversion_trace=True)
    early.detect(image)
    early_groups={row['role']:row['connection_group_id'] for row in early.conversion_trace
                  if row['role'] in ('hold_body','hold_head','hold_tail')}
    assert set(early_groups)=={'hold_body','hold_head','hold_tail'}
    assert len(set(early_groups.values()))==1

    observations, *_ = LaneFilter(g).process_rectified(image,run_id='r',source_frame=1,
        video_frame=1,captured_at=1.,acquired_at=1.)
    hold_rows=[o.csv_row() for o in observations if o.role in ('HOLD_BODY','HOLD_HEAD','HOLD_TAIL')]
    assert {row['connection_group_id'] for row in hold_rows}=={next(iter(seg_groups.values()))}


def test_early_hold_spans_use_only_their_connection_group_and_keep_ambiguity():
    g=geometry();g.rectify=lambda frame:frame
    image=np.zeros((g.height,g.plane_width,3),np.uint8)
    green=color(62);yellow=color(27)
    # The yellow ribbon overlaps the green head's x-range below its endpoint.
    # A frame-wide Hold union therefore gives the green head a false below span.
    cv2.line(image,(196,55),(200,181),green,9)
    cv2.rectangle(image,(174,170),(226,192),green,-1)
    cv2.rectangle(image,(184,46),(215,66),green,-1)
    cv2.line(image,(225,207),(241,318),yellow,9)
    cv2.rectangle(image,(212,306),(258,328),yellow,-1)
    cv2.rectangle(image,(207,193),(238,216),yellow,-1)

    provider=EarlyPixelProvider(g)
    detections=provider.detect(image)
    green_head=next(d for d in detections if d.kind=='hold_head' and d.color=='green')
    yellow_head=next(d for d in detections if d.kind=='hold_head' and d.color=='yellow')
    assert green_head.connection_group_id!=yellow_head.connection_group_id
    assert green_head.below==0
    assert 'physical_owner_not_confirmed_across_frames' in green_head.evidence
    assert 'head_tail_ownership_requires_distinct_endpoint_evidence' in next(
        c.ambiguity for c in provider.last_result.components
        if c.role=='hold_body' and c.connection_group_id==green_head.connection_group_id)
    bodies=[c for c in provider.last_result.components if c.role=='hold_body']
    assert {c.connection_group_id for c in bodies}==set(
        provider.last_result.connection_group_masks)
    for body in bodies:
        bbox,mask=provider.last_result.connection_group_masks[body.connection_group_id]
        assert bbox==body.bbox and mask.dtype==np.bool_
        assert mask.shape==(bbox[3],bbox[2])
        assert np.count_nonzero(mask)==body.area
