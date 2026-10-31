"""Calibrated horizontal note bodies from edges and HSV evidence."""
from __future__ import annotations
from dataclasses import dataclass, field as dataclass_field
import time
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


def detect(frame: np.ndarray, playfield: Playfield, key_map: list[str], cfg: dict,
           diagnostics: dict | None = None, profile: dict | None = None,
           frame_index: int | None = None) -> list[Candidate]:
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
    hsv = cv2.cvtColor(frame,cv2.COLOR_BGR2HSV)
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
        # Paired horizontal edges plus colored body evidence establish only
        # a provisional conventional tap appearance; track motion must confirm.
        note_type = ("tap" if appearance in ("cyan_bar","yellow_bar","neutral_candidate") and
                     edge_count>=2 and bh>=4 and path_bbox is None
                     else "tap" if appearance == "pink_candidate" and pink_enabled and
                     edge_count>=2 and bh>=4 and path_bbox is None
                     else "unknown")
        # Path-depth is the expensive part of candidate classification.  A
        # candidate can only be a Hold when a matching path contour was found;
        # avoid scanning the full frame for ordinary taps (including pink).
        depth = (path_depth(frame,playfield,cy,(u0+u1)/2,appearance,
                            mask=path_masks[appearance])
                 if appearance in path_masks and path_bbox is not None and
                 cy>=250*rh/404 else 0)
        candidate = Candidate(box,appearance,score,u0,u1,[key_map[i] for i in lanes],note_type,
                              body_box,path_bbox,raw,False,depth,
                              diagnostic_id=proposal_id, parent_proposal_id=proposal_id)
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
