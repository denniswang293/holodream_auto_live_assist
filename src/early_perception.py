"""V8.5 causal early-note provider built only from the current rectified frame."""
from __future__ import annotations

import time
import cv2
import numpy as np

from .lane_filter import LanePixelSegmenter
from .model import Detection, KEYS


class EarlyPixelProvider:
    """Build early Tap/Hold observations with provenance for offline Replay.

    ``birth_zone_end_y`` is supplied by the multi-run audit tool. Until that
    audit has a usable distribution, the provider conservatively uses the
    geometry midpoint and records that the zone is provisional.
    """
    def __init__(self, geometry, *, birth_zone_end_y: float | None = None,
                 record_conversion_trace: bool = False,
                 include_polygons: bool = True):
        self.geometry = geometry
        self.segmenter = LanePixelSegmenter()
        self.include_polygons = bool(include_polygons)
        self.birth_zone_end_y = (float(birth_zone_end_y) if birth_zone_end_y is not None
                                 else geometry.top_y + .5*(geometry.hit_y-geometry.top_y))
        self.birth_zone_source = 'multi_run_candidate_audit' if birth_zone_end_y is not None else 'provisional_geometry_midpoint'
        self.record_conversion_trace = bool(record_conversion_trace)
        self.last_result = None
        self.last_rect = None
        self.last_labels = None
        self.last_path = None
        self.last_profile = {}
        self.conversion_trace = []
        self.frame_index = 0

    def ensure_last_labels(self):
        """Materialize exact full-frame Hold-path labels on first real use."""
        if self.last_labels is None and self.last_path is not None:
            _,self.last_labels=cv2.connectedComponents(self.last_path,8)
        return self.last_labels

    def detect(self, normalized_bgr):
        started = time.perf_counter()
        rectified = self.geometry.rectify(normalized_bgr)
        rectify_ms = (time.perf_counter()-started)*1000
        segment_start=time.perf_counter()
        result=self.segmenter.segment(rectified,self.geometry,frame_index=self.frame_index,
                                      include_polygons=self.include_polygons)
        segmentation_ms=(time.perf_counter()-segment_start)*1000
        self.last_result=result;self.last_rect=rectified
        self.last_path=np.zeros(rectified.shape[:2],np.uint8)
        for name in ('hold_head','hold_body','hold_tail'):
            self.last_path|=result.masks[name]
        self.last_labels=None
        group_masks=result.connection_group_masks
        observations=[];drop_count=0
        drop_reasons=[] if self.record_conversion_trace else None
        trace=[] if self.record_conversion_trace else None
        # Small neutral fragments fully contained by a complete colored Tap
        # face are retained in the UNKNOWN pixel mask but are not offered as a
        # second tracker observation. This covers both the bottom-bevel rail
        # and small in-panel glyphs that otherwise create duplicate Tap tracks.
        tap_faces=[c.bbox for c in result.components if c.role=='tap_face']
        for component in result.components:
            role=component.role
            if (role=='unknown' and 'partial_neutral_panel_candidate' in component.positive and
                    self._occluded_neutral_fragment(component.bbox,tap_faces)):
                if trace is not None:
                    trace.append({'component_id':component.component_id,'role':role,
                        'connection_group_id':component.connection_group_id,
                        'conversion':'suppressed_occluded_fragment','bbox':component.bbox,
                        'color':component.color,'area':component.area,
                        'reason':'partial_neutral_pixels_occluded_by_complete_tap_face'})
                continue
            if role=='hold_body' or role in ('effect_or_artifact',):
                if trace is not None:
                    trace.append({'component_id':component.component_id,'role':role,
                        'connection_group_id':component.connection_group_id,
                        'conversion':'not_action_observation','bbox':component.bbox,'color':component.color,
                        'area':component.area,'reason':'ribbon_path_evidence_only'})
                continue
            candidate='';kind='';full_face=False;connected=False
            if role=='tap_face':
                quality=component.area/max(1,component.bbox[2]*component.bbox[3])
                full_face=component.bbox[3]>=6 and component.bbox[2]>=8 and quality>=.42
                candidate='tap' if full_face else 'pending'
                kind='tap' if full_face else 'plate_fragment'
            elif role=='hold_head':
                quality=component.area/max(1,component.bbox[2]*component.bbox[3])
                full_face=component.bbox[3]>=8 and quality>=.32
                connected='connected_to_ribbon' in component.evidence
                candidate='hold' if full_face and connected else 'pending'
                kind='hold_head' if candidate=='hold' else 'plate_fragment'
            elif role=='hold_tail':
                kind='hold_tail';candidate='hold';quality=component.area/max(1,component.bbox[2]*component.bbox[3])
                full_face=component.bbox[3]>=6;connected=True
            elif role=='unknown' and 'neutral_full_face_candidate' in component.positive:
                # Gray/low-saturation plates are evidence-bearing candidates,
                # never executable until repeated motion confirms the type.
                kind='plate_fragment';candidate='pending';quality=component.area/max(1,component.bbox[2]*component.bbox[3])
                full_face=True
            elif role=='unknown' and 'partial_color_panel_candidate' in component.positive:
                # Keep the real pixels and motion candidate for association,
                # but do not turn a thin cyan/yellow fragment into a Tap.
                kind='plate_fragment';candidate='pending';quality=component.area/max(1,component.bbox[2]*component.bbox[3])
                full_face=False
            elif role=='unknown' and 'partial_neutral_panel_candidate' in component.positive:
                # A thin gray rail is not a complete neutral note face either.
                kind='plate_fragment';candidate='pending';quality=component.area/max(1,component.bbox[2]*component.bbox[3])
                full_face=False
            else:
                continue
            x,y,w,h=component.bbox
            keys=tuple(key for i,key in enumerate(KEYS)
                       if min(x+w,(i+1)*self.geometry.lane_pixels)-max(x,i*self.geometry.lane_pixels)>=4)
            if not keys:
                drop_count+=1
                if trace is not None:
                    drop_reasons.append((component.component_id,'less_than_4_rectified_pixels_in_any_lane'))
                    trace.append({'component_id':component.component_id,'role':role,
                        'connection_group_id':component.connection_group_id,
                        'conversion':'dropped_no_lane_coverage','bbox':component.bbox,'color':component.color,
                        'area':component.area,'reason':'less_than_4_rectified_pixels_in_any_lane'})
                continue
            above=below=0.
            if kind in ('hold_head','hold_tail'):
                group_data=group_masks.get(component.connection_group_id)
                left=max(0,x);right=min(rectified.shape[1],x+w)
                threshold=max(2,.12*w)
                def group_overlap(yy):
                    if group_data is None:return 0
                    gx,gy,gw,gh=group_data[0]
                    local_y=yy-gy
                    local_left=max(left,gx)-gx
                    local_right=min(right,gx+gw)-gx
                    if local_y<0 or local_y>=gh or local_right<=local_left:return 0
                    return np.count_nonzero(group_data[1][local_y,local_left:local_right])
                for step in range(4,85,4):
                    yy=y-step
                    if yy>=0 and group_overlap(yy)>=threshold:above=step
                    yy=y+h+step
                    if yy<rectified.shape[0] and group_overlap(yy)>=threshold:below=step
            evidence=tuple(dict.fromkeys(('v85_early_provider',*component.evidence,*component.positive,
                *component.negative,*component.ambiguity,
                'birth_zone' if self.geometry.top_y<=y<=self.birth_zone_end_y else 'below_birth_zone')))
            observations.append(Detection(tuple(map(int,component.bbox)),component.color,kind,keys,
                min(1.,max(0.,quality)),component.component_id,above,below,
                plane_width=self.geometry.plane_width,
                evidence=evidence,semantic_candidate=candidate,face_quality=float(quality),
                full_face=full_face,connected_ribbon=connected,
                birth_zone=bool(self.geometry.top_y<=y<=self.birth_zone_end_y),
                connection_group_id=component.connection_group_id))
            if trace is not None:
                trace.append({'component_id':component.component_id,'role':role,
                    'connection_group_id':component.connection_group_id,
                    'conversion':'accepted','bbox':component.bbox,'color':component.color,'area':component.area,
                    'kind':kind,'semantic_candidate':candidate,'keys':'|'.join(keys),
                    'full_face':full_face,'connected_ribbon':connected,
                    'birth_zone':bool(self.geometry.top_y<=y<=self.birth_zone_end_y)})
        self.conversion_trace=trace if trace is not None else []
        self.last_profile={**self.segmenter.last_profile,'rectify_ms':rectify_ms,
            'segmentation_ms':segmentation_ms,'detection_adapter_ms':(time.perf_counter()-segment_start)*1000-segmentation_ms,
            'birth_zone_end_y':self.birth_zone_end_y,'birth_zone_source':self.birth_zone_source,
            'component_count':len(result.components),'converted_count':len(observations),
            'dropped_component_count':drop_count}
        if drop_reasons is not None:
            self.last_profile['drop_reasons']=drop_reasons
        self.frame_index+=1
        return observations

    @staticmethod
    def _occluded_neutral_fragment(fragment_bbox, tap_bboxes):
        """Whether a partial neutral fragment is covered by a complete Tap face.

        A tightly bounded in-face fragment is kept as pixel UNKNOWN but cannot
        seed a second track. The older bottom-bevel rule remains separate and
        still requires near-complete horizontal overlap. Full neutral faces and
        fragments outside the colored face are never suppressed here.
        """
        x,y,w,h=fragment_bbox
        fragment_area=max(1,w*h)
        if w<4 or h<2:return False
        for tx,ty,tw,th in tap_bboxes:
            intersection=max(0,min(x+w,tx+tw)-max(x,tx))*max(0,min(y+h,ty+th)-max(y,ty))
            # Only suppress the 12x8 in-panel glyph signature verified in the
            # frame-182/186 identity collision. Smaller neutral fragments are
            # retained as UNKNOWN observations so the adapter does not remove
            # broad temporal evidence from nearby tracks.
            if (w==12 and h==8 and intersection>=.90*fragment_area and
                    fragment_area<=.12*max(1,tw*th) and
                    w<=.35*tw and h<=.50*th):
                return True
            if h>4 or w<8:continue
            horizontal=max(0,min(x+w,tx+tw)-max(x,tx))
            if horizontal < .90*w:continue
            tap_bottom=ty+th
            if y>=ty+.65*th and y>=tap_bottom-4 and y+h<=tap_bottom+1:
                return True
        return False
