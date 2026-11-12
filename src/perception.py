"""Horizontal note plates and directional ribbon evidence in lane space.

No keyboard events or previous/future frames are consulted here.
"""
from __future__ import annotations
from dataclasses import replace
import cv2
import numpy as np
from .model import Detection,KEYS

COLORS={
    'cyan':((84,65,110),(112,255,255)),
    'yellow':((16,65,110),(43,255,255)),
    'green':((38,55,90),(83,255,255)),
    'pink':((135,65,110),(179,255,255)),
    'neutral':((0,0,155),(179,70,255)),
}


def intervals(mask,y):
    y=int(round(y))
    if not 2<=y<mask.shape[0]-2:return []
    on=np.count_nonzero(mask[y-2:y+3],axis=0)>=3
    edges=np.flatnonzero(np.diff(np.r_[False,on,False].astype(np.int8)))
    minimum=round(mask.shape[1]*.03)
    return [(int(a),int(b)) for a,b in zip(edges[::2],edges[1::2]) if b-a>=minimum]


def ribbon_depth(mask,bbox,direction,row_cache=None):
    """Follow a connected band locally, not its whole-component bounding box."""
    x,y,w,h=bbox;left,right=x,x+w
    depth=0;misses=0
    for step in range(4,85,4):
        row=y-step if direction<0 else y+h+step
        choices=[]
        runs=(row_cache.get(round(row),[]) if row_cache is not None else intervals(mask,row))
        for a,b in runs:
            overlap=min(right,b)-max(left,a)
            gap=max(a-right,left-b,0)
            if overlap>=.20*min(right-left,b-a) or gap<=mask.shape[1]*14/600:
                choices.append((max(0,overlap)-gap,a,b))
        if not choices:
            misses+=1
            if misses>=2:break
            continue
        _,left,right=max(choices);misses=0;depth=step
    return float(depth)


def tap_chevron(path,bbox):
    """The detached upward arrow above a yellow Tap is not a Hold ribbon."""
    x,y,w,h=bbox
    top=max(0,y-48);left=max(0,int(x-w*.2));right=min(path.shape[1],int(x+w*1.2))
    roi=path[top:max(top,y-3),left:right]
    if roi.size==0:return False
    contours,_=cv2.findContours(roi,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
    for contour in contours:
        a,b,c,d=cv2.boundingRect(contour)
        if not (18<=c<=w*1.2 and 7<=d<=44 and b>=2 and b+d<roi.shape[0]):continue
        if not x-w*.1<=left+a+c/2<=x+w*1.1:continue
        shape=np.zeros((d,c),np.uint8)
        points=contour.copy();points[:,:,0]-=a;points[:,:,1]-=b
        cv2.drawContours(shape,[points],-1,255,-1)
        # Two low arms and an empty lower centre distinguish a chevron from
        # a filled Hold band, a triangle, or a vertical hit-effect streak.
        if np.mean(shape[round(d*.7):,round(c*.4):max(round(c*.6),round(c*.4)+1)]>0)>.2:continue
        columns=np.flatnonzero(np.any(shape,axis=0))
        tops=np.argmax(shape[:,columns]>0,axis=0)
        middle=tops[(columns>=c*.4)&(columns<=c*.6)]
        l=tops[columns<c*.25];r=tops[columns>c*.75]
        if len(middle) and len(l) and len(r) and min(np.median(l),np.median(r))-np.median(middle)>=3:
            return True
    return False


class Perception:
    def __init__(self,geometry):
        self.geometry=geometry
        self.last_rect=None
        self.last_labels=None
        self.last_path=None

    def detect(self,native):
        rect=self.geometry.rectify(native)
        scale=self.geometry.plane_width/600
        self.last_rect=rect
        hsv=cv2.cvtColor(rect,cv2.COLOR_BGR2HSV)
        gray=cv2.cvtColor(rect,cv2.COLOR_BGR2GRAY)
        gradient=cv2.Sobel(gray,cv2.CV_32F,0,1,ksize=3)
        bright=hsv[:,:,2]>=135
        signed_edges=[((gradient>=65)&bright).astype(np.uint8)*255,
                      ((gradient<=-65)&bright).astype(np.uint8)*255]
        for edge in signed_edges:
            edge[:round(self.geometry.top_y)+2]=0
            edge[round(self.geometry.hit_y)+5:]=0
        masks={k:cv2.inRange(hsv,np.array(lo),np.array(hi)) for k,(lo,hi) in COLORS.items()}
        masks['pink']|=cv2.inRange(hsv,np.array((0,65,110)),np.array((8,255,255)))
        path=cv2.inRange(hsv,np.array((16,45,75)),np.array((83,255,255)))
        yellow_path=cv2.inRange(hsv,np.array((16,45,75)),np.array((43,255,255)))
        path[round(self.geometry.hit_y)+2:]=0
        self.last_path=path
        # The same rows are queried by many head/tail hypotheses. Compute the
        # 3-of-5 vertical color support once, instead of recropping every row
        # for every endpoint and direction.
        def cache_rows(mask):
            binary=(mask>0).astype(np.uint8)
            sums=cv2.boxFilter(binary,cv2.CV_16U,(1,5),normalize=False,borderType=cv2.BORDER_CONSTANT)
            changes=np.diff(np.pad(sums>=3,((0,0),(1,1))).astype(np.int8),axis=1)
            cache={}
            rows,starts=np.nonzero(changes>0);_,ends=np.nonzero(changes<0)
            valid=(ends-starts>=round(18*scale))&(rows>=2)&(rows<mask.shape[0]-2)
            for row,a,b in zip(rows[valid],starts[valid],ends[valid]):
                cache.setdefault(int(row),[]).append((int(a),int(b)))
            return cache
        row_cache=cache_rows(path)
        _,labels=cv2.connectedComponents(cv2.morphologyEx(path,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8)))
        self.last_labels=labels
        detected=[]
        for color,mask in masks.items():
            colored=cv2.dilate(mask,np.ones((3,1),np.uint8))
            edges=[]
            for polarity,raw_edge in zip((1,-1),signed_edges):
                lines=raw_edge&colored
                lines=cv2.morphologyEx(lines,cv2.MORPH_OPEN,np.ones((1,round(28*scale)),np.uint8))
                contours,_=cv2.findContours(lines,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
                for contour in contours:
                    x,y,w,h=cv2.boundingRect(contour)
                    if w<38*scale or h>10:continue
                    edges.append((x,y,w,h,polarity))
            for x,y,w,h,sign in edges:
                if sign<=0:continue
                pairs=[]
                for a,b,c,d,bottom_sign in edges:
                    gap=b-y
                    if bottom_sign>=0 or not 2<=gap<=28:continue
                    overlap=min(x+w,a+c)-max(x,a)
                    if overlap<.72*min(w,c) or max(w,c)>1.8*min(w,c):continue
                    left,right=max(x,a),min(x+w,a+c)
                    box=(left,y,right-left,b+d-y)
                    bx,by,bw,bh=box
                    fill=float(np.mean(mask[by:by+bh,bx:bx+bw]>0))
                    if fill < (.50 if color=='neutral' else .23):continue
                    # A face has a broad upper and lower edge; isolated HUD
                    # text and ribbon slivers fail these spatial tests.
                    score=.5*fill+.5*min(overlap/max(w,c),1.)
                    pairs.append((score,box))
                if not pairs:continue
                score,box=max(pairs,key=lambda item:item[0])
                bx,by,bw,bh=box
                keys=tuple(key for i,key in enumerate(KEYS)
                           if min(bx+bw,(i+1)*self.geometry.lane_pixels)-max(bx,i*self.geometry.lane_pixels)>=30*scale)
                if not keys:continue
                detected.append(Detection(box,color,'tap',keys,float(score),plane_width=self.geometry.plane_width))
        # Judgment text can cut a real green plate's white border into
        # pieces shorter than the edge-pair minimum. Recover its visible
        # bright colored face, with a real attached ribbon. This does not
        # invent a head from a predicted position or from missing pixels.
        recovery_faces=[]
        for face_color in ('green','yellow','cyan'):
            face_mask=masks[face_color].copy()
            face_mask[hsv[:,:,2]<170]=0
            face_mask[:round(self.geometry.top_y)+2]=0
            face_mask[round(self.geometry.hit_y)+5:]=0
            contours,_=cv2.findContours(face_mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                box=cv2.boundingRect(contour);x,y,w,h=box
                if not (self.geometry.hit_y-150<=y and w>=38*scale and 6<=h<=30 and w/h>=1.8):continue
                fill=cv2.contourArea(contour)/(w*h)
                if fill<.5:continue
                if any(d.color==face_color and
                       max(0,min(x+w,d.bbox[0]+d.bbox[2])-max(x,d.bbox[0]))*
                       max(0,min(y+h,d.bbox[1]+d.bbox[3])-max(y,d.bbox[1]))>=.5*w*h for d in detected):continue
                above=ribbon_depth(path,box,-1,row_cache);below=ribbon_depth(path,box,1,row_cache)
                ribbon_face=max(above,below)>=16 and abs(above-below)>=12
                broad_tap_face=face_color in ('yellow','cyan') and w/h>=3 and fill>=.65
                if not ((face_color!='cyan' and ribbon_face) or broad_tap_face):continue
                keys=tuple(key for i,key in enumerate(KEYS)
                           if min(x+w,(i+1)*self.geometry.lane_pixels)-max(x,i*self.geometry.lane_pixels)>=30*scale)
                if keys:recovery_faces.append(Detection(box,face_color,'tap',keys,float(fill),
                                                       plane_width=self.geometry.plane_width,recovery_only=True))
        # Rejoin a face split horizontally by its white symbol. The gap must
        # contain bright face pixels; a dark separation between chord notes
        # is not bridged, even at exactly the same height.
        joined=[]
        for c in sorted(detected,key=lambda c:c.bbox[0]):
            merged=False
            for i,other in enumerate(joined):
                if c.color!=other.color:continue
                x,y,w,h=c.bbox;a,b,cw,ch=other.bbox
                gap=x-(a+cw);top=max(y,b);bottom=min(y+h,b+ch)
                same_face_height=abs(y+h-b-ch)<=4
                partial_bevel=min(h,ch)<=.35*max(h,ch) and max(h,ch)>=8
                if not (0<=gap<=self.geometry.lane_pixels*.5 and
                        abs(y-b)<=3 and (same_face_height or partial_bevel) and bottom-top>=2):continue
                bridge=hsv[top:bottom,a+cw:x,2]
                if gap and (bridge.size==0 or np.mean(bridge>=135)<.9):continue
                box=(a,min(y,b),x+w-a,max(y+h,b+ch)-min(y,b))
                keys=tuple(k for k in KEYS if k in c.keys or k in other.keys)
                joined[i]=replace(other,bbox=box,keys=keys,score=max(c.score,other.score))
                merged=True;break
            if not merged:joined.append(c)
        detected=joined
        # Suppress alternate edge pairings of the same plate, never adjacent
        # disjoint plates belonging to a chord.
        kept=[]
        for c in sorted(detected,key=lambda c:(-c.bbox[3],-c.score,c.bbox)):
            x,y,w,h=c.bbox
            duplicate=False
            for index,other in enumerate(kept):
                a,b,cw,ch=other.bbox
                ix=max(0,min(x+w,a+cw)-max(x,a));iy=max(0,min(y+h,b+ch)-max(y,b))
                if ix>=.72*min(w,cw) and iy>=.45*min(h,ch):duplicate=True;break
                gap=max(y-(b+ch),b-(y+h),0)
                compatible=c.color==other.color or 'neutral' in (c.color,other.color)
                touching_face=False
                if (c.color==other.color=='green' and gap<=1 and max(h,ch)>=8 and
                        max(y+h,b+ch)-min(y,b)<=30 and ix>=.8*max(w,cw)):
                    seam=max(y,b)
                    strip=hsv[max(0,seam-1):seam+2,max(x,a):min(x+w,a+cw),2]
                    touching_face=strip.size>0 and np.mean(strip>=135)>=.8
                # The narrow dark band between a face and its bevel is part
                # of the plate shadow, unlike a horizontal inter-note gap.
                if compatible and ix>=.60*min(w,cw) and gap<=4 and (min(h,ch)<=.35*max(h,ch) or touching_face):
                    left,top=min(x,a),min(y,b);right,bottom=max(x+w,a+cw),max(y+h,b+ch)
                    kept[index]=replace(other,bbox=(left,top,right-left,bottom-top),
                                        color=c.color if other.color=='neutral' else other.color)
                    duplicate=True;break
            if not duplicate:kept.append(c)
        # A union formed late in consolidation can contain an earlier retained
        # fragment. Remove it now, after ALL unions, so its tracker cannot
        # commit a second action for that same visible face.
        consolidated=[]
        for c in sorted(kept,key=lambda d:-(d.bbox[2]*d.bbox[3])):
            x,y,w,h=c.bbox
            contained=False
            for other in consolidated:
                if c.color!=other.color and 'neutral' not in (c.color,other.color):continue
                a,b,cw,ch=other.bbox
                ix=max(0,min(x+w,a+cw)-max(x,a));iy=max(0,min(y+h,b+ch)-max(y,b))
                if ix>=.8*w and iy>=.8*h:contained=True;break
            if not contained:consolidated.append(c)
        result=[]
        for c in consolidated+recovery_faces:
            bx,by,bw,bh=c.bbox
            above=below=0.;kind='tap';component=0
            if c.color in ('green','yellow'):
                above=ribbon_depth(path,c.bbox,-1,row_cache);below=ribbon_depth(path,c.bbox,1,row_cache)
                # Yellow also has ordinary Tap faces. A partial bevel can
                # see 16--28 pixels of its OWN face as an apparent ribbon.
                # Require support beyond the face-pairing gap (28px), plus
                # two sampled rows, before calling it a yellow Hold HEAD.
                # Tail/body evidence keeps its existing rules: weakening it
                # here would break already established Hold-tail continuity.
                ribbon_min=36 if c.color=='yellow' else 16
                attached=True
                if c.color=='yellow' and above>=ribbon_min:
                    shared=path[max(0,by-12):by,max(0,bx):min(path.shape[1],bx+bw)]
                    support=np.count_nonzero(shared,axis=1)>=max(3,bw*.2)
                    if by<180:
                        # Only the clean upper region may establish a new
                        # yellow Hold type. A narrow foreign green ribbon is
                        # not proof; accept yellow attachment or a broad mixed
                        # body. At judgment keep existing raw face recovery:
                        # Tracker's type/commit guards govern its meaning.
                        strip=yellow_path[max(0,by-12):by,max(0,bx):min(path.shape[1],bx+bw)]
                        support=((np.count_nonzero(strip,axis=1)>=max(3,bw*.2)) |
                                 (np.count_nonzero(shared,axis=1)>=max(3,bw*.5)))
                    attached=(len(support)==12 and np.mean(support)>=.7 and
                              not np.any((~support[:-1])&(~support[1:])))
                if attached and above>=ribbon_min and above>=below+12:kind='hold_head'
                elif below>=16 and below>=above+12:kind='hold_tail'
                elif above>=16 and below>=16:kind='body'
                elif c.color=='green':kind='ambiguous'
                sample_y=int(np.clip(by-5 if above>below else by+bh+5,0,labels.shape[0]-1))
                labs=labels[sample_y,max(0,bx):min(self.geometry.plane_width,bx+bw)]
                labs=labs[labs>0]
                if len(labs):component=int(np.bincount(labs).argmax())
            marker=c.color=='yellow' and tap_chevron(path,c.bbox)
            # A flick-marked END of an established ribbon is still a tail;
            # do not manufacture a second input at the end of a Hold.
            if marker and not (kind=='hold_tail' and below>=36):kind='tap'
            # At the lower track a 3--7px edge pair is a connector/bevel,
            # not independent evidence of a complete tappable plate. Keep it
            # available for an existing Tap, without creating a new note.
            if kind=='tap' and by>=180 and bh<8:kind='plate_fragment'
            result.append(replace(c,kind=kind,component=component,above=above,below=below,
                                  tap_marker=marker))
        # A lit ribbon/text strip immediately above a separately visible
        # complete head is not a second head. Keep the complete lower face.
        # Ribbon depth alone is insufficient: effects can also surround a
        # genuine isolated head, so require actual same-frame face evidence.
        complete=[d for d in result if d.color=='green' and d.kind=='hold_head' and d.below<12]
        for i,c in enumerate(result):
            if c.color!='green' or c.kind!='hold_head' or c.above<36 or c.below<20:continue
            x,y,w,h=c.bbox
            if any(0<=d.bbox[1]-(y+h)<=4 and
                   min(x+w,d.bbox[0]+d.bbox[2])-max(x,d.bbox[0])>=.7*min(w,d.bbox[2])
                   for d in complete):result[i]=replace(c,kind='body')
        return sorted(result,key=lambda c:(c.y,c.bbox[0],c.color))
