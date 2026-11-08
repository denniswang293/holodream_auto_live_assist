import cv2
import numpy as np
import pytest
from src.perception import Perception


class Plane:
    plane_width=360
    lane_pixels=60
    top_y=28
    hit_y=325.5
    def rectify(self,image):return image


def color(h,s=180,v=240):
    return tuple(int(x) for x in cv2.cvtColor(np.uint8([[[h,s,v]]]),cv2.COLOR_HSV2BGR)[0,0])


@pytest.mark.parametrize('name,h,s',[('cyan',95,180),('pink',155,180),('yellow',25,180),('neutral',0,0)])
def test_plate_colors_and_simultaneous_independent_spans(name,h,s):
    im=np.zeros((404,360,3),np.uint8)
    for x in (30,240):cv2.rectangle(im,(x,100),(x+70,110),color(h,s),-1)
    found=[d for d in Perception(Plane()).detect(im) if d.color==name]
    assert len(found)==2
    assert all(d.kind=='tap' for d in found)
    assert found[0].bbox[0]+found[0].bbox[2]<found[1].bbox[0]


def test_ribbon_direction_separates_hold_head_and_tail():
    im=np.zeros((404,360,3),np.uint8)
    cv2.rectangle(im,(40,35),(100,150),color(60,180,130),-1)
    cv2.rectangle(im,(35,145),(105,156),color(60),-1)
    cv2.rectangle(im,(240,110),(300,260),color(60,180,130),-1)
    cv2.rectangle(im,(235,100),(305,111),color(60),-1)
    found=Perception(Plane()).detect(im)
    assert any(d.kind=='hold_head' and d.bbox[0]<120 for d in found)
    assert any(d.kind=='hold_tail' and d.bbox[0]>200 for d in found)


def test_text_speckles_and_stationary_background_do_not_make_wide_plates():
    im=np.zeros((404,360,3),np.uint8)
    for x in range(20,340,15):cv2.circle(im,(x,190),2,color(95),-1)
    assert not Perception(Plane()).detect(im)


def test_white_symbol_cannot_split_one_tap_into_two_actions():
    im=np.zeros((404,360,3),np.uint8)
    cv2.rectangle(im,(40,100),(160,111),color(95),-1)
    cv2.rectangle(im,(94,100),(104,111),(255,255,255),-1)
    cyan=[d for d in Perception(Plane()).detect(im) if d.color=='cyan']
    assert len(cyan)==1 and cyan[0].bbox[2]>=118


def test_near_adjacent_same_height_chord_with_dark_gap_stays_independent():
    im=np.zeros((404,360,3),np.uint8)
    for x in (30,108):cv2.rectangle(im,(x,100),(x+70,111),color(95),-1)
    cyan=[d for d in Perception(Plane()).detect(im) if d.color=='cyan']
    assert len(cyan)==2


def test_partial_top_bevel_is_rejoined_with_adjacent_full_face():
    im=np.zeros((404,360,3),np.uint8)
    cv2.rectangle(im,(40,100),(160,125),color(95),-1)
    cv2.rectangle(im,(40,105),(90,125),(0,0,0),-1)
    cv2.rectangle(im,(91,100),(96,125),(255,255,255),-1)
    cyan=[d for d in Perception(Plane()).detect(im) if d.color=='cyan']
    assert len(cyan)==1 and cyan[0].bbox[2]>=118 and cyan[0].bbox[3]>=24


def test_two_full_faces_in_same_lane_remain_distinct():
    im=np.zeros((404,360,3),np.uint8)
    for y in (200,236):cv2.rectangle(im,(40,y),(160,y+20),color(95),-1)
    cyan=[d for d in Perception(Plane()).detect(im) if d.color=='cyan']
    assert len(cyan)==2


def test_indexed_real_tap_face_and_bevel_produce_one_plate():
    from pathlib import Path
    im=cv2.imread(str(Path(__file__).parent/'fixtures/tap_bevel.png'))
    cyan=[d for d in Perception(Plane()).detect(im) if d.color=='cyan']
    assert len(cyan)==1 and cyan[0].bbox[2]>=75 and cyan[0].bbox[3]>=24


def test_indexed_real_tail_partial_and_full_face_keep_one_endpoint():
    from pathlib import Path
    im=cv2.imread(str(Path(__file__).parent/'fixtures/hold_tail_bevel.png'))
    faces=[d for d in Perception(Plane()).detect(im) if d.color=='green' and 255<=d.bbox[1]<=265]
    assert len(faces)==1 and faces[0].bbox[2]>=80 and faces[0].bbox[3]>=24


def test_late_face_union_does_not_leave_an_earlier_fragment_candidate():
    from pathlib import Path
    im=cv2.imread(str(Path(__file__).parent/'fixtures/tap_union_fragment.png'))
    faces=[d for d in Perception(Plane()).detect(im) if d.color=='cyan' and 250<=d.y<=290]
    assert len(faces)==1 and faces[0].bbox[2]>=80


def test_real_neutral_face_shadow_is_not_a_second_note():
    from pathlib import Path
    im=cv2.imread(str(Path(__file__).parent/'fixtures/neutral_shadow.png'))
    faces=[d for d in Perception(Plane()).detect(im) if d.color=='neutral' and 240<=d.y<=275]
    assert len(faces)==1 and faces[0].bbox[3]>=20
