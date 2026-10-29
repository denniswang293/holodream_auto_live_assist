import pytest
from src.detector import Candidate
from src.geometry import Playfield
from src.tracker import Tracker


@pytest.fixture
def make_candidate():
    geometry = Playfield(28,346,374,352,36,684)
    def make(y=100, u=0.4, appearance="cyan_bar", keys=None, width=0.14):
        left,right = geometry.bounds(y)
        u0,u1 = u-width/2,u+width/2
        x = round(left+u0*(right-left))
        box = (x,round(y-3),max(3,round(width*(right-left))),6)
        lanes = geometry.candidate_lanes(left+u0*(right-left),left+u1*(right-left),y)
        return Candidate(box,appearance,0.9,u0,u1,keys if keys is not None else [list("SDFJKL")[i] for i in lanes],
                         "tap" if appearance in ("cyan_bar","yellow_bar") else "unknown",body_bbox=box)
    return make


@pytest.fixture
def tracker():
    return Tracker({"max_gap_s":0.16,"max_missed_frames":8},352)
