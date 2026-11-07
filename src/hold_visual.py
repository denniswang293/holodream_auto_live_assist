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


def assign_hold_runs(runs, positions, max_gap=.12):
    """Allocate observed color to existing Holds together, independent of order.

    Overlapping row samples describe one observation. When a continuous band
    contains several known centers, partition its visible width between them;
    otherwise it can support only one Hold, prioritizing a contained center.
    This never creates a note or chooses a keyboard key.
    """
    bands = []
    for left, right in sorted(set(runs)):
        if right <= left:
            continue
        if bands and left <= bands[-1][1]:
            bands[-1] = (bands[-1][0], max(right, bands[-1][1]))
        else:
            bands.append((left, right))
    offers = []
    for index, (left, right) in enumerate(bands):
        contained = sorted((u, uid) for uid, u in positions.items() if left <= u <= right)
        if contained:
            cuts = [left] + [(a[0]+b[0])/2 for a, b in zip(contained, contained[1:])] + [right]
            for part, (u, uid) in enumerate(contained):
                span = cuts[part], cuts[part+1]
                if span[1] > span[0]:
                    offers.append((0, abs((left+right)/2-u), u, uid, (index, part), span))
        else:
            for uid, u in positions.items():
                gap = max(left-u, u-right, 0.)
                if gap <= max_gap:
                    offers.append((1, gap, u, uid, (index, 0), (left, right)))
    assigned, occupied = {}, set()
    for _, _, _, uid, slot, span in sorted(offers):
        if uid not in assigned and slot not in occupied:
            assigned[uid] = span
            occupied.add(slot)
    return assigned


def connected_hold_runs(lower, middle, upper, minimum_width):
    """Fresh near-line color must connect to a wider ribbon on two rows.

    This admits an occluded ribbon edge, not an isolated narrow sparkle.
    All spans come from the same frame and color.
    """
    def linked(a, b):
        return min(a[1],b[1])-max(a[0],b[0]) >= .5*min(a[1]-a[0],b[1]-b[0])
    return [a for a in lower if any(linked(a,b) and any(
        linked(b,c) and max(a[1]-a[0],b[1]-b[0],c[1]-c[0]) >= minimum_width
        for c in upper) for b in middle)]


def hold_probe_is_bright(frame, playfield, y, u):
    """Require visible hit-light occlusion, rather than a dark gap in a tail."""
    h, w = frame.shape[:2]
    rw, rh = playfield.reference_resolution
    left, right = playfield.bounds(y)
    x = round((left+u*(right-left))*w/rw)
    py = round(y*h/rh)
    radius = max(2, round((right-left)/playfield.lane_count*.125*w/rw))
    ry = max(1, round(2*h/rh))
    patch = frame[max(0,py-ry):min(h,py+ry+1),max(0,x-radius):min(w,x+radius+1)]
    return bool(patch.size and np.mean(np.max(patch,axis=2) >= 230) >= .5)


def continuous_hold_body(rows, start, minimum_width):
    """Require an unbroken 28px ribbon above an occluded near-line edge.

    Several broad rows and a broad upper endpoint distinguish a body from
    the short color cloud left by a departing cap. No missing row is bridged.
    """
    if len(rows) < 8:
        return False
    states = [(start, int(start[1]-start[0] >= minimum_width))]
    for row in rows[1:]:
        following = []
        for span in row:
            counts = [count for previous,count in states
                      if min(span[1],previous[1])-max(span[0],previous[0]) >=
                      .25*min(span[1]-span[0],previous[1]-previous[0])]
            if counts:
                following.append((span,max(counts)+int(span[1]-span[0] >= minimum_width)))
        states = following
        if not states:
            return False
    return any(count >= 3 and span[1]-span[0] >= minimum_width for span,count in states)


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
