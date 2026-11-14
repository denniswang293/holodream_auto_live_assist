"""Causal perception, tracking, timing and action planning for live Assist."""
from __future__ import annotations
from collections import Counter,deque
import math,time
from statistics import median
import cv2,numpy as np
from .perception import Perception
from .tracking import Tracker
from .timing import Timing
from .scheduler import Action
from .model import KEYS


class GameGate:
    def __init__(self):self.streak=0
    def update(self,image):
        hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV)
        mask=cv2.inRange(hsv,np.array((78,65,170)),np.array((104,255,255)))
        fractions=[float(np.mean(mask[y0:y1,x0:x1]>0)) for x0,y0,x1,y1 in
                   [(80,10,280,38),(550,10,655,40),(675,10,710,50)]]
        present=fractions[0]>=.15 and sum(f>=.15 for f in fractions)>=2
        self.streak=self.streak+1 if present else 0
        return self.streak>=3


class Engine:
    def __init__(self,geometry,scheduler,calibration):
        self.geometry=geometry;self.scheduler=scheduler
        self.perception=Perception(geometry);self.tracker=Tracker(geometry)
        self.timing=Timing(geometry,calibration);self.gate=GameGate()
        self.last_capture=float('-inf');self.absent_since=None;self.reset_done=False
        self.decisions=[];self.frame_count=0
        self.hold_connections={}

    def _consolidate_tap_identity(self,frame):
        """A recovered complete face may replace a late-created fragment UID.

        Require earlier observations of this same complete span, containment of
        the lost fragment and its predicted position inside the current face.
        Time proximity alone never merges notes; current distinct faces and
        two complete consecutive faces are kept independent.
        """
        snapshot=self.scheduler.snapshot();t=frame.captured_at
        for young in list(self.tracker.notes.values()):
            moving=(len(young.head)>=3 and young.head[-1][0]-young.head[0][0]>=.045 and
                    young.head[-1][1]-young.head[0][1]>=5)
            if (young.kind!='tap' or (not young.confirmed and not moving) or young.last_seen!=t or
                    young.detection.bbox[3]<8):continue
            lo,hi=young.detection.span;proof=[]
            for old in self.tracker.notes.values():
                hold_recovery=(old.kind=='hold' and old.color=='yellow' and
                               old.full_head_observations>=2 and bool(old.tail_uid))
                if (old.uid==young.uid or (old.kind!='tap' and not hold_recovery) or old.color!=young.color or
                        not old.confirmed or not 0<t-old.last_seen<=(.24 if hold_recovery else .14) or len(old.head)<6 or
                        young.origin_y<old.origin_y+45):continue
                olo,ohi=old.detection.span
                if ohi-olo>.8*(hi-lo) or min(hi,ohi)-max(lo,olo)<.85*(ohi-olo):continue
                prior=[p for p in old.head if p[0]<young.head[0][0] and
                       abs(p[2]-lo)<=.03 and abs(p[3]-hi)<=.03]
                if len(prior)<3 or prior[-1][0]-prior[0][0]<.08:continue
                # For an occluded Hold use the earlier complete-face motion,
                # not the late stationary bevel/text fragment it split into.
                unreserved=old.uid not in snapshot['pending'] and old.uid not in snapshot['consumed']
                if not young.confirmed and (not unreserved or hold_recovery):continue
                points=prior[-6:] if hold_recovery or unreserved else list(old.head)[-6:]
                slopes=[(b[1]-a[1])/(b[0]-a[0]) for i,a in enumerate(points) for b in points[i+1:]]
                projected=points[-1][1]+max(0,median(slopes))*(t-points[-1][0])
                _,top,_,height=young.detection.bbox
                if not top-3<=projected<=top+height+3:continue
                if unreserved and not hold_recovery and abs(projected-(top+height))>4:continue
                if old.key:
                    lane=KEYS.index(old.key)
                    if min(hi,(lane+1)/6)-max(lo,lane/6)<.05:continue
                proof.append(old)
            caps=[c for c in self.tracker.caps.values() if c.note_uid==young.uid and c.samples[-1][0]==t]
            if len(proof)!=1 or len(caps)!=1:continue
            old=proof[0]
            canonical,alias=old,young
            if not self.scheduler.consume_alias(alias.uid,canonical.uid):
                if old.kind=='hold':continue
                # A scheduler poll may have fired the recovered UID while the
                # frame was processing. Keep that real action and cancel only
                # the still-unused original reservation, never send twice.
                canonical,alias=young,old
                if young.uid not in self.scheduler.snapshot()['fired'] or not self.scheduler.consume_alias(alias.uid,canonical.uid):continue
            existing={p[0]:p for p in canonical.head}
            canonical.observations+=sum(p[0] not in existing for p in alias.head)
            for point in alias.head:
                if point[0] not in existing or point[1]>existing[point[0]][1]:existing[point[0]]=point
            canonical.head=deque(sorted(existing.values())[-32:],maxlen=32)
            canonical.detection=young.detection;canonical.missed=0
            canonical.origin_y=min(old.origin_y,young.origin_y)
            canonical.last_full_tap_at=max(old.last_full_tap_at,young.last_full_tap_at)
            canonical.aliases.extend([alias.uid,*alias.aliases])
            for endpoint in self.tracker.caps.values():
                if endpoint.terminal_owner_uid==alias.uid:endpoint.terminal_owner_uid=canonical.uid
                if endpoint.connection_owner_uid==alias.uid:endpoint.connection_owner_uid=canonical.uid
            for uid,c in list(self.tracker.caps.items()):
                if c.note_uid in (old.uid,young.uid) and c is not caps[0]:self.tracker.caps.pop(uid)
            caps[0].note_uid=canonical.uid;caps[0].samples=deque(canonical.head,maxlen=16)
            self.tracker.notes.pop(alias.uid)

    def _recover_unreserved_hold_head(self,frame):
        """Replace an interior observation with a uniquely connected real head.

        Only a previously confirmed, never-reserved Hold can lend identity.
        Connectivity is measured in THIS image, not by reusing component IDs.
        No new detection, deadline or action is invented here.
        """
        labels=self.perception.last_labels
        if labels is None:return
        snapshot=self.scheduler.snapshot();t=frame.captured_at
        used=set(snapshot['pending'])|set(snapshot['consumed'])|{a.uid for a in snapshot['held'].values()}
        notes=list(self.tracker.notes.values())
        for young in notes:
            d=young.detection
            if (young.uid in used or young.kind!='hold' or young.last_seen!=t or
                    young.origin_y<self.geometry.hit_y-75 or young.full_head_observations<2 or
                    d.kind!='hold_head' or d.bbox[3]<10 or d.above<36 or d.below>=16 or not d.component):continue
            if not young.confirmed:
                motion=list(young.head)
                if not (len(motion)>=3 and motion[-1][0]-motion[0][0]>=.045 and
                        motion[-1][1]-motion[0][1]>=5 and
                        np.mean(np.diff([p[1] for p in motion])>=-2)>=.8):continue
            parents=[]
            for old in notes:
                if (old.uid==young.uid or old.uid in used or old.kind!='hold' or old.color!=young.color or
                        not old.confirmed or old.origin_y>=180 or old.full_head_observations<4 or
                        not 0<t-old.last_seen<=.30 or not (old.detection.kind=='body' or
                        (old.detection.kind=='hold_head' and old.detection.bbox[1]>=180 and
                         old.detection.bbox[3]<8))):continue
                tail=self.tracker.caps.get(old.tail_uid)
                if (tail is None or tail.full_tail_observations<2 or t-tail.samples[-1][0]>.06 or
                        tail.detection.kind!='hold_tail' or tail.terminal_owner_uid!=old.uid):continue
                x,y,w,h=old.detection.bbox
                region=labels[max(0,y):min(labels.shape[0],y+h),max(0,x):min(labels.shape[1],x+w)]
                positive=region[region>0]
                if len(positive) and float(np.mean(positive==d.component))>=.9:parents.append(old)
            if len(parents)!=1:continue
            # A shared component containing another complete late head is
            # ambiguous (e.g. a chord crossing an effect). Do not merge it.
            siblings=[n for n in notes if n.uid not in used and n.uid!=young.uid and
                      n.kind=='hold' and n.last_seen==t and n.origin_y>=self.geometry.hit_y-75 and
                      n.detection.kind=='hold_head' and n.detection.bbox[3]>=10 and
                      n.detection.component==d.component]
            caps=[c for c in self.tracker.caps.values() if c.note_uid==young.uid and c.samples[-1][0]==t]
            if siblings or len(caps)!=1:continue
            old=parents[0]
            other_ribbon=False
            for other in notes:
                if other.uid in (old.uid,young.uid) or other.kind!='hold' or not other.confirmed or other.state=='DONE':continue
                endpoint=self.tracker.caps.get(other.tail_uid)
                if ((other.last_seen==t and other.detection.component==d.component) or
                        (endpoint is not None and endpoint.samples[-1][0]==t and
                         endpoint.detection.component==d.component)):
                    other_ribbon=True;break
            if other_ribbon:continue
            if not self.scheduler.consume_alias(young.uid,old.uid):continue
            old.head=deque(young.head,maxlen=32);old.detection=d;old.missed=0
            old.observations+=young.observations;old.last_full_head_at=t
            old.aliases.extend([young.uid,*young.aliases])
            for uid,cap in list(self.tracker.caps.items()):
                if cap.note_uid==old.uid:self.tracker.caps.pop(uid)
                if cap.terminal_owner_uid==young.uid:cap.terminal_owner_uid=old.uid
                if cap.connection_owner_uid==young.uid:cap.connection_owner_uid=old.uid
            if not old.tail_uid and young.tail_uid:
                old.tail_uid=young.tail_uid;old.tail=deque(young.tail,maxlen=16);old.tail_last_kind=young.tail_last_kind
            caps[0].note_uid=old.uid;caps[0].samples=deque(old.head,maxlen=16)
            young.state='DONE';young.reason='recovered_head_from_current_ribbon'
            used.add(young.uid)

    def _consolidate_hold_fragments(self,frame):
        """Retire a late interior fragment that recovers the same full head.

        Releasing a stuck Hold frees keys and otherwise exposes this recorded
        duplicate. Require its initial narrow span inside an older moving
        head at the SAME capture time, then recovery of that complete span.
        The original Hold action, tail and starting key remain untouched.
        """
        snapshot=self.scheduler.snapshot();t=frame.captured_at
        reserved=set(snapshot['pending'])|{a.uid for a in snapshot['held'].values()}
        held={a.uid for a in snapshot['held'].values() if a.kind=='hold'}
        for young in self.tracker.notes.values():
            motion=list(young.head)
            fragment_motion=(len(motion)>=3 and motion[-1][0]-motion[0][0]>=.045 and
                             motion[-1][1]-motion[0][1]>=5)
            if (young.kind!='hold' or (not young.confirmed and not fragment_motion) or young.state=='DONE' or
                    (young.uid in snapshot['consumed'] and young.uid not in held) or young.last_seen!=t or
                    young.detection.bbox[3]<8):continue
            first=young.head[0];first_width=first[3]-first[2]
            proof=[]
            for old in self.tracker.notes.values():
                old_reserved=old.uid in reserved
                if (old.uid==young.uid or (not old_reserved and
                        (not old.confirmed or old.full_head_observations<2)) or old.state=='DONE' or old.kind!='hold' or
                        old.color!=young.color or
                        t-old.last_seen>.24):continue
                # A late ID can start on a stray bevel OUTSIDE the head,
                # then recover that same complete moving face. Do not let
                # its one bad birth sample veto all later image evidence.
                # Require an older verified endpoint plus three subsequent
                # whole-span views and the old head's projected edge inside
                # the current face. A nearby independent head is insufficient.
                endpoint=self.tracker.caps.get(old.tail_uid)
                if (old.confirmed and old.origin_y<180 and young.origin_y>=self.geometry.hit_y-100 and
                        not young.tail_uid and endpoint is not None and endpoint.full_tail_observations>=2 and
                        endpoint.connection_owner_uid==old.uid and
                        old.full_head_observations>=4 and 8<=young.detection.bbox[3]<=30):
                    lo,hi=young.detection.span
                    prior=[p for p in old.head if p[0]<first[0] and
                           p[3]-p[2]>=.9*(hi-lo) and
                           min(p[3],hi)-max(p[2],lo)>=.85*(hi-lo)]
                    if len(prior)>=3 and prior[-1][0]-prior[0][0]>=.08:
                        a,b=prior[-1][2:4];width=b-a
                        recovered=[p for p in motion[1:] if p[3]-p[2]>=.8*width and
                                   p[2]>=a-.02 and p[3]<=b+.02]
                        if len(recovered)>=3 and recovered[-1][0]-recovered[0][0]>=.04 and recovered[-1][1]-recovered[0][1]>=5:
                            slopes=[(q[1]-p[1])/(q[0]-p[0]) for i,p in enumerate(prior) for q in prior[i+1:]]
                            speed=median(slopes);edge=prior[-1][1]+speed*(t-prior[-1][0])
                            _,top,_,height=young.detection.bbox
                            if 20<speed<1400 and top-3<=edge<=top+height+3:
                                proof.append(old);continue
                if t-old.last_seen<=.06 and not (old.tail_uid and young.tail_uid and old.tail_uid!=young.tail_uid):
                    x,y,w,h=young.detection.bbox;a,b,c,d=old.detection.bbox
                    ix=max(0,min(x+w,a+c)-max(x,a));iy=max(0,min(y+h,b+d)-max(y,b))
                    if d<=h and ix>=.8*c and iy>=.8*d:
                        common=[];used=set();observed=list(old.head);j=0
                        for p in young.head:
                            while j+1<len(observed) and abs(observed[j+1][0]-p[0])<abs(observed[j][0]-p[0]):j+=1
                            q=observed[j]
                            if (q[0] not in used and abs(q[0]-p[0])<=.02 and abs(p[1]-q[1])<=8 and
                                    min(p[3],q[3])-max(p[2],q[2])>=.8*min(p[3]-p[2],q[3]-q[2])):
                                common.append(p);used.add(q[0])
                        moving=(common and common[-1][1]-common[0][1]>=5 and
                                observed[-1][1]-observed[0][1]>=5)
                        if len(common)>=3 and common[-1][0]-common[0][0]>=.04 and moving:
                            proof.append(old);continue
                if old.origin_y+45>young.origin_y:continue
                shared=next((p for p in old.head if p[0]==first[0]),None)
                adjacent=False;reappearance=False
                if shared is None:
                    prior_edge=[p for p in old.head if 0<first[0]-p[0]<=.04]
                    if prior_edge:
                        edge=prior_edge[-1]
                        # A bevel can disappear in one capture and the full
                        # face reappear in the very next one. Require that
                        # old leading edge INSIDE the first fragment's face,
                        # in addition to the complete-span history below.
                        if 0<=first[1]-edge[1]<=max(32,young.detection.bbox[3]+4):
                            shared=edge;adjacent=True
                    if shared is None and old.tail_uid:
                        endpoint=self.tracker.caps.get(old.tail_uid)
                        prior_edge=[p for p in old.head if 0<first[0]-p[0]<=.14]
                        if endpoint and endpoint.full_tail_observations>=2 and prior_edge:
                            shared=prior_edge[-1];reappearance=True
                if shared is None:continue
                lo,hi=young.detection.span;olo,ohi=old.detection.span
                width=shared[3]-shared[2]
                contained=(young.origin_y>=self.geometry.hit_y-75 and not adjacent and
                           0<=shared[1]-first[1]<=young.detection.bbox[3]+4 and
                           t-old.last_seen<=.06 and first_width<=.6*width and
                           min(first[3],shared[3])-max(first[2],shared[2])>=.9*first_width and
                           min(hi,ohi)-max(lo,olo)>=.85*max(hi-lo,ohi-olo))
                # Complementary left/right face fragments can alternate. The
                # old track must have seen this COMPLETE span repeatedly
                # before the split, and both fragments share the same real
                # timestamp and leading edge. Time proximity alone is not proof.
                prior=[p for p in old.head if p[0]<first[0] and
                       p[3]-p[2]>=.9*(hi-lo) and
                       min(p[3],hi)-max(p[2],lo)>=.85*(hi-lo) and
                       min(p[3],first[3])-max(p[2],first[2])>=.9*first_width]
                slice_pair=False
                if prior and not adjacent and abs(shared[1]-first[1])<=32:
                    whole=prior[-1][3]-prior[-1][2]
                    joined=max(shared[3],first[3])-min(shared[2],first[2])
                    intersection=min(shared[3],first[3])-max(shared[2],first[2])
                    slice_pair=(shared[3]-shared[2]<=.8*whole and first_width<=.8*whole and
                                intersection>=.2*min(shared[3]-shared[2],first_width) and
                                joined>=.85*whole and
                                min(shared[3],prior[-1][3])-max(shared[2],prior[-1][2])>=.9*(shared[3]-shared[2]))
                full_history=(len(prior)>=3 and prior[-1][0]-prior[0][0]>=.04 and
                              first_width<=(1.2 if reappearance else .8 if adjacent or slice_pair else .6)*(prior[-1][3]-prior[-1][2]) and
                              min(first[3],prior[-1][3])-max(first[2],prior[-1][2])>=.9*first_width)
                split_edge=False
                if full_history and 0<t-prior[-1][0]<=.5 and (reappearance or abs(shared[1]-first[1])<=32):
                    slopes=[(b[1]-a[1])/(b[0]-a[0]) for i,a in enumerate(prior) for b in prior[i+1:]]
                    speed=median(slopes)
                    projected=prior[-1][1]+speed*(t-prior[-1][0])
                    _,top,_,height=young.detection.bbox
                    split_edge=speed>20 and top-3<=projected<=top+height+3
                recovered=full_history and (split_edge if reappearance else
                          abs(shared[1]-first[1])<=3 or adjacent or split_edge or slice_pair)
                if not (contained or recovered):continue
                if not old_reserved and not recovered:continue
                proof.append(old)
            if len(proof)==1:
                old=proof[0]
                if old.uid in held:
                    canonical,alias=old,young
                elif young.uid in held:
                    canonical,alias=young,old
                elif old.uid in snapshot['pending'] or young.uid in snapshot['pending']:
                    planned=[n for n in (old,young) if n.uid in snapshot['pending']]
                    canonical=min(planned,key=lambda n:snapshot['pending'][n.uid].press_at)
                    alias=young if canonical is old else old
                else:
                    def identity_priority(n):
                        tail=self.tracker.caps.get(n.tail_uid)
                        return (not (tail and tail.full_tail_observations>=2),n.origin_y)
                    canonical=min((old,young),key=identity_priority)
                    alias=young if canonical is old else old
                if self.scheduler.consume_alias(alias.uid,canonical.uid):
                    canonical.aliases.append(alias.uid)
                    for endpoint in self.tracker.caps.values():
                        if endpoint.terminal_owner_uid==alias.uid:endpoint.terminal_owner_uid=canonical.uid
                        if endpoint.connection_owner_uid==alias.uid:endpoint.connection_owner_uid=canonical.uid
                    if not canonical.tail_uid and alias.tail_uid:
                        canonical.tail_uid=alias.tail_uid;canonical.tail=deque(alias.tail,maxlen=16);canonical.tail_last_kind=alias.tail_last_kind
                        alias.tail_uid='';alias.tail.clear();alias.tail_last_kind=''
                        cap=self.tracker.caps.get(canonical.tail_uid)
                        if cap:
                            if cap.terminal_owner_uid==alias.uid:cap.terminal_owner_uid=canonical.uid
                            if cap.connection_owner_uid==alias.uid:cap.connection_owner_uid=canonical.uid
                    current_caps=[c for c in self.tracker.caps.values() if c.note_uid==young.uid and
                                  c.samples[-1][0]==t]
                    if len(current_caps)==1:
                        # Identity consolidation must also move the CURRENT
                        # measurements, not leave the surviving head stale.
                        samples={p[0]:p for p in old.head}
                        for p in young.head:
                            if p[0] not in samples or p[1]>samples[p[0]][1]:samples[p[0]]=p
                        canonical.head=deque(sorted(samples.values())[-32:],maxlen=32)
                        canonical.detection=young.detection;canonical.missed=0
                        canonical.origin_y=min(old.origin_y,young.origin_y)
                        canonical.last_full_tap_at=max(old.last_full_tap_at,young.last_full_tap_at)
                        canonical.last_full_head_at=max(old.last_full_head_at,young.last_full_head_at)
                        for uid,c in list(self.tracker.caps.items()):
                            if c.note_uid in (old.uid,young.uid) and c is not current_caps[0]:self.tracker.caps.pop(uid)
                        current_caps[0].note_uid=canonical.uid
                        current_caps[0].samples=deque(canonical.head,maxlen=16)
                    alias.state='DONE';alias.reason='duplicate_hold_head_fragment'
        # Resolve a proven head identity before considering ribbon-interior
        # suppression: an older Hold effect can cover a NEW real head.
        for young in self.tracker.notes.values():
            if (young.kind=='hold' and young.uid not in held and young.state!='DONE' and
                    young.last_seen==t and young.confirmed):
                owners=self.tracker.ribbon_owners(young.detection,self.perception.last_path,t,held,
                                                  allow_near=young.origin_y>=self.geometry.hit_y-100)
                if young.tail_uid:
                    cap=self.tracker.caps.get(young.tail_uid)
                    if cap and cap.full_tail_observations>=2:
                        owners=[uid for uid in owners if self.tracker.notes[uid].tail_uid==young.tail_uid]
                previous=self.hold_connections.get(young.uid)
                if len(owners)==1:
                    owner=owners[0]
                    first,count=(previous[1],previous[2]+1) if previous and previous[0]==owner and t-previous[3]<.06 else (t,1)
                    self.hold_connections[young.uid]=(owner,first,count,t)
                    if count>=3 and t-first>=.04 and self.scheduler.consume_alias(young.uid,owner):
                        self.tracker.notes[owner].aliases.append(young.uid)
                        young.state='DONE';young.reason='connected_hold_interior'
                else:self.hold_connections.pop(young.uid,None)
        self.hold_connections={uid:v for uid,v in self.hold_connections.items()
                               if uid in self.tracker.notes and t-v[3]<.12}

    def observe(self,frame):
        if not (math.isfinite(frame.captured_at) and math.isfinite(frame.acquired_at) and
                frame.acquired_at>=frame.captured_at and frame.captured_at>self.last_capture):
            self.scheduler.disarm('invalid_capture_clock')
            raise ValueError('Invalid or nonmonotonic capture timestamp')
        self.last_capture=frame.captured_at;self.frame_count+=1
        self.scheduler.begin_frame(frame.captured_at,frame.focused,frame.roi_valid)
        started=time.perf_counter()
        profile={}
        stage=time.perf_counter()
        image=self.geometry.normalize(frame.image)
        profile['normalize_ms']=(time.perf_counter()-stage)*1000
        stage=time.perf_counter()
        playing=self.gate.update(image) if frame.focused and frame.roi_valid else False
        profile['game_gate_ms']=(time.perf_counter()-stage)*1000
        if playing:
            self.absent_since=None;self.reset_done=False
            stage=time.perf_counter()
            ds=self.perception.detect(image)
            profile['perception_ms']=(time.perf_counter()-stage)*1000
            stage=time.perf_counter()
            notes=self.tracker.update(ds,frame.captured_at,self.perception.last_labels,self.perception.last_path)
            profile['tracker_association_ms']=(time.perf_counter()-stage)*1000
        else:
            if self.absent_since is None:self.absent_since=frame.captured_at
            if not self.reset_done and frame.captured_at-self.absent_since>=.3:
                self.tracker.reset();self.reset_done=True
            notes=list(self.tracker.notes.values());ds=[]
            profile['perception_ms']=0.;profile['tracker_association_ms']=0.
        provider_profile=getattr(self.perception,'last_profile',{})
        return dict(frame=frame,image=image,playing=playing,notes=notes,detections=ds,
                    cpu_ms=(time.perf_counter()-started)*1000,profile={**profile,**provider_profile})

    def decide(self,observation,processed_at=None):
        s=self.scheduler;frame=observation['frame']
        now=s.clock() if processed_at is None else processed_at
        s.update_context(frame.captured_at,observation['playing'],frame.focused,frame.roi_valid)
        for uid,reason in s.drain_releases():
            note=self.tracker.notes.get(uid)
            if note:note.state='DONE';note.reason=reason
        for note in self.tracker.notes.values():
            if (not note.kind_locked and note.kind=='hold' and note.color=='yellow' and note.tap_marker_observations>=2 and
                    frame.captured_at-note.last_tap_marker_at<.06 and not note.tail_uid):
                if s.correct_hold_to_tap(note.uid):note.kind='tap'
        self._consolidate_tap_identity(frame)
        self._recover_unreserved_hold_head(frame)
        self._consolidate_hold_fragments(frame)
        observation['notes']=list(self.tracker.notes.values())
        snapshot=s.snapshot();held={a.uid:a for a in snapshot['held'].values()}
        self.decisions=[]
        for n in sorted(observation['notes'],key=lambda n:(-n.head[-1][1],n.uid)):
            row=dict(sequence=frame.sequence,capture_timestamp=frame.captured_at,note_uid=n.uid,
                     kind=n.kind,kind_locked=n.kind_locked,color=n.color,bbox=list(self.geometry.native_bbox(n.detection.bbox)),
                     keys='|'.join(n.detection.keys),last_observation=n.last_seen,observations=n.observations,
                     state=n.state,reason=n.reason,crossing_at='',press_at='',release_at='',uncertainty='',
                     detection_kind=n.detection.kind,detection_color=n.detection.color,
                     detection_component=n.detection.component,origin_y=n.origin_y,
                     confirmed=n.confirmed,
                     full_head_observations=n.full_head_observations,
                     last_full_tap_at=n.last_full_tap_at if math.isfinite(n.last_full_tap_at) else None)
            cap=self.tracker.caps.get(n.tail_uid)
            row.update(tail_last_kind=n.tail_last_kind,tail_last_observation=n.tail[-1][0] if n.tail else None,
                       tail_bbox=list(self.geometry.native_bbox(cap.detection.bbox)) if cap else None,
                       tail_y=n.tail[-1][1] if n.tail else None,
                       tail_prediction_reason='',tail_crossing_at=None,tail_uncertainty=None,
                       release_update_reason='',tail_detection_kind=cap.detection.kind if cap else None,
                       tail_detection_color=cap.detection.color if cap else None,
                       tail_terminal_owner=cap.terminal_owner_uid if cap else None)
            if n.uid in held and held[n.uid].kind=='tap':
                n.state='PRESSED';n.reason='tap_in_progress'
            elif n.uid in held:
                n.state='HELD'
                tail=self.timing.predict(n.tail,frame.captured_at,kind='tail')
                row.update(tail_prediction_reason=tail.reason,tail_crossing_at=tail.crossing_at,
                           tail_uncertainty=tail.uncertainty)
                full_tail=(cap is not None and cap.detection.bbox[3]>=6 and cap.samples[-1][0]==frame.captured_at)
                if len(n.tail)>=4 and full_tail and n.tail[-1][1]>=self.geometry.hit_y:
                    result=s.release_hold(n.uid)
                    row['release_update_reason']=result.reason
                    if result:n.release_at=now
                    n.reason='tail_observed_crossing' if result else result.reason
                elif tail.reason=='ready' or (
                        tail.reason=='motion_uncertainty' and cap is not None and
                        n.release_at is None and
                        cap.terminal_owner_uid==n.uid and frame.captured_at-cap.samples[-1][0]<.06 and
                        tail.eta_s is not None and 0<tail.eta_s<=.5):
                    # This only ends an existing Hold. Never use this bound
                    # to schedule a new down or to relax Tap uncertainty.
                    # The measured endpoint's uncertainty DELAYS release;
                    # hiding the endpoint alone cannot authorize an up.
                    end=tail.crossing_at+tail.uncertainty+self.timing.release_guard
                    result=s.update_release(n.uid,end)
                    row['release_update_reason']=result.reason
                    if result:n.release_at=end
                    n.reason=('tail_prediction' if tail.reason=='ready' else 'verified_terminal_upper_bound') if result else result.reason
                else:n.reason='holding_until_measured_tail:'+tail.reason
            elif n.uid in snapshot['consumed']:
                n.state='DONE'
            elif not n.confirmed:
                n.reason='insufficient_motion_or_late_origin'
            elif (n.kind=='tap' and n.uid not in snapshot['pending'] and
                  n.detection.kind!='tap' and not (n.detection.kind=='plate_fragment' and
                      0<=frame.captured_at-n.last_full_tap_at<=.14)):
                n.reason='tap_face_not_visible'
            elif not observation['playing']:
                n.reason='not_playing'
            elif (n.kind=='hold' and n.uid not in snapshot['pending'] and
                  (n.full_head_observations<2 or frame.captured_at-n.last_full_head_at>.2)):
                n.reason='hold_head_not_verified'
            elif (n.kind=='hold' and n.uid not in snapshot['pending'] and
                  n.origin_y>=self.geometry.hit_y-75 and
                  (not cap or cap.full_tail_observations<2)):
                # A new ID born inside the judgment effect is not evidence
                # of an independent Hold. Recover its earlier head identity
                # or establish a real tail before reserving a long press.
                n.reason='late_hold_head_without_identity'
            else:
                estimate=self.timing.predict(n.head,frame.captured_at,kind=n.kind)
                n.crossing_at=estimate.crossing_at;n.uncertainty=estimate.uncertainty
                n.reason=estimate.reason
                if estimate.reason=='ready' and estimate.press_at is not None:
                    if estimate.press_at<=now:n.reason='prediction_late'
                    elif estimate.press_at-now>.30:n.reason='outside_commit_horizon'
                    else:
                        existing=snapshot['pending'].get(n.uid)
                        if existing:keys=[existing.key]
                        else:
                            votes=Counter(key for point in list(n.head)[-8:] for i,key in enumerate(KEYS)
                                          if min(point[3],(i+1)/6)-max(point[2],i/6)>=.05)
                            keys=[k for k in KEYS if votes[k]>=max(1,min(8,len(n.head))*.6)]
                            center=sum(n.detection.span)/2*6
                            keys.sort(key=lambda k:(abs(KEYS.index(k)+.5-center),KEYS.index(k)))
                        end=None
                        if n.kind=='hold':
                            tail=self.timing.predict(n.tail,frame.captured_at,kind='tail')
                            if tail.reason=='ready':
                                proposed=tail.crossing_at+tail.uncertainty+self.timing.release_guard
                                if estimate.press_at+.04<proposed<=estimate.press_at+s.max_hold_s:end=proposed
                        if not keys:n.reason='no_reliable_key_coverage'
                        for key in keys:
                            press=estimate.press_at
                            if existing and n.kind=='hold' and n.aliases:
                                # A proven recovered head can repair an old
                                # fragment's ETA within the scheduler's SAME
                                # per-update/total/freeze limits. No extension
                                # or new action is created after expiry.
                                press=existing.press_at+max(-s.MAX_UPDATE_STEP,min(s.MAX_UPDATE_STEP,press-existing.press_at))
                            result=s.offer(Action(n.uid,key,n.kind,press,estimate.uncertainty,end))
                            n.reason=result.reason
                            if result:
                                n.key=key;n.press_at=press;n.release_at=end;n.state='SCHEDULED'
                                break
            row.update(state=n.state,reason=n.reason,key=n.key,crossing_at=n.crossing_at,
                       press_at=n.press_at,release_at=n.release_at,uncertainty=n.uncertainty,
                       tail_uid=n.tail_uid,tail_observations=len(n.tail),aliases='|'.join(n.aliases))
            self.decisions.append(row)
        s.poll()
        info=dict(sequence=frame.sequence,captured_at=frame.captured_at,acquired_at=frame.acquired_at,
                  processed_at=now,playing=observation['playing'],focused=frame.focused,roi_valid=frame.roi_valid,
                  hit_y=self.geometry.hit_y,held_keys='|'.join(sorted(s.snapshot()['held'])),
                  capture_age_ms=(now-frame.captured_at)*1000,cpu_ms=observation['cpu_ms'],
                  detections=len(observation['detections']),tracks=len(observation['notes']),
                  armed=s.armed,status=('INPUT PAUSED' if s.snapshot()['paused'] else 'ASSIST ARMED') if s.armed else 'INPUT OFF')
        return info,self.decisions
