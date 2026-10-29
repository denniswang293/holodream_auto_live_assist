"""Calibrated horizontal note bodies from edges and HSV evidence."""
from __future__ import annotations
from dataclasses import dataclass, field as dataclass_field
import cv2
import numpy as np
from .geometry import Playfield
from .hold_visual import path_depth, path_mask


@dataclass
class Candidate:
    bbox: tuple[int, int, int, int]
    appearance: str
    score: float
    u_min: float
    u_max: float
    candidate_keys: list[str]
    note_type: str = "unknown"
    body_bbox: tuple[int, int, int, int] | None = None
    path_bbox: tuple[int, int, int, int] | None = None
    raw_mask: np.ndarray | None = dataclass_field(default=None, repr=False)
    suspected_overlap: bool = False
    hold_path_px: int = 0


def _playfield_mask(shape: tuple[int, int], playfield: Playfield,
                    reference_resolution: tuple[int, int]) -> np.ndarray:
    h,w = shape
    rw,rh = reference_resolution
    if tuple(reference_resolution)!=tuple(playfield.reference_resolution):
        raise ValueError("Detector and geometry reference coordinate systems differ")
    pts = np.array(playfield.playfield_polygon(),dtype=np.float32)
    pts[:,0] *= w/rw
    pts[:,1] *= h/rh
    mask = np.zeros((h,w),np.uint8)
    cv2.fillPoly(mask,[pts.astype(np.int32)],255)
    return mask


def _horizontal_bodies(edge: np.ndarray, playfield: Playfield, sx: float, sy: float,
                       lane_count: int) -> np.ndarray:
    """Depth-scaled opening retains long horizontal edges, not vertical glow.

    Closing is limited to a few horizontal pixels; it cannot bridge a lane.
    No vertical closing joins heads to lower judgment text or long paths.
    """
    result = np.zeros_like(edge)
    pixel_scale_y=playfield.reference_resolution[1]/404
    band_height = max(1,round(20*pixel_scale_y*sy))
    for y0 in range(0,edge.shape[0],band_height):
        y1 = min(y0+band_height,edge.shape[0])
        lane_width = playfield.row_lane_width((y0+y1)/2/sy)
        if lane_width is None:
            continue
        lane_width *= sx
        opening = max(5,round(lane_width*0.65))
        closing = max(1,round(lane_width*0.02))
        region = cv2.morphologyEx(edge[y0:y1],cv2.MORPH_CLOSE,np.ones((1,closing),np.uint8))
        result[y0:y1] = cv2.morphologyEx(region,cv2.MORPH_OPEN,np.ones((1,opening),np.uint8))
    return result


def _iou(a: tuple, b: tuple) -> float:
    x,y,w,h = a
    xx,yy,ww,hh = b
    intersection = max(0,min(x+w,xx+ww)-max(x,xx))*max(0,min(y+h,yy+hh)-max(y,yy))
    return intersection/max(w*h+ww*hh-intersection,1)


def _merge_body_edges(boxes: list[tuple], playfield: Playfield, sx: float, sy: float,
                      lane_count: int) -> list[tuple[tuple, int]]:
    groups: list[tuple[tuple,int]] = []
    pixel_scale_y=playfield.reference_resolution[1]/404
    for box in sorted(boxes,key=lambda b:(b[1],b[0])):
        x,y,w,h = box
        lane_width = playfield.row_lane_width((y+h/2)/sy)
        if lane_width is None:
            continue
        max_height = max(9*pixel_scale_y,min(28*pixel_scale_y,lane_width*0.40))*sy
        best,best_cost = None,float("inf")
        for i,((xx,yy,ww,hh),count) in enumerate(groups):
            overlap = max(0,min(x+w,xx+ww)-max(x,xx))/max(1,min(w,ww))
            total_height = max(y+h,yy+hh)-min(y,yy)
            cost = abs(y-yy)+0.1*abs(x-xx)
            if overlap >= .75 and .65 <= w/ww <= 1.55 and total_height <= max_height and cost < best_cost:
                best,best_cost = i,cost
        if best is None:
            groups.append((box,1))
        else:
            (xx,yy,ww,hh),count = groups[best]
            nx,ny = min(x,xx),min(y,yy)
            groups[best] = ((nx,ny,max(x+w,xx+ww)-nx,max(y+h,yy+hh)-ny),count+1)
    return groups


def detect(frame: np.ndarray, playfield: Playfield, key_map: list[str], cfg: dict, diagnostics: dict | None = None) -> list[Candidate]:
    h,w = frame.shape[:2]
    rw,rh = playfield.reference_resolution
    if tuple(cfg["reference_resolution"])!=(rw,rh):
        raise ValueError("Detector config and model use different reference resolutions")
    def rejected_geometry(box,reason):
        if diagnostics is not None:
            diagnostics.setdefault("rejections",[]).append({"bbox":box,"reason":reason})
    sx,sy = w/rw,h/rh
    hsv = cv2.cvtColor(frame,cv2.COLOR_BGR2HSV)
    roi = _playfield_mask((h,w),playfield,(rw,rh))
    # Disjoint hue ranges; pale/gray evidence never establishes tap semantics.
    ranges = {"cyan_bar": ((84,75,100),(112,255,255)),
              "yellow_bar": ((18,95,125),(37,255,255)),
              "green_candidate": ((38,65,100),(83,255,255)),
              "pink_candidate": ((135,65,100),(179,255,255)),
              "neutral_candidate": ((0,0,180),(179,70,255))}
    masks = {name: cv2.inRange(hsv,np.array(low),np.array(high)) & roi
             for name,(low,high) in ranges.items()}
    masks["pink_candidate"] |= cv2.inRange(hsv,np.array([0,65,100]),np.array([8,255,255])) & roi
    gray = cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
    gradient = np.abs(cv2.Sobel(gray,cv2.CV_32F,0,1,ksize=3))
    edge = ((gradient >= cfg.get("edge_threshold",65)) & (hsv[:,:,2] >= 145)).astype(np.uint8)*255
    edge &= roi
    bodies = _horizontal_bodies(edge,playfield,sx,sy,len(key_map))
    contours,_ = cv2.findContours(bodies,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    if diagnostics is not None:
        diagnostics["raw_edge_contours"] = len(contours)
    edges = []
    for contour in contours:
        box = cv2.boundingRect(contour)
        x,y,bw,bh = box
        row = playfield.lane_bounds_at_y((y+bh/2)/sy)
        if row is None:
            rejected_geometry(box,"outside_vertical_domain")
            continue
        left,right = row[0],row[-1]
        if y/sy < playfield.top_y+8*rh/404 or bw/sx > (right-left)*.48:
            continue
        if bw/sx < playfield.row_lane_width((y+bh/2)/sy)*cfg.get("min_lane_width",.7) or bh/sy > 20*rh/404:
            continue
        edges.append(box)
    proposals = _merge_body_edges(edges,playfield,sx,sy,len(key_map))
    path_masks = {'green_candidate':masks['green_candidate'],
                  'yellow_bar':path_mask(hsv,'yellow_bar') & roi}
    path_boxes = {}
    for appearance,mask in path_masks.items():
        path_contours,_ = cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        path_boxes[appearance] = [cv2.boundingRect(p) for p in path_contours]
    candidates = []
    for box,edge_count in proposals:
        x,y,bw,bh = box
        cy = (y+bh/2)/sy
        interval = playfield.safe_bbox_interval(x/sx,(x+bw)/sx,cy)
        if interval is None:
            rejected_geometry(box,"outside_physical_roi_or_projected_key_span")
            continue
        left,right = playfield.bounds(cy)
        min_area = cfg.get("min_area",55)*max(.4,(right-left)/(playfield.bottom_right_x-playfield.bottom_left_x))*sx*sy
        if bw*bh < min_area or bw/max(bh,1) < cfg.get("min_aspect",2.0):
            continue
        evidence = {name: cv2.countNonZero(mask[y:y+bh,x:x+bw])/(bw*bh)
                    for name,mask in masks.items() if name != "neutral_candidate"}
        winner = max(evidence,key=evidence.get)
        appearance = winner if evidence[winner] >= cfg.get("min_colored_fraction",.12) else "neutral_candidate"
        raw = masks[appearance][y:y+bh,x:x+bw].copy()
        if appearance in ("cyan_bar","yellow_bar"):
            raw |= masks["neutral_candidate"][y:y+bh,x:x+bw]
        fill = cv2.countNonZero(raw)/(bw*bh)
        if fill < .10:
            continue
        score = min(.96,.28+min(fill,1)*.30+min(1,bw/max(bh,1)/5)*.25+min(edge_count,2)*.05)
        if score < cfg.get("min_score",.42):
            continue
        u0,u1 = interval
        lanes = playfield.safe_candidate_lanes(x/sx,(x+bw)/sx,cy,cfg.get("lane_min_overlap_fraction",.15))
        if not lanes:
            continue
        path_bbox = None
        if appearance in path_boxes:
            paths = [p for p in path_boxes[appearance] if _iou(box,p)>0 and p[3]>bh*1.5]
            path_bbox = max(paths,key=lambda p:p[2]*p[3],default=None)
        # Paired horizontal edges plus colored body evidence establish only
        # a provisional conventional tap appearance; track motion must confirm.
        note_type = ("tap" if appearance in ("cyan_bar","yellow_bar") and edge_count>=2 and bh>=4
                     else "unknown")
        depth = (path_depth(frame,playfield,cy,(u0+u1)/2,appearance,
                            mask=path_masks[appearance])
                 if appearance in path_masks and cy>=250*rh/404 else 0)
        candidates.append(Candidate(box,appearance,score,u0,u1,[key_map[i] for i in lanes],note_type,
                                    box,path_bbox,raw,False,depth))
    # An inner highlight can produce another long Sobel edge inside a complete
    # colored head. IoU alone misses this containment when the fragment is thin.
    heads = [c for c in candidates if c.note_type=='tap']
    bodies = []
    for c in candidates:
        x,y,bw,bh = c.bbox
        area = bw*bh
        nested = False
        for head in heads:
            if head is c or head.appearance!=c.appearance:
                continue
            xx,yy,ww,hh = head.bbox
            intersection = max(0,min(x+bw,xx+ww)-max(x,xx))*max(0,min(y+bh,yy+hh)-max(y,yy))
            if ww*hh >= 1.25*area and intersection >= .9*area:
                nested = True
                break
        if nested:
            if diagnostics is not None:
                diagnostics['nested_fragments_suppressed'] = diagnostics.get('nested_fragments_suppressed',0)+1
        else:
            bodies.append(c)
    kept = []
    for c in sorted(bodies,key=lambda c:c.score,reverse=True):
        if not any(_iou(c.bbox,k.bbox)>.65 for k in kept):
            kept.append(c)
    for i,c in enumerate(kept):
        c.suspected_overlap = any(i!=j and _iou(c.bbox,other.bbox)>.12 for j,other in enumerate(kept))
    return kept
