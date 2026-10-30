"""Vectorized per-track particle filter for ordinary Tap position and hit ETA.

The filter is a motion estimate only. It never establishes note type, lane/key,
or input eligibility; LiveEngine's existing observation and safety gates do that.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import time

import numpy as np

from .predictor import Prediction


@dataclass(frozen=True)
class ParticleDiagnostics:
    status: str
    ess: float
    observation_count: int
    coast_ms: float


class ParticlePredictor:
    """Small vectorized SMC with robust Student-t measurement weighting."""

    def __init__(self, cfg: dict | None = None, *, seed: int = 20261030,
                 track_id: int = 0, physical_hit_y: float | None = None):
        self.cfg = dict(cfg or {})
        if self.cfg.get("use_acceleration", False):
            raise ValueError("acceleration particles are not implemented; set use_acceleration=false")
        if self.cfg.get("measurement_model", "student_t") != "student_t":
            raise ValueError("only the Student-t measurement model is currently implemented")
        self.count = int(self.cfg.get("count", 128))
        if self.count < 32 or self.count > 512:
            raise ValueError("particle count must be between 32 and 512")
        self.min_observations = int(self.cfg.get("min_real_observations", 4))
        self.max_coast_s = float(self.cfg.get("max_coast_ms", 90)) / 1000
        self.max_horizon_s = float(self.cfg.get("max_prediction_horizon_ms", 1500)) / 1000
        self.max_width_s = float(self.cfg.get("max_posterior_width_ms", 40)) / 1000
        self.min_crossing_mass = float(self.cfg.get("min_valid_crossing_mass", .95))
        self.min_velocity = float(self.cfg.get("min_velocity", 20))
        self.max_velocity = float(self.cfg.get("max_velocity", 1800))
        self.y_process = float(self.cfg.get("position_process_noise_px_sqrt_s", 1.8))
        self.v_process = float(self.cfg.get("velocity_process_noise_px_s_sqrt_s", 8.0))
        self.u_process = float(self.cfg.get("lane_process_noise_sqrt_s", .0015))
        self.y_measurement = float(self.cfg.get("position_measurement_noise_px", 3.0))
        self.u_measurement = float(self.cfg.get("lane_measurement_noise", .012))
        self.gate_px = float(self.cfg.get("observation_gate_px", 32.0))
        self.resample_fraction = float(self.cfg.get("ess_resample_fraction", .5))
        if not (0 < self.min_crossing_mass <= 1 and 0 < self.resample_fraction <= 1 and
                0 < self.max_coast_s <= .3 and self.max_horizon_s > 0 and
                self.y_measurement > 0 and self.u_measurement > 0):
            raise ValueError("invalid particle predictor configuration")
        base_seed = int(seed) & 0xffffffff
        # Stable arithmetic; never depend on Python's randomized hash().
        self.rng = np.random.default_rng((base_seed + int(track_id) * 2654435761) & 0xffffffff)
        self.physical_hit_y = physical_hit_y
        self.last_time: float | None = None
        self.initialized = False
        self.observation_count = 0
        self.y = self.v = self.u = self.vu = None
        self.weights = None
        self.ess = 0.0
        self.last_status = "PF_NOT_READY"
        self.elapsed = 0.0

    def _initialize(self, history: list[tuple[float, float, float]]) -> bool:
        data = np.asarray(history[-7:], dtype=float)
        if len(data) < self.min_observations or not np.all(np.isfinite(data)):
            return False
        ts, ys, us = data[:, 0], data[:, 1], data[:, 2]
        dt = np.diff(ts)
        if np.any(dt <= 0) or ts[-1] - ts[0] < .035:
            self.last_status = "PF_INVALID_TIMESTAMP"
            return False
        vy = float(np.median(np.diff(ys) / dt))
        vu = float(np.median(np.diff(us) / dt))
        if not self.min_velocity <= vy <= self.max_velocity:
            self.last_status = "PF_INVALID_INITIAL_VELOCITY"
            return False
        n = self.count
        self.y = self.rng.normal(ys[-1], max(.7, self.y_measurement * .45), n)
        self.v = np.clip(self.rng.normal(vy, max(1.5, abs(vy) * .012), n),
                         self.min_velocity, self.max_velocity)
        self.u = self.rng.normal(us[-1], max(.002, self.u_measurement * .35), n)
        self.vu = self.rng.normal(vu, max(.002, abs(vu) * .12), n)
        self.weights = np.full(n, 1. / n)
        self.ess = float(n)
        self.last_time = float(ts[-1])
        self.observation_count = len(data)
        self.initialized = True
        self.last_status = "PF_READY"
        return True

    def _propagate(self, dt: float) -> None:
        if dt <= 0 or dt > .25:
            return
        root = math.sqrt(dt)
        self.y = self.y + self.v * dt + self.rng.normal(0, self.y_process * root, self.count)
        self.v = np.clip(self.v + self.rng.normal(0, self.v_process * root, self.count),
                         0., self.max_velocity * 1.15)
        self.u = self.u + self.vu * dt + self.rng.normal(0, self.u_process * root, self.count)
        self.vu = self.vu + self.rng.normal(0, self.u_process * .2 * root, self.count)

    def position_at(self, timestamp: float) -> float | None:
        if not self.initialized or self.last_time is None or timestamp < self.last_time:
            return None
        dt = timestamp - self.last_time
        if dt > self.max_coast_s:
            return None
        return float(np.average(self.y + self.v * dt, weights=self.weights))

    def _weighted_quantile(self, values: np.ndarray, weights: np.ndarray, q: float) -> float:
        order = np.argsort(values)
        v, w = values[order], weights[order]
        cdf = np.cumsum(w)
        return float(np.interp(q, cdf, v))

    def _prediction(self, target_y: float, timestamp: float, status: str) -> Prediction:
        if not self.initialized:
            return Prediction(reason=self.last_status, predictor_mode="particle", measurement_status=status)
        dt = max(0., timestamp - float(self.last_time))
        coast_ms = dt * 1000
        if coast_ms > self.max_coast_s * 1000:
            return Prediction(velocity=float(np.average(self.v, weights=self.weights)),
                              fitted_y=float(np.average(self.y, weights=self.weights)),
                              reason="PF_COAST_EXPIRED", ess=self.ess,
                              real_observation_count=self.observation_count, coast_ms=coast_ms,
                              predictor_mode="particle", measurement_status=status)
        ys = self.y + self.v * dt
        vs = self.v
        valid = (vs > self.min_velocity) & (vs <= self.max_velocity * 1.05) & (ys < target_y)
        taus = np.full(self.count, np.nan)
        taus[valid] = (target_y - ys[valid]) / vs[valid]
        valid &= np.isfinite(taus) & (taus >= 0) & (taus <= self.max_horizon_s)
        mass = float(self.weights[valid].sum())
        common = dict(velocity=float(np.average(vs, weights=self.weights)),
                      fitted_y=float(np.average(ys, weights=self.weights)),
                      valid_crossing_mass=mass, ess=self.ess,
                      real_observation_count=self.observation_count, coast_ms=coast_ms,
                      predictor_mode="particle", measurement_status=status)
        if mass < self.min_crossing_mass:
            reason = "ALREADY_PAST_TRIGGER" if float(np.average(ys, weights=self.weights)) >= target_y else "PF_NO_VALID_CROSSING"
            return Prediction(**common, reason=reason)
        weights = self.weights[valid] / mass
        tau = taus[valid]
        p10, p50, p90 = (self._weighted_quantile(tau, weights, q) for q in (.1, .5, .9))
        # A linear no-measurement coast must become less certain even though
        # the deterministic crossing time of a constant-velocity sample stays
        # invariant as its timestamp advances.
        if dt > 0:
            speed = max(self.min_velocity, float(np.average(vs, weights=self.weights)))
            coast_pad = (self.y_process * math.sqrt(dt) +
                         self.v_process * dt * math.sqrt(dt)) / speed
            p10, p90 = max(0., p10 - coast_pad), min(self.max_horizon_s, p90 + coast_pad)
        width = p90 - p10
        absolute = timestamp + p50
        physical_time = None
        if self.physical_hit_y is not None and self.physical_hit_y > target_y:
            physical_tau = (self.physical_hit_y - ys[valid]) / vs[valid]
            good = np.isfinite(physical_tau) & (physical_tau >= 0) & (physical_tau <= self.max_horizon_s)
            if np.any(good):
                physical_time = timestamp + self._weighted_quantile(physical_tau[good], weights[good] / weights[good].sum(), .5)
        if width > self.max_width_s:
            reason = "PF_POSTERIOR_TOO_WIDE"
        elif p50 <= 0:
            reason = "ALREADY_PAST_TRIGGER"
        else:
            reason = ""
        return Prediction(**common, eta=p50, hit_time=absolute, uncertainty=width / 2,
                          eta_p10=p10, eta_p50=p50, eta_p90=p90,
                          physical_hit_time=physical_time, reason=reason)

    def update(self, history: list[tuple[float, float, float]], target_y: float,
               *, physical_hit_y: float | None = None) -> Prediction:
        began = time.perf_counter()
        try:
            if physical_hit_y is not None:
                self.physical_hit_y = physical_hit_y
            if not self.initialized:
                if not self._initialize(history):
                    return Prediction(reason=self.last_status, predictor_mode="particle",
                                      measurement_status="not_initialized")
                return self._prediction(target_y, float(self.last_time), "INITIALIZED")
            t, measured_y, measured_u = map(float, history[-1])
            if not all(math.isfinite(v) for v in (t, measured_y, measured_u)) or t <= self.last_time:
                self.last_status = "PF_INVALID_TIMESTAMP"
                return Prediction(reason="PF_INVALID_TIMESTAMP", ess=self.ess,
                                  real_observation_count=self.observation_count,
                                  predictor_mode="particle", measurement_status="REJECTED_TIMESTAMP")
            dt = t - self.last_time
            if dt > .25:
                self.last_status = "PF_GAP_TOO_LARGE"
                return self._prediction(target_y, t, "REJECTED_GAP")
            self._propagate(dt)
            self.last_time = t
            self.observation_count += 1
            y_residual = measured_y - self.y
            u_residual = measured_u - self.u
            innovation = float(np.average(np.abs(y_residual), weights=self.weights))
            if innovation > self.gate_px:
                self.last_status = "REJECTED_MEASUREMENT"
                return self._prediction(target_y, t, "REJECTED_MEASUREMENT")
            # Student-t likelihood (df=4), computed in log space.
            logw = np.log(np.maximum(self.weights, 1e-300))
            logw -= 2.5 * np.log1p((y_residual / self.y_measurement) ** 2 / 4.)
            logw -= 2.5 * np.log1p((u_residual / self.u_measurement) ** 2 / 4.)
            logw -= np.max(logw)
            w = np.exp(logw)
            total = float(w.sum())
            if not math.isfinite(total) or total <= 1e-300:
                self.last_status = "PF_INVALID_WEIGHTS"
                return self._prediction(target_y, t, "PF_INVALID_WEIGHTS")
            self.weights = w / total
            self.ess = float(1. / np.sum(self.weights ** 2))
            if not math.isfinite(self.ess) or self.ess < 1:
                self.last_status = "PF_INVALID_ESS"
                return self._prediction(target_y, t, "PF_INVALID_ESS")
            if self.ess < self.resample_fraction * self.count:
                # Systematic resampling, followed by small roughening.
                positions = (self.rng.random() + np.arange(self.count)) / self.count
                indexes = np.searchsorted(np.cumsum(self.weights), positions, side="left")
                self.y, self.v, self.u, self.vu = (a[indexes].copy() for a in (self.y,self.v,self.u,self.vu))
                self.y += self.rng.normal(0, self.y_measurement * .12, self.count)
                self.v += self.rng.normal(0, max(1., self.v_process * .04), self.count)
                self.u += self.rng.normal(0, self.u_measurement * .08, self.count)
                self.weights.fill(1. / self.count)
                self.ess = float(self.count)
            if not all(np.all(np.isfinite(a)) for a in (self.y,self.v,self.u,self.vu,self.weights)):
                self.last_status = "PF_INVALID_STATE"
                return Prediction(reason=self.last_status, predictor_mode="particle",
                                  measurement_status="PF_INVALID_STATE")
            self.last_status = "UPDATED"
            return self._prediction(target_y, t, "USED")
        finally:
            self.elapsed += time.perf_counter() - began

    def coast_to(self, timestamp: float, target_y: float) -> Prediction:
        if not self.initialized or self.last_time is None or timestamp < self.last_time:
            return Prediction(reason="PF_NOT_READY", predictor_mode="particle", measurement_status="coast")
        return self._prediction(target_y, timestamp, "COAST")
