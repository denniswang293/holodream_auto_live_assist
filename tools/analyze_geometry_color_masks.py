"""Compare threshold/opening candidates on a source crop without using Legacy detections."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from src.geometry_video.geometry import VideoGeometry
from src.geometry_video.segmenter import PixelGeometryConverter


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("image", type=Path)
    p.add_argument("--geometry", type=Path, default=Path("config/geometry_video_v1.json"))
    args = p.parse_args()
    image = cv2.imread(str(args.image))
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    field = PixelGeometryConverter(VideoGeometry(args.geometry)).field_mask
    for name, h0, h1, v0 in (("cyan", 82, 110, 155), ("green", 38, 84, 100),
                             ("yellow", 14, 42, 125), ("pink", 140, 178, 125)):
        for saturation in (65, 100, 125, 140, 160):
            mask = cv2.inRange(hsv, np.array([h0,saturation,v0],np.uint8), np.array([h1,255,255],np.uint8))
            mask = cv2.bitwise_and(mask, mask, mask=field)
            for opening in (0, 3, 5, 7):
                current = mask if opening == 0 else cv2.morphologyEx(mask, cv2.MORPH_OPEN,
                    cv2.getStructuringElement(cv2.MORPH_RECT,(opening,opening)))
                count, _, stats, _ = cv2.connectedComponentsWithStats(current, connectivity=8)
                comps = sorted((tuple(map(int,row[:5])) for row in stats[1:] if row[4] >= 150),
                               key=lambda row: row[4], reverse=True)[:5]
                print(name, "s>=", saturation, "open=", opening, "components>=150=", count-1, "top=", comps)
    for name, h0, h1, v0 in (("cyan",82,110,130),("green",38,84,75),("yellow",14,42,100),("pink",140,178,100)):
        broad = cv2.inRange(hsv,np.array([h0,25,v0],np.uint8),np.array([h1,255,255],np.uint8))
        broad = cv2.bitwise_and(broad,broad,mask=field)
        opened = cv2.morphologyEx(broad,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(41,13)))
        count,labels,stats,_=cv2.connectedComponentsWithStats(opened,connectivity=8)
        rows=[]
        for label in range(1,count):
            x,y,w,h,area=map(int,stats[label])
            if 850<x+w and x<1050 and 420<y+h and y<480:
                rows.append((label,x,y,w,h,area))
        print("BROAD_PANEL",name,"intersecting expected Tap region",rows)
        cv2.imwrite(str(args.image.parent/f"{args.image.stem}_{name}_broad_panel_mask.png"),opened)
    edges=cv2.Canny(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY),55,150)
    lines=cv2.HoughLinesP(edges,1,np.pi/360,25,minLineLength=35,maxLineGap=10)
    candidates=[]
    verticals=[]
    if lines is not None:
        for x1,y1,x2,y2 in lines[:,0,:]:
            if 800 <= min(x1,x2) <= 1100 and 405 <= min(y1,y2) <= 485:
                dx,dy=x2-x1,y2-y1
                if abs(dy)<=4 and abs(dx)>=35:
                    candidates.append((int(x1),int(y1),int(x2),int(y2)))
                if abs(dx)<=4 and abs(dy)>=10:
                    verticals.append((int(x1),int(y1),int(x2),int(y2)))
    print("EDGE_HORIZONTAL_LINES_NEAR_TAP",candidates)
    print("EDGE_VERTICAL_LINES_NEAR_TAP",verticals)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
