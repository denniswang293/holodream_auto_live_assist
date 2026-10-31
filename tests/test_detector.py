import json
from pathlib import Path
import cv2
import numpy as np
from src.detector import detect
from src.geometry import Playfield


def run(frame):
    cfg = json.loads((Path(__file__).resolve().parents[1]/"config.json").read_text())
    return detect(frame,Playfield.from_config(cfg["playfield"]),cfg["key_map"],
                  {**cfg["detector"],"reference_resolution":cfg["reference_resolution"]})


def test_pink_arrow_candidate_is_ordinary_tap_and_preserves_mask():
    frame = np.zeros((404,720,3),np.uint8)
    cv2.rectangle(frame,(280,200),(345,207),(255,70,255),-1)
    notes = run(frame)
    assert len(notes) == 1
    assert notes[0].appearance == "pink_candidate"
    assert notes[0].note_type == "tap"
    assert notes[0].raw_mask is not None
    assert notes[0].body_bbox == notes[0].bbox


def test_pink_arrow_body_trims_small_outer_glow_and_keeps_lane_keys():
    frame = np.zeros((404,720,3),np.uint8)
    # Representative frame-285 geometry: the visible glow extends a few
    # pixels beyond the calibrated right rail, while the body is a K/L Tap.
    cv2.rectangle(frame,(432,219),(572,239),(255,70,255),-1)
    diagnostics = {}
    cfg = json.loads((Path(__file__).resolve().parents[1]/"config.json").read_text())
    notes = detect(frame, Playfield.from_config(cfg["playfield"]), cfg["key_map"],
                   {**cfg["detector"], "reference_resolution": cfg["reference_resolution"]}, diagnostics)
    pink = [note for note in notes if note.appearance == "pink_candidate"]
    assert len(pink) == 1
    assert pink[0].note_type == "tap"
    assert pink[0].candidate_keys == ["K", "L"]
    assert pink[0].bbox[0] + pink[0].bbox[2] <= 567
    assert diagnostics.get("pink_core_trimmed", 0) >= 1


def test_pink_tap_feature_flag_can_roll_back_to_unknown():
    frame = np.zeros((404,720,3),np.uint8)
    cv2.rectangle(frame,(280,200),(345,207),(255,70,255),-1)
    cfg = json.loads((Path(__file__).resolve().parents[1]/"config.json").read_text())
    detector_cfg = {**cfg["detector"], "reference_resolution": cfg["reference_resolution"],
                    "pink_tap": {"enabled": False}}
    notes = detect(frame, Playfield.from_config(cfg["playfield"]), cfg["key_map"], detector_cfg)
    assert len(notes) == 1 and notes[0].appearance == "pink_candidate"
    assert notes[0].note_type == "unknown"


def test_adjacent_bodies_are_not_joined():
    frame = np.zeros((404,720,3),np.uint8)
    cv2.rectangle(frame,(250,200),(300,207),(255,255,0),-1)
    cv2.rectangle(frame,(309,200),(359,207),(255,255,0),-1)
    notes = run(frame)
    assert len(notes) == 2
    assert all(n.appearance == "cyan_bar" for n in notes)


def test_green_and_cyan_hue_classes_do_not_overlap():
    hsv = np.zeros((404,720,3),np.uint8)
    hsv[200:208,280:345] = (81,220,240)
    notes = run(cv2.cvtColor(hsv,cv2.COLOR_HSV2BGR))
    assert len(notes) == 1
    assert notes[0].appearance == "green_candidate"
    assert notes[0].note_type == "unknown"


def test_conventional_tap_requires_colored_horizontal_body():
    frame = np.zeros((404,720,3),np.uint8)
    cv2.rectangle(frame,(280,200),(345,207),(255,255,0),-1)
    notes = run(frame)
    assert len(notes) == 1
    assert notes[0].appearance == "cyan_bar"
    assert notes[0].note_type == "tap"


def test_gray_neutral_body_is_a_simple_tap():
    frame = np.zeros((404,720,3),np.uint8)
    cv2.rectangle(frame,(280,200),(345,207),(205,205,205),-1)
    notes = run(frame)
    assert len(notes) == 1
    assert notes[0].appearance == "neutral_candidate"
    assert notes[0].note_type == "tap"


def test_low_contrast_gray_rejection_is_logged():
    cfg = json.loads((Path(__file__).resolve().parents[1]/"config.json").read_text())
    frame = np.zeros((404,720,3),np.uint8)
    cv2.rectangle(frame,(280,200),(290,203),(185,185,185),-1)
    diagnostics = {}
    detect(frame, Playfield.from_config(cfg["playfield"]), cfg["key_map"],
           {**cfg["detector"], "reference_resolution": cfg["reference_resolution"]}, diagnostics)
    assert "gray_rejections" in diagnostics or diagnostics.get("raw_edge_contours", 0) == 0


def test_green_head_and_long_path_have_separate_boxes():
    frame = np.zeros((404,720,3),np.uint8)
    cv2.rectangle(frame,(310,120),(320,207),(0,255,0),-1)
    cv2.rectangle(frame,(280,200),(345,207),(0,255,0),-1)
    notes = run(frame)
    heads = [n for n in notes if n.path_bbox is not None]
    assert heads
    assert all(n.note_type == "unknown" for n in heads)
    assert heads[0].body_bbox[3] < 20
    assert heads[0].path_bbox[3] > 60


def test_inner_highlight_is_part_of_one_cyan_head():
    frame = np.zeros((404,720,3),np.uint8)
    cv2.rectangle(frame,(240,200),(360,218),(255,255,0),-1)
    cv2.rectangle(frame,(270,205),(310,209),(255,255,255),-1)
    notes = run(frame)
    assert len(notes)==1
    assert notes[0].appearance=='cyan_bar' and notes[0].note_type=='tap'
    assert notes[0].bbox[2]>100 and notes[0].bbox[3]>15


def test_inner_dark_stripe_does_not_create_second_tap():
    frame = np.zeros((404,720,3),np.uint8)
    cv2.rectangle(frame,(240,200),(360,218),(255,255,0),-1)
    cv2.rectangle(frame,(300,210),(360,214),(0,0,0),-1)
    notes = run(frame)
    assert len(notes)==1 and notes[0].note_type=='tap'


def test_yellow_hold_body_provides_path_evidence_but_short_tap_does_not():
    hsv=np.zeros((404,720,3),np.uint8)
    # The translucent body can shift toward yellow-green over the lane.
    hsv[230:293,290:371]=(39,110,170)
    hsv[292:301,280:381]=(27,220,250)
    notes=run(cv2.cvtColor(hsv,cv2.COLOR_HSV2BGR))
    heads=[c for c in notes if c.appearance=='yellow_bar' and c.bbox[1]>=280]
    assert heads and any(c.hold_path_px>=40 for c in heads)
    hsv[230:292]=0
    notes=run(cv2.cvtColor(hsv,cv2.COLOR_HSV2BGR))
    assert notes and all(c.hold_path_px<40 for c in notes)


