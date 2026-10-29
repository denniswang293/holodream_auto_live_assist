"""Geometry document validation/loading and frame normalization transforms."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path

MODELS = ("linear","homography","piecewise")
BANDS = ("spawn","middle","hit")
HUMAN = ("human_click","human_manual")


def geometry_hash(document: dict) -> str:
    # Timestamp/preview changes are not a geometry migration. Evidence and
    # source identity remain in the saved full document separately.
    payload = {k:document[k] for k in ("reference_resolution","lane_count","key_map","model_type","controls")}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()


def _number(value,name):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"Nonfinite {name}")
    return result


def _validate_control_document(document: dict) -> None:
    if document.get("schema_version")!=4 or document.get("model_type") not in MODELS:
        raise ValueError("Expected v4 linear/homography/piecewise geometry")
    if document.get("lane_count")!=6 or document.get("key_map")!=list("SDFJKL"):
        raise ValueError("Geometry requires six keys S,D,F,J,K,L")
    width,height = document["reference_resolution"]
    if int(width)!=width or int(height)!=height or width<=0 or height<=0:
        raise ValueError("Invalid native reference resolution")
    source = document["source"]
    if len(source.get("video_sha256",""))!=64 or _number(source.get("fps",0),"source FPS")<=0 or _number(source.get("frame_count",0),"source frame count")<=0:
        raise ValueError("Geometry must identify the source video, FPS and frame count")
    if document.get("status") not in ("pending_calibration","manual_unverified","validated"):
        raise ValueError("Unknown calibration status")
    def point(p):
        if not isinstance(p,dict):
            raise ValueError("Missing control point")
        x,y = _number(p["x"],"x"),_number(p["y"],"y")
        if not 0<=x<=width-1 or not 0<=y<=height-1:
            raise ValueError("Control point outside original frame")
        if p["frame"] is None:
            # Static coordinates supplied outside the GUI need no invented
            # observation frame. Clicks and independent validation stay framed.
            if (p.get("frame_scope")!="static_video_geometry" or
                    p.get("origin") not in ("human_manual","derived_estimate")):
                raise ValueError("Unknown source frame requires explicit static geometry provenance")
        else:
            frame = _number(p["frame"],"frame")
            if int(frame)!=frame or not 0<=frame<source["frame_count"]:
                raise ValueError("Invalid source frame for control point")
        if type(p.get("confirmed")) is not bool:
            raise ValueError("Control point needs an explicit confirmed flag")
        if p["confirmed"] and (p.get("origin") not in HUMAN or not str(p.get("reviewer","")).strip()):
            raise ValueError("Confirmed controls must be manually observed and identify the reviewer")
    controls = document["controls"]
    rows = controls["lane_rows"]
    if len(rows)<(3 if document["model_type"]=="piecewise" else 2):
        raise ValueError("Insufficient height rows for geometry model")
    ids,ys = set(),[]
    for row in rows:
        if not row.get("id") or row["id"] in ids:
            raise ValueError("Missing/duplicate lane row ID")
        ids.add(row["id"])
        y = _number(row["y"],"row y")
        ys.append(y)
        if row.get("band") not in BANDS or len(row["points"])!=7:
            raise ValueError("Each row needs seven indexed boundaries and a height band")
        for p in row["points"]:
            point(p)
            if abs(p["y"]-y)>1e-6:
                raise ValueError("Row controls must lie on the explicitly selected native y")
        if any(b["x"]-a["x"]<=1e-5 for a,b in zip(row["points"],row["points"][1:])):
            raise ValueError("Crossed, duplicate or reversed lane boundary points")
    if any(b-a<=1e-5 for a,b in zip(ys,ys[1:])):
        raise ValueError("Lane rows must have unique, increasing y values")
    outer = controls["outer_rows"]
    if len(outer)<2 or abs(outer[0]["y"]-ys[0])>1e-6 or abs(outer[-1]["y"]-ys[-1])>1e-6:
        raise ValueError("Outer rails must span exactly the same vertical domain")
    for row in outer:
        for side in ("left","right"):
            point(row[side])
            if abs(row[side]["y"]-row["y"])>1e-6:
                raise ValueError("Outer control is at a different row y")
        if row["left"]["x"]>=row["right"]["x"]:
            raise ValueError("Outer rail ordering is reversed")
    if any(b["y"]<=a["y"] for a,b in zip(outer,outer[1:])):
        raise ValueError("Duplicate/reversed outer rail rows")
    hit = controls["hit_line"]
    if len(hit)!=2:
        raise ValueError("Hit line needs two measured endpoints")
    for p in hit:
        point(p)
    if hit[0]["x"]>=hit[1]["x"]:
        raise ValueError("Hit endpoints must be left to right")


def validate_control_document(document: dict) -> None:
    try:
        _validate_control_document(document)
    except (KeyError,TypeError,OverflowError,IndexError) as error:
        raise ValueError(f"Malformed/missing geometry controls: {error}") from error


def load_calibration(path: Path | str):
    from .geometry import CalibratedGeometry
    document = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    geometry = CalibratedGeometry(document)
    if document["status"]=="validated":
        raise ValueError("This Assist-only build accepts pending/manual geometry; the independent validation workflow was removed")
    return geometry


class FrameTransform:
    """Native ↔ preview with explicit crop and aspect-preserving letterbox."""
    def __init__(self,native_size,viewport_size,crop=None):
        self.native_size,self.viewport_size = tuple(native_size),tuple(viewport_size)
        width,height = self.native_size
        self.crop = tuple(crop if crop is not None else (0,0,width,height))
        x,y,w,h = self.crop
        if not all(math.isfinite(float(v)) for v in (*self.native_size,*self.viewport_size,*self.crop)):
            raise ValueError("Nonfinite frame transform")
        if min(*self.native_size,*self.viewport_size,w,h)<=0 or x<0 or y<0 or x+w>width+1e-8 or y+h>height+1e-8:
            raise ValueError("Crop/viewport outside native frame")
        self.scale = min(viewport_size[0]/w,viewport_size[1]/h)
        self.offset = ((viewport_size[0]-w*self.scale)/2,(viewport_size[1]-h*self.scale)/2)

    def native_to_display(self,x,y):
        if not all(math.isfinite(float(v)) for v in (x,y)):
            raise ValueError("Nonfinite native preview point")
        cx,cy,cw,ch = self.crop
        return (x-cx)*self.scale+self.offset[0],(y-cy)*self.scale+self.offset[1]

    def display_to_native(self,x,y):
        if not all(math.isfinite(float(v)) for v in (x,y)):
            return None
        if not 0<=x<=self.viewport_size[0] or not 0<=y<=self.viewport_size[1]:
            return None
        cx,cy,cw,ch = self.crop
        nx,ny = (x-self.offset[0])/self.scale+cx,(y-self.offset[1])/self.scale+cy
        if not cx<=nx<=cx+cw or not cy<=ny<=cy+ch:
            return None
        return nx,ny

    def as_dict(self):
        return {"native_size":self.native_size,"viewport_size":self.viewport_size,"crop":self.crop,
                "scale":self.scale,"letterbox_offset":self.offset,"stored_points":"native_original_frame"}


