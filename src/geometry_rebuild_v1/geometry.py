from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Rail:
    slope_dx_per_dy: float
    x_at_top: float

    def x(self, y: float) -> float:
        return self.x_at_top + self.slope_dx_per_dy * y


@dataclass(frozen=True)
class Geometry:
    width: int
    height: int
    rails: tuple[Rail, ...]
    judgment_y: float
    judgment_band: tuple[float, float]
    calibrated_from: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.rails) != 7:
            raise ValueError("six lanes require exactly seven boundaries")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("invalid native dimensions")
        for y in (0, self.judgment_y, self.height - 1):
            xs = [rail.x(y) for rail in self.rails]
            if any(a >= b for a, b in zip(xs, xs[1:])):
                raise ValueError(f"rail boundaries cross at y={y}")
        if not (0 <= self.judgment_band[0] <= self.judgment_y <= self.judgment_band[1] < self.height):
            raise ValueError("judgment reference must lie within observed band")

    def boundaries(self, y: float) -> tuple[float, ...]:
        return tuple(rail.x(y) for rail in self.rails)

    def source_to_lane_plane(self, x: float, y: float, lane_width: int = 360,
                             ref_height: int = 404) -> tuple[float, float]:
        left, right = self.rails[0].x(y), self.rails[-1].x(y)
        u = (x - left) * lane_width / (right - left)
        v = y * ref_height / self.height
        return u, v

    def lane_plane_to_source(self, u: float, v: float, lane_width: int = 360,
                             ref_height: int = 404) -> tuple[float, float]:
        y = v * self.height / ref_height
        left, right = self.rails[0].x(y), self.rails[-1].x(y)
        x = left + u * (right - left) / lane_width
        return x, y

    def to_dict(self) -> dict:
        return {
            "schema": "geometry-video-v1-fresh-1",
            "native_size": [self.width, self.height],
            "reference_size": [720, 404],
            "lane_plane": [360, 404],
            "coordinate_mapping": "source x,y -> 720x404 uniform scale -> row-wise outer-rail rectification -> 360x404 lane plane",
            "rails": [{"slope_dx_per_dy": r.slope_dx_per_dy, "x_at_y0": r.x_at_top}
                      for r in self.rails],
            "judgment_y": self.judgment_y,
            "judgment_band": list(self.judgment_band),
            "lane_keys_for_diagnostics_only": ["S", "D", "F", "J", "K", "L"],
            "calibrated_from_development_runs": list(self.calibrated_from),
            "holdout_used_for_fitting": False,
            "status": "AUTO_SOURCE_HOUGH_CALIBRATION_PROVISIONAL",
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Geometry":
        rails = tuple(Rail(float(r["slope_dx_per_dy"]), float(r["x_at_y0"]))
                      for r in data["rails"])
        w, h = map(int, data["native_size"])
        return cls(w, h, rails, float(data["judgment_y"]),
                   tuple(map(float, data["judgment_band"])),
                   tuple(data.get("calibrated_from_development_runs", [])))


def assert_round_trip(geometry: Geometry, points: Iterable[tuple[float, float]],
                      tolerance_px: float = 1e-7) -> None:
    for x, y in points:
        u, v = geometry.source_to_lane_plane(x, y)
        x2, y2 = geometry.lane_plane_to_source(u, v)
        if abs(x - x2) > tolerance_px or abs(y - y2) > tolerance_px:
            raise AssertionError((x, y, x2, y2))
