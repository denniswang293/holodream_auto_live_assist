"""Independent, auditable native-frame projection geometry."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class Rail:
    slope: float | None = None
    intercept: float | None = None
    pixel_anchors: tuple[tuple[float, float], ...] = ()

    def x(self, y: float) -> float:
        if not self.pixel_anchors:
            if self.slope is None or self.intercept is None:
                raise ValueError("Rail needs linear parameters or pixel anchors")
            return self.intercept + self.slope * y
        anchors = self.pixel_anchors
        ys = [point[0] for point in anchors]
        xs = [point[1] for point in anchors]
        if y < ys[0]:
            i = 0
        elif y > ys[-1]:
            i = len(ys)-2
        else:
            return float(np.interp(y, ys, xs))
        return xs[i] + (y-ys[i]) * (xs[i+1]-xs[i]) / (ys[i+1]-ys[i])


class VideoGeometry:
    def __init__(self, source):
        if isinstance(source, (str, Path)):
            source = json.loads(Path(source).read_text(encoding="utf-8"))
        self.document = source
        self.width, self.height = map(int, source["source_resolution"])
        self.rails = []
        for row in source["rails_left_to_right"]:
            if "pixel_anchors" in row:
                anchors = tuple((float(point["y"]), float(point["x"]))
                                for point in row["pixel_anchors"])
                if len(anchors) < 2 or any(a[0] >= b[0] for a, b in zip(anchors, anchors[1:])):
                    raise ValueError("Rail pixel anchors must have at least two strictly ordered y rows")
                self.rails.append(Rail(pixel_anchors=anchors))
            else:
                self.rails.append(Rail(float(row["slope_dx_per_dy"]), float(row["x_intercept_at_y0"])))
        self.judgment_y = float(source["judgment_line"]["y"])
        if len(self.rails) != 7:
            raise ValueError("Six lanes require exactly seven ordered boundaries")
        self.field_bottom_y = min(self.height-1, self.judgment_y+35)
        for y in (0, self.judgment_y, self.field_bottom_y):
            xs = [rail.x(y) for rail in self.rails]
            inside_frame = y != self.field_bottom_y or all(-2 <= x <= self.width+1 for x in xs)
            if not inside_frame or not all(a < b for a, b in zip(xs, xs[1:])):
                raise ValueError(f"Invalid or crossing lane rails at y={y}: {xs}")

    def boundaries(self, y: float) -> list[float]:
        return [rail.x(y) for rail in self.rails]

    def lane_polygon(self, lane: int, y_top: float = 0, y_bottom: float | None = None) -> list[list[float]]:
        if not 0 <= lane < 6:
            raise ValueError("lane index must be 0..5")
        y_bottom = self.judgment_y if y_bottom is None else min(y_bottom, self.height-1)
        return [[self.rails[lane].x(y_top), y_top], [self.rails[lane+1].x(y_top), y_top],
                [self.rails[lane+1].x(y_bottom), y_bottom], [self.rails[lane].x(y_bottom), y_bottom]]

