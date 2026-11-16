from collections import deque
from types import SimpleNamespace

import numpy as np

from src.engine import Engine


def _detection(kind, bbox, *, component=0, above=0, below=0):
    return SimpleNamespace(kind=kind, bbox=bbox, component=component,
                           above=above, below=below)


def test_hold_recovery_builds_labels_only_at_parent_region_check():
    captured_at=10.0
    young_detection=_detection('hold_head',(20,220,24,12),component=7,above=40,below=4)
    old_detection=_detection('body',(20,30,24,12))
    young=SimpleNamespace(uid='young',detection=young_detection,kind='hold',color='green',
        last_seen=captured_at,origin_y=260,full_head_observations=2,confirmed=True,
        head=deque([(9.9,100,220,244)]),tail_uid=None,observations=2,
        last_full_head_at=9.9,aliases=[],state='TRACKING',reason='',missed=0)
    old=SimpleNamespace(uid='old',detection=old_detection,kind='hold',color='green',
        confirmed=True,origin_y=100,full_head_observations=4,last_seen=9.9,
        tail_uid='old-tail',head=deque([(9.8,100,30,54)]),observations=4,
        last_full_head_at=9.8,aliases=[],state='TRACKING',reason='',missed=0,
        tail=deque(),tail_last_kind='')
    old_tail=SimpleNamespace(full_tail_observations=2,
        samples=deque([(9.99,0,0,0)]),detection=_detection('hold_tail',(20,40,24,8)),
        terminal_owner_uid='old',connection_owner_uid='old',note_uid='old')
    young_cap=SimpleNamespace(samples=deque([(captured_at,0,0,0)]),note_uid='young',
        terminal_owner_uid='young',connection_owner_uid='young')
    tracker=SimpleNamespace(notes={'young':young,'old':old},
                            caps={'old-tail':old_tail,'young-cap':young_cap})
    class Scheduler:
        def snapshot(self):
            return {'pending':{},'consumed':set(),'held':{}}
        def consume_alias(self, young_uid, old_uid):
            assert (young_uid,old_uid)==('young','old')
            return True
    class LazyPerception:
        last_labels=None
        def ensure_last_labels(self):
            self.calls+=1
            self.last_labels=np.zeros((300,100),np.int32)
            self.last_labels[30:42,20:44]=7
            return self.last_labels
        def __init__(self):
            self.calls=0
    perception=LazyPerception()
    engine=Engine.__new__(Engine)
    engine.perception=perception
    engine.tracker=tracker
    engine.scheduler=Scheduler()
    engine.geometry=SimpleNamespace(hit_y=300)

    engine._recover_unreserved_hold_head(SimpleNamespace(captured_at=captured_at))

    assert perception.calls==1
    assert old.detection is young_detection
    assert young.state=='DONE'
    assert young_cap.note_uid=='old'
