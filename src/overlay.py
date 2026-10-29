"""Debug rendering for lifecycle, geometry and rejected predictions."""
from __future__ import annotations
import cv2
import numpy as np
from .geometry import Playfield
from .tracker import Track
from .geometry_render import draw_geometry

COLORS = {"tentative": (0, 210, 255), "confirmed": (70, 255, 80),
          "rejected": (70, 70, 255), "lost": (0, 130, 255), "completed": (170, 170, 170)}


def render(frame: np.ndarray, playfield: Playfield, tracks: list[Track], state: str,
           timestamp: float, gate_evidence: dict, key_map: list[str], explicit_candidates: bool = False,
           status_label: str = "ASSIST INPUT OFF", footer_label: str | None = None) -> np.ndarray:
    image = frame.copy()
    sx,sy = image.shape[1]/playfield.reference_resolution[0],image.shape[0]/playfield.reference_resolution[1]
    scale = max(.1,min(image.shape[1]/720,image.shape[0]/404))
    thickness = max(1,round(scale))
    draw_geometry(image,playfield)
    used = []
    lost_count = sum(tr.missed > 0 for tr in tracks)
    for tr in sorted(tracks, key=lambda tr: tr.bbox[1], reverse=True):
        c = tr.candidate
        if tr.missed and tr.status not in ("lost", "completed"):
            continue
        x, y, w, h = c.bbox
        color = COLORS[tr.status]
        if tr.missed > 2:
            continue
        cv2.rectangle(image, (x,y), (x+w,y+h), color, thickness)
        if tr.missed:
            cv2.putText(image,f"#{tr.track_id} lost",(x,max(round(15*sy),y-round(2*sy))),cv2.FONT_HERSHEY_SIMPLEX,.28*scale,color,thickness,cv2.LINE_AA)
            continue
        if c.path_bbox:
            px, py, pw, ph = c.path_bbox
            cv2.rectangle(image, (px,py), (px+pw,py+ph), (80,120,80), thickness)
        hit = f"hit={tr.prediction.hit_time:.3f}" if tr.eta() is not None else tr.reason
        appearance = {"cyan_bar":"cyan","yellow_bar":"yellow","pink_candidate":"pink?", 
                      "green_candidate":"green?","neutral_candidate":"neutral?"}[c.appearance]
        key_text = f"cand:{'/'.join(tr.stable_keys)} input:?" if explicit_candidates else '/'.join(tr.stable_keys)
        label = f"#{tr.track_id} {tr.status} {appearance}/{c.note_type} {key_text} {hit}"
        if c.suspected_overlap:
            label += " OVERLAP"
        # Small dark-backed labels with collision avoidance are legible over flashes.
        font = .32*scale
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font, thickness)
        lx, ly = min(max(0, x), max(0, image.shape[1]-tw-round(2*scale))), max(round(76*sy), y-round(4*sy))
        while any(abs(ly-other_y) < round(11*sy) and lx < other_x+other_w and lx+tw > other_x
                  for other_x, other_y, other_w in used) and ly > round(77*sy):
            ly -= round(12*sy)
        used.append((lx,ly,tw))
        cv2.rectangle(image, (lx,ly-th-round(2*sy)), (lx+tw+round(2*scale),ly+round(2*sy)), (10,10,10), -1)
        cv2.putText(image, label, (lx,ly), cv2.FONT_HERSHEY_SIMPLEX, font, color, thickness, cv2.LINE_AA)
    cv2.rectangle(image, (0,0), (image.shape[1],round(12*sy)), (10,10,10), -1)
    evidence = ' '.join(f'{k}:{v:.2f}' for k,v in gate_evidence.items())
    cv2.putText(image, f"{timestamp:.3f}s {state} | {evidence} | lost:{lost_count} | {status_label}", (4,9),
                cv2.FONT_HERSHEY_SIMPLEX, 0.31, (255,255,255), 1, cv2.LINE_AA)
    cv2.rectangle(image, (0,image.shape[0]-round(15*sy)), (image.shape[1],image.shape[0]), (10,10,10), -1)
    footer = ("cand=possible lanes; input=UNRESOLVED | Yellow:tent Green:conf Red:rej Orange:lost Gray:done"
              if explicit_candidates else "Yellow:tentative Green:confirmed Red:rejected Orange:lost Gray:completed | score is heuristic")
    cv2.putText(image, footer_label if footer_label is not None else footer,
                (round(3*scale),image.shape[0]-round(4*sy)), cv2.FONT_HERSHEY_SIMPLEX, 0.31*scale, (255,255,255), thickness, cv2.LINE_AA)
    return image
