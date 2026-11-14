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
    def __init__(self, geometry, *, birth_zone_end_y: float | None = None):
        self.geometry = geometry
        self.segmenter = LanePixelSegmenter()
        self.birth_zone_end_y = (float(birth_zone_end_y) if birth_zone_end_y is not None
                                 else geometry.top_y + .5*(geometry.hit_y-geometry.top_y))
        self.birth_zone_source = 'multi_run_candidate_audit' if birth_zone_end_y is not None else 'provisional_geometry_midpoint'
        self.last_result = None
        self.last_rect = None
        self.last_labels = None
        self.last_path = None
        self.last_profile = {}
        self.conversion_trace = []
        self.frame_index = 0

    def detect(self, normalized_bgr):
        started = time.perf_counter()
        rectified = self.geometry.rectify(normalized_bgr)
        rectify_ms = (time.perf_counter()-started)*1000
        segment_start=time.perf_counter()
        result=self.segmenter.segment(rectified,self.geometry,frame_index=self.frame_index)
        segmentation_ms=(time.perf_counter()-segment_start)*1000
        self.last_result=result;self.last_rect=rectified
        self.last_path=np.zeros(rectified.shape[:2],np.uint8)
        for name in ('hold_head','hold_body','hold_tail'):
            self.last_path|=result.masks[name]
        _,self.last_labels=cv2.connectedComponents((self.last_path>0).astype(np.uint8),8)
        path_binary=self.last_path>0
        observations=[];drop_reasons=[];trace=[]
        for component in result.components:
            role=component.role
            if role=='hold_body' or role in ('effect_or_artifact',):
                trace.append({'component_id':component.component_id,'role':role,
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
            else:
                continue
            x,y,w,h=component.bbox
            keys=tuple(key for i,key in enumerate(KEYS)
                       if min(x+w,(i+1)*self.geometry.lane_pixels)-max(x,i*self.geometry.lane_pixels)>=4)
            if not keys:
                drop_reasons.append((component.component_id,'less_than_4_rectified_pixels_in_any_lane'))
                trace.append({'component_id':component.component_id,'role':role,
                    'conversion':'dropped_no_lane_coverage','bbox':component.bbox,'color':component.color,
                    'area':component.area,'reason':'less_than_4_rectified_pixels_in_any_lane'});continue
            above=below=0.
            if kind in ('hold_head','hold_tail'):
                for step in range(4,85,4):
                    yy=y-step
                    if yy>=0 and np.count_nonzero(path_binary[yy,max(0,x):min(path_binary.shape[1],x+w)])>=max(2,.12*w):above=step
                    yy=y+h+step
                    if yy<path_binary.shape[0] and np.count_nonzero(path_binary[yy,max(0,x):min(path_binary.shape[1],x+w)])>=max(2,.12*w):below=step
            evidence=tuple(dict.fromkeys(('v85_early_provider',*component.evidence,*component.positive,
                'birth_zone' if self.geometry.top_y<=y<=self.birth_zone_end_y else 'below_birth_zone')))
            observations.append(Detection(tuple(map(int,component.bbox)),component.color,kind,keys,
                min(1.,max(0.,quality)),component.component_id,above,below,
                plane_width=self.geometry.plane_width,
                evidence=evidence,semantic_candidate=candidate,face_quality=float(quality),
                full_face=full_face,connected_ribbon=connected,
                birth_zone=bool(self.geometry.top_y<=y<=self.birth_zone_end_y)))
            trace.append({'component_id':component.component_id,'role':role,
                'conversion':'accepted','bbox':component.bbox,'color':component.color,'area':component.area,
                'kind':kind,'semantic_candidate':candidate,'keys':'|'.join(keys),
                'full_face':full_face,'connected_ribbon':connected,
                'birth_zone':bool(self.geometry.top_y<=y<=self.birth_zone_end_y)})
        self.conversion_trace=trace
        self.last_profile={**self.segmenter.last_profile,'rectify_ms':rectify_ms,
            'segmentation_ms':segmentation_ms,'detection_adapter_ms':(time.perf_counter()-segment_start)*1000-segmentation_ms,
            'birth_zone_end_y':self.birth_zone_end_y,'birth_zone_source':self.birth_zone_source,
            'component_count':len(result.components),'converted_count':len(observations),
            'dropped_component_count':len(drop_reasons),'drop_reasons':drop_reasons}
        self.frame_index+=1
        return observations
