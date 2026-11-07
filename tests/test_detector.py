import json
from pathlib import Path
from dataclasses import asdict
import cv2
import numpy as np
import pytest
from src.detector import detect
from src.geometry import Playfield
from src.calibration import load_calibration
from src.assist_config import resolve_config


def test_recorded_green_hold_head_in_blue_judgment_light_stays_hold():
    root = Path(__file__).resolve().parents[1]
    frame = cv2.imread(str(root/'tests/fixtures/green_hold_blue_flash.png'))
    cfg = resolve_config(profile='stable').config
    geometry = load_calibration(root/'config/geometry_live_assist.json')
    dc = {**cfg['detector'],'reference_resolution':cfg['reference_resolution']}
    diagnostics = {}
    notes = detect(frame,geometry,cfg['key_map'],dc,diagnostics)
    heads = [n for n in notes if n.bbox[0]>345 and 215<n.bbox[1]<250 and n.bbox[3]>=8]
    assert heads and all(n.appearance == 'green_candidate' for n in heads)
    assert all(n.path_bbox is not None and n.note_type != 'tap' for n in heads)
    assert diagnostics['green_hold_blue_flash_recovered'] >= 1


@pytest.mark.parametrize('head_y',[220,280])
def test_true_cyan_head_crossing_green_body_is_still_a_tap(head_y):
    root = Path(__file__).resolve().parents[1]
    cfg = json.loads((root/'config.json').read_text(encoding='utf-8-sig'))
    frame = np.zeros((404,720,3),np.uint8)
    cv2.rectangle(frame,(290,120),(340,head_y+10),(0,255,0),-1)
    cv2.rectangle(frame,(280,head_y),(350,head_y+15),(255,255,0),-1)
    notes = detect(frame,Playfield.from_config(cfg['playfield']),cfg['key_map'],
                   {**cfg['detector'],'reference_resolution':cfg['reference_resolution']})
    assert any(n.appearance=='cyan_bar' and n.note_type=='tap' and n.bbox[1]>=head_y-5
               for n in notes)


@pytest.mark.parametrize('ribbon_present',[True,False])
def test_recorded_green_head_missing_lower_edge_recovers_only_with_long_ribbon(ribbon_present):
    root = Path(__file__).resolve().parents[1]
    frame = cv2.imread(str(root/'tests/fixtures/curved_hold_head_fragments.png'))
    if not ribbon_present:
        frame[:265,340:650] = 0
    cfg = resolve_config(profile='stable').config
    geometry = load_calibration(root/'config/geometry_live_assist.json')
    diagnostics = {}
    notes = detect(frame,geometry,cfg['key_map'],
                   {**cfg['detector'],'reference_resolution':cfg['reference_resolution']},diagnostics)
    recovered = [n for n in notes if n.appearance=='green_candidate' and
                 350<n.bbox[0]<380 and 270<n.bbox[1]<285 and n.bbox[3]>=20]
    assert bool(recovered) == ribbon_present
    if ribbon_present:
        assert recovered[0].hold_path_px >= 40 and recovered[0].path_bbox is not None
        assert recovered[0].note_type != 'tap'
        assert recovered[0].bbox[1]+recovered[0].bbox[3] <= 313
        assert diagnostics['green_head_rectangle_recovered'] >= 1


def test_recorded_outer_cyan_head_keeps_both_edges():
    root = Path(__file__).resolve().parents[1]
    frame = cv2.imread(str(root/'tests/fixtures/cyan_outer_head.png'))
    assert frame is not None
    geometry = load_calibration(root/'config/geometry_live_assist.json')
    config = resolve_config(profile='stable').config
    dc = {**config['detector'], 'reference_resolution': geometry.reference_resolution}
    heads = [c for c in detect(frame, geometry, config['key_map'], dc)
             if c.bbox[0] >= 480 and 250 <= c.bbox[1] <= 265 and c.bbox[3] >= 29]
    assert len(heads) == 1
    assert heads[0].note_type == 'tap'
    assert heads[0].candidate_keys == ['K', 'L']
    x, y, w, h = heads[0].bbox
    assert geometry.safe_bbox_interval(x, x+w, y+h/2) is not None


def test_two_key_left_head_is_not_replaced_by_its_internal_edge():
    # Run 033847, video 2661 / capture 374304.1611031. The old center-only
    # live trace returned a 5px highlight instead of the S/D head. Compression
    # changes its edges, so the decoded image also serves as a preservation case.
    root = Path(__file__).resolve().parents[1]
    frame = cv2.imread(str(root/'tests/fixtures/cyan_left_two_key_head.png'))
    geometry = load_calibration(root/'config/geometry_live_assist.json')
    config = resolve_config(profile='stable').config
    dc = {**config['detector'], 'reference_resolution': geometry.reference_resolution}
    notes = detect(frame, geometry, config['key_map'], dc)
    heads = [c for c in notes if c.appearance == 'cyan_bar' and c.note_type == 'tap'
             and c.bbox[0] < 150 and 275 <= c.bbox[1] <= 300 and c.bbox[3] >= 20]
    assert len(heads) == 1
    assert heads[0].candidate_keys == ['S', 'D']
    assert not any(c.note_type == 'tap' and c.appearance == 'cyan_bar'
                   and c.bbox[0] < 150 and c.bbox[1] >= 275 and c.bbox[3] < 8
                   for c in notes)


@pytest.mark.parametrize('rail_present', [False, True])
def test_judgment_rail_edge_loss_recovers_only_observed_blue_body(monkeypatch, rail_present):
    # These are the two surviving raw contours in source frame 2942,
    # capture 374304.1611031. The lower head edge joined the judgment rail.
    def surviving_edges(edge, *args):
        bodies = np.zeros_like(edge)
        bodies[286:289,95:267] = 255
        bodies[290:291,94:268] = 255
        if rail_present:
            bodies[305:314,74:648] = 255
        return bodies
    monkeypatch.setattr('src.detector._horizontal_bodies', surviving_edges)
    root = Path(__file__).resolve().parents[1]
    frame = cv2.imread(str(root/'tests/fixtures/cyan_left_two_key_head.png'))
    geometry = load_calibration(root/'config/geometry_live_assist.json')
    config = resolve_config(profile='stable').config
    dc = {**config['detector'], 'reference_resolution': geometry.reference_resolution}
    notes = detect(frame, geometry, config['key_map'], dc)
    heads = [c for c in notes if c.appearance == 'cyan_bar' and c.note_type == 'tap']
    if rail_present:
        assert len(heads) == 1
        assert heads[0].bbox[3] >= 12 and heads[0].candidate_keys == ['S', 'D']
    else:
        assert heads == []
    # The same pair of thin blue lines without a filled body cannot create
    # another Tap. Actual pixel support is mandatory for reconstruction.
    fragment = np.zeros_like(frame)
    fragment[286:289,95:267] = (255,255,0)
    fragment[290:291,94:268] = (255,255,0)
    assert not any(c.note_type == 'tap' for c in detect(fragment, geometry, config['key_map'], dc))


def test_interior_judgment_light_column_is_not_reconstructed(monkeypatch):
    def surviving_edges(edge, *args):
        bodies = np.zeros_like(edge)
        bodies[294:297,222:320] = 255
        bodies[298:299,222:320] = 255
        bodies[305:314,74:648] = 255
        return bodies
    monkeypatch.setattr('src.detector._horizontal_bodies', surviving_edges)
    frame = np.zeros((404,720,3), np.uint8)
    frame[294:313,222:320] = (255,255,0)
    root = Path(__file__).resolve().parents[1]
    geometry = load_calibration(root/'config/geometry_live_assist.json')
    config = resolve_config(profile='stable').config
    dc = {**config['detector'], 'reference_resolution': geometry.reference_resolution}
    # A blue input-light column in an interior lane satisfies the color test
    # but is outside this narrowly justified outer-rail recovery rule.
    assert not any(c.bbox[3] >= 12 for c in detect(frame, geometry, config['key_map'], dc))


def test_opencv_worker_limit_preserves_recorded_detection():
    root = Path(__file__).resolve().parents[1]
    frame = np.zeros((404, 720, 3), np.uint8)
    frame[230:315, 90:290] = cv2.imread(str(root/'tests/fixtures/yellow_head_glow.png'))
    geometry = load_calibration(root/'config/geometry_live_assist.json')
    config = resolve_config(profile='stable').config
    detector_config = {**config['detector'], 'reference_resolution': geometry.reference_resolution}
    previous_threads = cv2.getNumThreads()
    signatures = []
    try:
        for threads in (16, 4):
            cv2.setNumThreads(threads)
            notes = detect(frame, geometry, config['key_map'], detector_config)
            signatures.append(json.dumps([asdict(note) for note in notes],
                                         default=lambda value: value.tolist(), sort_keys=True))
    finally:
        cv2.setNumThreads(previous_threads)
    assert signatures[0] == signatures[1]


def test_recorded_yellow_head_glow_remains_tap():
    # Run 091102, source frame 2929: the bar's connected glow was mistaken
    # for a Hold, starving Tap tracking before this visible note was missed.
    root = Path(__file__).resolve().parents[1]
    crop = cv2.imread(str(root/'tests/fixtures/yellow_head_glow.png'))
    assert crop is not None
    frame = np.zeros((404,720,3), np.uint8)
    frame[230:315,90:290] = crop
    geometry = load_calibration(root/'config/geometry_live_assist.json')
    cfg = resolve_config().config
    notes = detect(frame, geometry, cfg['key_map'],
                   {**cfg['detector'], 'reference_resolution': geometry.reference_resolution})
    heads = [n for n in notes if n.appearance == 'yellow_bar' and n.bbox[2] > 140 and n.bbox[3] > 10]
    assert len(heads) == 1 and heads[0].note_type == 'tap'
    assert heads[0].path_bbox is None and heads[0].hold_path_px == 0


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


@pytest.mark.parametrize('hue', [27, 60])
def test_hold_path_survives_a_highlight_gap_above_the_head(hue):
    hsv = np.zeros((404,720,3),np.uint8)
    hsv[180:245,308:362] = (hue,110,170)
    # Three blank rows split the body and head into separate contours.
    hsv[248:257,280:381] = (hue,220,250)
    heads = [c for c in run(cv2.cvtColor(hsv,cv2.COLOR_HSV2BGR)) if c.bbox[1] >= 245]
    assert heads
    assert all(c.path_bbox is not None and c.note_type == 'unknown' for c in heads)
    assert any(c.hold_path_px >= 40 for c in heads)


@pytest.mark.parametrize('body_box', [(308,180,362,230), (400,180,470,245), (308,230,362,245)])
def test_separate_or_short_color_patch_does_not_convert_yellow_tap(body_box):
    hsv = np.zeros((404,720,3),np.uint8)
    x0,y0,x1,y1 = body_box
    hsv[y0:y1,x0:x1] = (27,110,170)
    hsv[248:257,280:381] = (27,220,250)
    heads = [c for c in run(cv2.cvtColor(hsv,cv2.COLOR_HSV2BGR))
             if c.bbox[1] >= 245 and c.bbox[0] < 390]
    assert heads and any(c.note_type == 'tap' for c in heads)
    assert all(c.path_bbox is None and c.hold_path_px == 0 for c in heads)


def test_reference_yellow_head_clipped_by_rail_has_no_invented_center():
    root = Path(__file__).resolve().parents[1]
    frame = cv2.imread(str(root/'tests/fixtures/reference_yellow_rail_head.png'))
    assert frame is not None
    geometry = load_calibration(root/'config/geometry_live_assist.json')

    stable = resolve_config(profile='stable').config
    stable_notes = detect(frame, geometry, stable['key_map'],
                          {**stable['detector'], 'reference_resolution': stable['reference_resolution']})
    assert not any(c.note_type == 'tap' and c.appearance == 'yellow_bar' and
                   c.bbox[1] >= 285 and c.bbox[2] > 200 for c in stable_notes)

    experimental = resolve_config(profile='reference-yellow-rail').config
    diagnostics = {}
    notes = detect(frame, geometry, experimental['key_map'],
                   {**experimental['detector'], 'reference_resolution': experimental['reference_resolution']},
                   diagnostics, frame_index=590)
    heads = [c for c in notes if c.appearance == 'yellow_bar' and c.note_type == 'tap' and
             c.bbox[0] > 350 and c.bbox[1] >= 285 and c.bbox[3] >= 12]
    assert heads == []
    assert diagnostics.get('yellow_rail_head_recovered',0) == 0


def test_yellow_surviving_lower_edge_recovers_upward_without_moving_center_down():
    root = Path(__file__).resolve().parents[1]
    frame = cv2.imread(str(root/'tests/fixtures/reference_yellow_lower_edge.png'))
    geometry = load_calibration(root/'config/geometry_live_assist.json')
    cfg = resolve_config(profile='reference-yellow-rail').config
    notes = detect(frame,geometry,cfg['key_map'],
                   {**cfg['detector'],'reference_resolution':cfg['reference_resolution']})
    heads = [c for c in notes if c.appearance=='yellow_bar' and c.note_type=='tap'
             and c.bbox[0]>350 and 265<=c.bbox[1]<=275 and c.bbox[2]>240]
    assert len(heads)==1
    x,y,w,h=heads[0].bbox
    assert y+h<=313 and h>=20
    assert y+h/2<290  # Raw edge at y=293 is the bottom, not the center.
    interval=geometry.safe_bbox_interval(x,x+w,y+h/2)
    assert (heads[0].u_min,heads[0].u_max)==pytest.approx(interval)


def test_yellow_rail_recovery_rejects_a_thin_line_with_rail_evidence():
    root = Path(__file__).resolve().parents[1]
    frame = cv2.imread(str(root/'tests/fixtures/reference_yellow_rail_head.png'))
    frame[297:313, 364:638] = 0
    frame[297:300, 365:631] = (0, 255, 255)
    geometry = load_calibration(root/'config/geometry_live_assist.json')
    cfg = resolve_config(profile='reference-yellow-rail').config
    diagnostics = {}
    notes = detect(frame, geometry, cfg['key_map'],
                   {**cfg['detector'], 'reference_resolution': cfg['reference_resolution']}, diagnostics)
    fragments = [c for c in notes if c.appearance == 'yellow_bar' and c.bbox[0] > 350 and
                 c.bbox[1] >= 285 and c.bbox[2] > 200]
    assert fragments and all(c.note_type == 'unknown' and c.bbox[3] < 8 for c in fragments)
    assert diagnostics.get('yellow_rail_head_recovered', 0) == 0


def test_yellow_head_glow_is_not_rail_reconstructed():
    root = Path(__file__).resolve().parents[1]
    crop = cv2.imread(str(root/'tests/fixtures/yellow_head_glow.png'))
    frame = np.zeros((404, 720, 3), np.uint8)
    frame[230:315, 90:290] = crop
    geometry = load_calibration(root/'config/geometry_live_assist.json')
    cfg = resolve_config(profile='reference-yellow-rail').config
    diagnostics = {}
    notes = detect(frame, geometry, cfg['key_map'],
                   {**cfg['detector'], 'reference_resolution': cfg['reference_resolution']}, diagnostics)
    assert any(c.appearance == 'yellow_bar' and c.note_type == 'tap' for c in notes)
    assert not any(c.appearance == 'yellow_bar' and c.bbox[1] >= 285 and c.bbox[3] >= 12
                   for c in notes)
    assert diagnostics.get('yellow_rail_head_recovered', 0) == 0


def test_yellow_hold_path_is_not_rail_reconstructed_as_tap():
    root = Path(__file__).resolve().parents[1]
    frame = cv2.imread(str(root/'tests/fixtures/reference_yellow_rail_head.png'))
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    hsv[250:297, 480:530] = (39, 110, 170)
    frame = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    geometry = load_calibration(root/'config/geometry_live_assist.json')
    cfg = resolve_config(profile='reference-yellow-rail').config
    diagnostics = {}
    notes = detect(frame, geometry, cfg['key_map'],
                   {**cfg['detector'], 'reference_resolution': cfg['reference_resolution']}, diagnostics)
    heads = [c for c in notes if c.appearance == 'yellow_bar' and c.bbox[0] > 350 and
             c.bbox[1] >= 285 and c.bbox[2] > 200]
    assert heads and all(c.note_type != 'tap' for c in heads)
    assert any(c.hold_path_px >= 40 and c.path_bbox is not None for c in heads)
    assert diagnostics.get('yellow_rail_head_recovered', 0) == 0


