"""M4 dynamical trajectory evaluation and headless Matplotlib figures (M5, Nguyen)."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np

from m2_ilp.instance import Instance
from m2_ilp.metrics import loads as staff_loads
from m4_dynamics.fatigue import (
    FatigueParameters,
    calibrate,
    fit_threshold,
    fixed_point,
    simulate,
    simulate_history,
    stability,
    step,
    threshold_penalty,
)
from m4_dynamics.workload import weekly_workload

FALLBACK_PARAMETERS = FatigueParameters(a=0.27063439282332274, b=0.7293656071766772, r=0.0)
FALLBACK_THRESHOLD = 5.660327617142248


def evaluate_dynamics(
    inst: Instance,
    schedules: dict[str, object],
    *,
    weeks: int = 52,
    shock_staff_index: int = 0,
    shock_amount: float = 0.0,
) -> dict:
    """Calibrate or reuse Direction B parameters and simulate observed + long-run maps."""
    if type(weeks) is not int or weeks < 1:
        raise ValueError("weeks must be a positive integer")
    if not schedules:
        raise ValueError("schedules must contain at least one valid schedule")

    workloads = {label: weekly_workload(inst, pairs) for label, pairs in schedules.items()}
    ref_label = "Baseline" if "Baseline" in workloads else next(iter(workloads))
    ref_wl = workloads[ref_label]

    try:
        parameters, calibration = calibrate(ref_wl)
        ref_hist = simulate_history(ref_wl, parameters)
        threshold = fit_threshold(ref_hist)
        calibrated_from_data = True
    except ValueError:
        parameters = FALLBACK_PARAMETERS
        calibration = {
            "method": "fallback to 27-day Faculty dataset calibration (slice has <2 blocks)",
            "observations": int(max(0, ref_wl.counts.shape[0] - 1) * ref_wl.counts.shape[1]),
        }
        threshold = FALLBACK_THRESHOLD
        calibrated_from_data = False

    histories = {
        label: simulate_history(wl, parameters) for label, wl in workloads.items()
    }
    initial = histories[ref_label][-1].copy()
    if shock_amount != 0.0 and 0 <= shock_staff_index < initial.size:
        initial[shock_staff_index] = max(0.0, initial[shock_staff_index] + float(shock_amount))

    mean_loads = {label: wl.mean_load for label, wl in workloads.items()}
    mean_loads["Equal-load reference"] = np.full(
        len(inst.staff_ids), float(ref_wl.mean_load.mean())
    )

    trajectories, equilibria, summary_rows = {}, {}, []
    for label, load_vec in mean_loads.items():
        eq = fixed_point(load_vec, parameters)
        traj = simulate(load_vec, parameters, initial=initial, weeks=weeks)
        fp_residual = float(np.max(np.abs(step(eq, load_vec, parameters) - eq)))
        final_err = float(np.max(np.abs(traj[-1] - eq)))
        obs_pen = (
            round(threshold_penalty(histories[label], threshold), 6)
            if label in histories
            else None
        )
        obs_max = (
            round(float(histories[label].max()), 6) if label in histories else None
        )
        trajectories[label] = traj
        equilibria[label] = eq
        summary_rows.append({
            "scenario": label,
            "mean_weekly_load": round(float(np.mean(load_vec)), 6),
            "equilibrium_mean": round(float(eq.mean()), 6),
            "equilibrium_spread": round(float(np.ptp(eq)), 6),
            "equilibrium_variance": round(float(np.var(eq)), 6),
            "final_spread": round(float(np.ptp(traj[-1])), 6),
            "final_variance": round(float(np.var(traj[-1])), 6),
            "fixed_point_residual": fp_residual,
            "final_max_error": final_err,
            "observed_max_fatigue": obs_max,
            "observed_threshold_excess": obs_pen,
        })

    return {
        "parameters": {
            "a": parameters.a,
            "b": parameters.b,
            "r": parameters.r,
        },
        "stability": stability(parameters),
        "threshold": threshold,
        "calibrated_from_data": calibrated_from_data,
        "calibration": calibration,
        "weeks": weeks,
        "weekly_days": ref_wl.days.tolist(),
        "shock_staff_id": (
            inst.staff_ids[shock_staff_index]
            if 0 <= shock_staff_index < len(inst.staff_ids)
            else None
        ),
        "shock_amount": float(shock_amount),
        "histories": histories,
        "trajectories": trajectories,
        "equilibria": equilibria,
        "summary_rows": summary_rows,
    }


def plot_fairness_over_time(dyn: dict) -> Figure:
    """Plot fatigue spread (max-min) and variance trajectories across weeks."""
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    for label, traj in dyn["trajectories"].items():
        x = np.arange(len(traj))
        style = "--" if label == "Equal-load reference" else "-"
        axes[0].plot(x, np.ptp(traj, axis=1), linestyle=style, linewidth=1.8, label=label)
        axes[1].plot(x, np.var(traj, axis=1), linestyle=style, linewidth=1.8, label=label)
    axes[0].set(
        title="Fairness Curve: Fatigue Spread (max - min)",
        xlabel="Weeks at constant term-average load",
        ylabel="Spread (weekly-load units)",
    )
    axes[1].set(
        title="Fairness Curve: Fatigue Variance Over Time",
        xlabel="Weeks at constant term-average load",
        ylabel="Variance",
    )
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


def plot_fatigue_trajectories(dyn: dict, active_label: str | None = None) -> Figure:
    """Plot observed block-end peak fatigue and long-run equilibrium convergence."""
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    threshold = dyn["threshold"]

    for label, hist in dyn["histories"].items():
        axes[0].plot(range(len(hist)), hist.max(axis=1), marker="o", linewidth=1.8, label=label)
    axes[0].axhline(threshold, color="crimson", linestyle="--", linewidth=1.2, label=f"Soft H={threshold:.2f}")
    axes[0].set(
        title="Observed Within-Term Peak Fatigue",
        xlabel="Observed week block boundary",
        ylabel="Max staff fatigue proxy",
    )
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(fontsize=8)

    chosen = active_label if active_label in dyn["trajectories"] else next(iter(dyn["trajectories"]))
    traj = dyn["trajectories"][chosen]
    eq = dyn["equilibria"][chosen]
    x = np.arange(len(traj))
    axes[1].fill_between(x, traj.min(axis=1), traj.max(axis=1), alpha=0.25, label="Staff min-max band")
    axes[1].plot(x, traj.mean(axis=1), linewidth=2.0, label="Staff mean F[n]")
    axes[1].axhline(float(eq.mean()), color="black", linestyle=":", linewidth=1.3, label=f"Mean F*={eq.mean():.2f}")
    axes[1].axhline(threshold, color="crimson", linestyle="--", linewidth=1.2, label=f"Soft H={threshold:.2f}")
    axes[1].set(
        title=f"Long-Run Trajectory & Equilibrium ({chosen})",
        xlabel="Weeks at constant term-average load",
        ylabel="Fatigue proxy",
    )
    axes[1].grid(True, alpha=0.25)
    axes[1].legend(fontsize=8)
    fig.tight_layout()
    return fig


def plot_workload_distribution(inst: Instance, schedules: dict[str, object]) -> Figure:
    """Plot sorted total session loads per invigilator across schedules."""
    fig, ax = plt.subplots(figsize=(10, 3.3))
    ranks = np.arange(1, len(inst.staff_ids) + 1)
    for label, pairs in schedules.items():
        ordered = sorted(staff_loads(inst, pairs), reverse=True)
        ax.plot(ranks, ordered, marker=".", linewidth=1.6, label=label)
    mean_load = sum(inst.demand) / len(inst.staff_ids)
    ax.axhline(mean_load, color="black", linestyle=":", linewidth=1.1, label=f"Mean={mean_load:.2f}")
    ax.set(
        title="Sorted Total Session Load Profile Across Staff",
        xlabel="Invigilator rank (sorted descending by load)",
        ylabel="Assigned sessions",
    )
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


def observed_block_summary(inst: Instance, assigned, parameters: dict | None = None) -> list[dict]:
    """Summarize each calendar week block's assignments, rate and end-of-block fatigue."""
    wl = weekly_workload(inst, assigned)
    params = (
        FALLBACK_PARAMETERS
        if parameters is None
        else FatigueParameters(**parameters)
    )
    hist = simulate_history(wl, params)
    rows = []
    for k, (start, days) in enumerate(zip(wl.starts, wl.days)):
        rows.append({
            "week": k + 1,
            "start": start.isoformat(),
            "days": int(days),
            "assignments": int(wl.counts[k].sum()),
            "mean_weekly_rate": round(float(wl.rates[k].mean()), 4),
            "max_fatigue_end": round(float(hist[k + 1].max()), 4),
            "spread_fatigue_end": round(float(np.ptp(hist[k + 1])), 4),
        })
    return rows
