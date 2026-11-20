"""Direction B: vector fatigue, data calibration, fixed points and stability.

Fatigue is an unobserved proxy measured in weekly-load equivalents. The retention
coefficient is estimated from workload persistence, not physiological measurements.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from .workload import WeeklyWorkload


@dataclass(frozen=True)
class FatigueParameters:
    a: float
    b: float
    r: float = 0.0

    def __post_init__(self):
        if not all(math.isfinite(value) for value in (self.a, self.b, self.r)):
            raise ValueError("Fatigue coefficients must be finite")
        if self.b < 0 or self.r < 0:
            raise ValueError("Load and rest coefficients must be nonnegative")


def _vector(values, name: str) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if result.ndim != 1 or result.size == 0 or not np.isfinite(result).all():
        raise ValueError(f"{name} must be a nonempty finite vector")
    return result


def step(state, load, parameters: FatigueParameters, rest=None) -> np.ndarray:
    state, load = _vector(state, "state"), _vector(load, "load")
    rest = np.zeros_like(load) if rest is None else _vector(rest, "rest")
    if state.shape != load.shape or rest.shape != load.shape:
        raise ValueError("State, load and rest must have matching sizes")
    if (load < 0).any() or (rest < 0).any():
        raise ValueError("Load and rest must be nonnegative")
    return parameters.a * state + parameters.b * load - parameters.r * rest


def fixed_point(load, parameters: FatigueParameters, rest=None) -> np.ndarray:
    load = _vector(load, "load")
    if parameters.a == 1:
        raise ValueError("a=1 has no unique fixed point (zero forcing gives a continuum)")
    return step(np.zeros_like(load), load, parameters, rest) / (1 - parameters.a)


def stability(parameters: FatigueParameters) -> dict:
    """The Jacobian is a*I. At |a|=1 perturbations persist without attraction."""
    radius = abs(parameters.a)
    label = ("asymptotically stable" if radius < 1 else
             "neutral" if radius == 1 else "unstable")
    return {"jacobian": "a I", "spectral_radius": radius, "classification": label}


def simulate(load, parameters: FatigueParameters, *, initial=None, weeks=52, rest=None):
    """Iterate the autonomous constant-load map, with time zero included."""
    load = _vector(load, "load")
    if type(weeks) is not int or weeks < 0:
        raise ValueError("weeks must be a nonnegative integer")
    state = np.zeros_like(load) if initial is None else _vector(initial, "initial")
    if state.shape != load.shape:
        raise ValueError("Initial state and load must have matching sizes")
    result = [state.copy()]
    for _ in range(weeks):
        state = step(state, load, parameters, rest)
        result.append(state)
    return np.asarray(result)


def block_coefficients(parameters: FatigueParameters, days: int) -> tuple[float, float]:
    """Semigroup interpolation for a partial week with a constant weekly load rate."""
    if type(days) is not int or not 1 <= days <= 7:
        raise ValueError("A weekly block must contain 1 to 7 calendar days")
    if not 0 <= parameters.a < 1 or parameters.r != 0:
        raise ValueError("Observed blocks require 0<=a<1 and the calibrated r=0 model")
    retention = parameters.a ** (days / 7)
    gain = parameters.b * (1 - retention) / (1 - parameters.a)
    return retention, gain


def simulate_history(workload: WeeklyWorkload, parameters: FatigueParameters, initial=None):
    """Use each actual block's rate and duration; never tile it into a fixed point."""
    state = (np.zeros(workload.counts.shape[1]) if initial is None
             else _vector(initial, "initial"))
    if state.shape != (workload.counts.shape[1],):
        raise ValueError("Initial state must contain one value per staff member")
    result = [state.copy()]
    for days, load in zip(workload.days, workload.rates):
        retention, gain = block_coefficients(parameters, int(days))
        state = retention * state + gain * load
        result.append(state)
    return np.asarray(result)


def calibrate(workload: WeeklyWorkload) -> tuple[FatigueParameters, dict]:
    """Unconstrained pooled lag-one OLS, then equilibrium normalization b=1-a.

    Each observation is a (staff, adjacent-block) pair, with partial blocks
    converted to weekly rates. Lack of fatigue measurements prevents identifying
    a recovery effect, so r=0 is explicit. The regression intercept is a workload
    diagnostic, not the forcing in the calibrated fatigue recurrence.
    """
    if workload.counts.shape[0] < 2:
        raise ValueError("Calibration needs at least two observed weekly blocks")
    previous = workload.rates[:-1].ravel()
    following = workload.rates[1:].ravel()
    centered = previous - previous.mean()
    denominator = float(centered @ centered)
    if denominator == 0:
        raise ValueError("Constant lagged workload cannot identify retention")
    a = float(centered @ (following - following.mean()) / denominator)
    intercept = float(following.mean() - a * previous.mean())
    if not 0 <= a < 1:
        raise ValueError(f"Workload retention estimate a={a:g} is outside [0,1); "
                         "the fatigue proxy is unsupported, so it was not clipped")
    parameters = FatigueParameters(a=a, b=1 - a, r=0.0)
    residual = following - (a * previous + intercept)
    sst = float(((following - following.mean()) ** 2).sum())
    target = float(workload.mean_load.mean())
    evidence = {
        "method": "pooled lag-one OLS of weekly assignment rates with intercept",
        "observations": int(previous.size),
        "workload_intercept": intercept,
        "workload_rmse": float(np.sqrt(np.mean(residual ** 2))),
        "workload_r_squared": None if sst == 0 else 1 - float(residual @ residual) / sst,
        "target_mean_weekly_load": target,
        "calibrated_mean_equilibrium": float(fixed_point([target], parameters)[0]),
        "assumptions": [
            "Workload persistence is a surrogate for unobserved fatigue retention.",
            "b=1-a defines fatigue units so mean equilibrium equals mean weekly load.",
            "r=0: separate physiological recovery is not identifiable in these data.",
            "F0=0 is a reference state; pre-dataset fatigue is unknown.",
            "Each block has a constant mean rate; the last partial week uses a^(days/7).",
            "Long-run fixed points use constant term-average loads, not a tiled roster.",
        ],
    }
    return parameters, evidence


def fit_threshold(history, coverage=0.95) -> float:
    """Nearest-rank quantile of baseline block-end proxy fatigue, including idle staff."""
    values = np.asarray(history, dtype=float)
    if (values.ndim != 2 or values.shape[0] < 2 or values.shape[1] == 0
            or not np.isfinite(values).all() or not 0 < coverage <= 1):
        raise ValueError("Threshold needs a finite history and coverage in (0,1]")
    return float(np.quantile(values[1:], coverage, method="inverted_cdf"))


def threshold_penalty(trajectory, threshold: float) -> float:
    """Sum of positive exceedances over all states/staff; initial state included."""
    values = np.asarray(trajectory, dtype=float)
    if (values.ndim != 2 or values.size == 0 or not np.isfinite(values).all()
            or not math.isfinite(threshold) or threshold < 0):
        raise ValueError("Need a finite trajectory and a nonnegative finite threshold")
    return float(np.maximum(values - threshold, 0).sum())
