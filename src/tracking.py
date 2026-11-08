"""Causal one-to-one plate tracks; Hold tails are endpoints, never new heads."""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass,field
import math
from statistics import median
import numpy as np
from .model import Note
from .perception import intervals


def overlap(a,b):
    return max(0,min(a[1],b[1])-max(a[0],b[0]))/max(.001,min(a[1]-a[0],b[1]-b[0]))


@dataclass
class Cap:
    uid: str
    detection: object
    samples: deque=field(default_factory=lambda:deque(maxlen=16))
    votes: dict=field(default_factory=dict)
    note_uid: str=''


class Tracker:
    def __init__(self,geometry):
        self.geometry=geometry;self.next_id=1;self.caps={};self.notes={};self.retired=deque(maxlen=128)
        self.last_timestamp=float('-inf');self.audit=[]

    def reset(self):
        self.caps.clear();self.notes.clear();self.last_timestamp=float('-inf')

    def update(self,detections,timestamp,labels=None,path_mask=None):
        if not math.isfinite(timestamp) or timestamp<=self.last_timestamp:
            raise ValueError('Tracker requires strictly increasing real capture timestamps')
        self.last_timestamp=timestamp;self.audit=[]
        current=list(detections);offers=[]
        live={uid:c for uid,c in self.caps.items() if timestamp-c.samples[-1][0]<=.24}
        for uid,cap in live.items():
            t,y,lo,hi=cap.samples[-1];dt=timestamp-t
            velocity=0.
            if len(cap.samples)>=2:
                recent=list(cap.samples)[-6:]
                slopes=[(b[1]-a[1])/(b[0]-a[0]) for i,a in enumerate(recent) for b in recent[i+1:] if b[0]>a[0]]
                velocity=float(min(1400,max(0,median(slopes))))
            predicted=y+velocity*dt
            gate=max(9.,min(50.,6.+.35*velocity*dt+180*dt))
            for j,c in enumerate(current):
                old=cap.detection
                compatible=(old.color==c.color or 'neutral' in (old.color,c.color))
                owner=self.notes.get(cap.note_uid)
                if owner is not None and owner.color!='neutral' and c.color not in (owner.color,'neutral'):
                    compatible=False
                role=cap.votes.get('hold_tail',0)>cap.votes.get('hold_head',0)
                if not compatible or (role and c.kind=='hold_head') or (not role and c.kind=='hold_tail' and cap.note_uid):continue
                cy=c.bbox[1] if role else c.bbox[1]+c.bbox[3]
                if len(cap.samples)>=5:
                    recent=list(cap.samples)[-5:]
                    if max(p[1] for p in recent)-min(p[1] for p in recent)<=2 and abs(cy-y)>2:
                        continue
                error=abs(cy-predicted);iou=overlap((lo,hi),c.span)
                center_gap=abs((lo+hi)/2-sum(c.span)/2)
                if error>gate or center_gap>.28 or (iou<.1 and center_gap>.12):continue
                cost=error/gate+.8*(1-min(iou,1))+.8*center_gap
                offers.append((cost,uid,j))
        assigned={};used=set()
        # Global sorted competition, with explicit one-to-one constraints.
        # Ambiguous alternatives remain observable rather than spawning aliases.
        for cost,uid,j in sorted(offers):
            if uid in assigned or j in used:continue
            assigned[uid]=j;used.add(j)
        for uid,j in assigned.items():
            self._observe(live[uid],current[j],timestamp)
        for j,c in enumerate(current):
            if j in used or c.kind in ('body','ambiguous'):continue
            uid=f'cap:{self.next_id}';self.next_id+=1
            cap=Cap(uid,c);self.caps[uid]=cap;self._observe(cap,c,timestamp)
        for uid,note in list(self.notes.items()):
            if timestamp-note.last_seen>.04:note.missed+=1
            expired=(timestamp-note.last_seen>(9.5 if note.kind=='hold' else .45))
            if expired and note.state not in ('HELD','SCHEDULED'):
                note.reason='track_lost';self.retired.append(note);self.notes.pop(uid)
        self._link_tails(timestamp,path_mask)
        self.caps={uid:c for uid,c in self.caps.items() if timestamp-c.samples[-1][0]<=.45 or c.note_uid in self.notes}
        return list(self.notes.values())

    def _observe(self,cap,c,t):
        cap.detection=c;cap.votes[c.kind]=cap.votes.get(c.kind,0)+1
        is_tail=cap.votes.get('hold_tail',0)>cap.votes.get('hold_head',0)
        y=c.bbox[1] if is_tail else c.bbox[1]+c.bbox[3]
        cap.samples.append((t,float(y),*c.span))
        if is_tail:return
        if not cap.note_uid and c.kind not in ('tap','hold_head'):return
        if not cap.note_uid:
            cap.note_uid=f'note:{cap.uid.split(":")[-1]}'
            self.notes[cap.note_uid]=Note(cap.note_uid,'hold' if c.kind=='hold_head' else 'tap',c.color,c)
        note=self.notes.get(cap.note_uid)
        if note is None:return
        if note.origin_y is None:note.origin_y=float(y)
        note.detection=c;note.head.append((t,float(y),*c.span));note.observations+=1;note.missed=0
        if note.color in ('green','yellow') and cap.votes.get('hold_head',0)>=2:note.kind='hold'
        points=list(note.head)
        span=max(p[1] for p in points)-min(p[1] for p in points)
        note.confirmed=bool(note.confirmed or (len(points)>=3 and points[-1][0]-points[0][0]>=.045 and span>=5 and
                        note.origin_y<=self.geometry.hit_y-45 and
                        np.mean(np.diff([p[1] for p in points])>=-2)>=.8))
        note.reason='confirmed' if note.confirmed else 'insufficient_real_motion'

    def _link_tails(self,t,path_mask):
        probe=self.geometry.hit_y-18
        width=self.geometry.plane_width
        if path_mask is not None:
            lower=intervals(path_mask,probe);middle=intervals(path_mask,probe-8);upper=intervals(path_mask,probe-16)
            runs=[(a/width,b/width) for a,b in lower if any(overlap((a,b),m)>.35 and
                  any(overlap(m,u)>.35 for u in upper) for m in middle)]
            body_offers=[]
            for n in self.notes.values():
                if n.kind!='hold' or not n.confirmed or n.state=='DONE' or n.head[-1][1]<probe:continue
                if n.body_span is not None and t-n.body_seen_at>.25:continue
                expected=n.body_span or n.detection.span
                for i,run in enumerate(runs):
                    if overlap(expected,run)>.4:
                        body_offers.append((abs(sum(expected)-sum(run)), -n.last_seen,n.uid,i))
            used_notes=set();used_runs=set()
            for _,_,uid,i in sorted(body_offers):
                if uid in used_notes or i in used_runs:continue
                n=self.notes[uid];n.body_span=runs[i];n.body_seen_at=t
                used_notes.add(uid);used_runs.add(i)
        tails=[c for c in self.caps.values() if c.votes.get('hold_tail',0)>=2 and t-c.samples[-1][0]<.12]
        occupied={n.tail_uid for n in self.notes.values() if n.tail_uid}
        endpoints={}
        if path_mask is not None:
            for cap in tails:
                c=cap.detection;states=[(c.bbox[0],c.bbox[0]+c.bbox[2])];misses=0
                for y in np.arange(c.bbox[1]+c.bbox[3]+4,probe+1,8):
                    choices=intervals(path_mask,y)
                    linked=[r for r in choices if any(overlap(r,old)>.25 for old in states)]
                    if not linked:
                        misses+=1
                        if misses>=2:states=[];break
                    else:states=linked;misses=0
                endpoints[cap.uid]=[(a/width,b/width) for a,b in states]
        for n in self.notes.values():
            if n.kind!='hold' or not n.confirmed:continue
            if n.tail_uid:
                cap=self.caps.get(n.tail_uid)
                if cap is not None:
                    n.tail=deque(cap.samples,maxlen=16)
                continue
            offers=[]
            for cap in tails:
                if cap.uid in occupied:continue
                c=cap.detection;tail_y=cap.samples[-1][1]
                head_y=n.head[-1][1]
                if tail_y>=min(head_y,self.geometry.hit_y)-6:continue
                fresh_head=t-n.last_seen<.12
                # Connected-component numbers are local to ONE image. Reusing
                # a numeric label from a previous frame is not ribbon evidence.
                same_frame=(n.last_seen==t and cap.samples[-1][0]==t)
                same_component=(same_frame and c.component and c.component==n.detection.component)
                # The same component must not own multiple independent heads.
                owners=[o for o in self.notes.values() if o.kind=='hold' and o.last_seen==t and
                        o.detection.component==c.component]
                if same_component and len(owners)==1:
                    offers.append((0.,cap));continue
                if not fresh_head and path_mask is not None and t-n.body_seen_at<.12:
                    possible=[o.uid for o in self.notes.values() if o.kind=='hold' and o.confirmed and
                              not o.tail_uid and o.body_span is not None and t-o.body_seen_at<.12 and
                              any(overlap(end,o.body_span)>.55 for end in endpoints.get(cap.uid,[]))]
                    if possible==[n.uid]:offers.append((1.,cap))
            if len(offers)==1:
                n.tail_uid=offers[0][1].uid;occupied.add(n.tail_uid)
                n.tail=deque(offers[0][1].samples,maxlen=16)
