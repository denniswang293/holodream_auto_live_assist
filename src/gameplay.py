"""HUD-presence gate with conservative startup/resume hysteresis."""
from __future__ import annotations
import cv2
import numpy as np


class GameplayGate:
    def __init__(self, cfg: dict | None = None, reference_resolution: tuple[int, int] = (720, 404)):
        self.cfg = cfg or {}
        self.reference_resolution = reference_resolution
        self.streak = 0
        self.state = "UNCERTAIN"
        self.evidence: dict[str, float] = {}

    def update(self, frame: np.ndarray) -> str:
        h, w = frame.shape[:2]
        rw, rh = self.reference_resolution
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        cyan = cv2.inRange(hsv, np.array(self.cfg.get("hsv_lower", [78,65,170])),
                           np.array(self.cfg.get("hsv_upper", [104,255,255])))
        regions = self.cfg.get("hud_regions", {
            "score": [80, 10, 280, 38], "life": [550, 10, 655, 40], "pause": [675, 10, 710, 50]})
        self.evidence = {}
        for name, (x0, y0, x1, y1) in regions.items():
            patch = cyan[round(y0*h/rh):round(y1*h/rh), round(x0*w/rw):round(x1*w/rw)]
            self.evidence[name] = float(np.mean(patch > 0)) if patch.size else 0.0
        votes = sum(value >= self.cfg.get("min_cyan_fraction", 0.15) for value in self.evidence.values())
        score_present = self.evidence.get("score", 0) >= self.cfg.get("min_cyan_fraction", 0.15)
        if score_present and votes >= 2:
            self.streak += 1
            self.state = "PLAYING" if self.streak >= self.cfg.get("confirm_frames", 3) else "UNCERTAIN"
        else:
            self.streak = 0
            self.state = "NOT_PLAYING" if votes == 0 or not score_present else "UNCERTAIN"
        return self.state
