"""Current-frame color/shape to provisional pixel-supported geometry objects."""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .geometry import VideoGeometry


PALETTE = {
    "cyan": (255, 220, 100),
    "green": (75, 220, 130),
    "yellow": (40, 205, 255),
    "pink": (230, 115, 255),
    "unknown": (190, 190, 190),
}

COLOR_BANDS = (
    ("cyan", (82, 110, 65, 150, 155)),
    ("green", (38, 84, 60, 180, 100)),
    ("yellow", (14, 42, 80, 210, 125)),
    ("pink", (140, 178, 65, 220, 125)),
)


def _runs(row: np.ndarray) -> list[tuple[int, int]]:
    indices = np.flatnonzero(row)
    if not len(indices):
        return []
    split = np.flatnonzero(np.diff(indices) > 1) + 1
    return [(int(group[0]), int(group[-1] - group[0] + 1)) for group in np.split(indices, split)]


def _mask_spans(mask: np.ndarray, bbox: tuple[int, int, int, int]) -> list[list[int]]:
    x, y, w, h = bbox
    crop = mask if mask.shape[:2] == (h, w) else mask[y:y+h, x:x+w]
    return [[dy, start, length] for dy, row in enumerate(crop) for start, length in _runs(row)]


def _contour_polygon(mask: np.ndarray, bbox: tuple[int, int, int, int]) -> list[list[float]]:
    x, y, w, h = bbox
    local = (mask if mask.shape[:2] == (h, w) else mask[y:y+h, x:x+w])
    local = (local > 0).astype(np.uint8)
    contours, _ = cv2.findContours(local, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return []
    contour = max(contours, key=cv2.contourArea)
    epsilon = max(1.0, cv2.arcLength(contour, True) * .003)
    poly = cv2.approxPolyDP(contour, epsilon, True).reshape(-1, 2)
    return [[float(px+x), float(py+y)] for px, py in poly]


def _shape_metrics(mask: np.ndarray, bbox: tuple[int, int, int, int], area: int) -> dict:
    x, y, w, h = bbox
    local = mask if mask.shape[:2] == (h, w) else mask[y:y+h, x:x+w]
    ys, xs = np.nonzero(local)
    if len(xs) < 3:
        return {"elongation": 1.0, "axis_verticality": 0.0, "fill_ratio": 0.0}
    covariance = np.cov(np.stack((xs, ys), axis=1), rowvar=False)
    values, vectors = np.linalg.eigh(covariance)
    major = vectors[:, int(np.argmax(values))]
    return {
        "elongation": float(np.sqrt(max(values) / max(min(values), 1e-6))),
        "axis_verticality": float(abs(major[1])),
        "fill_ratio": float(area / max(1, w*h)),
    }


def _hold_parts(mask: np.ndarray, bbox: tuple[int, int, int, int]) -> list[dict]:
    """Partition only observed pixels into screen-top tail/body/screen-bottom head."""
    x, y, w, h = bbox
    local = mask if mask.shape[:2] == (h, w) else mask[y:y+h, x:x+w]
    occupied_rows = np.flatnonzero(local.any(axis=1))
    if len(occupied_rows) < 20:
        return [{"kind": "HOLD_BODY", "polygon": _contour_polygon(mask, bbox),
                 "bbox": list(bbox), "mask_spans_rle": _mask_spans(mask, bbox)}]
    y_lo, y_hi = int(occupied_rows[0]), int(occupied_rows[-1])
    length = y_hi-y_lo+1
    cut = max(3, int(round(length*.12)))
    parts = []
    for kind, lo, hi in (("HOLD_TAIL", y_lo, min(y_hi, y_lo+cut)),
                         ("HOLD_BODY", min(y_hi, y_lo+cut+1), max(y_lo, y_hi-cut-1)),
                         ("HOLD_HEAD", max(y_lo, y_hi-cut), y_hi)):
        part_mask = np.zeros_like(local)
        part_mask[lo:hi+1] = local[lo:hi+1]
        if np.count_nonzero(part_mask) < 2:
            continue
        ys, xs = np.nonzero(part_mask)
        bx, by = int(xs.min()), int(ys.min())
        bw, bh = int(xs.max()-xs.min()+1), int(ys.max()-ys.min()+1)
        pb = (x+bx, y+by, bw, bh)
        part_crop = part_mask[by:by+bh, bx:bx+bw]
        parts.append({"kind": kind, "polygon": _contour_polygon(part_crop, pb), "bbox": list(pb),
                      "mask_spans_rle": _mask_spans(part_crop, pb)})
    return parts


def _horizontal_edge_pairs(frame: np.ndarray, field_mask: np.ndarray,
                           bottom_y: int) -> list[tuple[int, int, int, int]]:
    """Find source-supported flat panel outlines without relying on color blobs."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 55, 150)
    # Restrict Hough to the calibrated playfield and the note-bearing rows.
    # The previous full-frame pass spent most of its time on UI/scenery edges.
    roi = cv2.bitwise_and(edges, edges, mask=field_mask)
    roi[max(0, min(roi.shape[0], bottom_y+1)):] = 0
    lines = cv2.HoughLinesP(roi, 1, np.pi/360, 25, minLineLength=35, maxLineGap=10)
    if lines is None:
        return []
    horizontals = []
    for x1,y1,x2,y2 in lines[:,0,:]:
        if abs(y2-y1) > 4 or abs(x2-x1) < 35:
            continue
        left,right=sorted((int(x1),int(x2)))
        horizontals.append((int(round((y1+y2)/2)),left,right))
    horizontals.sort()
    bands=[]
    for y,left,right in horizontals:
        if not bands or y-bands[-1][0] > 4:
            bands.append([y,[(left,right)]])
        else:
            bands[-1][1].append((left,right))
    merged=[]
    for y,intervals in bands:
        intervals.sort()
        groups=[]
        for left,right in intervals:
            if not groups or left-groups[-1][1] > 24:
                groups.append([left,right])
            else:
                groups[-1][1]=max(groups[-1][1],right)
        for left,right in groups:
            if right-left>=40:
                merged.append((y,left,right))
    pairs=[]
    for i,(y0,x0a,x0b) in enumerate(merged):
        for y1,x1a,x1b in merged[i+1:]:
            dy=y1-y0
            if dy>64:
                break
            if dy<10:
                continue
            overlap=max(0,min(x0b,x1b)-max(x0a,x1a))
            if overlap/max(1,min(x0b-x0a,x1b-x1a)) < .52:
                continue
            pad=min(18,round(dy*.42))
            left=max(0,min(x0a,x1a)-pad)
            right=min(frame.shape[1]-1,max(x0b,x1b)+pad)
            if right-left < 40:
                continue
            pairs.append((left,y0,right,y1))
    # Keep the strongest/fattest pair first, then suppress near-identical pairs.
    pairs.sort(key=lambda row: (-(row[2]-row[0]), row[1]))
    kept=[]
    for candidate in pairs:
        x0,y0,x1,y1=candidate
        overlap=False
        for old in kept:
            ox0,oy0,ox1,oy1=old
            ix=max(0,min(x1,ox1)-max(x0,ox0))*max(0,min(y1,oy1)-max(y0,oy0))
            union=(x1-x0)*(y1-y0)+(ox1-ox0)*(oy1-oy0)-ix
            if ix/max(1,union)>.45:
                overlap=True;break
        if not overlap:
            kept.append(candidate)
    return kept


@dataclass
class Candidate:
    class_name: str
    color_name: str
    confidence: float
    bbox: tuple[int, int, int, int]
    area: int
    polygon: list[list[float]]
    pixel_evidence: dict
    parts: list[dict]
    uncertainty_reasons: list[str]

    def __post_init__(self):
        self.confidence = max(0.0, min(1.0, float(self.confidence)))


class PixelGeometryConverter:
    def __init__(self, geometry: VideoGeometry):
        self.geometry = geometry
        self.field_mask = np.zeros((geometry.height, geometry.width), dtype=np.uint8)
        top = [round(v) for v in geometry.boundaries(0)]
        bottom_y = min(geometry.height-1, round(geometry.judgment_y+35))
        bottom = [round(v) for v in geometry.boundaries(bottom_y)]
        points = np.array([[top[0], 0], [top[-1], 0], [bottom[-1], bottom_y], [bottom[0], bottom_y]], np.int32)
        cv2.fillPoly(self.field_mask, [points], 1)
        # At most one-pixel gaps are bridged: nearby parallel Hold ribbons and
        # adjacent Tap panels remain separate connected components.
        self.close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        self.open_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))

    def segment(self, frame: np.ndarray) -> tuple[list[Candidate], list[Candidate]]:
        if frame.shape[:2] != (self.geometry.height, self.geometry.width):
            raise ValueError(f"Expected native {self.geometry.width}x{self.geometry.height} source frame")
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        objects: list[Candidate] = []
        uncertain: list[Candidate] = []
        panel_source_masks = {}
        for color_name, (h0, h1, s0, s1, v0) in COLOR_BANDS:
            color_mask = cv2.inRange(hsv, np.array([h0, s0, v0], np.uint8), np.array([h1, 255, 255], np.uint8))
            color_mask = cv2.bitwise_and(color_mask, color_mask, mask=self.field_mask)
            # Open thin effect bridges before sealing single-pixel texture gaps.
            # This keeps neighboring notes and the long hold ribbons separate;
            # no temporal pixels are added to masks.
            color_mask = cv2.morphologyEx(color_mask, cv2.MORPH_OPEN, self.open_kernel)
            color_mask = cv2.morphologyEx(color_mask, cv2.MORPH_CLOSE, self.close_kernel)
            count, labels, stats, _ = cv2.connectedComponentsWithStats(color_mask, connectivity=8)
            for label in range(1, count):
                x, y, w, h, area = map(int, stats[label])
                if area < 90 or w < 18 or h < 7:
                    continue
                component = (labels[y:y+h, x:x+w] == label).astype(np.uint8) * 255
                bbox = (x, y, w, h)
                shape = _shape_metrics(component, bbox, area)
                ratio = w / max(1, h)
                is_tap = (w >= 36 and h <= 58 and ratio >= 2.0 and area >= 160 and
                          shape["fill_ratio"] >= .10)
                is_hold = (color_name == "green" and h >= 65 and area >= 450 and
                           shape["elongation"] >= 1.05 and shape["axis_verticality"] >= .42)
                reasons = []
                if is_tap:
                    confidence = min(.94, .55 + min(ratio, 7)*.045 + min(shape["fill_ratio"], .8)*.15)
                    kind = "TAP"
                    parts = [{"kind": kind, "polygon": _contour_polygon(component, bbox),
                              "bbox": list(bbox), "mask_spans_rle": _mask_spans(component, bbox)}]
                    if y+h >= self.geometry.judgment_y-65:
                        confidence -= .30
                        reasons.append("near_judgment_effect_overlap")
                    if y < 26:
                        confidence -= .16
                        reasons.append("candidate_touches_spawn_crop")
                    local_lane_width = float(np.median(np.diff(self.geometry.boundaries(y+h/2))))
                    if w / max(1.,local_lane_width) > 2.5:
                        confidence -= .35
                        reasons.append("candidate_spans_more_than_two_and_a_half_lanes")
                elif is_hold:
                    confidence = min(.90, .58 + min(shape["elongation"], 4)*.06 + min(h, 400)*.0002)
                    kind = "HOLD"
                    parts = _hold_parts(component, bbox)
                    if y <= 4 or y+h >= self.geometry.judgment_y+30:
                        confidence -= .12
                        reasons.append("hold_endpoint_clipped_or_in_judgment_band")
                    # End ownership is provisional because color masks alone
                    # cannot prove the chart's semantic head/tail convention.
                    reasons.append("head_tail_ownership_provisional_from_screen_y")
                else:
                    confidence = .35
                    kind = "UNKNOWN"
                    parts = []
                    reasons.append("component_shape_not_decisive_for_tap_or_hold")
                    plausible_note_shape = (
                        (w >= 24 and 8 <= h <= 100 and w <= 460 and ratio >= 1.45 and area >= 140) or
                        (16 <= w <= 420 and 40 <= h <= 420 and shape["axis_verticality"] >= .30 and area >= 220)
                    )
                    # Large connected stage/background regions are not note
                    # candidates; preserve compact bright panels and ribbons.
                    if not plausible_note_shape:
                        continue
                if y >= self.geometry.judgment_y-65 and kind in ("TAP", "HOLD"):
                    confidence -= .15
                    reasons.append("near_judgment_effect_overlap")
                hsv_pixels = hsv[y:y+h, x:x+w][component > 0]
                pixel_evidence = {
                    "bbox": list(bbox), "mask_pixel_count": area,
                    "mask_spans_rle": _mask_spans(component, bbox),
                    "median_hsv": [float(v) for v in np.median(hsv_pixels, axis=0)],
                    "color_band": color_name, **shape,
                }
                candidate = Candidate(kind, color_name, max(0., min(1., confidence)), bbox, area,
                                      _contour_polygon(component, bbox), pixel_evidence, parts, reasons)
                if kind == "UNKNOWN" or confidence < .62 or "near_judgment_effect_overlap" in reasons:
                    uncertain.append(candidate)
                else:
                    objects.append(candidate)
            # Independent panel proposal: a horizontal morphological opening
            # disconnects the flat face from connected flashes/background.
            # It is a seed only; the emitted contour is recovered from observed
            # source pixels in a tightly bounded neighborhood.
            panel_source_mask = cv2.inRange(
                hsv, np.array([h0, max(25, s0//2), max(130, v0-25)], np.uint8),
                np.array([h1, 255, 255], np.uint8))
            panel_source_mask = cv2.bitwise_and(panel_source_mask, panel_source_mask, mask=self.field_mask)
            panel_source_masks[color_name] = panel_source_mask
            panel_seed = cv2.morphologyEx(
                panel_source_mask, cv2.MORPH_OPEN,
                cv2.getStructuringElement(cv2.MORPH_RECT, (41, 13)))
            panel_count, panel_labels, panel_stats, _ = cv2.connectedComponentsWithStats(
                panel_seed, connectivity=8)
            for panel_label in range(1, panel_count):
                px, py, pw, ph, panel_area = map(int, panel_stats[panel_label])
                if pw < 36 or ph < 8 or pw / max(1, ph) < 2.0 or panel_area < 100:
                    continue
                seed_bbox = (px, py, pw, ph)
                existing = objects + uncertain
                overlaps_hold = any(c.class_name == "HOLD" and c.color_name == color_name and
                    max(0,min(px+pw,c.bbox[0]+c.bbox[2])-max(px,c.bbox[0])) *
                    max(0,min(py+ph,c.bbox[1]+c.bbox[3])-max(py,c.bbox[1])) /
                    max(1,pw*ph) > .30 for c in objects)
                if overlaps_hold:
                    continue
                duplicate = any(c.color_name == color_name and
                    (max(0, min(px+pw,c.bbox[0]+c.bbox[2])-max(px,c.bbox[0])) *
                     max(0, min(py+ph,c.bbox[1]+c.bbox[3])-max(py,c.bbox[1]))) /
                    max(1, pw*ph + c.bbox[2]*c.bbox[3] - max(0, min(px+pw,c.bbox[0]+c.bbox[2])-max(px,c.bbox[0])) *
                        max(0, min(py+ph,c.bbox[1]+c.bbox[3])-max(py,c.bbox[1]))) > .42
                    for c in existing)
                if duplicate:
                    continue
                margin_x, margin_y = max(10, round(pw*.18)), max(4, round(ph*.18))
                bx, by = max(0,px-margin_x), max(0,py-margin_y)
                ex, ey = min(self.geometry.width,px+pw+margin_x), min(self.geometry.height,py+ph+margin_y)
                local_mask = panel_source_mask[by:ey,bx:ex].copy()
                seed = panel_labels[py:py+ph,px:px+pw] == panel_label
                seed_center = (py+ph//2-by, px+pw//2-bx)
                local_count, local_labels, local_stats, _ = cv2.connectedComponentsWithStats(local_mask, connectivity=8)
                chosen = 0
                if 0 <= seed_center[0] < local_labels.shape[0] and 0 <= seed_center[1] < local_labels.shape[1]:
                    chosen = int(local_labels[seed_center])
                if chosen == 0:
                    # The seed can have its center removed by a bright emblem;
                    # choose the source component with greatest overlap instead.
                    best_overlap = 0
                    for local_id in range(1, local_count):
                        overlap_pixels = np.count_nonzero((local_labels[py-by:py+ph-by,px-bx:px+pw-bx] == local_id) & seed)
                        if overlap_pixels > best_overlap:
                            best_overlap, chosen = overlap_pixels, local_id
                if chosen == 0:
                    continue
                lx, ly, lw, lh, area = map(int, local_stats[chosen])
                observed_bbox = (bx+lx, by+ly, lw, lh)
                observed_mask = (local_labels[ly:ly+lh,lx:lx+lw] == chosen).astype(np.uint8)*255
                ratio = lw/max(1,lh)
                if ratio < 1.8 or area < 100:
                    continue
                component_shape = _shape_metrics(observed_mask, observed_bbox, area)
                confidence = min(.92, .60 + min(ratio,7)*.04 + min(component_shape["fill_ratio"],.8)*.12)
                reasons = []
                local_lane_width = float(np.median(np.diff(self.geometry.boundaries(py+ph/2))))
                if pw / max(1.,local_lane_width) > 2.5:
                    confidence -= .35
                    reasons.append("candidate_spans_more_than_two_and_a_half_lanes")
                if py < 26:
                    confidence -= .16
                    reasons.append("candidate_touches_spawn_crop")
                if py+ph >= self.geometry.judgment_y-65:
                    confidence -= .30
                    reasons.append("near_judgment_effect_overlap")
                hsv_pixels = hsv[observed_bbox[1]:observed_bbox[1]+observed_bbox[3],
                                 observed_bbox[0]:observed_bbox[0]+observed_bbox[2]][observed_mask>0]
                evidence = {"bbox": list(observed_bbox), "mask_pixel_count": area,
                            "mask_spans_rle": _mask_spans(observed_mask,observed_bbox),
                            "median_hsv": [float(v) for v in np.median(hsv_pixels,axis=0)],
                            "color_band": color_name, **component_shape,
                            "proposal": "horizontal_morphological_seed_then_bounded_source_pixels"}
                parts = [{"kind":"TAP", "polygon":_contour_polygon(observed_mask,observed_bbox),
                          "bbox":list(observed_bbox), "mask_spans_rle":evidence["mask_spans_rle"]}]
                candidate = Candidate("TAP",color_name,max(0.,min(1.,confidence)),observed_bbox,
                                      area,_contour_polygon(observed_mask,observed_bbox),evidence,parts,reasons)
                (uncertain if confidence < .62 or "near_judgment_effect_overlap" in reasons else objects).append(candidate)
        # Recover panels whose color masks were joined to a bright effect. The
        # paired Canny lines define the primitive; actual color-mask pixels in
        # that tight box provide the recorded pixel evidence.
        for x0,y0,x1,y1 in _horizontal_edge_pairs(
                frame, self.field_mask, round(self.geometry.judgment_y+35)):
            width,height=x1-x0,y1-y0
            if not 10 <= height <= 64 or width/max(1,height)<2.2:
                continue
            ymid=(y0+y1)/2
            lane_width=float(np.median(np.diff(self.geometry.boundaries(ymid))))
            if not .45 <= width/max(1.,lane_width) <= 2.6:
                continue
            # Keep edge evidence inside the trapezoid and away from HUD.
            boundaries=self.geometry.boundaries(ymid)
            left_bound,right_bound=boundaries[0],boundaries[-1]
            if x0 < left_bound-60 or x1 > right_bound+60:
                continue
            bbox=(int(x0),int(y0),int(width),int(height))
            if any(max(0,min(x0+width,c.bbox[0]+c.bbox[2])-max(x0,c.bbox[0]))*
                   max(0,min(y0+height,c.bbox[1]+c.bbox[3])-max(y0,c.bbox[1]))/
                   max(1,width*height)>.35 for c in objects):
                continue
            color_hits=[]
            for color_name,mask in panel_source_masks.items():
                crop=mask[y0:y1,x0:x1]
                color_hits.append((int(np.count_nonzero(crop)),color_name,crop))
            pixel_count,color_name,local_mask=max(color_hits,key=lambda row:row[0])
            if pixel_count < 90:
                continue
            fill_ratio=pixel_count/max(1,width*height)
            if fill_ratio < .68 or width/max(1.,lane_width) > 1.85 or not .15 <= height/max(1.,lane_width) <= .40:
                continue
            if color_name=="green" and any(c.class_name=="HOLD" and
                max(0,min(x0+width,c.bbox[0]+c.bbox[2])-max(x0,c.bbox[0]))*
                max(0,min(y0+height,c.bbox[1]+c.bbox[3])-max(y0,c.bbox[1]))/(width*height)>.25
                for c in objects):
                continue
            median_hsv=[float(v) for v in np.median(hsv[y0:y1,x0:x1][local_mask>0],axis=0)]
            confidence=.68
            reasons=["paired_source_horizontal_edges_and_color_pixels"]
            if x0 < 820 and x1 > 430 and y0 < 486 and y1 > 405:
                confidence-=.4
                reasons.append("overlaps_center_judgment_text_hud")
            if any(max(0,min(x0+width,c.bbox[0]+c.bbox[2])-max(x0,c.bbox[0]))*
                   max(0,min(y0+height,c.bbox[1]+c.bbox[3])-max(y0,c.bbox[1]))/(width*height)>.25
                   for c in objects if c.class_name=="HOLD"):
                confidence-=.25
                reasons.append("overlaps_hold_pixel_region")
            if y1>=self.geometry.judgment_y-65:
                confidence-=.32
                reasons.append("near_judgment_effect_overlap")
            evidence={"bbox":list(bbox),"mask_pixel_count":pixel_count,
                      "mask_spans_rle":_mask_spans(local_mask,bbox),"median_hsv":median_hsv,
                      "color_band":color_name,"horizontal_edge_pair_height_px":height,
                      "edge_support":"CANNY_HOUGH_LONG_PARALLEL_SEGMENTS"}
            polygon=[[float(x0),float(y0)],[float(x1),float(y0)],
                     [float(x1),float(y1)],[float(x0),float(y1)]]
            part={"kind":"TAP","polygon":polygon,"bbox":list(bbox),
                  "mask_spans_rle":evidence["mask_spans_rle"]}
            candidate=Candidate("TAP",color_name,confidence,bbox,pixel_count,polygon,evidence,[part],reasons)
            # Wide candidates suggesting two same-height panels stay visible in
            # the review queue instead of being collapsed into one Tap.
            (uncertain if confidence<.62 or any(reason in reasons for reason in
                ("overlaps_center_judgment_text_hud","overlaps_hold_pixel_region","near_judgment_effect_overlap"))
                else objects).append(candidate)
        # Colored glints inside the known rating-text patch and masks that land
        # on top of another color's Hold are ambiguous, not separate Tap notes.
        safe_objects=[]
        for candidate in objects:
            x,y,w,h=candidate.bbox
            hud_overlap=(candidate.class_name=="TAP" and x<820 and x+w>430 and y<486 and y+h>405)
            hold_overlap=candidate.class_name=="TAP" and any(max(0,min(x+w,hold.bbox[0]+hold.bbox[2])-max(x,hold.bbox[0]))*
                             max(0,min(y+h,hold.bbox[1]+hold.bbox[3])-max(y,hold.bbox[1]))/
                             max(1,w*h)>.22 for hold in objects if hold.class_name=="HOLD" and hold is not candidate)
            if hud_overlap or hold_overlap:
                candidate.confidence=min(candidate.confidence,.58)
                candidate.uncertainty_reasons.append("center_hud_overlap" if hud_overlap else "overlaps_hold_pixel_region")
                uncertain.append(candidate)
            else:
                safe_objects.append(candidate)
        objects=safe_objects
        return objects, uncertain

