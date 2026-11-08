"""Small shared values; all timestamps are host monotonic seconds."""
from __future__ import annotations
from dataclasses import dataclass, field
from collections import deque
import hashlib,json
from pathlib import Path
import cv2
import numpy as np

KEYS = tuple('SDFJKL')


@dataclass(frozen=True)
class Frame:
    sequence: int
    image: np.ndarray
    captured_at: float
    acquired_at: float
    focused: bool = True
    roi_valid: bool = True
    run_id: str = ''


class Geometry:
    """Use the existing linear/piecewise boundaries without recalibration."""
    def __init__(self, path='config/geometry_live_assist.json', *, plane_width=360):
        self.path=Path(path)
        self.document=json.loads(self.path.read_text(encoding='utf-8-sig'))
        d=self.document
        if d.get('model_type') not in ('linear','piecewise') or d.get('key_map')!=list(KEYS):
            raise ValueError('Expected the existing six-key linear/piecewise geometry')
        self.width,self.height=d['reference_resolution']
        if plane_width%6 or plane_width<240:raise ValueError('Lane feature width must be a multiple of six, at least 240')
        self.plane_width=int(plane_width);self.lane_pixels=plane_width/6
        rows=sorted(d['controls']['lane_rows'],key=lambda r:r['y'])
        self.ys=np.array([r['y'] for r in rows],float)
        self.xs=np.array([[p['x'] for p in r['points']] for r in rows],float)
        if self.xs.shape!=(len(rows),7) or np.any(np.diff(self.ys)<=0) or np.any(np.diff(self.xs,axis=1)<=0):
            raise ValueError('Invalid lane boundaries')
        self.hit_y=float(np.mean([p['y'] for p in d['controls']['hit_line']]))
        self.top_y=float(self.ys[0])
        self.status=d['status']
        self.sha256=hashlib.sha256(self.path.read_bytes()).hexdigest()
        y=np.arange(self.height,dtype=np.float32)
        boundaries=np.stack([np.interp(y,self.ys,self.xs[:,i]) for i in range(7)],axis=1)
        self.map_y=np.repeat(y[:,None],self.plane_width,axis=1)
        lane_x=np.arange(self.plane_width)/self.lane_pixels
        lane=np.minimum(lane_x.astype(int),5);frac=lane_x-lane
        self.map_x=(boundaries[:,lane]*(1-frac)+boundaries[:,lane+1]*frac).astype(np.float32)

    def boundaries(self,y):
        return np.array([np.interp(y,self.ys,self.xs[:,i]) for i in range(7)])

    def normalize(self,image):
        h,w=image.shape[:2]
        if abs((w/h)/(16/9)-1)>.015 and abs(w-h*16/9)>2:
            raise ValueError('Game display must be approximately 16:9')
        s=min(self.width/w,self.height/h)
        transform=np.array([[s,0,(self.width-w*s)/2],[0,s,(self.height-h*s)/2]],np.float32)
        return cv2.warpAffine(image,transform,(self.width,self.height),flags=cv2.INTER_LINEAR)

    def rectify(self,image):
        return cv2.remap(image,self.map_x,self.map_y,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)

    def native_bbox(self,bbox):
        x,y,w,h=bbox;b=self.boundaries(y+h/2)
        def project(q):
            q=float(np.clip(q/self.lane_pixels,0,6));i=min(5,int(q));return float(b[i]+(q-i)*(b[i+1]-b[i]))
        left,right=project(x),project(x+w)
        return (round(left),int(y),max(1,round(right-left)),int(h))


@dataclass(frozen=True)
class Detection:
    bbox: tuple[int,int,int,int]  # rectified x, native reference y
    color: str
    kind: str
    keys: tuple[str,...]
    score: float
    component: int = 0
    above: float = 0.
    below: float = 0.
    plane_width: int = 360

    @property
    def y(self):return self.bbox[1]+self.bbox[3]/2
    @property
    def span(self):return self.bbox[0]/self.plane_width,(self.bbox[0]+self.bbox[2])/self.plane_width


@dataclass
class Note:
    uid: str
    kind: str
    color: str
    detection: Detection
    origin_y: float | None = None
    head: deque = field(default_factory=lambda:deque(maxlen=12))
    tail: deque = field(default_factory=lambda:deque(maxlen=12))
    observations: int = 0
    missed: int = 0
    confirmed: bool = False
    state: str = 'TRACKING'
    key: str = ''
    press_at: float | None = None
    crossing_at: float | None = None
    release_at: float | None = None
    uncertainty: float | None = None
    reason: str = 'insufficient_observations'
    tail_uid: str = ''
    aliases: list[str] = field(default_factory=list)
    body_span: tuple[float,float] | None = None
    body_seen_at: float = float('-inf')

    @property
    def last_seen(self):return self.head[-1][0] if self.head else float('-inf')
