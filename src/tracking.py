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
    tail_locked: bool=False
    full_tail_observations: int=0
    terminal_seen_at: float=float('-inf')
    terminal_owner_uid: str=''
    connection_owner_uid: str=''


class Tracker:
    def __init__(self,geometry):
        self.geometry=geometry;self.next_id=1;self.caps={};self.notes={};self.retired=deque(maxlen=128)
        self.last_timestamp=float('-inf');self.audit=[]

    def reset(self):
        self.caps.clear();self.notes.clear();self.last_timestamp=float('-inf')

    def ribbon_owners(self,detection,path_mask,timestamp,eligible,*,allow_near=False):
        """Follow real color BELOW a plate to a unique held ribbon.

        A new independent head has empty space below it. An interior plate
        has a continuing ribbon there. No cached component IDs are used.
        """
        probe=self.geometry.hit_y-18
        x,y,w,h=detection.bbox
        if path_mask is None or detection.below<16:return []
        end=probe
        if y+h+8>=probe:
            if not allow_near or y+h+12>self.geometry.hit_y-3:return []
            end=max(probe,y+h+12)
        states=[(x,x+w)];support=0;misses=0
        for row in np.arange(y+h+4,end+1,4):
            linked=[r for r in intervals(path_mask,row) if any(overlap(r,s)>.35 for s in states)]
            if not linked:
                misses+=1
                if support<2 or misses>=2:return []
            else:states=linked;support+=1;misses=0
        return [n.uid for n in self.notes.values() if n.uid in eligible and
                n.body_span is not None and timestamp-n.body_seen_at<.12 and
                any(overlap((a/self.geometry.plane_width,b/self.geometry.plane_width),n.body_span)>.65
                    for a,b in states)]

    def update(self,detections,timestamp,labels=None,path_mask=None):
        if not math.isfinite(timestamp) or timestamp<=self.last_timestamp:
            raise ValueError('Tracker requires strictly increasing real capture timestamps')
        self.last_timestamp=timestamp;self.audit=[]
        current=list(detections);offers=[]
        active_tails={n.tail_uid for n in self.notes.values() if n.state in ('HELD','SCHEDULED')}
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
                if c.recovery_only:
                    if owner is None:
                        owners=[n for n in self.notes.values() if n.tail_uid==uid and n.state in ('HELD','SCHEDULED')]
                        if not (cap.tail_locked and cap.full_tail_observations>=2 and len(owners)==1):continue
                    else:
                        tail=self.caps.get(owner.tail_uid)
                        if (not owner.confirmed or (owner.kind=='hold' and
                                (owner.full_head_observations<2 or tail is None or tail.full_tail_observations<2))):continue
                if owner is not None and owner.color!='neutral' and c.color not in (owner.color,'neutral'):
                    compatible=False
                if c.kind=='plate_fragment' and owner is not None and owner.kind=='hold':continue
                role=not cap.note_uid and (cap.tail_locked or cap.votes.get('hold_tail',0)>max(cap.votes.get('hold_head',0),
                        cap.votes.get('tap',0) if cap.detection.color=='yellow' else 0))
                # An endpoint cannot become a new head just because effects
                # or the bottom ROI hide its below-ribbon evidence. Preserve
                # role only after repeated COMPLETE tail faces and coherent
                # fresh motion, with all existing spatial gates still applied.
                moving_tail=(role and uid in active_tails and cap.full_tail_observations>=2 and
                             len(cap.samples)>=4 and dt<=.06 and velocity>20 and
                             c.bbox[1]>=y-2 and overlap((lo,hi),c.span)>.55)
                if (not compatible or (role and c.kind=='hold_head' and not moving_tail) or
                        (not role and c.kind=='hold_tail' and cap.note_uid)):continue
                cy=c.bbox[1] if role else c.bbox[1]+c.bbox[3]
                if (role and cap.tail_locked and uid in active_tails and c.kind in ('tap','plate_fragment') and
                        c.color in ('cyan','pink') and cy<y-2):continue
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
        recovered=[current[j] for j in assigned.values() if current[j].recovery_only]
        for j,c in enumerate(current):
            if j in used or c.kind in ('body','ambiguous'):continue
            if c.recovery_only:continue
            x,y,w,h=c.bbox
            if any(c.color==r.color and
                   max(0,min(x+w,r.bbox[0]+r.bbox[2])-max(x,r.bbox[0]))*
                   max(0,min(y+h,r.bbox[1]+r.bbox[3])-max(y,r.bbox[1]))>=.8*w*h for r in recovered):continue
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
        if cap.samples and t-cap.samples[-1][0]>.14:
            # update() already accepted this REAL observation through the
            # unchanged <=240ms association/motion gates. A brief occlusion
            # must not erase an exclusively owned, verified endpoint while
            # its original action is still reserved or held.
            bound=self.notes.get(cap.connection_owner_uid)
            preserve=(t-cap.samples[-1][0]<=.24 and cap.tail_locked and
                      cap.full_tail_observations>=2 and bound is not None and
                      bound.state in ('SCHEDULED','HELD') and bound.tail_uid==cap.uid and
                      cap.terminal_owner_uid==bound.uid and
                      sum(n.tail_uid==cap.uid for n in self.notes.values())==1)
            if not preserve:
                cap.terminal_owner_uid='';cap.terminal_seen_at=float('-inf')
                cap.connection_owner_uid=''
        previous_tail=not cap.note_uid and (cap.tail_locked or cap.votes.get('hold_tail',0)>max(cap.votes.get('hold_head',0),
                        cap.votes.get('tap',0) if cap.detection.color=='yellow' else 0))
        owner=self.notes.get(cap.note_uid)
        evidence_kind='tap' if c.recovery_only and owner and owner.kind=='tap' else c.kind
        cap.detection=c;cap.votes[evidence_kind]=cap.votes.get(evidence_kind,0)+1
        if (c.kind=='hold_tail' or previous_tail) and c.bbox[3]>=6:cap.full_tail_observations+=1
        is_tail=not cap.note_uid and (cap.tail_locked or cap.votes.get('hold_tail',0)>max(cap.votes.get('hold_head',0),
                        cap.votes.get('tap',0) if cap.detection.color=='yellow' else 0))
        y=c.bbox[1] if is_tail else c.bbox[1]+c.bbox[3]
        cap.samples.append((t,float(y),*c.span))
        if is_tail:return
        if not cap.note_uid and c.kind not in ('tap','hold_head','plate_fragment'):return
        if not cap.note_uid:
            cap.note_uid=f'note:{cap.uid.split(":")[-1]}'
            # Yellow has both Tap and Hold appearances. A weak first bevel
            # observation cannot latch the whole lifetime into Hold.
            self.notes[cap.note_uid]=Note(cap.note_uid,'hold' if c.kind=='hold_head' and c.color!='yellow' else 'tap',c.color,c)
        note=self.notes.get(cap.note_uid)
        if note is None:return
        if note.origin_y is None:note.origin_y=float(y)
        note.detection=c;note.head.append((t,float(y),*c.span));note.observations+=1;note.missed=0
        if c.kind=='tap' and c.bbox[3]>=8:note.last_full_tap_at=t
        if c.tap_marker:
            note.tap_marker=True;note.tap_marker_observations+=1;note.last_tap_marker_at=t
        minimum_face=10 if c.bbox[1]>=180 else 6
        early_yellow=(note.color!='yellow' or note.kind=='hold' or c.bbox[1]<180)
        if evidence_kind=='hold_head' and c.bbox[3]>=minimum_face and early_yellow:
            note.full_head_observations+=1;note.last_full_head_at=t
        if not c.recovery_only and note.state not in ('SCHEDULED','HELD','PRESSED','DONE'):
            if note.tap_marker:note.kind='tap'
            elif note.color=='green' and cap.votes.get('hold_head',0)>=2:note.kind='hold'
            elif note.color=='yellow' and note.full_head_observations>=2:note.kind='hold'
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
                if n.kind!='hold' or not n.confirmed or n.state=='DONE':continue
                # A pressed head can disappear under the judgment effect just
                # before the probe. Seed its visible ribbon while still fresh.
                fresh_start=(n.state=='HELD' and (t-n.last_seen<.12 or
                             (n.press_at is not None and 0<=t-n.press_at<.12)))
                if n.head[-1][1]<probe and not fresh_start:continue
                if n.body_span is not None and t-n.body_seen_at>.25:continue
                expected=n.body_span or n.detection.span
                for i,run in enumerate(runs):
                    if overlap(expected,run)>.4:
                        body_offers.append((n.state not in ('HELD','SCHEDULED'),abs(sum(expected)-sum(run)), -n.last_seen,n.uid,i))
            used_notes=set();used_runs=set()
            for _,_,_,uid,i in sorted(body_offers):
                if uid in used_notes or i in used_runs:continue
                n=self.notes[uid];n.body_span=runs[i];n.body_seen_at=t
                used_notes.add(uid);used_runs.add(i)
        # A cap already owns a HEAD identity. Historical tail votes cannot
        # also assign that same plate as another note's tail.
        def moving_endpoint(cap):
            points=list(cap.samples)
            return (len(points)>=3 and points[-1][0]-points[0][0]>=.045 and
                    points[-1][1]-points[0][1]>=5 and
                    np.mean(np.diff([p[1] for p in points])>=-2)>=.8)
        tails=[c for c in self.caps.values() if not c.note_uid and
               c.votes.get('hold_tail',0)>=2 and (c.tail_locked or
               c.votes.get('hold_tail',0)>max(c.votes.get('hold_head',0),c.votes.get('tap',0) if c.detection.color=='yellow' else 0)) and
               t-c.samples[-1][0]<.12 and
               (any(n.tail_uid==c.uid for n in self.notes.values()) or moving_endpoint(c))]
        occupied={n.tail_uid for n in self.notes.values() if n.tail_uid}
        claims={uid:[n for n in self.notes.values() if n.tail_uid==uid] for uid in occupied}
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
        # A measured terminal face with one actual ribbon owner can authorize
        # a conservative KEY-UP estimate even if judgment effects hide it
        # before the tighter key-DOWN timing bands are reached.
        for cap in tails:
            d=cap.detection
            if (cap.samples[-1][0]!=t or d.bbox[3]<6 or cap.full_tail_observations<2):continue
            # Establish the relationship while BOTH endpoints are visible,
            # before the head disappears into the judgment effect. Component
            # labels are compared only within this exact capture frame.
            current_heads=[n for n in self.notes.values() if n.kind=='hold' and n.last_seen==t and
                           d.component and n.detection.component==d.component]
            bound_heads=[n for n in current_heads if n.confirmed and n.full_head_observations>=2 and
                         n.tail_uid==cap.uid]
            connected_head=bound_heads[0] if len(bound_heads)==1 else None
            bound_owner=self.notes.get(cap.connection_owner_uid)
            continuous_connection=(bound_owner is not None and bound_owner.confirmed and
                                   bound_owner.full_head_observations>=2 and bound_owner.tail_uid==cap.uid)
            if (connected_head is not None or continuous_connection) and d.kind=='hold_tail' and d.below>=16:
                cap.terminal_owner_uid=connected_head.uid if connected_head is not None else bound_owner.uid
                cap.terminal_seen_at=t
                continue
            if d.kind not in ('hold_tail','body') or d.above>28 or d.below<36:continue
            owners=[n for n in self.notes.values() if n.state in ('HELD','SCHEDULED') and
                    n.body_span is not None and t-n.body_seen_at<.12 and
                    any(overlap(end,n.body_span)>.55 for end in endpoints.get(cap.uid,[]))]
            # A different, unresolved Hold touching the same effect must not
            # veto the endpoint's already established, non-transferable owner.
            bound=[n for n in owners if n.tail_uid==cap.uid]
            if len(bound)==1:owners=bound
            if len(owners)==1:
                cap.terminal_owner_uid=owners[0].uid;cap.terminal_seen_at=t
        for n in sorted(self.notes.values(),key=lambda n:n.state not in ('HELD','SCHEDULED')):
            if n.kind!='hold' or not n.confirmed or n.state=='DONE':continue
            if n.tail_uid:
                cap=self.caps.get(n.tail_uid)
                if cap is not None:
                    n.tail=deque(cap.samples,maxlen=16)
                    n.tail_last_kind=cap.detection.kind
                # Preserve an already measured release deadline. Only an
                # unresolved, lost endpoint may seek a replacement; absence
                # itself neither releases the key nor deletes its history.
                if (n.release_at is not None or
                        (cap is not None and t-cap.samples[-1][0]<.12)):continue
                if n.state not in ('HELD','SCHEDULED') and (
                        n.full_head_observations<4 or n.origin_y is None or n.origin_y>=180 or
                        n.tail_last_kind!='hold_tail'):continue
            offers=[]
            for cap in tails:
                previous=claims.get(cap.uid,[])
                transfer=bool(previous)
                if transfer and (n.state not in ('HELD','SCHEDULED') or
                                 any(o.state in ('HELD','SCHEDULED') for o in previous)):continue
                if transfer and cap.detection.bbox[3]<6:continue
                if n.tail_uid and cap.detection.bbox[3]<6:continue
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
                if n.tail_uid and n.state not in ('HELD','SCHEDULED') and (
                        not same_component or c.color!=n.color or c.bbox[3]<6 or
                        c.kind!='hold_tail' or cap.full_tail_observations<2 or c.above>8 or
                        n.detection.kind!='hold_head' or
                        n.detection.bbox[3]<(6 if n.detection.bbox[1]<180 else 10) or
                        c.bbox[3]>n.detection.bbox[3]+2):continue
                if not transfer and same_component and len(owners)==1:
                    offers.append((0.,cap));continue
                if (not fresh_head or n.state in ('HELD','SCHEDULED')) and path_mask is not None and t-n.body_seen_at<.12:
                    possible=[o.uid for o in self.notes.values() if o.kind=='hold' and o.confirmed and o.state!='DONE' and
                              (not o.tail_uid or (o.state in ('HELD','SCHEDULED') and o.release_at is None and
                               (o.tail_uid not in self.caps or t-self.caps[o.tail_uid].samples[-1][0]>=.12))) and
                              o.body_span is not None and t-o.body_seen_at<.12 and
                              any(overlap(end,o.body_span)>.55 for end in endpoints.get(cap.uid,[]))]
                    active=[uid for uid in possible if self.notes[uid].state in ('HELD','SCHEDULED')]
                    if active:possible=active
                    if possible==[n.uid]:offers.append((1.,cap))
            if len(offers)==1:
                n.tail_uid=offers[0][1].uid
                for old in claims.get(n.tail_uid,[]):
                    old.tail_uid='';old.tail.clear();old.tail_last_kind=''
                    self.audit.append(dict(event='tail_transferred',previous_uid=old.uid,
                                           note_uid=n.uid,tail_uid=n.tail_uid,capture_timestamp=t))
                occupied.add(n.tail_uid);claims[n.tail_uid]=[n]
                offers[0][1].tail_locked=True
                offers[0][1].connection_owner_uid=n.uid
                n.tail=deque(offers[0][1].samples,maxlen=16)
                n.tail_last_kind=offers[0][1].detection.kind
