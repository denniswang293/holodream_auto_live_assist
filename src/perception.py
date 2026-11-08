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
        path[round(self.geometry.hit_y)+2:]=0
        self.last_path=path
        # The same rows are queried by many head/tail hypotheses. Compute the
        # 3-of-5 vertical color support once, instead of recropping every row
        # for every endpoint and direction.
        binary=(path>0).astype(np.uint8)
        sums=cv2.boxFilter(binary,cv2.CV_16U,(1,5),normalize=False,borderType=cv2.BORDER_CONSTANT)
        supported=sums>=3
        changes=np.diff(np.pad(supported,((0,0),(1,1))).astype(np.int8),axis=1)
        row_cache={}
        rows,starts=np.nonzero(changes>0);_,ends=np.nonzero(changes<0)
        valid=(ends-starts>=round(18*scale))&(rows>=2)&(rows<path.shape[0]-2)
        for row,a,b in zip(rows[valid],starts[valid],ends[valid]):
            row_cache.setdefault(int(row),[]).append((int(a),int(b)))
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
                # The narrow dark band between a face and its bevel is part
                # of the plate shadow, unlike a horizontal inter-note gap.
                if compatible and ix>=.60*min(w,cw) and gap<=4 and min(h,ch)<=.35*max(h,ch):
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
        for c in consolidated:
            bx,by,bw,bh=c.bbox
            above=below=0.;kind='tap';component=0
            if c.color in ('green','yellow'):
                above=ribbon_depth(path,c.bbox,-1,row_cache);below=ribbon_depth(path,c.bbox,1,row_cache)
                if above>=16 and above>=below+12:kind='hold_head'
                elif below>=16 and below>=above+12:kind='hold_tail'
                elif above>=16 and below>=16:kind='body'
                elif c.color=='green':kind='ambiguous'
                sample_y=int(np.clip(by-5 if above>below else by+bh+5,0,labels.shape[0]-1))
                labs=labels[sample_y,max(0,bx):min(self.geometry.plane_width,bx+bw)]
                labs=labs[labs>0]
                if len(labs):component=int(np.bincount(labs).argmax())
            result.append(replace(c,kind=kind,component=component,above=above,below=below))
        return sorted(result,key=lambda c:(c.y,c.bbox[0],c.color))
