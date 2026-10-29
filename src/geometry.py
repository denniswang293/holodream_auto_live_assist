"""Shared geometry for live capture, six-key projection, and drawing.

Legacy bounds/lane retain their historical clamp behavior. New pipeline paths
use safe mapping methods: outside points return None rather than a valid key.
"""
from __future__ import annotations
from dataclasses import dataclass
from copy import deepcopy
from functools import lru_cache
import math
import cv2
import numpy as np

EPS = 1e-8


class GeometryAPI:
    lane_count = 6
    model_type = "legacy_linear"
    status = "unverified_legacy"

    def _valid_y(self,y):
        # Only numerical round-off (1e-8 native pixel), never an off-screen
        # observation, is snapped to a closed projection boundary.
        if not math.isfinite(y) or y<self.top_y-EPS or y>self.hit_y+EPS:
            return None
        return min(self.hit_y,max(self.top_y,y))

    def lane_bounds_at_y(self,y: float) -> tuple[float,...] | None:
        y=self._valid_y(y)
        if y is None:
            return None
        left,right = self.bounds(y)
        return tuple(left+(right-left)*i/self.lane_count for i in range(self.lane_count+1))

    def lane_centers_at_y(self,y: float) -> tuple[float,...] | None:
        edges = self.lane_bounds_at_y(y)
        return tuple((a+b)/2 for a,b in zip(edges,edges[1:])) if edges is not None else None

    def outer_bounds_at_y(self,y: float) -> tuple[float,float] | None:
        edges = self.lane_bounds_at_y(y)
        return (edges[0],edges[-1]) if edges is not None else None

    def is_inside_playfield(self,x: float,y: float) -> bool:
        if not all(math.isfinite(v) for v in (x,y)):
            return False
        outer = self.outer_bounds_at_y(y)
        return outer is not None and outer[0]-EPS <= x <= outer[1]+EPS

    def screen_to_uv(self,x: float,y: float) -> tuple[float,float] | None:
        if not self.is_inside_playfield(x,y):
            return None
        edges = self.lane_bounds_at_y(y)
        if edges is None or x<edges[0]-EPS or x>edges[-1]+EPS:
            return None
        u = float(np.interp(x,edges,np.linspace(0,1,self.lane_count+1)))
        return u,min(1.,max(0.,(y-self.top_y)/(self.hit_y-self.top_y)))

    def uv_to_screen(self,u: float,v: float) -> tuple[float,float]:
        if not all(math.isfinite(z) and 0<=z<=1 for z in (u,v)):
            raise ValueError("u/v must be finite and within 0..1")
        y = self.top_y+v*(self.hit_y-self.top_y)
        edges = self.lane_bounds_at_y(y)
        return float(np.interp(u,np.linspace(0,1,self.lane_count+1),edges)),y

    def safe_lane(self,x: float,y: float) -> int | None:
        uv = self.screen_to_uv(x,y)
        return min(self.lane_count-1,max(0,math.floor(uv[0]*self.lane_count))) if uv else None

    def safe_bbox_interval(self,x_min: float,x_max: float,y: float) -> tuple[float,float] | None:
        if not all(math.isfinite(v) for v in (x_min,x_max,y)) or x_max<=x_min:
            return None
        left,right = self.screen_to_uv(x_min,y),self.screen_to_uv(x_max,y)
        return (left[0],right[0]) if left is not None and right is not None else None

    def safe_candidate_lanes(self,x_min: float,x_max: float,y: float,min_overlap_fraction=0.0) -> list[int]:
        if self.safe_bbox_interval(x_min,x_max,y) is None:
            return []
        return self._overlapping_lanes(x_min,x_max,y,min_overlap_fraction)

    def _overlapping_lanes(self,x_min: float,x_max: float,y: float,fraction: float) -> list[int]:
        edges = self.lane_bounds_at_y(y)
        if edges is None:
            return []
        if not 0<=fraction<=1:
            raise ValueError("Lane overlap fraction must be within 0..1")
        return [i for i,(a,b) in enumerate(zip(edges,edges[1:]))
                if min(x_max,b)>max(x_min,a) and (min(x_max,b)-max(x_min,a))/(b-a)>=fraction]

    def row_lane_width(self,y: float) -> float | None:
        edges = self.lane_bounds_at_y(y)
        return float(np.median(np.diff(edges))) if edges is not None else None

    def sample_ys(self) -> list[float]:
        return [self.top_y,self.hit_y]

    def lane_polylines(self,centers=False) -> list[list[tuple[float,float]]]:
        lines = [[] for _ in range(self.lane_count if centers else self.lane_count+1)]
        for y in self.sample_ys():
            xs = self.lane_centers_at_y(y) if centers else self.lane_bounds_at_y(y)
            for line,x in zip(lines,xs):
                line.append((float(x),float(y)))
        return lines

    def playfield_polygon(self) -> list[tuple[float,float]]:
        ys = self.sample_ys()
        return [(self.outer_bounds_at_y(y)[0],y) for y in ys]+[(self.outer_bounds_at_y(y)[1],y) for y in reversed(ys)]

    def hit_line_points(self) -> list[tuple[float,float]]:
        left,right = self.outer_bounds_at_y(self.hit_y)
        return [(left,self.hit_y),(right,self.hit_y)]


@dataclass(frozen=True)
class Playfield(GeometryAPI):
    top_y: float
    top_left_x: float
    top_right_x: float
    hit_y: float
    bottom_left_x: float
    bottom_right_x: float
    reference_resolution: tuple[int,int] = (720,404)

    @classmethod
    def from_config(cls,data: dict,reference_resolution=(720,404)) -> "Playfield":
        names = ("top_y","top_left_x","top_right_x","hit_y","bottom_left_x","bottom_right_x")
        values = {k:float(data[k]) for k in names}
        if not all(math.isfinite(v) for v in values.values()) or values["top_y"]>=values["hit_y"]:
            raise ValueError("Invalid legacy playfield height/coordinates")
        if values["top_left_x"]>=values["top_right_x"] or values["bottom_left_x"]>=values["bottom_right_x"]:
            raise ValueError("Invalid legacy left/right ordering")
        return cls(**values,reference_resolution=tuple(reference_resolution))

    def bounds(self,y: float) -> tuple[float,float]:
        y = min(max(float(y),self.top_y),self.hit_y)
        alpha = (y-self.top_y)/(self.hit_y-self.top_y)
        return (self.top_left_x+(self.bottom_left_x-self.top_left_x)*alpha,
                self.top_right_x+(self.bottom_right_x-self.top_right_x)*alpha)

    def normalized_x(self,x: float,y: float) -> float:
        left,right = self.bounds(y)
        return (float(x)-left)/(right-left)

    def lane(self,x: float,y: float,lanes=6) -> int:
        return min(lanes-1,max(0,math.floor(self.normalized_x(x,y)*lanes)))

    def candidate_lanes(self,x_min: float,x_max: float,y: float,lanes=6,min_overlap_fraction=0.0) -> list[int]:
        if lanes!=self.lane_count:
            raise ValueError("This project maps exactly six keys")
        return self._overlapping_lanes(x_min,x_max,y,min_overlap_fraction)


class CalibratedGeometry(GeometryAPI):
    """A calibration snapshot; construct a new instance after editing controls.

    Cache exact query heights, without rounding or changing model semantics.
    Each instance owns bounded caches, shared by detection and rendering.
    """
    def __init__(self,document: dict, *, cache_enabled: bool = True):
        from .calibration import validate_control_document
        validate_control_document(document)
        self.document = deepcopy(document)
        document = self.document
        self.model_type,self.status = document["model_type"],document["status"]
        self.reference_resolution = tuple(document["reference_resolution"])
        self.rows = sorted(document["controls"]["lane_rows"],key=lambda r:r["y"])
        self.ys = np.array([r["y"] for r in self.rows],dtype=float)
        self.xs = np.array([[p["x"] for p in row["points"]] for row in self.rows],dtype=float)
        self.outer_rows = sorted(document["controls"]["outer_rows"],key=lambda r:r["y"])
        self.top_y,self.hit_y = float(self.ys[0]),float(self.ys[-1])
        self.top_left_x,self.top_right_x = self.xs[0,0],self.xs[0,-1]
        self.bottom_left_x,self.bottom_right_x = self.xs[-1,0],self.xs[-1,-1]
        self.homography = self.inverse_homography = None
        self.fit_diagnostics = {}
        if self.model_type=="homography":
            rw,rh = self.reference_resolution
            source = np.array([[self.xs[0,0]/rw,self.top_y/rh],[self.xs[0,-1]/rw,self.top_y/rh],
                               [self.xs[-1,-1]/rw,self.hit_y/rh],[self.xs[-1,0]/rw,self.hit_y/rh]],dtype=float)
            target = np.array([[0,0],[1,0],[1,1],[0,1]],dtype=float)
            equations = []
            for (x,y),(u,v) in zip(source,target):
                equations += [[-x,-y,-1,0,0,0,u*x,u*y,u],[0,0,0,-x,-y,-1,v*x,v*y,v]]
            _,singular,vectors = np.linalg.svd(np.asarray(equations))
            if singular[-1]<1e-12:
                raise ValueError("Degenerate four-point homography")
            matrix = vectors[-1].reshape(3,3)
            matrix = matrix/matrix[2,2]
            condition = float(np.linalg.cond(matrix))
            if not np.all(np.isfinite(matrix)) or abs(np.linalg.det(matrix))<1e-12 or condition>1e6:
                raise ValueError("Degenerate/ill-conditioned homography")
            self.homography,self.inverse_homography = matrix,np.linalg.inv(matrix)
            restored = cv2.perspectiveTransform(target[None].astype(float),self.inverse_homography)[0]
            error = np.linalg.norm((restored-source)*[rw,rh],axis=1)
            self.fit_diagnostics = {"normalized_matrix_condition":condition,"corner_reprojection_max_px":float(np.max(error)),
                                    "maximum_normalized_condition":1e6,
                                    "corner_error_is_training_fit_not_validation":True,
                                    "screen_normalized_to_uv":matrix.tolist(),"uv_to_screen_normalized":self.inverse_homography.tolist()}
        # Union knots are sufficient for linear/piecewise non-crossing checks;
        # dense samples additionally check the projective denominator/ordering.
        for y in sorted(set(self.sample_ys()+np.linspace(self.top_y,self.hit_y,129).tolist())):
            edges = self.lane_bounds_at_y(y)
            outer = self.outer_bounds_at_y(y)
            if edges is None or not np.all(np.isfinite(edges)) or np.min(np.diff(edges))<=1e-5:
                raise ValueError("Crossing/degenerate lane boundaries")
            if edges[0]<outer[0]-1e-4 or edges[-1]>outer[1]+1e-4:
                raise ValueError("Projected key boundaries extend outside the physical outer rails")
        # Install only after model validation. No class/global cache can retain
        # an old calibration when the GUI rebuilds its geometry snapshot.
        self._lookup_caches = {}
        if cache_enabled:
            for name in ("lane_bounds_at_y", "outer_bounds_at_y", "row_lane_width"):
                lookup = lru_cache(maxsize=2048)(getattr(self,name))
                self._lookup_caches[name] = lookup
                setattr(self,name,lookup)

    def cache_info(self) -> dict:
        return {"enabled":bool(self._lookup_caches), "strategy":"exact_y_bounded_lru_v1",
                "lookups":{name:lookup.cache_info()._asdict()
                           for name,lookup in self._lookup_caches.items()}}

    def sample_ys(self) -> list[float]:
        return sorted(set(self.ys.tolist()+[float(r["y"]) for r in self.outer_rows]))

    def lane_bounds_at_y(self,y: float) -> tuple[float,...] | None:
        y=self._valid_y(y)
        if y is None:
            return None
        if self.model_type=="homography":
            h = self.homography
            yn = y/self.reference_resolution[1]
            values = []
            for u in np.linspace(0,1,7):
                denominator = u*h[2,0]-h[0,0]
                if abs(denominator)<1e-12:
                    return None
                values.append(float((h[0,1]*yn+h[0,2]-u*(h[2,1]*yn+h[2,2]))/denominator*self.reference_resolution[0]))
            return tuple(values)
        indices = [0,-1] if self.model_type=="linear" else list(range(len(self.ys)))
        return tuple(float(np.interp(y,self.ys[indices],self.xs[indices,i])) for i in range(7))

    def bounds(self,y: float) -> tuple[float,float]:
        edges = self.lane_bounds_at_y(y)
        if edges is None:
            raise ValueError("out_of_playfield_height")
        return edges[0],edges[-1]

    def outer_bounds_at_y(self,y: float) -> tuple[float,float] | None:
        y=self._valid_y(y)
        if y is None:
            return None
        ys = [r["y"] for r in self.outer_rows]
        return tuple(float(np.interp(y,ys,[r[side]["x"] for r in self.outer_rows])) for side in ("left","right"))

    def normalized_x(self,x: float,y: float) -> float:
        uv = self.screen_to_uv(x,y)
        if uv is None:
            raise ValueError("out_of_playfield_point")
        return uv[0]

    def lane(self,x: float,y: float,lanes=6) -> int | None:
        return self.safe_lane(x,y)

    def candidate_lanes(self,x_min: float,x_max: float,y: float,lanes=6,min_overlap_fraction=0.0) -> list[int]:
        if lanes!=6:
            raise ValueError("Expected six lanes")
        return self.safe_candidate_lanes(x_min,x_max,y,min_overlap_fraction)

    def screen_to_uv(self,x: float,y: float) -> tuple[float,float] | None:
        normal = super().screen_to_uv(x,y)
        if normal is None or self.model_type!="homography":
            return normal
        vec = self.homography@np.array([x/self.reference_resolution[0],y/self.reference_resolution[1],1.])
        if abs(vec[2])<1e-12:
            return None
        u,v = vec[:2]/vec[2]
        return (min(1.,max(0.,float(u))),min(1.,max(0.,float(v)))) if -EPS<=u<=1+EPS and -EPS<=v<=1+EPS else None

    def uv_to_screen(self,u: float,v: float) -> tuple[float,float]:
        if self.model_type!="homography":
            return super().uv_to_screen(u,v)
        if not all(math.isfinite(z) and 0<=z<=1 for z in (u,v)):
            raise ValueError("Invalid u/v")
        vec = self.inverse_homography@np.array([u,v,1.])
        if abs(vec[2])<1e-12:
            raise ValueError("Invalid projective denominator")
        x,y = vec[:2]/vec[2]*np.array(self.reference_resolution)
        return float(x),float(y)

    def hit_line_points(self) -> list[tuple[float,float]]:
        return [(float(p["x"]),float(p["y"])) for p in self.document["controls"]["hit_line"]]


def load_geometry(config: dict,geometry_path=None,require_confirmed=False):
    if geometry_path is None:
        return Playfield.from_config(config["playfield"],config["reference_resolution"])
    from .calibration import load_calibration
    geometry = load_calibration(geometry_path)
    if require_confirmed and geometry.status!="validated":
        raise ValueError("Geometry is PENDING/UNVERIFIED: confirm independent spawn/middle/hit points in calibrate_geometry before v4 analysis")
    return geometry
