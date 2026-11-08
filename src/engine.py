"""One causal perception-to-action path shared by replay and Windows live."""
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

    def _consolidate_tap_identity(self,frame):
        """A recovered complete face may replace a late-created fragment UID.

        Require earlier observations of this same complete span, containment of
        the lost fragment and its predicted position inside the current face.
        Time proximity alone never merges notes; current distinct faces and
        two complete consecutive faces are kept independent.
        """
        snapshot=self.scheduler.snapshot();t=frame.captured_at
        for young in list(self.tracker.notes.values()):
            if (young.kind!='tap' or not young.confirmed or young.last_seen!=t or
                    young.detection.bbox[3]<8):continue
            lo,hi=young.detection.span;proof=[]
            for old in self.tracker.notes.values():
                if (old.uid==young.uid or old.kind!='tap' or old.color!=young.color or
                        not old.confirmed or not 0<t-old.last_seen<=.14 or len(old.head)<6 or
                        young.origin_y<old.origin_y+45 or
                        old.uid not in snapshot['pending'] and old.uid not in snapshot['consumed']):continue
                olo,ohi=old.detection.span
                if ohi-olo>.8*(hi-lo) or min(hi,ohi)-max(lo,olo)<.85*(ohi-olo):continue
                prior=[p for p in old.head if p[0]<young.head[0][0] and
                       abs(p[2]-lo)<=.03 and abs(p[3]-hi)<=.03]
                if len(prior)<3 or prior[-1][0]-prior[0][0]<.08:continue
                points=list(old.head)[-6:]
                slopes=[(b[1]-a[1])/(b[0]-a[0]) for i,a in enumerate(points) for b in points[i+1:]]
                projected=old.head[-1][1]+max(0,median(slopes))*(t-old.last_seen)
                _,top,_,height=young.detection.bbox
                if not top-3<=projected<=top+height+3:continue
                if old.key:
                    lane=KEYS.index(old.key)
                    if min(hi,(lane+1)/6)-max(lo,lane/6)<.05:continue
                proof.append(old)
            caps=[c for c in self.tracker.caps.values() if c.note_uid==young.uid and c.samples[-1][0]==t]
            if len(proof)!=1 or len(caps)!=1:continue
            old=proof[0]
            canonical,alias=old,young
            if not self.scheduler.consume_alias(alias.uid,canonical.uid):
                # A scheduler poll may have fired the recovered UID while the
                # frame was processing. Keep that real action and cancel only
                # the still-unused original reservation, never send twice.
                canonical,alias=young,old
                if young.uid not in self.scheduler.snapshot()['fired'] or not self.scheduler.consume_alias(alias.uid,canonical.uid):continue
            existing={p[0]:p for p in canonical.head}
            canonical.observations+=sum(p[0] not in existing for p in alias.head)
            for point in alias.head:
                if point[0] not in existing or point[1]>existing[point[0]][1]:existing[point[0]]=point
            canonical.head=deque(sorted(existing.values())[-12:],maxlen=12)
            canonical.detection=young.detection;canonical.missed=0
            canonical.origin_y=min(old.origin_y,young.origin_y)
            canonical.aliases.extend([alias.uid,*alias.aliases])
            for uid,c in list(self.tracker.caps.items()):
                if c.note_uid in (old.uid,young.uid) and c is not caps[0]:self.tracker.caps.pop(uid)
            caps[0].note_uid=canonical.uid;caps[0].samples=deque(canonical.head,maxlen=16)
            self.tracker.notes.pop(alias.uid)

    def observe(self,frame):
        if not (math.isfinite(frame.captured_at) and math.isfinite(frame.acquired_at) and
                frame.acquired_at>=frame.captured_at and frame.captured_at>self.last_capture):
            self.scheduler.disarm('invalid_capture_clock')
            raise ValueError('Invalid or nonmonotonic capture timestamp')
        self.last_capture=frame.captured_at;self.frame_count+=1
        self.scheduler.begin_frame(frame.captured_at,frame.focused,frame.roi_valid)
        started=time.perf_counter()
        image=self.geometry.normalize(frame.image)
        playing=self.gate.update(image) if frame.focused and frame.roi_valid else False
        if playing:
            self.absent_since=None;self.reset_done=False
            ds=self.perception.detect(image)
            notes=self.tracker.update(ds,frame.captured_at,self.perception.last_labels,self.perception.last_path)
        else:
            if self.absent_since is None:self.absent_since=frame.captured_at
            if not self.reset_done and frame.captured_at-self.absent_since>=.3:
                self.tracker.reset();self.reset_done=True
            notes=list(self.tracker.notes.values());ds=[]
        return dict(frame=frame,image=image,playing=playing,notes=notes,detections=ds,
                    cpu_ms=(time.perf_counter()-started)*1000)

    def decide(self,observation,processed_at=None):
        s=self.scheduler;frame=observation['frame']
        now=s.clock() if processed_at is None else processed_at
        s.update_context(frame.captured_at,observation['playing'],frame.focused,frame.roi_valid)
        for uid,reason in s.drain_releases():
            note=self.tracker.notes.get(uid)
            if note:note.state='DONE';note.reason=reason
        self._consolidate_tap_identity(frame)
        observation['notes']=list(self.tracker.notes.values())
        snapshot=s.snapshot();held={a.uid:a for a in snapshot['held'].values()}
        self.decisions=[]
        for n in sorted(observation['notes'],key=lambda n:(-n.head[-1][1],n.uid)):
            row=dict(sequence=frame.sequence,capture_timestamp=frame.captured_at,note_uid=n.uid,
                     kind=n.kind,color=n.color,bbox=list(self.geometry.native_bbox(n.detection.bbox)),
                     keys='|'.join(n.detection.keys),last_observation=n.last_seen,observations=n.observations,
                     state=n.state,reason=n.reason,crossing_at='',press_at='',release_at='',uncertainty='')
            cap=self.tracker.caps.get(n.tail_uid)
            row.update(tail_last_observation=n.tail[-1][0] if n.tail else None,
                       tail_bbox=list(self.geometry.native_bbox(cap.detection.bbox)) if cap else None,
                       tail_y=n.tail[-1][1] if n.tail else None,
                       tail_prediction_reason='',tail_crossing_at=None,tail_uncertainty=None,
                       release_update_reason='')
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
                elif tail.reason=='ready':
                    end=tail.crossing_at+tail.uncertainty+self.timing.release_guard
                    result=s.update_release(n.uid,end)
                    row['release_update_reason']=result.reason
                    if result:n.release_at=end
                    n.reason='tail_prediction' if result else result.reason
                else:n.reason='holding_until_measured_tail:'+tail.reason
            elif n.uid in snapshot['consumed']:
                n.state='DONE'
            elif not n.confirmed:
                n.reason='insufficient_motion_or_late_origin'
            elif not observation['playing']:
                n.reason='not_playing'
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
                            result=s.offer(Action(n.uid,key,n.kind,estimate.press_at,estimate.uncertainty,end))
                            n.reason=result.reason
                            if result:
                                n.key=key;n.press_at=estimate.press_at;n.release_at=end;n.state='SCHEDULED'
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
