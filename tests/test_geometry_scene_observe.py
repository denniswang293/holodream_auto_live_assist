import numpy as np

from tools.geometry_scene.association import SceneTrack, TrackObservation
from tools.geometry_scene.segmentation import PixelCandidate
from tools.geometry_scene_observe import classify_track


def _track(*, outline_count=8, fill=0.96, profile=0.02, candidate_status="AMBIGUOUS"):
    observations=[]
    for i in range(3):
        x,y,w,h=100,20+i*20,80,12
        panel=((x,y),(x+w-1,y),(x+w-1,y+h-1),(x,y+h-1))
        raw=tuple((x+j,y+(j%h)) for j in range(outline_count))
        c=PixelCandidate((x,y,w,h),"UNKNOWN",candidate_status,("cyan",),
                         ("OBSERVED_COLOR_COMPONENT","PANEL_GEOMETRY"),False,
                         .96,800,np.empty((0,0),np.uint8),raw,panel,fill,profile)
        evidence_status="UNKNOWN" if candidate_status=="UNKNOWN" else "AMBIGUOUS"
        observations.append(TrackObservation(i,i*.1,f"frame_{i}/region_0",(x,y,w,h),evidence_status,c))
    return SceneTrack("track_1","UNKNOWN",("cyan",),tuple(observations),())


def test_compact_panel_and_downward_motion_can_form_only_provisional_tap_hypothesis():
    kind,status,confidence,reason=classify_track(_track())
    assert kind=="TAP"
    assert status=="PROVISIONAL_MORPHOLOGY_AND_TEMPORAL_MOTION"
    assert 0 < confidence < 1
    assert reason=="COMPACT_PANEL_TRACK"


def test_irregular_splash_shape_does_not_become_tap_from_color_and_motion_alone():
    kind,status,confidence,reason=classify_track(_track(outline_count=42,fill=.92,profile=.10))
    assert kind=="UNKNOWN"
    assert status=="TYPE_UNRESOLVED"
    assert confidence==0
    assert reason=="TRACK_DOES_NOT_MEET_TYPED_RULES"


def test_unknown_pixel_evidence_path_never_promotes_to_tap_or_hold():
    kind,status,confidence,reason=classify_track(_track(candidate_status="UNKNOWN"))
    assert kind=="UNKNOWN"
    assert status=="LOW_CONFIDENCE_PIXEL_TRACK"
    assert confidence==0
    assert reason=="UNKNOWN_STATUS_EVIDENCE_PATH"
