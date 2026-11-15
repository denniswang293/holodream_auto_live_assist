"""Causal current-frame pixel segmentation in rectified lane coordinates."""
from __future__ import annotations
from dataclasses import dataclass
from bisect import bisect_left
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
    connection_group_id: int | None = None

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
        mask_setup_start = perf_counter()
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
            # A neutral panel stays UNKNOWN until repeated motion and separate
            # ribbon evidence establish its physical meaning.
            "neutral": (sat <= 72) & (val >= 160) & note_region,
        }
        # Keep every neutral pixel available for inspection, but do not run
        # per-component geometry, row profiles, or contour work on the many
        # unrelated bright HUD/background regions. Plausible panel/ribbon ROIs
        # are reconsidered below; unexamined pixels remain explicitly UNKNOWN.
        masks["unknown"][class_masks["neutral"]] = 255
        components: list[PixelComponent] = []
        assigned = np.zeros((h, w), bool)
        next_id = 1
        class_mask_setup_ms = (perf_counter() - mask_setup_start) * 1000

        # Label each hue class independently: unrelated lane/cyan pixels can
        # neither merge a green ribbon nor generate a mixed full-plane object.
        connected_components_ms = 0.0
        class_component_start = perf_counter()
        # Every class mask is already zero outside lane_region. Crop only the
        # connected-components input to that exact nonzero y domain so OpenCV
        # doesn't label rows that can never contain a component. Keep exported
        # masks full-sized and translate component coordinates back to the
        # same rectified image coordinates.
        class_roi_top=max(0,int(np.floor(geometry.top_y)))
        class_roi_bottom=min(h-1,int(np.ceil(geometry.hit_y+34)))+1
        for color_name, class_mask in class_masks.items():
            cc_start = perf_counter()
            class_roi=class_mask[class_roi_top:class_roi_bottom,:]
            n, labels, stats, _ = cv2.connectedComponentsWithStats(class_roi.view(np.uint8), 8)
            connected_components_ms += (perf_counter() - cc_start) * 1000
            # Filter components that the scalar loop would immediately skip.
            # Keeping the ascending label order preserves component IDs and
            # record ordering while avoiding Python work for tiny fragments.
            widths = stats[1:n, cv2.CC_STAT_WIDTH]
            heights = stats[1:n, cv2.CC_STAT_HEIGHT]
            areas = stats[1:n, cv2.CC_STAT_AREA]
            boxes = widths * heights
            keep = (boxes >= 5) & (areas >= 4)
            if color_name == "neutral":
                aspect_values = widths / np.maximum(1, heights)
                density_values = areas / np.maximum(1, boxes)
                plausible_panel = ((widths >= 8) & (widths <= .62 * w) &
                                   (heights >= 3) & (heights <= 22) &
                                   (aspect_values >= 1.45) &
                                   (density_values >= .28) & (areas >= 18))
                plausible_ribbon = ((heights >= 24) &
                                    (heights >= 1.05 * widths) & (areas >= 80))
                keep &= plausible_panel | plausible_ribbon
            for label in np.flatnonzero(keep) + 1:
                x0, local_y0, cw, ch, _ = map(int, stats[label])
                y0=local_y0+class_roi_top
                # Restrict per-component work to its tight ROI. Rebuilding
                # ``labels == label`` over the full rectified image for every
                # fragment was the dominant avoidable cost on busy frames.
                y1, x1 = y0 + ch, x0 + cw
                area = int(stats[label, cv2.CC_STAT_AREA])
                aspect = cw / max(1, ch)
                density = area / max(1, cw * ch)
                # Cheap stats reject most background fragments. Materialize
                # the exact pixel ROI only after those gates pass.
                region = labels[local_y0:local_y0+ch, x0:x1] == label
                plate = (8 <= cw <= .62 * w and 3 <= ch <= 22 and
                         aspect >= 1.45 and density >= .28 and area >= 18)
                role = "unknown"
                evidence = ["current_frame_hsv_chroma", "connected_observed_pixels",
                            "hue_isolated_component"]
                positive: list[str] = []
                negative: list[str] = []
                ambiguity: list[str] = []
                head = tail = None

                neutral_face=(color_name=="neutral" and plate and density>=.48 and ch>=12)
                yellow_ribbon=(color_name=="yellow" and ch>=24 and ch>=1.05*cw and area>=60)
                neutral_ribbon=(color_name=="neutral" and ch>=24 and ch>=1.05*cw and area>=80)
                full_color_panel = plate and ch >= 12
                if color_name in ("yellow", "cyan") and full_color_panel:
                    role = "tap_face"
                    positive.extend(("horizontal_panel_shape", "measured_color_fill"))
                    evidence.extend(("aspect_ratio", "pixel_density"))
                elif color_name in ("yellow", "cyan") and plate:
                    # Preserve partial near-hit faces as observed UNKNOWN pixels.
                    # A 3–11 px rail can be a clipped panel, a hit spark, or a
                    # judgment-line fragment; it is not enough evidence to
                    # create an actionable Tap face.
                    positive.append("partial_color_panel_candidate")
                    negative.append("visible_panel_height_below_12px")
                    ambiguity.append("full_tap_face_not_visible")
                    evidence.extend(("aspect_ratio", "pixel_density", "partial_vertical_extent"))
                elif neutral_face:
                    positive.extend(("neutral_full_face_candidate", "horizontal_panel_shape",
                                     "measured_neutral_pixel_fill"))
                    evidence.extend(("aspect_ratio", "pixel_density", "low_saturation_bright_pixels"))
                    ambiguity.append("tap_or_hold_type_requires_motion_and_ribbon_evidence")
                elif color_name=="neutral" and plate:
                    positive.append("partial_neutral_panel_candidate")
                    negative.append("visible_panel_height_below_12px")
                    ambiguity.append("full_neutral_face_not_visible")
                    evidence.extend(("aspect_ratio", "pixel_density", "partial_vertical_extent"))
                elif color_name in ("green", "yellow", "neutral") and ch >= 18 and area >= 24 and (
                        color_name=="green" or yellow_ribbon or neutral_ribbon):
                    role = "hold_body"
                    head = np.zeros((ch, cw), bool)
                    tail = np.zeros((ch, cw), bool)
                    positive.extend(("elongated_color_region", "continuous_component"))
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
                            center_min=center_max=None
                            width_min=width_max=None
                            sorted_widths=[]
                            for row_index in ordered:
                                count=int(rows[row_index])
                                if count < max(8, .55*base):
                                    misses += 1
                                    if misses >= 2: break
                                    continue
                                row_pixels=region[row_index]
                                center=(int(np.argmax(row_pixels))+
                                        cw-1-int(np.argmax(row_pixels[::-1])))/2
                                if selected:
                                    next_center_min=min(center_min,center)
                                    next_center_max=max(center_max,center)
                                    next_width_min=min(width_min,count)
                                    next_width_max=max(width_max,count)
                                    next_sorted_widths=sorted_widths.copy()
                                    next_sorted_widths.insert(bisect_left(next_sorted_widths,count),count)
                                    nwidths=len(next_sorted_widths)
                                    if nwidths%2:
                                        width_median=float(next_sorted_widths[nwidths//2])
                                    else:
                                        width_median=(next_sorted_widths[nwidths//2-1]+
                                                      next_sorted_widths[nwidths//2])/2
                                    if (next_center_max-next_center_min > .18*max(base,8) or
                                            next_width_max-next_width_min > .35*max(1,width_median)):
                                        break
                                else:
                                    next_center_min=next_center_max=center
                                    next_width_min=next_width_max=count
                                    next_sorted_widths=[count]
                                sorted_widths=next_sorted_widths
                                center_min,center_max=next_center_min,next_center_max
                                width_min,width_max=next_width_min,next_width_max
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
                    if color_name == "neutral":
                        masks["unknown"][y0:y1, x0:x1][region] = 0
                    masks[role][y0:y1, x0:x1][region] = 255
                    assigned[y0:y1, x0:x1][region] = True
                elif color_name == "neutral":
                    masks["unknown"][y0:y1, x0:x1][region] = 0

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
                connection_group_id = next_id if role == "hold_body" else None
                components.append(PixelComponent(next_id, role, (x0, y0, cw, ch),
                    polygon, color_name, area, tuple(evidence), tuple(positive),
                    tuple(negative), tuple(ambiguity), frame_index, connection_group_id))
                next_id += 1
                if role == "hold_body":
                    for end_role, end_pixels in (("hold_head", head), ("hold_tail", tail)):
                        end_area = int(np.count_nonzero(end_pixels))
                        if end_area < 2:
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
                            ("physical_owner_not_confirmed_across_frames",), frame_index,
                            connection_group_id))
                        next_id += 1
        class_component_loop_ms = (perf_counter() - class_component_start) * 1000

        # Recover complete cyan/yellow Tap faces that connect to a bright
        # judgment glint or lane line in the raw hue mask. A horizontal open
        # kernel proposes only panel-like cores; the exported mask is then
        # clipped back to the observed current-frame chroma pixels. This uses
        # no Perception detections and never fills the proposed rectangle.
        tap_recovery_start=perf_counter()
        roi_top=max(0,int(np.floor(geometry.top_y)))
        roi_bottom=min(h,int(np.ceil(geometry.hit_y-3)))
        for color_name in ("yellow", "cyan"):
            # Boolean arrays use the same 0/1 byte representation needed by
            # OpenCV morphology, so pass a byte view instead of copying.
            source_mask=class_masks[color_name][roi_top:roi_bottom,:].view(np.uint8)
            opened=cv2.morphologyEx(source_mask,cv2.MORPH_OPEN,
                np.ones((3,max(12,round(.22*geometry.lane_pixels))),np.uint8))
            count,labels,stats,_=cv2.connectedComponentsWithStats(opened,8)
            for label in range(1,count):
                px,py,pw,ph,proposal_area=map(int,stats[label])
                py+=roi_top
                if not (24<=pw<=2.2*geometry.lane_pixels and 8<=ph<=26 and
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
                if not (bh>=12 and bw/max(1,bh)>=2.4 and density>=.42 and fill_rows>=.65 and
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
                observed=pixels
                masks["tap_face"][by:by+bh,bx:bx+bw][observed]=255
                masks["unknown"][by:by+bh,bx:bx+bw][observed]=0
                assigned[by:by+bh,bx:bx+bw][observed]=True
                contours,_=cv2.findContours(observed.view(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
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
        # A screen-wide cyan connection can erase a real panel during opening.
        # Recheck one bounded 2.2-lane ROI centered on each lane (rather than
        # sliding many overlapping windows across every x position). A black
        # separator keeps the tiled ROIs independent for morphology/labeling.
        # Only a dense, sufficiently tall horizontal core may restore observed
        # pixels; clipped hit glows and thin rails remain UNKNOWN.
        cyan_top=max(0,int(np.floor(geometry.top_y)))
        cyan_bottom=min(h,int(np.ceil(geometry.hit_y-3)))
        cyan_source=class_masks["cyan"][cyan_top:cyan_bottom,:].view(np.uint8)
        roi_width=max(48,int(round(2.2*geometry.lane_pixels)))
        roi_specs=[]
        for lane_index in range(6):
            center=(lane_index+.5)*geometry.lane_pixels
            rx0=int(round(center-roi_width/2));rx1=rx0+roi_width
            if lane_index==0:
                # Keep a full-width window at each outer screen edge. Clipping
                # the nominal lane-centered ROI would leave only 96px of the
                # 132px window and can cut the panel core itself.
                roi_specs.append((lane_index,0,min(w,roi_width)))
            elif lane_index==5:
                roi_specs.append((lane_index,max(0,w-roi_width),w))
            elif rx0>=0 and rx1<=w:
                roi_specs.append((lane_index,rx0,rx1))
        separator=1;stride=roi_width+separator
        tiled=np.zeros((cyan_source.shape[0],
                        len(roi_specs)*roi_width+max(0,len(roi_specs)-1)*separator),np.uint8)
        for tile_index,(_,rx0,rx1) in enumerate(roi_specs):
            left=tile_index*stride
            tiled[:,left:left+roi_width]=cyan_source[:,rx0:rx1]
        kernel_width=max(30,round(.58*geometry.lane_pixels))
        opened=cv2.morphologyEx(tiled,cv2.MORPH_OPEN,
            np.ones((3,kernel_width),np.uint8))
        proposal_count,proposal_labels,proposal_stats,_=cv2.connectedComponentsWithStats(opened,8)
        cyan_proposals=[]
        for label in range(1,proposal_count):
            tx,ty,pw,ph,proposal_area=map(int,proposal_stats[label])
            tile_index=tx//stride
            if tile_index>=len(roi_specs):continue
            local_x=tx-tile_index*stride
            if local_x+pw>roi_width:continue  # component touched the separator
            edge_tile=tile_index in (0,len(roi_specs)-1)
            if (local_x==0 or local_x+pw>=roi_width) and not edge_tile:continue
            if not (24<=pw<=2.2*geometry.lane_pixels and 8<=ph<=32 and
                    pw/max(1,ph)>=2.4 and proposal_area>=32):continue
            _,rx0,rx1=roi_specs[tile_index]
            px,py=rx0+local_x,cyan_top+ty
            if geometry.hit_y-(py+ph/2)<18:continue
            # At the screen edge, the opened core can sit inside a broader
            # connected glow. Keep its vertical recovery band tight so the
            # actual panel rows pass density/fill checks without absorbing
            # the glow above or below it.
            pad_y=2 if edge_tile else max(2,round(.75*ph))
            if edge_tile:
                # Preserve just the horizontal span of the opened panel core.
                # Expanding x around it would absorb a thin cyan bridge that
                # was deliberately removed by the opening operation.
                x0=max(rx0,px);x1=min(rx1,px+pw)
            else:
                pad_x=max(2,round(.08*pw))
                x0=max(rx0,px-pad_x);x1=min(rx1,px+pw+pad_x)
            y0=max(cyan_top,py-pad_y);y1=min(cyan_bottom,py+ph+pad_y)
            local=class_masks["cyan"][y0:y1,x0:x1]
            ys,xs=np.nonzero(local)
            if len(xs)<40:continue
            bx,by=x0+int(xs.min()),y0+int(ys.min())
            ex,ey=x0+int(xs.max()+1),y0+int(ys.max()+1)
            pixels=local[int(ys.min()):int(ys.max()+1),int(xs.min()):int(xs.max()+1)]
            bw,bh=ex-bx,ey-by
            density=float(np.mean(pixels));rows=np.count_nonzero(pixels,axis=1)
            fill_rows=np.count_nonzero(rows>=.45*bw)/max(1,bh)
            hsv_roi=hsv[by:ey,bx:ex]
            if not (bh>=12 and bw/max(1,bh)>=2.4 and density>=.42 and fill_rows>=.65 and
                    float(np.mean(hsv_roi[:,:,1]))>=95 and float(np.mean(hsv_roi[:,:,2]))>=150):continue
            cyan_proposals.append((int(np.count_nonzero(pixels)),bx,by,ex,ey,pixels.copy()))
        accepted_boxes=[]
        for area,bx,by,ex,ey,pixels in sorted(cyan_proposals,key=lambda p:(-p[0],p[1],p[2])):
            bw,bh=ex-bx,ey-by
            duplicate=False
            for existing in components:
                if existing.role!="tap_face" or existing.color!="cyan":continue
                ex0,ey0,ew,eh=existing.bbox
                overlap=max(0,min(ex,ex0+ew)-max(bx,ex0))*max(0,min(ey,ey0+eh)-max(by,ey0))
                if overlap/max(1,min(bw*bh,ew*eh))>=.55:
                    duplicate=True;break
            if duplicate:continue
            if any(max(0,min(ex,x0+ww)-max(bx,x0))*max(0,min(ey,y0+hh)-max(by,y0)) /
                   max(1,min(bw*bh,ww*hh))>=.55 for x0,y0,ww,hh in accepted_boxes):
                continue
            accepted_boxes.append((bx,by,bw,bh))
            masks["tap_face"][by:ey,bx:ex][pixels]=255
            masks["unknown"][by:ey,bx:ex][pixels]=0
            assigned[by:ey,bx:ex][pixels]=True
            contours,_=cv2.findContours(pixels.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            approx=cv2.approxPolyDP(max(contours,key=cv2.contourArea),1.0,True).reshape(-1,2)
            polygon=tuple((int(x+bx),int(y+by)) for x,y in approx)
            components.append(PixelComponent(next_id,"tap_face",(bx,by,bw,bh),polygon,
                "cyan",area,
                ("current_frame_hsv_chroma","lane_centered_panel_core","connected_observed_pixels"),
                ("horizontal_panel_shape","dense_saturated_face_fill"),(),
                ("judgment_glow_excluded_by_hit_distance_and_screen_edge",),frame_index))
            next_id+=1
        tap_recovery_ms=(perf_counter()-tap_recovery_start)*1000

        effect_y0=max(0,int(np.ceil(geometry.hit_y-34)))
        effect_y1=min(h,int(np.floor(geometry.hit_y+34))+1)
        effect_pad_top=max(0,effect_y0-1)
        effect_pad_bottom=min(h,effect_y1+1)
        gray_start=perf_counter()
        gray = cv2.cvtColor(image[effect_pad_top:effect_pad_bottom], cv2.COLOR_BGR2GRAY)
        gray_conversion_ms=(perf_counter()-gray_start)*1000
        effect_mask_start = perf_counter()
        pad_offset=effect_y0-effect_pad_top
        row_end=pad_offset+(effect_y1-effect_y0)
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)[pad_offset:row_end]
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)[pad_offset:row_end]
        near_hit=np.abs(np.arange(effect_y0,effect_y1)[:,None]-float(geometry.hit_y))<=34
        hue_roi=hue[effect_y0:effect_y1]
        sat_roi=sat[effect_y0:effect_y1]
        val_roi=val[effect_y0:effect_y1]
        bright=near_hit & (val_roi>=218) & ((sat_roi<=105)|((hue_roi>=13)&(hue_roi<=40)))
        edges=near_hit & (np.hypot(gx,gy)>=170) & (sat_roi<90) & ~lane[effect_y0:effect_y1]
        effect=(bright|edges) & ~assigned[effect_y0:effect_y1]
        masks["effect_or_artifact"][effect_y0:effect_y1][effect]=255
        effect_mask_ms = (perf_counter() - effect_mask_start) * 1000
        effect_cc_start = perf_counter()
        n, labels, stats, _ = cv2.connectedComponentsWithStats(effect.astype(np.uint8), 8)
        effect_connected_components_ms = (perf_counter() - effect_cc_start) * 1000
        effect_component_start = perf_counter()
        for label in range(1, n):
            x0, local_y0, cw, ch, area = map(int, stats[label])
            if area < 3:
                continue
            y0=local_y0+effect_y0
            region = labels[local_y0:local_y0 + ch, x0:x0 + cw] == label
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
        effect_component_loop_ms = (perf_counter() - effect_component_start) * 1000

        self.last_profile = {"hsv_conversion_ms": hsv_ms,
                             "gray_conversion_ms": gray_conversion_ms,
                             "connected_components_ms": connected_components_ms,
                             "class_mask_setup_ms": class_mask_setup_ms,
                             "class_component_loop_ms": class_component_loop_ms,
                             "tap_panel_recovery_ms":tap_recovery_ms,
                             "effect_mask_ms": effect_mask_ms,
                             "effect_connected_components_ms": effect_connected_components_ms,
                             "effect_component_loop_ms": effect_component_loop_ms,
                             "mask_and_component_ms": max(0., (perf_counter() - stage_start) * 1000 - hsv_ms - gray_conversion_ms - connected_components_ms-tap_recovery_ms)}
        return SegmentationResult(masks, components, frame_index, float(geometry.hit_y),
                                  (float(geometry.top_y), float(geometry.hit_y)))
