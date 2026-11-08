"""Causal log-position motion fit selected against observed reference crossings.

Reference-success input timing is explicitly not an ideal judgment center.
"""
from __future__ import annotations
from dataclasses import dataclass
import json,math
from pathlib import Path
import numpy as np


@dataclass(frozen=True)
class Estimate:
    crossing_at: float | None=None
    press_at: float | None=None
    eta_s: float | None=None
    uncertainty: float | None=None
    reason: str='insufficient_observations'
    velocity: float | None=None


class Timing:
    def __init__(self,geometry,calibration=None):
        self.geometry=geometry
        widths=geometry.xs[:,-1]-geometry.xs[:,0]
        slope=(widths[-1]-widths[0])/(geometry.ys[-1]-geometry.ys[0])
        self.vanish=float(geometry.ys[0]-widths[0]/slope)
        if isinstance(calibration,(str,Path)):
            calibration=json.loads(Path(calibration).read_text(encoding='utf-8-sig'))
        self.calibration=calibration
        if calibration is not None:
            if calibration.get('geometry_sha256')!=geometry.sha256 or calibration.get('model')!='log':
                raise ValueError('Timing calibration does not match this geometry/model')
            if calibration.get('kind')!='reference_success_timing':
                raise ValueError('Unknown timing calibration provenance')
            if not math.isfinite(float(calibration['input_offset_s'])) or abs(float(calibration['input_offset_s']))>.2:
                raise ValueError('Input calibration outside supported range')

    def predict(self,samples,capture_timestamp,*,kind='tap'):
        points=np.asarray(list(samples)[-12:],float)
        if len(points):
            points=points[points[:,0]>=points[-1,0]-.30]
            if len(points)>8:
                points=points[np.linspace(0,len(points)-1,8,dtype=int)]
        if len(points)<4:return Estimate()
        ts,y=points[:,0],points[:,1]
        if (not np.all(np.isfinite(points)) or np.any(np.diff(ts)<=0) or
                ts[-1]>capture_timestamp or ts[-1]-ts[0]<.08):
            return Estimate(reason='invalid_or_future_observations')
        if capture_timestamp-ts[-1]>.14:return Estimate(reason='stale_observation')
        if np.any(y<=self.vanish+1):return Estimate(reason='outside_motion_domain')
        q=np.log(y-self.vanish);tx=ts-ts[-1]
        slopes=np.array([(q[j]-q[i])/(tx[j]-tx[i]) for i in range(len(tx)) for j in range(i+1,len(tx))])
        speed=float(np.median(slopes))
        if not .03<speed<10:return Estimate(reason='stationary_or_implausible_motion')
        intercept=float(np.median(q-speed*tx))
        target=math.log(self.geometry.hit_y-self.vanish)
        crossing=float(ts[-1]+(target-intercept)/speed)
        eta=crossing-capture_timestamp
        if eta<=0:return Estimate(crossing_at=crossing,eta_s=eta,reason='crossing_in_past')
        if eta>1.5:return Estimate(crossing_at=crossing,eta_s=eta,reason='outside_prediction_horizon')
        residual=q-(intercept+speed*tx)
        fit_sigma=float(np.median(np.abs(residual-np.median(residual)))*1.4826/speed)
        physical_speed=speed*(self.geometry.hit_y-self.vanish)
        noise=1.5/max(physical_speed,20)
        # Extrapolation error is calibrated on development visual crossings,
        # not keyboard timestamps or future runtime observations.
        empirical=0.
        if self.calibration:
            bands=self.calibration.get('visual_error_bands',[])
            eligible=[b for b in bands if y[-1]>=b['from_y']]
            if bands and not eligible:
                return Estimate(crossing_at=crossing,eta_s=eta,
                                reason='uncalibrated_visual_height',velocity=physical_speed)
            if eligible:empirical=float(eligible[-1]['p90_absolute_s'])
        uncertainty=float(math.hypot(fit_sigma,noise,empirical))
        if uncertainty>.04:
            return Estimate(crossing_at=crossing,eta_s=eta,uncertainty=uncertainty,
                            reason='motion_uncertainty',velocity=physical_speed)
        if not self.calibration:
            return Estimate(crossing_at=crossing,eta_s=eta,uncertainty=uncertainty,
                            reason='input_calibration_missing',velocity=physical_speed)
        offset=float(self.calibration['input_offset_s']) if kind!='tail' else 0.
        return Estimate(crossing,crossing-offset,eta,uncertainty,'ready',physical_speed)

    @property
    def release_guard(self):
        return max(0.,float((self.calibration or {}).get('release_guard_s',0.)))
