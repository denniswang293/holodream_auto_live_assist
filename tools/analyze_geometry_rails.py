"""Report long projection rails detected independently in temporal-median frames."""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", nargs="+", type=Path)
    args = parser.parse_args()
    for path in args.images:
        image = cv2.imread(str(path))
        if image is None:
            print(path, "UNREADABLE")
            continue
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 40, 125)
        roi = np.zeros_like(edges)
        roi[0:585, :] = edges[0:585, :]
        lines = cv2.HoughLinesP(roi, 1, np.pi / 1800, 140, minLineLength=300, maxLineGap=14)
        candidates = []
        if lines is not None:
            for (x1, y1, x2, y2) in lines[:, 0, :]:
                dy = y2 - y1
                dx = x2 - x1
                if dy == 0 or abs(dx / dy) < .12 or abs(dx / dy) > 1.2:
                    continue
                xs = [x1 + (y-y1)*dx/dy for y in (30, 190, 325, 560)]
                candidates.append((round(np.hypot(dx, dy)), round(dx/dy, 4), [round(x, 1) for x in xs]))
        candidates.sort(reverse=True)
        print("\n", path)
        for length, slope, xs in candidates[:40]:
            print(f"len={length:4d} dx/dy={slope:7.4f} x@30,190,325,560={xs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
