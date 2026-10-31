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


def test_pink_is_unknown_and_preserves_mask():
    frame = np.zeros((404,720,3),np.uint8)
    cv2.rectangle(frame,(280,200),(345,207),(255,70,255),-1)
    notes = run(frame)
    assert len(notes) == 1
    assert notes[0].appearance == "pink_candidate"
    assert notes[0].note_type == "unknown"
    assert notes[0].raw_mask is not None
    assert notes[0].body_bbox == notes[0].bbox


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


