"""Robust local motion estimates using video timestamps in seconds."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class Prediction:
    velocity: float | None = None
    fitted_y: float | None = None
    eta: float | None = None
    hit_time: float | None = None
    uncertainty: float | None = None
    reason: str = "insufficient_observations"
    inlier_fraction: float = 0.0


class Predictor:
    def __init__(self, cfg: dict | None = None):
        self.cfg = cfg or {}

    def predict(self, history: list[tuple[float, float, float]], hit_y: float) -> Prediction:
        """Theil–Sen slope and MAD residual rejection over recent observations.

        History is (timestamp, center_y, normalized_center_x). Uncertainty is
        a fit diagnostic, not an error bar validated against judgment labels.
        """
        cfg = self.cfg
        data = np.asarray(history[-int(cfg.get("window", 11)):], dtype=float)
        if len(data) < int(cfg.get("min_observations", 5)):
            return Prediction()
        ts, ys = data[:, 0], data[:, 1]
        if ts[-1] - ts[0] < cfg.get("min_duration_s", 0.05) or np.any(np.diff(ts) <= 0):
            return Prediction(reason="invalid_or_short_timestamps")
        tx = ts - ts[-1]
        slopes = [(ys[j]-ys[i])/(tx[j]-tx[i])
                  for i in range(len(tx)) for j in range(i+1, len(tx))]
        velocity = float(np.median(slopes))
        intercept = float(np.median(ys - velocity*tx))
        residuals = ys - (intercept + velocity*tx)
        mad = float(np.median(np.abs(residuals - np.median(residuals))))
        threshold = max(float(cfg.get("jitter_px", 3.5)), 3.0 * 1.4826 * mad)
        inliers = np.abs(residuals) <= threshold
        fraction = float(np.mean(inliers))
        common = dict(velocity=velocity, fitted_y=intercept, inlier_fraction=fraction)
        if fraction < 0.7 or np.sum(inliers) < int(cfg.get("min_observations", 5)):
            return Prediction(**common, reason="motion_outliers")
        if not inliers[-1]:
            return Prediction(**common, reason="latest_position_outlier")
        if velocity < float(cfg.get("min_velocity", 20)):
            return Prediction(**common, reason="stationary_or_backward")
        if velocity > float(cfg.get("max_velocity", 1800)):
            return Prediction(**common, reason="implausible_velocity")
        yv, tv = ys[inliers], tx[inliers]
        if np.mean(np.diff(yv) > 0) < 0.6 or np.ptp(yv) < cfg.get("min_displacement_px", 5):
            return Prediction(**common, reason="insufficient_forward_motion")
        eta = (hit_y - intercept) / velocity
        if ys[-1] > hit_y or eta < 0:
            return Prediction(**common, reason="past_hit_line")
        local_hits = ts[-1] + tv + (hit_y-yv)/velocity
        uncertainty = float(np.percentile(np.abs(local_hits-np.median(local_hits)), 90))
        if uncertainty > float(cfg.get("max_uncertainty_s", 0.04)):
            return Prediction(**common, uncertainty=uncertainty, reason="unstable_eta")
        if eta > float(cfg.get("lookahead_s", 1.5)):
            return Prediction(**common, uncertainty=uncertainty, reason="outside_lookahead")
        return Prediction(**common, eta=eta, hit_time=float(ts[-1]+eta),
                          uncertainty=uncertainty, reason="")
