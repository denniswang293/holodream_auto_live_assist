import cv2
import numpy as np

from src.lane_segmentation import LanePixelSegmenter
from src.model import Geometry


def color(h, s=220, v=230):
    return tuple(int(x) for x in cv2.cvtColor(
        np.uint8([[[h, s, v]]]), cv2.COLOR_HSV2BGR)[0, 0])


def geometry():
    return Geometry("config/geometry_live_assist.json", plane_width=360)


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

    result = LanePixelSegmenter().segment(image, g, frame_index=294)
    assert result.frame_index == 294
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
    base = "output/analysis_lane_filter_v84_rework/annotations/review_frames"
    for index, timestamp, minimum in ((360, "6.0s", 5000), (294, "4.9s", 1)):
        path = f"{base}/frame_{index:06d}_{timestamp}_source.png"
        source = cv2.imread(path)
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
    source_path = "output/recording/run_20261106T164049_800126Z/live_source.mp4"
    cap = cv2.VideoCapture(source_path)
    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 77)
        ok, source = cap.read()
    finally:
        cap.release()
    assert ok and source is not None
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
