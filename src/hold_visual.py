"""Color-specific Hold path evidence in calibrated lane coordinates."""
from __future__ import annotations

import cv2
import numpy as np


PATH_RANGES = {
    'green_candidate': ((38,65,100),(83,255,255)),
    # The translucent yellow body shifts toward yellow-green over the track.
    # The bright yellow head keeps the detector's narrower appearance range.
    'yellow_bar': ((18,65,100),(42,255,255)),
}


def path_mask(hsv, appearance):
    low,high = PATH_RANGES[appearance]
    return cv2.inRange(hsv,np.array(low),np.array(high))


def path_runs(frame, playfield, y, appearance, mask=None):
    """Return intervals of this Hold's color near a horizontal judgment row."""
    if appearance not in PATH_RANGES:
        raise ValueError('Hold path color must be green_candidate or yellow_bar')
    h, w = frame.shape[:2]
    rw, rh = playfield.reference_resolution
    py = round(y*h/rh)
    scale_x, scale_y = (w/rw)*(rw/720), (h/rh)*(rh/404)
    radius = max(1,round(2*scale_y))
    y0, y1 = max(0, py-radius), min(h, py+radius+1)
    minimum_rows = max(1,round(3*scale_y))
    if y1-y0 < minimum_rows:
        return []
    left, right = playfield.bounds(y)
    x0, x1 = max(0, round(left*w/rw)), min(w, round(right*w/rw))
    if x1 <= x0:
        return []
    if mask is None:
        hsv = cv2.cvtColor(frame[y0:y1,x0:x1],cv2.COLOR_BGR2HSV)
        colored = path_mask(hsv,appearance)>0
    else:
        colored = mask[y0:y1,x0:x1]>0
    columns = np.count_nonzero(colored,axis=0)>=minimum_rows
    indices = np.flatnonzero(np.diff(np.r_[False,columns,False].astype(np.int8)))
    minimum = max(round(3*scale_x),round(playfield.row_lane_width(y)*w/rw*.08))
    scale = right-left
    return [(((x0+a)*rw/w-left)/scale,((x0+b)*rw/w-left)/scale)
            for a,b in zip(indices[::2],indices[1::2]) if b-a>=minimum]


def nearest_run(runs, expected_u, max_gap=.12):
    if not runs:
        return None
    def distance(run):
        return max(run[0]-expected_u,expected_u-run[1],0.)
    run = min(runs,key=distance)
    return run if distance(run)<=max_gap else None


def path_depth(frame, playfield, head_y, head_u, appearance, max_depth=80, mask=None):
    """Measure a continuous band of one color extending upward from a head."""
    u, depth, misses = head_u, 0, 0
    top = playfield.top_y+5
    step = max(1,round(4*playfield.reference_resolution[1]/404))
    start = max(1,round(12*playfield.reference_resolution[1]/404))
    end = round(max_depth*playfield.reference_resolution[1]/404)
    for offset in range(start,end+1,step):
        y = head_y-offset
        if y<=top:
            break
        run = nearest_run(path_runs(frame,playfield,y,appearance,mask),u,.08)
        if run is None:
            misses += 1
            if misses>=2:break
            continue
        u = min(max(u,run[0]),run[1])
        depth = offset
        misses = 0
    return depth


def green_runs(frame, playfield, y, mask=None):
    return path_runs(frame,playfield,y,'green_candidate',mask)


def green_path_depth(frame, playfield, head_y, head_u, max_depth=80, mask=None):
    return path_depth(frame,playfield,head_y,head_u,'green_candidate',max_depth,mask)
