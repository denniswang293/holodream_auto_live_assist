"""Causal current-frame pixel segmentation in rectified lane coordinates."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import cv2
import numpy as np
from time import perf_counter

MASK_ROLES = ("lane", "tap_face", "hold_head", "hold_body", "hold_tail",
              "effect_or_artifact", "unknown", "judgment_line")

@dataclass(frozen=True)
class PixelComponent:
    component_id: int
    role: str
    bbox: tuple[int, int, int, int]
    polygon: tuple[tuple[int, int], ...]
    color: str
    area: int
    evidence: tuple[str, ...]
    positive: tuple[str, ...]
    negative: tuple[str, ...]
    ambiguity: tuple[str, ...]
    frame_index: int | None

@dataclass
class SegmentationResult:
    masks: dict[str, np.ndarray]
    components: list[PixelComponent]
    frame_index: int | None
    hit_y: float
    lane_bounds: tuple[float, float]
    def __getitem__(self, role: str) -> np.ndarray:
        return self.masks[role]

class LanePixelSegmenter:
    """Extract conservative masks; every semantic pixel comes from this image."""
    def segment(self, rectified_bgr: np.ndarray, geometry: Any, *,
                frame_index: int | None = None) -> SegmentationResult:
        stage_start = perf_counter()
        image = np.asarray(rectified_bgr)
        if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("rectified_bgr must be an HxWx3 uint8 BGR image")
        h, w = image.shape[:2]
        if (w != int(geometry.plane_width) or h != int(geometry.height)):
            raise ValueError("image dimensions must match geometry's rectified plane")
        hsv_start = perf_counter()
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        hue, sat, val = cv2.split(hsv)
        hsv_ms = (perf_counter() - hsv_start) * 1000
        y = np.arange(h)[:, None]
        lane_region = (y >= max(0, int(np.floor(geometry.top_y)))) & (
            y <= min(h - 1, int(np.ceil(geometry.hit_y + 34))))
        lane = lane_region & (hue >= 76) & (hue <= 120) & (sat >= 35) & (val <= 210)
        masks = {name: np.zeros((h, w), np.uint8) for name in MASK_ROLES}
        masks["lane"][lane] = 255

        # The measured line is separate. Excluding its complete geometric band
        # prevents its horizontal pixels from joining objects in note topology.
        hit_band = np.abs(y - float(geometry.hit_y)) <= 3
        judgment = hit_band & (hue >= 78) & (hue <= 115) & (sat >= 45) & (val >= 125)
        masks["judgment_line"][judgment] = 255
        note_region = lane_region & ~hit_band
        class_masks = {
            "green": (hue >= 40) & (hue <= 83) & (sat >= 55) & (val >= 105) & note_region,
            "yellow": (hue >= 16) & (hue < 40) & (sat >= 65) & (val >= 125) & note_region,
            "cyan": (hue >= 84) & (hue <= 112) & (sat >= 65) & (val >= 135) & note_region,
        }
        components: list[PixelComponent] = []
        assigned = np.zeros((h, w), bool)
        next_id = 1

        # Label each hue class independently: unrelated lane/cyan pixels can
        # neither merge a green ribbon nor generate a mixed full-plane object.
        connected_components_ms = 0.0
        for color_name, class_mask in class_masks.items():
            cc_start = perf_counter()
            n, labels, stats, _ = cv2.connectedComponentsWithStats(class_mask.astype(np.uint8), 8)
            connected_components_ms += (perf_counter() - cc_start) * 1000
            for label in range(1, n):
                x0, y0, cw, ch, _ = map(int, stats[label])
                # Restrict per-component work to its tight ROI. Rebuilding
                # ``labels == label`` over the full rectified image for every
                # fragment was the dominant avoidable cost on busy frames.
                y1, x1 = y0 + ch, x0 + cw
                region = labels[y0:y1, x0:x1] == label
                area = int(stats[label, cv2.CC_STAT_AREA])
                if cw * ch < 5 or area < 4:
                    continue
                aspect = cw / max(1, ch)
                density = area / max(1, cw * ch)
                plate = (8 <= cw <= .62 * w and 3 <= ch <= 22 and
                         aspect >= 1.45 and density >= .28 and area >= 18)
                role = "unknown"
                evidence = ["current_frame_hsv_chroma", "connected_observed_pixels",
                            "hue_isolated_component"]
                positive: list[str] = []
                negative: list[str] = []
                ambiguity: list[str] = []
                head = np.zeros((ch, cw), bool)
                tail = np.zeros((ch, cw), bool)

                if color_name in ("yellow", "cyan") and plate:
                    role = "tap_face"
                    positive.extend(("horizontal_panel_shape", "measured_color_fill"))
                    evidence.extend(("aspect_ratio", "pixel_density"))
                elif color_name == "green" and ch >= 18 and area >= 24:
                    role = "hold_body"
                    positive.extend(("elongated_green_region", "continuous_component"))
                    evidence.extend(("vertical_extent", "component_area"))
                    ambiguity.append("head_tail_ownership_requires_distinct_endpoint_evidence")
                    rows = np.count_nonzero(region, axis=1)
                    active = np.flatnonzero(rows)
                    mid = active[(active >= int(.2 * ch)) & (active <= int(.7 * ch))]
                    base = float(np.median(rows[mid])) if len(mid) else 0.
                    if base > 0:
                        # Find a flat, panel-like terminal face. Comparing only
                        # ribbon width to a global median misses valid heads on
                        # curved notes where the end panel is only modestly
                        # wider than the ribbon. A stable row span and center
                        # at a component endpoint provide the face evidence.
                        def terminal_cap(reverse: bool) -> np.ndarray:
                            ordered = active[::-1] if reverse else active
                            selected=[];centers=[];widths=[];misses=0
                            for row_index in ordered:
                                count=int(rows[row_index])
                                if count < max(8, .55*base):
                                    misses += 1
                                    if misses >= 2: break
                                    continue
                                xs=np.flatnonzero(region[row_index])
                                center=(int(xs[0])+int(xs[-1]))/2
                                next_centers=centers+[center];next_widths=widths+[count]
                                if selected and (max(next_centers)-min(next_centers) > .18*max(base,8) or
                                        max(next_widths)-min(next_widths) > .35*max(1,float(np.median(next_widths)))):
                                    break
                                selected.append(int(row_index));centers.append(center);widths.append(count);misses=0
                                if len(selected)>=36:break
                            if len(selected)<8:return np.zeros((ch,cw),bool)
                            selected=np.asarray(selected,dtype=int)
                            if np.ptp(selected)+1 < 8 or float(np.median(widths))/max(1,np.ptp(selected)+1)<1.4:
                                return np.zeros((ch,cw),bool)
                            out=np.zeros((ch,cw),bool);out[selected]=region[selected]
                            return out
                        head = terminal_cap(True)
                        tail = terminal_cap(False)
                        if np.any(head & tail):
                            head[:] = False
                            tail[:] = False
                    body = region & ~head & ~tail
                    if not np.any(body):
                        role = "unknown"
                        head[:] = False
                        tail[:] = False
                        body = region
                        ambiguity.append("endpoint_seen_without_separable_body")
                    else:
                        masks["hold_body"][y0:y1, x0:x1][body] = 255
                        assigned[y0:y1, x0:x1][body] = True
                        masks["hold_head"][y0:y1, x0:x1][head] = 255
                        masks["hold_tail"][y0:y1, x0:x1][tail] = 255
                        assigned[y0:y1, x0:x1][head | tail] = True
                else:
                    if cw < 8 or ch < 3:
                        negative.append("too_thin_or_small_for_a_panel")
                    if color_name == "green":
                        ambiguity.append("green_fragment_lacks_continuous_ribbon_extent")
                    if color_name in ("yellow", "cyan") and not plate:
                        ambiguity.append("panel_geometry_not_confirmed")

                if role == "unknown":
                    masks["unknown"][y0:y1, x0:x1][region] = 255
                    assigned[y0:y1, x0:x1][region] = True
                elif role != "hold_body":
                    masks[role][y0:y1, x0:x1][region] = 255
                    assigned[y0:y1, x0:x1][region] = True

                polygon: tuple[tuple[int, int], ...] = ()
                # Unknown/effect specks keep their exact pixels in the masks
                # and their component bbox/area here. Contouring every tiny
                # artifact consumed most of the non-CC CPU time without adding
                # usable shape evidence. Semantic note components still get a
                # polygon from observed pixels.
                if role not in ("unknown", "effect_or_artifact"):
                    contours, _ = cv2.findContours(region.astype(np.uint8), cv2.RETR_EXTERNAL,
                                                    cv2.CHAIN_APPROX_SIMPLE)
                else:
                    contours = []
                if contours:
                    contour = max(contours, key=cv2.contourArea)
                    approx = cv2.approxPolyDP(contour, 1.0, True).reshape(-1, 2)
                    polygon = tuple((int(px + x0), int(py + y0)) for px, py in approx)
                components.append(PixelComponent(next_id, role, (x0, y0, cw, ch),
                    polygon, color_name, area, tuple(evidence), tuple(positive),
                    tuple(negative), tuple(ambiguity), frame_index))
                next_id += 1
                for end_role, end_pixels in (("hold_head", head), ("hold_tail", tail)):
                    end_area = int(np.count_nonzero(end_pixels))
                    if role != "hold_body" or end_area < 2:
                        continue
                    ey, ex = np.nonzero(end_pixels)
                    local_x, local_y = int(ex.min()), int(ey.min())
                    ecx, ecy = x0 + local_x, y0 + local_y
                    ecw, ech = int(ex.max() - local_x + 1), int(ey.max() - local_y + 1)
                    contours, _ = cv2.findContours(end_pixels.astype(np.uint8), cv2.RETR_EXTERNAL,
                                                   cv2.CHAIN_APPROX_SIMPLE)
                    contour = max(contours, key=cv2.contourArea)
                    approx = cv2.approxPolyDP(contour, 1.0, True).reshape(-1, 2)
                    components.append(PixelComponent(next_id, end_role, (ecx, ecy, ecw, ech),
                        tuple((int(px + x0), int(py + y0)) for px, py in approx), color_name, end_area,
                        ("current_frame_hsv_chroma", "connected_to_ribbon", "broad_endpoint_cap"),
                        ("endpoint_wider_than_ribbon_body",), (),
                        ("physical_owner_not_confirmed_across_frames",), frame_index))
                    next_id += 1

        # Recover complete cyan/yellow Tap faces that connect to a bright
        # judgment glint or lane line in the raw hue mask. A horizontal open
        # kernel proposes only panel-like cores; the exported mask is then
        # clipped back to the observed current-frame chroma pixels. This uses
        # no Perception detections and never fills the proposed rectangle.
        tap_recovery_start=perf_counter()
        roi_top=max(0,int(np.floor(geometry.top_y)))
        roi_bottom=min(h,int(np.ceil(geometry.hit_y-3)))
        for color_name in ("yellow", "cyan"):
            source_mask=class_masks[color_name][roi_top:roi_bottom,:].astype(np.uint8)
            opened=cv2.morphologyEx(source_mask,cv2.MORPH_OPEN,
                np.ones((3,max(12,round(.22*geometry.lane_pixels))),np.uint8))
            count,labels,stats,_=cv2.connectedComponentsWithStats(opened,8)
            for label in range(1,count):
                px,py,pw,ph,proposal_area=map(int,stats[label])
                py+=roi_top
                if not (24<=pw<=2.2*geometry.lane_pixels and 5<=ph<=26 and
                        pw/max(1,ph)>=2.4 and proposal_area>=32):continue
                pad_x=max(2,round(.08*pw));pad_y=2
                x0=max(0,px-pad_x);x1=min(w,px+pw+pad_x)
                y0=max(0,py-pad_y);y1=min(h,py+ph+pad_y)
                local=class_masks[color_name][y0:y1,x0:x1]
                ys,xs=np.nonzero(local)
                if len(xs)<40:continue
                # Trim the proposal to actual chroma-supported pixels only.
                lx,rx=int(xs.min()),int(xs.max()+1);ly,ry=int(ys.min()),int(ys.max()+1)
                bx,by,bw,bh=x0+lx,y0+ly,rx-lx,ry-ly
                pixels=local[ly:ry,lx:rx]
                density=float(np.mean(pixels))
                row_counts=np.count_nonzero(pixels,axis=1)
                fill_rows=np.count_nonzero(row_counts>=.45*bw)/max(1,bh)
                hsv_roi=hsv[by:by+bh,bx:bx+bw]
                if not (bw/max(1,bh)>=2.4 and density>=.42 and fill_rows>=.65 and
                        float(np.mean(hsv_roi[:,:,1]))>=95 and float(np.mean(hsv_roi[:,:,2]))>=150):continue
                # Do not duplicate a panel already isolated as its own
                # connected component; preserve the larger, full face mask.
                duplicate=False
                for existing in components:
                    if existing.role!="tap_face" or existing.color!=color_name:continue
                    ex,ey,ew,eh=existing.bbox
                    overlap=max(0,min(bx+bw,ex+ew)-max(bx,ex))*max(0,min(by+bh,ey+eh)-max(by,ey))
                    cover=overlap/max(1,bw*bh)
                    if cover>=.55:duplicate=True;break
                if duplicate:continue
                observed=pixels.astype(bool)
                masks["tap_face"][by:by+bh,bx:bx+bw][observed]=255
                masks["unknown"][by:by+bh,bx:bx+bw][observed]=0
                assigned[by:by+bh,bx:bx+bw][observed]=True
                contours,_=cv2.findContours(observed.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
                polygon=()
                if contours:
                    approx=cv2.approxPolyDP(max(contours,key=cv2.contourArea),1.0,True).reshape(-1,2)
                    polygon=tuple((int(x+bx),int(y+by)) for x,y in approx)
                components.append(PixelComponent(next_id,"tap_face",(bx,by,bw,bh),polygon,
                    color_name,int(np.count_nonzero(observed)),
                    ("current_frame_hsv_chroma","horizontal_morphology_panel_core","connected_observed_pixels"),
                    ("horizontal_panel_shape","dense_saturated_face_fill"),(),
                    ("judgment_effect_excluded_by_hit_band_and_panel_geometry",),frame_index))
                next_id+=1
        tap_recovery_ms=(perf_counter()-tap_recovery_start)*1000

        near_hit = np.abs(y - float(geometry.hit_y)) <= 34
        gray_start=perf_counter()
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray_conversion_ms=(perf_counter()-gray_start)*1000
        bright = near_hit & (val >= 218) & ((sat <= 105) | ((hue >= 13) & (hue <= 40)))
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        edges = near_hit & (np.hypot(gx, gy) >= 170) & (sat < 90) & ~lane
        effect = (bright | edges) & ~assigned
        masks["effect_or_artifact"][effect] = 255
        n, labels, stats, _ = cv2.connectedComponentsWithStats(effect.astype(np.uint8), 8)
        for label in range(1, n):
            x0, y0, cw, ch, area = map(int, stats[label])
            if area < 3:
                continue
            region = labels[y0:y0 + ch, x0:x0 + cw] == label
            polygon: tuple[tuple[int, int], ...] = ()
            if area >= 16:
                contours, _ = cv2.findContours(region.astype(np.uint8), cv2.RETR_EXTERNAL,
                                               cv2.CHAIN_APPROX_SIMPLE)
                if contours:
                    approx = cv2.approxPolyDP(max(contours, key=cv2.contourArea), 1.0, True).reshape(-1, 2)
                    polygon = tuple((int(px + x0), int(py + y0)) for px, py in approx)
            components.append(PixelComponent(next_id, "effect_or_artifact", (x0, y0, cw, ch),
                polygon, "bright_or_edge", area,
                ("current_frame_brightness_or_gradient", "near_judgment_line"),
                ("observed_flash_or_thin_stroke",), (),
                ("could_be_judgment_effect_or_artifact",), frame_index))
            next_id += 1

        self.last_profile = {"hsv_conversion_ms": hsv_ms,
                             "gray_conversion_ms": gray_conversion_ms,
                             "connected_components_ms": connected_components_ms,
                             "tap_panel_recovery_ms":tap_recovery_ms,
                             "mask_and_component_ms": max(0., (perf_counter() - stage_start) * 1000 - hsv_ms - gray_conversion_ms - connected_components_ms-tap_recovery_ms)}
        return SegmentationResult(masks, components, frame_index, float(geometry.hit_y),
                                  (float(geometry.top_y), float(geometry.hit_y)))
