"""Calibrated horizontal note bodies from edges and HSV evidence."""
from __future__ import annotations
from dataclasses import dataclass, field as dataclass_field
import time
import math
import cv2
import numpy as np
from .geometry import Playfield
from .hold_visual import path_depth, path_mask


_MORPH_KERNEL_CACHE: dict[tuple[int, int], tuple[np.ndarray, np.ndarray]] = {}
_PLAYFIELD_MASK_CACHE: dict[tuple[int, int, int, int, int], tuple[Playfield, np.ndarray]] = {}


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
    diagnostic_id: str = ""
    parent_proposal_id: str = ""
    # Keep visual body evidence for releasing an already held note, even when
    # Tap classification deliberately drops a short/ambiguous path contour.
    visual_path_bbox: tuple[int, int, int, int] | None = None


def _playfield_mask(shape: tuple[int, int], playfield: Playfield,
                    reference_resolution: tuple[int, int], *, cache_enabled: bool = True) -> np.ndarray:
    h,w = shape
    rw,rh = reference_resolution
    if tuple(reference_resolution)!=tuple(playfield.reference_resolution):
        raise ValueError("Detector and geometry reference coordinate systems differ")
    key = (id(playfield), h, w, rw, rh)
    if cache_enabled:
        cached = _PLAYFIELD_MASK_CACHE.get(key)
        if cached is not None and cached[0] is playfield:
            return cached[1]
    pts = np.array(playfield.playfield_polygon(),dtype=np.float32)
    pts[:,0] *= w/rw
    pts[:,1] *= h/rh
    mask = np.zeros((h,w),np.uint8)
    cv2.fillPoly(mask,[pts.astype(np.int32)],255)
    # Keep the geometry object in the value so an id cannot be reused for a
    # different calibration while this process is alive.
    if cache_enabled:
        _PLAYFIELD_MASK_CACHE[key] = (playfield, mask)
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
        kernel_key = (opening, closing)
        kernels = _MORPH_KERNEL_CACHE.get(kernel_key)
        if kernels is None:
            kernels = (np.ones((1,closing),np.uint8), np.ones((1,opening),np.uint8))
            _MORPH_KERNEL_CACHE[kernel_key] = kernels
        region = cv2.morphologyEx(edge[y0:y1],cv2.MORPH_CLOSE,kernels[0])
        result[y0:y1] = cv2.morphologyEx(region,cv2.MORPH_OPEN,kernels[1])
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
        # Outer-lane heads have slanted sides and a taller projected outline.
        # Keep the existing interior limit: raising every head's limit also
        # merges central judgment-effect edges into false heads.
        left, right = playfield.bounds((y+h/2)/sy)
        center_u = ((x+w/2)/sx-left)/(right-left)
        outer_lane = center_u < 1/lane_count or center_u > 1-1/lane_count
        height_cap = 32 if outer_lane else 28
        max_height = max(9*pixel_scale_y,min(height_cap*pixel_scale_y,lane_width*0.40))*sy
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


def detect(frame: np.ndarray, playfield: Playfield, key_map: list[str], cfg: dict,
           diagnostics: dict | None = None, profile: dict | None = None,
           frame_index: int | None = None, *, frame_hsv: np.ndarray | None = None) -> list[Candidate]:
    profile_started = time.perf_counter() if profile is not None else None
    profile_marks = {}
    def mark(name, started):
        if profile is not None:
            profile.setdefault(name, []).append((time.perf_counter()-started)*1000)
    def section(name):
        if profile is None:
            return None
        started = time.perf_counter()
        profile_marks[name] = started
        return started
    h,w = frame.shape[:2]
    rw,rh = playfield.reference_resolution
    if tuple(cfg["reference_resolution"])!=(rw,rh):
        raise ValueError("Detector config and model use different reference resolutions")
    pink_cfg = dict(cfg.get("pink_tap", {}) or {})
    pink_enabled = bool(pink_cfg.get("enabled", False))
    pink_min_fraction = float(pink_cfg.get("min_mask_fraction", .20))
    pink_trim_px = float(pink_cfg.get("max_core_trim_px", 8.0))
    trace_cfg = dict(cfg.get("association_diagnostics", {}) or {})
    trace_enabled = bool(trace_cfg.get("enabled", False))
    yellow_rail_recovery = cfg.get("yellow_rail_recovery", False)
    trace_rows = diagnostics.setdefault("candidate_trace", []) if trace_enabled and diagnostics is not None else None
    trace_limit = int(trace_cfg.get("max_candidate_rows", 2000))
    trace_dropped = 0
    def trace_add(row):
        nonlocal trace_dropped
        if trace_rows is None:
            return
        if len(trace_rows) >= trace_limit:
            trace_dropped += 1
            return
        trace_rows.append(row)
    def trace_base(stage, candidate_id, box, **extra):
        x,y,bw,bh = box
        return {"frame": frame_index, "stage": stage, "candidate_id": candidate_id,
                "parent_proposal_id": extra.pop("parent_proposal_id", ""),
                "raw_bbox": box, "core_bbox": extra.pop("core_bbox", box),
                "x": x, "y": y, "w": bw, "h": bh, **extra}
    def rejected_geometry(box,reason):
        if diagnostics is not None:
            diagnostics.setdefault("rejections",[]).append({"bbox":box,"reason":reason})
    sx,sy = w/rw,h/rh
    started = section("hsv_roi")
    if frame_hsv is not None and (frame_hsv.shape != frame.shape or frame_hsv.dtype != np.uint8):
        raise ValueError('Shared HSV must match the current BGR frame shape and uint8 type')
    hsv = cv2.cvtColor(frame,cv2.COLOR_BGR2HSV) if frame_hsv is None else frame_hsv
    cache_enabled = bool(cfg.get("cache_enabled", True))
    if not cache_enabled:
        _MORPH_KERNEL_CACHE.clear()
    roi = _playfield_mask((h,w),playfield,(rw,rh), cache_enabled=cache_enabled)
    # Disjoint hue ranges; pale/gray evidence never establishes tap semantics.
    ranges = {"cyan_bar": ((84,75,100),(112,255,255)),
              "yellow_bar": ((18,95,125),(37,255,255)),
              "green_candidate": ((38,65,100),(83,255,255)),
              "pink_candidate": ((135,65,100),(179,255,255)),
              "neutral_candidate": ((0,0,180),(179,70,255))}
    masks = {name: cv2.inRange(hsv,np.array(low),np.array(high)) & roi
             for name,(low,high) in ranges.items()}
    masks["pink_candidate"] |= cv2.inRange(hsv,np.array([0,65,100]),np.array([8,255,255])) & roi

    def pink_fraction(box):
        x0,y0,w0,h0 = box
        if w0 <= 0 or h0 <= 0:
            return 0.0
        return cv2.countNonZero(masks["pink_candidate"][y0:y0+h0, x0:x0+w0]) / max(w0*h0, 1)

    def record_pink_rejection(box, reason, *, core_box=None):
        if diagnostics is None:
            return
        fraction = pink_fraction(box)
        if fraction < pink_min_fraction:
            return
        counts = diagnostics.setdefault("pink_rejection_counts", {})
        counts[reason] = counts.get(reason, 0) + 1
        samples = diagnostics.setdefault("pink_rejections", [])
        if len(samples) < 32:
            samples.append({"frame": frame_index, "bbox": box, "core_bbox": core_box or box,
                            "reason": reason, "pink_fraction": fraction})
    mark("hsv_roi", started)
    started = section("gray_sobel_morphology")
    gray = cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
    gradient = np.abs(cv2.Sobel(gray,cv2.CV_32F,0,1,ksize=3))
    edge = ((gradient >= cfg.get("edge_threshold",65)) & (hsv[:,:,2] >= 145)).astype(np.uint8)*255
    edge &= roi
    bodies = _horizontal_bodies(edge,playfield,sx,sy,len(key_map))
    mark("gray_sobel_morphology", started)
    started = section("contours_merge")
    contours,_ = cv2.findContours(bodies,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    bar_top = getattr(playfield, 'document', {}).get('live_measurement', {}).get('judgment_bar_top_y')
    rail_occlusions = []
    if diagnostics is not None:
        diagnostics["raw_edge_contours"] = len(contours)
    edges = []
    def record_gray(box, stage, reason):
        if diagnostics is None:
            return
        x0, y0, w0, h0 = box
        if w0 <= 0 or h0 <= 0:
            return
        neutral_fraction = cv2.countNonZero(masks["neutral_candidate"][y0:y0+h0, x0:x0+w0]) / max(w0*h0, 1)
        if neutral_fraction >= .35:
            diagnostics.setdefault("gray_rejections", []).append({
                "bbox": box, "stage": stage, "reason": reason,
                "neutral_fraction": neutral_fraction,
            })
    for contour_index, contour in enumerate(contours):
        box = cv2.boundingRect(contour)
        raw_id = f"{frame_index}:raw:{contour_index}"
        x,y,bw,bh = box
        row = playfield.lane_bounds_at_y((y+bh/2)/sy)
        if row is None:
            trace_add(trace_base("raw_contour", raw_id, box, passed=False,
                                 reject_reason="vertical_geometry"))
            record_gray(box, "geometry", "outside_vertical_domain")
            rejected_geometry(box,"outside_vertical_domain")
            continue
        left,right = row[0],row[-1]
        if y/sy < playfield.top_y+8*rh/404 or bw/sx > (right-left)*.48:
            if (bar_top is not None and bw/sx > (right-left)*.48 and
                    y/sy <= bar_top+4*rh/404 and (y+bh)/sy >= bar_top-4*rh/404):
                rail_occlusions.append(box)
            trace_add(trace_base("raw_contour", raw_id, box, passed=False,
                                 reject_reason="edge_geometry"))
            continue
        if bw/sx < playfield.row_lane_width((y+bh/2)/sy)*cfg.get("min_lane_width",.7) or bh/sy > 20*rh/404:
            trace_add(trace_base("raw_contour", raw_id, box, passed=False,
                                 reject_reason="edge_shape"))
            record_gray(box, "edge_shape", "insufficient_lane_width_or_height")
            continue
        trace_add(trace_base("raw_contour", raw_id, box, passed=True, reject_reason=""))
        edges.append(box)
    proposals = _merge_body_edges(edges,playfield,sx,sy,len(key_map))
    proposal_ids = []
    for proposal_index, (proposal_box, edge_count) in enumerate(proposals):
        proposal_id = f"{frame_index}:proposal:{proposal_index}"
        proposal_ids.append(proposal_id)
        trace_add(trace_base("merge_proposal", proposal_id, proposal_box,
                             passed=True, edge_count=edge_count, reject_reason=""))
    mark("contours_merge", started)
    started = section("path_masks_contours")
    path_masks = {'green_candidate':masks['green_candidate'],
                  'yellow_bar':path_mask(hsv,'yellow_bar') & roi}
    path_boxes = {}
    for appearance,mask in path_masks.items():
        path_contours,_ = cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        path_boxes[appearance] = [cv2.boundingRect(p) for p in path_contours]
    mark("path_masks_contours", started)
    started = section("candidate_classification")
    candidates = []
    for proposal_index, (box,edge_count) in enumerate(proposals):
        proposal_id = proposal_ids[proposal_index]
        body_box = box
        x,y,bw,bh = box
        cy = (y+bh/2)/sy
        recovered_ribbon_depth = 0
        # A blue hit beam can hide the lower edge of a green head, leaving
        # only a 1-5px cyan proposal. Recover its visible rectangle only when
        # a long green ribbon reaches the head and the recovered head itself
        # still has green pixels. This also handles interior lanes; the
        # unrelated cyan outer-rail recovery below keeps its original gates.
        if edge_count >= 2 and bh < 8*sy and cy >= 250*rh/404:
            green_paths = [p for p in path_boxes['green_candidate']
                           if p[3]>=40*sy and y-p[1]>=40*sy and _iou(box,p)>0 and
                           min(x+bw,p[0]+p[2])-max(x,p[0]) >= .5*bw]
            if green_paths:
                left,right = playfield.bounds(cy)
                u = ((x+bw/2)/sx-left)/(right-left)
                depth = path_depth(frame,playfield,cy,u,'green_candidate',
                                   mask=path_masks['green_candidate'])
                if depth >= 40:
                    end = min(h, int(bar_top*sy) if bar_top is not None else y+bh,
                              y+round(32*rh/404*sy))
                    il,ir = x+round(bw*.2),x+bw-round(bw*.2)
                    colored = (masks['cyan_bar'][y:end,il:ir] |
                               masks['green_candidate'][y:end,il:ir])
                    filled = np.count_nonzero(colored,axis=1) >= max(1,(ir-il)*.5)
                    last,gaps = bh,0
                    for offset in range(bh,len(filled)):
                        gaps = 0 if filled[offset] else gaps+1
                        if gaps >= 2: break
                        if filled[offset]: last=offset+1
                    green_fill = cv2.countNonZero(masks['green_candidate'][y:y+last,x:x+bw])/max(1,bw*last)
                    if last >= 12*sy and green_fill >= cfg.get('min_colored_fraction',.12):
                        box = x,y,bw,last
                        bh = last
                        cy = (y+bh/2)/sy
                        recovered_ribbon_depth = depth
                        if diagnostics is not None:
                            diagnostics['green_head_rectangle_recovered'] = diagnostics.get(
                                'green_head_rectangle_recovered',0)+1
        # The judgment rail can connect to a blue head's lower Sobel edge;
        # that full-width contour is correctly rejected above. Recover only
        # a paired thin edge with a continuous blue body below it, stopping
        # strictly above the input-lit strip. Never infer a body from time.
        rail_below = any(y+bh <= oy <= y+round(32*rh/404*sy) and
                         max(0, min(x+bw,ox+ow)-max(x,ox)) >= .75*bw
                         for ox,oy,ow,oh in rail_occlusions)
        outer = playfield.outer_bounds_at_y(cy)
        rail_margin = playfield.row_lane_width(cy)*.15
        touches_outer = outer is not None and (x/sx <= outer[0]+rail_margin or
                                               (x+bw)/sx >= outer[1]-rail_margin)
        if edge_count >= 2 and bh < 8*sy and cy >= 250*rh/404 and rail_below and touches_outer:
            end = min(h, int(bar_top*sy), y+round(32*rh/404*sy))
            inner_left, inner_right = x+round(bw*.2), x+bw-round(bw*.2)
            if inner_right > inner_left and end > y+bh:
                body = masks['cyan_bar'][y:end, inner_left:inner_right]
                filled = np.count_nonzero(body, axis=1) >= (inner_right-inner_left)*.5
                last, gaps = bh, 0
                for offset in range(bh, len(filled)):
                    gaps = 0 if filled[offset] else gaps+1
                    if gaps >= 2:
                        break
                    if filled[offset]:
                        last = offset+1
                if last >= 12*sy:
                    box = (x,y,bw,last)
                    x,y,bw,bh = box
                    cy = (y+bh/2)/sy
        # A paired cyan head has slanted sides. Its axis-aligned bbox can
        # overhang the rail at the middle row even when the head follows it.
        # Trim only a small colored outline, then apply the normal ROI gates.
        if (edge_count >= 2 and cy >= 250*rh/404 and
                cv2.countNonZero(masks['cyan_bar'][y:y+bh,x:x+bw]) / max(bw*bh,1)
                >= cfg.get('min_colored_fraction', .12)):
            outer = playfield.outer_bounds_at_y(cy)
            if outer is not None:
                core_left = max(x, int(np.ceil(outer[0]*sx)))
                core_right = min(x+bw, int(np.floor(outer[1]*sx)))
                trim = max(0, core_left-x) + max(0, x+bw-core_right)
                if 0 < trim <= 8*sx and core_right > core_left:
                    box = (core_left, y, core_right-core_left, bh)
                    x,y,bw,bh = box
        # Pink arrow/glow edges may extend a small, measurable fringe beyond
        # the calibrated outer rail. Trim only that pink-rich fringe; the
        # physical ROI and lane gates remain mandatory.
        if pink_enabled and pink_fraction(box) >= pink_min_fraction:
            outer = playfield.outer_bounds_at_y(cy)
            if outer is not None:
                core_left = max(x, int(np.ceil(outer[0]*sx)))
                core_right = min(x+bw, int(np.floor(outer[1]*sx)))
                trim = max(0, core_left-x) + max(0, x+bw-core_right)
                if trim <= pink_trim_px and core_right > core_left:
                    box = (core_left, y, core_right-core_left, bh)
                    x,y,bw,bh = box
                    if diagnostics is not None and trim > 0:
                        diagnostics["pink_core_trimmed"] = diagnostics.get("pink_core_trimmed", 0) + 1
        interval = playfield.safe_bbox_interval(x/sx,(x+bw)/sx,cy)
        if interval is None:
            trace_add(trace_base("candidate", proposal_id, body_box, passed=False,
                                 parent_proposal_id=proposal_id, reject_reason="physical_roi",
                                 core_bbox=box, edge_count=edge_count))
            record_pink_rejection(body_box, "geometry_roi", core_box=box)
            record_gray(box, "geometry", "outside_physical_roi_or_projected_key_span")
            rejected_geometry(box,"outside_physical_roi_or_projected_key_span")
            continue
        left,right = playfield.bounds(cy)
        min_area = cfg.get("min_area",55)*max(.4,(right-left)/(playfield.bottom_right_x-playfield.bottom_left_x))*sx*sy
        if bw*bh < min_area or bw/max(bh,1) < cfg.get("min_aspect",2.0):
            trace_add(trace_base("candidate", proposal_id, body_box, passed=False,
                                 parent_proposal_id=proposal_id, reject_reason="shape",
                                 core_bbox=box, edge_count=edge_count))
            record_pink_rejection(body_box, "shape", core_box=box)
            record_gray(box, "shape", "min_area_or_aspect")
            continue
        evidence = {name: cv2.countNonZero(mask[y:y+bh,x:x+bw])/(bw*bh)
                    for name,mask in masks.items() if name != "neutral_candidate"}
        winner = max(evidence,key=evidence.get)
        appearance = winner if evidence[winner] >= cfg.get("min_colored_fraction",.12) else "neutral_candidate"
        recovered_yellow_rail = False
        yellow_rail_evidence = False
        if yellow_rail_recovery and bar_top is not None:
            lane_px = playfield.row_lane_width(cy)*sx
            max_gap = max(8*rh/404*sy, lane_px*.2)
            yellow_rail_evidence = any(
                y+bh <= oy <= bar_top*sy+4*rh/404*sy and
                abs(oy-bar_top*sy) <= 8*rh/404*sy and
                ow >= 2*lane_px and
                max(0, max(x-(ox+ow), ox-(x+bw))) <= max_gap
                for ox,oy,ow,oh in rail_occlusions)
        # A measured yellow head can lose its lower outline where it meets the
        # judgment rail. Recover only from a surviving Sobel edge, a separately
        # measured broad rail contour, and a continuous head-sized yellow body.
        # Both body boundaries must be visible above the calibrated rail top;
        # a clipped body has no measured center. Long paths remain Hold evidence.
        yellow_touches_outer = (outer is not None and
            (x <= math.ceil((outer[0]+rail_margin)*sx) or
             x+bw >= math.floor((outer[1]-rail_margin)*sx))) if yellow_rail_recovery else False
        if (yellow_rail_recovery and appearance == 'yellow_bar' and edge_count >= 1 and
                yellow_rail_evidence and yellow_touches_outer and
                cy >= 250*rh/404 and bh < 8*sy and
                0 <= bar_top*sy-(y+bh) <= 32*rh/404*sy):
            left,right = playfield.bounds(cy)
            head_u = ((x+bw/2)/sx-left)/(right-left)
            yellow_depth = path_depth(frame,playfield,cy,head_u,'yellow_bar',
                                      mask=path_masks['yellow_bar'])
            end = min(h,round(bar_top*sy),y+round(32*rh/404*sy))
            inner_left = x+round(bw*.15)
            inner_right = x+bw-round(bw*.15)
            begin = max(0,y-round(32*rh/404*sy))
            if yellow_depth < 40 and inner_right > inner_left and end>y:
                yellow_body = masks['yellow_bar'][begin:end,inner_left:inner_right]
                row_fill = np.count_nonzero(yellow_body,axis=1)
                filled = row_fill >= .75*(inner_right-inner_left)
                # White outlines need not pass the yellow mask. Find an
                # adjacent solid body, but require BOTH measured boundaries:
                # a head clipped by the rail has an unknown center and must
                # not contaminate the shared Global velocity profile.
                boundaries = np.flatnonzero(np.diff(np.r_[False,filled,False].astype(np.int8)))
                bodies = []
                for first,last in zip(boundaries[::2],boundaries[1::2]):
                    top,bottom = begin+int(first),begin+int(last)
                    gap = max(top-(y+bh),y-bottom,0)
                    if (top>begin and bottom<end and gap<=3*rh/404*sy and
                            12*rh/404*sy <= bottom-top <= 32*rh/404*sy):
                        bodies.append((gap,-(bottom-top),top,bottom))
                if bodies:
                    _,_,top,bottom = min(bodies)
                    proposed_height = bottom-top
                    proposed_cy = (top+proposed_height/2)/sy
                    proposed_interval = playfield.safe_bbox_interval(
                        x/sx,(x+bw)/sx,proposed_cy)
                    if proposed_interval is not None:
                        box = (x,top,bw,proposed_height)
                        y = top
                        bh = proposed_height
                        cy = proposed_cy
                        interval = proposed_interval
                        recovered_yellow_rail = True
                        if diagnostics is not None:
                            diagnostics['yellow_rail_head_recovered'] = diagnostics.get(
                                'yellow_rail_head_recovered',0)+1
        tap_edge_count = edge_count + int(recovered_yellow_rail)
        recovered_green_depth = recovered_ribbon_depth
        # Blue judgment light can dominate a green Hold head. A sizeable
        # green part of the head PLUS a connected, independently measured
        # long green ribbon establishes Hold evidence, not a 25ms cyan Tap.
        # A cyan Tap merely crossing a green body has no such green head fill.
        if (appearance == 'cyan_bar' and bh >= 4*sy and
                evidence.get('green_candidate',0.) >= cfg.get('min_colored_fraction',.12)):
            green_paths = [p for p in path_boxes.get('green_candidate',())
                           if p[3] >= 40*sy and y-p[1] >= 40*sy and _iou(box,p)>0 and
                           min(x+bw,p[0]+p[2])-max(x,p[0]) >= .5*bw]
            if green_paths and not recovered_green_depth:
                recovered_green_depth = path_depth(frame,playfield,cy,
                    sum(interval)/2,'green_candidate',mask=path_masks['green_candidate'])
            if recovered_green_depth >= 40:
                appearance = 'green_candidate'
                if diagnostics is not None:
                    diagnostics['green_hold_blue_flash_recovered'] = diagnostics.get(
                        'green_hold_blue_flash_recovered',0)+1
        raw = masks[appearance][y:y+bh,x:x+bw].copy()
        if appearance in ("cyan_bar","yellow_bar"):
            raw |= masks["neutral_candidate"][y:y+bh,x:x+bw]
        fill = cv2.countNonZero(raw)/(bw*bh)
        if fill < .10:
            trace_add(trace_base("candidate", proposal_id, body_box, passed=False,
                                 parent_proposal_id=proposal_id, reject_reason="fill",
                                 core_bbox=box, edge_count=edge_count))
            record_pink_rejection(body_box, "fill", core_box=box)
            record_gray(box, "fill", "insufficient_body_fill")
            continue
        score = min(.96,.28+min(fill,1)*.30+min(1,bw/max(bh,1)/5)*.25+min(edge_count,2)*.05)
        if score < cfg.get("min_score",.42):
            trace_add(trace_base("candidate", proposal_id, body_box, passed=False,
                                 parent_proposal_id=proposal_id, reject_reason="score",
                                 core_bbox=box, edge_count=edge_count))
            record_pink_rejection(body_box, "score", core_box=box)
            record_gray(box, "score", "below_min_score")
            continue
        u0,u1 = interval
        lanes = playfield.safe_candidate_lanes(x/sx,(x+bw)/sx,cy,cfg.get("lane_min_overlap_fraction",.15))
        if not lanes:
            trace_add(trace_base("candidate", proposal_id, body_box, passed=False,
                                 parent_proposal_id=proposal_id, reject_reason="lane",
                                 core_bbox=box, edge_count=edge_count))
            record_pink_rejection(body_box, "lane", core_box=box)
            record_gray(box, "lane", "no_projected_lane")
            continue
        path_bbox = None
        if appearance in path_boxes:
            paths = [p for p in path_boxes[appearance] if _iou(box,p)>0 and p[3]>bh*1.5]
            path_bbox = max(paths,key=lambda p:p[2]*p[3],default=None)
        depth = recovered_green_depth if appearance == 'green_candidate' else 0
        if path_bbox is None and appearance in path_boxes:
            # A white highlight can disconnect the colored head from its
            # translucent Hold body. Requiring contour intersection then
            # turns a yellow Hold into a 25ms Tap. Bridge only a small gap
            # ABOVE the head, with a long body in the same horizontal span
            # and independently measured continuous path evidence.
            nearby = [p for p in path_boxes[appearance]
                      if p[3] >= 40*sy and 0 <= y-(p[1]+p[3]) <= 6*sy and
                      max(0, min(x+bw, p[0]+p[2])-max(x, p[0])) >= .5*bw]
            if nearby:
                depth = path_depth(frame,playfield,cy,(u0+u1)/2,appearance,
                                   mask=path_masks[appearance])
                if depth >= 40:
                    path_bbox = max(nearby,key=lambda p:p[2]*p[3])
                else:
                    depth = 0
        # Paired horizontal edges plus colored body evidence establish only
        # a provisional conventional tap appearance; track motion must confirm.
        note_type = ("tap" if appearance in ("cyan_bar","yellow_bar","neutral_candidate") and
                     tap_edge_count>=2 and bh>=4 and path_bbox is None
                     else "tap" if appearance == "pink_candidate" and pink_enabled and
                     edge_count>=2 and bh>=4 and path_bbox is None
                     else "unknown")
        if (appearance == 'cyan_bar' and cy >= 250*rh/404 and bh < 8*sy and
                (0 in lanes or len(key_map)-1 in lanes)):
            # At this depth the full blue head is tall. Its 1–5px internal
            # highlight is not a second head and must not pull the existing
            # track onto the bottom edge before the full outline recovers.
            note_type = 'unknown'
        # Path-depth is the expensive part of candidate classification.  A
        # candidate can only be a Hold when a matching path contour was found;
        # avoid scanning the full frame for ordinary taps (including pink).
        if depth == 0 and appearance in path_masks and path_bbox is not None and cy>=250*rh/404:
            depth = path_depth(frame,playfield,cy,(u0+u1)/2,appearance,
                               mask=path_masks[appearance])
        # A yellow head/arrow joined to its glow can have a tall contour,
        # without a ribbon extending behind the head. Near the input line,
        # do not let that contour divert a normal bar away from Tap tracking.
        visual_path_bbox = None
        if (appearance == 'yellow_bar' and cy >= 250*rh/404 and
                path_bbox is not None and depth < 40 and
                y-path_bbox[1] < 40*sy):
            visual_path_bbox = path_bbox
            path_bbox, depth = None, 0
            note_type = 'tap' if tap_edge_count >= 2 and bh >= 4 else 'unknown'
        candidate = Candidate(box,appearance,score,u0,u1,[key_map[i] for i in lanes],note_type,
                              body_box,path_bbox,raw,False,depth,
                              diagnostic_id=proposal_id, parent_proposal_id=proposal_id,
                              visual_path_bbox=visual_path_bbox)
        candidates.append(candidate)
        trace_add(trace_base("candidate", proposal_id, body_box, passed=True,
                             parent_proposal_id=proposal_id, core_bbox=box,
                             appearance=appearance, note_type=note_type,
                             candidate_keys="|".join(candidate.candidate_keys),
                             u_min=u0, u_max=u1, edge_count=edge_count,
                             path_bbox=path_bbox, suspected_overlap=False,
                             reject_reason=""))
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
            trace_add(trace_base("postprocess", c.diagnostic_id or "", c.bbox,
                                 passed=False, parent_proposal_id=c.parent_proposal_id,
                                 reject_reason="nested_suppression", appearance=c.appearance,
                                 note_type=c.note_type))
        else:
            bodies.append(c)
    kept = []
    for c in sorted(bodies,key=lambda c:c.score,reverse=True):
        if not any(_iou(c.bbox,k.bbox)>.65 for k in kept):
            kept.append(c)
        else:
            trace_add(trace_base("postprocess", c.diagnostic_id or "", c.bbox,
                                 passed=False, parent_proposal_id=c.parent_proposal_id,
                                 reject_reason="duplicate_nms", appearance=c.appearance,
                                 note_type=c.note_type))
    for i,c in enumerate(kept):
        c.diagnostic_id = f"{frame_index}:candidate:{i}"
        c.suspected_overlap = any(i!=j and _iou(c.bbox,other.bbox)>.12 for j,other in enumerate(kept))
        if trace_rows is not None:
            trace_add(trace_base("candidate_final", c.diagnostic_id, c.bbox,
                                 passed=True, parent_proposal_id=c.parent_proposal_id,
                                 core_bbox=c.bbox, appearance=c.appearance,
                                 note_type=c.note_type,
                                 candidate_keys="|".join(c.candidate_keys),
                                 u_min=c.u_min, u_max=c.u_max,
                                 suspected_overlap=c.suspected_overlap,
                                 reject_reason=""))
    if trace_rows is not None:
        diagnostics["candidate_trace_dropped_rows"] = trace_dropped
    mark("candidate_classification", started)
    if profile is not None and profile_started is not None:
        profile.setdefault("detector_total", []).append((time.perf_counter()-profile_started)*1000)
    return kept
