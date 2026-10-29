"""Geometry renderer shared by live Assist overlays and diagnostics."""
from __future__ import annotations
import cv2
import numpy as np


def draw_geometry(image,geometry,options=None):
    options = {"outer":True,"lanes":True,"centers":False,"spawn":False,"hit":True,
               "controls":False,"predictions":False,"text":False,"axes":False,"status":False,**(options or {})}
    sx=image.shape[1]/geometry.reference_resolution[0]
    sy=image.shape[0]/geometry.reference_resolution[1]
    scale=max(.1,min(image.shape[1]/720,image.shape[0]/404))
    thickness=max(1,round(scale))
    def polyline(points,color,line_thickness=1,closed=False):
        if points:
            cv2.polylines(image,[np.rint(points).astype(np.int32)],closed,color,max(1,round(line_thickness*scale)),cv2.LINE_AA)
    if options["outer"]:
        polyline(geometry.playfield_polygon(),(0,170,255),1,True)
    if options["lanes"]:
        for line in geometry.lane_polylines():
            polyline(line,(60,180,180))
    if options["centers"]:
        for line in geometry.lane_polylines(centers=True):
            polyline(line,(210,140,70))
    if options["spawn"]:
        y0,y1 = geometry.top_y,geometry.top_y+.2*(geometry.hit_y-geometry.top_y)
        a,b = geometry.lane_bounds_at_y(y0),geometry.lane_bounds_at_y(y1)
        polyline([(a[0],y0),(a[-1],y0),(b[-1],y1),(b[0],y1)],(220,170,255),1,True)
    if options["hit"]:
        polyline(geometry.hit_line_points(),(70,70,255),1)
    if options["text"]:
        y = max(geometry.top_y,geometry.hit_y-8)
        centers = geometry.lane_centers_at_y(y)
        for key,x in zip("SDFJKL",centers):
            cv2.putText(image,key,(round(x)-round(3*scale),round(y)),cv2.FONT_HERSHEY_SIMPLEX,.35*scale,(255,255,255),thickness,cv2.LINE_AA)
        for name,ratio in (("spawn",.10),("middle",.5),("hit",.95)):
            y = geometry.top_y+ratio*(geometry.hit_y-geometry.top_y)
            edges = geometry.lane_bounds_at_y(y)
            cv2.putText(image,f"{name} y={y:.1f}",(round(3*scale),round(y)),cv2.FONT_HERSHEY_SIMPLEX,.3*scale,(255,255,255),thickness,cv2.LINE_AA)
            for i,x in enumerate(edges):
                cv2.circle(image,(round(x),round(y)),max(1,round(2*scale)),(50,200,255),-1)
                cv2.putText(image,str(i),(round(x)-round(2*scale),round(y)+round(9*sy)),cv2.FONT_HERSHEY_SIMPLEX,.25*scale,(50,220,255),thickness,cv2.LINE_AA)
            for key,x in zip("SDFJKL",geometry.lane_centers_at_y(y)):
                cv2.putText(image,key,(round(x)-round(2*scale),round(y)-round(4*sy)),cv2.FONT_HERSHEY_SIMPLEX,.25*scale,(255,255,255),thickness,cv2.LINE_AA)
    document = getattr(geometry,"document",None)
    if document and options["controls"]:
        points = [p for r in document["controls"]["lane_rows"] for p in r["points"]]
        points += [r[s] for r in document["controls"]["outer_rows"] for s in ("left","right")]
        points += document["controls"]["hit_line"]
        for p in points:
            color = (80,255,80) if p["confirmed"] else (150,150,150)
            cv2.drawMarker(image,(round(p["x"]),round(p["y"])),color,cv2.MARKER_CROSS,7,1)
    if options["predictions"]:
        for y in np.linspace(geometry.top_y,geometry.hit_y,9):
            for x in geometry.lane_bounds_at_y(float(y)):
                cv2.circle(image,(round(x),round(y)),max(1,round(2*scale)),(255,200,80),thickness)
    if options["axes"]:
        height,width = image.shape[:2]
        for x in range(0,width,max(1,round(80*sx))):
            cv2.line(image,(x,round(15*sy)),(x,round(22*sy)),(255,255,255),thickness)
            cv2.putText(image,str(x),(x+round(2*sx),round(31*sy)),cv2.FONT_HERSHEY_SIMPLEX,.28*scale,(255,255,255),thickness)
        for y in range(round(40*sy),height,max(1,round(40*sy))):
            cv2.line(image,(0,y),(round(6*sx),y),(255,255,255),thickness)
            cv2.putText(image,str(y),(round(7*sx),y-round(2*sy)),cv2.FONT_HERSHEY_SIMPLEX,.28*scale,(255,255,255),thickness)
    if options["status"]:
        cv2.rectangle(image,(0,0),(image.shape[1],round(14*sy)),(0,0,0),-1)
        text = f"{geometry.model_type} {geometry.status} | native pixels | measured + / predicted o | OFFLINE"
        cv2.putText(image,text,(round(3*scale),round(10*sy)),cv2.FONT_HERSHEY_SIMPLEX,.31*scale,(255,255,255),thickness,cv2.LINE_AA)
    return image
