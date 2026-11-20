"""Reproduce M4: python run_all.py --seed <team seed> --stage m4."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import numpy as np

from m1_logic.data_loader import DEFAULT_PATH, PROJECT_FOLDER
from m2_ilp.config import M2_DIR
from m2_ilp.instance import build_instance
from m2_ilp.run import write_schedule

from .fatigue import (FatigueParameters, calibrate, fit_threshold, fixed_point,
                      simulate, simulate_history, stability, step, threshold_penalty)
from .planning import refine_schedule
from .workload import read_schedule, weekly_workload

M4_DIR = Path(__file__).resolve().parent


def analyze_equilibrium(load, initial, parameters, weeks, tolerance):
    """Numerically check the fixed point, exact solution and convergence prediction."""
    equilibrium = fixed_point(load, parameters)
    trajectory = simulate(load, parameters, initial=initial, weeks=weeks)
    expected = (equilibrium + parameters.a ** np.arange(weeks + 1)[:, None]
                * (initial - equilibrium))
    fixed_error = float(np.max(np.abs(step(equilibrium, load, parameters) - equilibrium)))
    closed_error = float(np.max(np.abs(trajectory - expected)))
    final_error = float(np.max(np.abs(trajectory[-1] - equilibrium)))
    if max(fixed_error, closed_error, final_error) > tolerance:
        raise RuntimeError("M4 recurrence/fixed-point/convergence verification failed")
    info = {
        "mean_weekly_load": float(np.mean(load)),
        "equilibrium": equilibrium.tolist(),
        "equilibrium_mean": float(equilibrium.mean()),
        "equilibrium_spread": float(np.ptp(equilibrium)),
        "equilibrium_variance": float(np.var(equilibrium)),
        "initial_spread": float(np.ptp(initial)),
        "final_spread": float(np.ptp(trajectory[-1])),
        "final_variance": float(np.var(trajectory[-1])),
        "fixed_point_residual": fixed_error,
        "closed_form_max_error": closed_error,
        "final_max_error": final_error,
        "converged": final_error <= tolerance,
    }
    return trajectory, equilibrium, info


def stability_checks(parameters):
    """Check contraction, persistence and growth without imposing stability in the API."""
    checks = []
    for a in (parameters.a, 1.0, 1.05):
        candidate = FatigueParameters(a=a, b=parameters.b)
        # Zero forcing gives an actual fixed point at zero even at a=1.
        history = simulate([0.0], candidate, initial=[0.001], weeks=20)
        observed = float(abs(history[-1, 0] / history[0, 0]))
        predicted = abs(a) ** 20
        if not np.isclose(observed, predicted, atol=1e-12):
            raise RuntimeError("Stability perturbation check failed")
        checks.append({"a": a, **stability(candidate), "weeks": 20,
                       "observed_distance_ratio": observed, "predicted_distance_ratio": predicted})
    return checks


def _write_csv(path, header, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def run_m4(seed: int, out_dir=None, *, schedule_path=None, weeks=52, tolerance=1e-8):
    """Read completed M2 outputs; write only M4 artifacts after numerical validation."""
    if type(weeks) is not int or weeks < 1:
        raise ValueError("weeks must be a positive integer")
    if not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("tolerance must be positive and finite")
    inst = build_instance(seed)
    schedule_path = M2_DIR / "schedule.csv" if schedule_path is None else Path(schedule_path)
    if not schedule_path.is_file():
        raise FileNotFoundError(f"Missing {schedule_path}; run stage m2 first")
    assigned = read_schedule(inst, schedule_path)
    baseline = weekly_workload(inst, inst.baseline)
    parameters, calibration = calibrate(baseline)
    histories = {"baseline": simulate_history(baseline, parameters)}
    threshold = fit_threshold(histories["baseline"])
    refined, planning = refine_schedule(inst, assigned, parameters, threshold)
    workloads = {"baseline": baseline, "m2": weekly_workload(inst, assigned),
                 "fatigue_aware": weekly_workload(inst, refined)}
    histories.update({name: simulate_history(workload, parameters)
                      for name, workload in workloads.items() if name != "baseline"})

    # Same nonuniform initial fatigue isolates the effect of load policy on fairness.
    initial = histories["baseline"][-1]
    loads = {name: workload.mean_load for name, workload in workloads.items()}
    loads["equal_load"] = np.full(len(inst.staff_ids), baseline.mean_load.mean())
    trajectories, equilibria, scenarios = {}, {}, {}
    for name, load in loads.items():
        trajectory, equilibrium, info = analyze_equilibrium(
            load, initial, parameters, weeks, tolerance)
        info["constant_load_threshold_penalty"] = threshold_penalty(trajectory, threshold)
        if name in workloads:
            info["observed_threshold_penalty"] = threshold_penalty(histories[name], threshold)
            info["observed_max_fatigue"] = float(histories[name].max())
            info["assignments"] = int(workloads[name].counts.sum())
        trajectories[name], equilibria[name], scenarios[name] = trajectory, equilibrium, info

    equal = trajectories["equal_load"]
    predicted_spread = np.ptp(initial) * abs(parameters.a) ** np.arange(weeks + 1)
    predicted_variance = np.var(initial) * parameters.a ** (2 * np.arange(weeks + 1))
    spread_error = float(np.max(np.abs(np.ptp(equal, axis=1) - predicted_spread)))
    variance_error = float(np.max(np.abs(np.var(equal, axis=1) - predicted_variance)))
    if max(spread_error, variance_error) > tolerance:
        raise RuntimeError("Equal-load spread/variance contraction check failed")
    perturbation = equilibria["equal_load"].copy()
    perturbation[0] += float(baseline.mean_load.mean())
    _, _, perturbation_check = analyze_equilibrium(
        loads["equal_load"], perturbation, parameters, weeks, tolerance)

    results = {
        "direction": "B: vector fatigue and fairness",
        "seed": inst.seed,
        "source": {"dataset_sha256": hashlib.sha256(Path(DEFAULT_PATH).read_bytes()).hexdigest(),
                   "m2_schedule_sha256": hashlib.sha256(schedule_path.read_bytes()).hexdigest(),
                   "staff": len(inst.staff_ids), "sessions": len(inst.session_names),
                   "calendar_days": int(baseline.days.sum()),
                   "weekly_days": baseline.days.tolist(),
                   "weekly_assignments": baseline.counts.sum(axis=1).tolist(),
                   "staff_ids": inst.staff_ids},
        "recurrence": "F[n+1] = a F[n] + b load - r rest",
        "parameters": asdict(parameters),
        "calibration": calibration,
        "stability": stability(parameters),
        "stability_sensitivity": stability_checks(parameters),
        "simulation": {"weeks": weeks, "tolerance": tolerance,
                       "initial": "terminal baseline fatigue from actual weekly loads"},
        "threshold": {"value": threshold, "coverage": 0.95,
                      "method": "nearest-rank quantile of baseline block-end fatigue over all staff",
                      "meaning": "soft policy threshold on a workload proxy, not a clinical limit"},
        "planning": planning,
        "scenarios": scenarios,
        "verification": {"all_fixed_points_converged": True,
                         "equal_load_spread_max_error": spread_error,
                         "equal_load_variance_max_error": variance_error,
                         "equal_load_perturbation_final_error": perturbation_check["final_max_error"]},
    }

    out_dir = M4_DIR if out_dir is None else Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_schedule(inst, refined, out_dir / "fatigue_aware_schedule.csv")
    _write_csv(out_dir / "observed_weekly.csv",
               ["scenario", "week", "start", "days", "staff_id", "assignments",
                "weekly_rate", "cumulative_assignments", "fatigue_end"],
               ([name, k + 1, workload.starts[k].isoformat(), int(workload.days[k]), person,
                 int(workload.counts[k, i]), float(workload.rates[k, i]),
                 int(workload.cumulative[k + 1, i]), float(histories[name][k + 1, i])]
                for name, workload in workloads.items()
                for k in range(len(workload.starts)) for i, person in enumerate(inst.staff_ids)))
    _write_csv(out_dir / "trajectories.csv",
               ["scenario", "week", "staff_id", "fatigue", "equilibrium", "threshold_excess"],
               ([name, t, person, float(state[i]), float(equilibria[name][i]),
                 max(0.0, float(state[i]) - threshold)]
                for name, trajectory in trajectories.items()
                for t, state in enumerate(trajectory) for i, person in enumerate(inst.staff_ids)))
    from .plots import write_plots

    write_plots(out_dir, histories, trajectories, equilibria, threshold)
    (out_dir / "results.json").write_text(
        json.dumps(results, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(f"[m4] direction B; a={parameters.a:.6f}, b={parameters.b:.6f}, r={parameters.r:g}; "
          f"{stability(parameters)['classification']}")
    print(f"[m4] observed mean weekly load = mean equilibrium = "
          f"{baseline.mean_load.mean():.6f}; soft threshold={threshold:.6f}")
    for name, info in scenarios.items():
        print(f"[m4] {name}: equilibrium spread={info['equilibrium_spread']:.6f}; "
              f"final fixed-point error={info['final_max_error']:.3g}")
    print(f"[m4] threshold refinement: {planning['status']}; 0 hard-rule violations; "
          f"wrote results, CSVs and 3 plots to {out_dir}")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=None, help="defaults to data/seed.txt")
    parser.add_argument("--out-dir", type=Path, default=M4_DIR)
    parser.add_argument("--schedule", type=Path, default=M2_DIR / "schedule.csv")
    parser.add_argument("--weeks", type=int, default=52)
    args = parser.parse_args()
    seed = args.seed
    if seed is None:
        seed = int((PROJECT_FOLDER / "data/seed.txt").read_text(encoding="utf-8-sig").strip())
    run_m4(seed, args.out_dir, schedule_path=args.schedule, weeks=args.weeks)


if __name__ == "__main__":
    main()
