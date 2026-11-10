from collections import deque

import numpy as np
import pytest

from src.model import Detection, Geometry, Note
from src.tracking import Cap, Tracker


def head(uid='head', *, full=4, state='TRACKING'):
    d=Detection((120,220,120,20),'green','hold_head',('F','J'),.9,
                component=7,above=80,below=0)
    n=Note(uid,'hold','green',d,origin_y=70,confirmed=True,state=state,
           full_head_observations=full)
    n.head=deque([(9.90,220,*d.span),(9.95,230,*d.span),(10.,240,*d.span)],maxlen=32)
    return n


def terminal(uid='tail', *, full=4, height=10):
    d=Detection((120,140,120,height),'green','hold_tail',('F','J'),.9,
                component=7,above=0,below=80)
    c=Cap(uid,d,full_tail_observations=full,votes={'hold_tail':4})
    c.samples=deque([(9.90,120,*d.span),(9.95,130,*d.span),(10.,140,*d.span)],maxlen=16)
    return c


@pytest.mark.parametrize('full,height',[(0,3),(1,10),(5,3)])
def test_thin_or_unverified_endpoint_does_not_reserve_a_hold(full,height):
    tracker=Tracker(Geometry());n=head();c=terminal(full=full,height=height)
    tracker.notes[n.uid]=n;tracker.caps[c.uid]=c
    tracker._link_tails(10.,None)
    assert not n.tail_uid
    assert not c.connection_owner_uid


def test_complete_terminal_can_bind_after_interior_edge_was_rejected():
    tracker=Tracker(Geometry());n=head();ghost=terminal('ghost',full=0,height=3)
    tracker.notes[n.uid]=n;tracker.caps[ghost.uid]=ghost
    tracker._link_tails(10.,None)
    real=terminal('real');tracker.caps[real.uid]=real
    tracker._link_tails(10.,None)
    assert n.tail_uid=='real'
    assert real.connection_owner_uid==n.uid
    assert not ghost.tail_locked


def test_confirmed_motion_in_thin_head_cannot_steal_real_terminal():
    tracker=Tracker(Geometry());n=head(full=0);c=terminal()
    tracker.notes[n.uid]=n;tracker.caps[c.uid]=c
    tracker._link_tails(10.,None)
    assert not n.tail_uid


def test_judgment_sliver_does_not_collapse_held_ribbon_anchor():
    tracker=Tracker(Geometry());n=head(state='HELD')
    n.detection=Detection((120,300,120,28),'green','hold_head',('F','J'),.9)
    n.head.append((10.,328,*n.detection.span));n.body_span=(1/3,2/3);n.body_seen_at=9.98
    tracker.notes[n.uid]=n
    mask=np.zeros((404,360),np.uint8);mask[280:324,150:170]=255
    tracker._link_tails(10.,mask)
    assert n.body_span==(1/3,2/3)
    assert n.body_seen_at==10.
    tracker._link_tails(10.04,np.zeros_like(mask))
    assert n.body_seen_at==10.  # No pixels cannot renew ribbon support.


def test_ambiguous_two_heads_do_not_share_one_terminal():
    tracker=Tracker(Geometry());left=head('left');right=head('right');c=terminal()
    tracker.notes={left.uid:left,right.uid:right};tracker.caps[c.uid]=c
    tracker._link_tails(10.,None)
    assert not left.tail_uid and not right.tail_uid


def test_thin_last_view_keeps_already_owned_real_endpoint_and_release():
    tracker=Tracker(Geometry());n=head(state='HELD');c=terminal(full=5,height=3)
    n.tail_uid=c.uid;n.release_at=10.3;c.tail_locked=True
    c.connection_owner_uid=n.uid;c.terminal_owner_uid=n.uid
    tracker.notes[n.uid]=n;tracker.caps[c.uid]=c
    tracker._link_tails(10.,None)
    assert n.tail_uid==c.uid and n.release_at==10.3
    assert n.tail[-1]==c.samples[-1]
