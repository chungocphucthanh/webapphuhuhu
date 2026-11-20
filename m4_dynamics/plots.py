"""Headless, standalone figures for the M4 report and future app."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def write_plots(out_dir, histories, trajectories, equilibria, threshold):
    labels = {"baseline": "Baseline", "m2": "M2", "fatigue_aware": "M4 fatigue-aware",
              "equal_load": "Equal-load reference"}

    def save(fig, name):
        fig.tight_layout()
        fig.savefig(out_dir / name, dpi=150, metadata={"Software": "CO2011 M4"})
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    for name, history in histories.items():
        ax.plot(range(len(history)), history.max(axis=1), marker="o", label=labels[name])
    ax.axhline(threshold, color="black", linestyle="--", label="Soft threshold")
    ax.set(xlabel="Observed week block boundary",
           ylabel="Maximum fatigue proxy", title="Observed weekly loads")
    ax.legend()
    save(fig, "observed_fatigue.png")

    fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex=True)
    for ax, (name, trajectory) in zip(axes.flat, trajectories.items()):
        weeks = np.arange(len(trajectory))
        ax.fill_between(weeks, trajectory.min(axis=1), trajectory.max(axis=1), alpha=0.25,
                        label="Staff range")
        ax.plot(weeks, trajectory.mean(axis=1), label="Staff mean")
        ax.axhline(equilibria[name].mean(), color="black", linestyle=":", label="Mean equilibrium")
        ax.axhline(threshold, color="red", linestyle="--", linewidth=0.8, label="Soft threshold")
        ax.set(title=labels[name], xlabel="Weeks at constant term-average load", ylabel="Fatigue proxy")
    axes.flat[0].legend(fontsize=8)
    save(fig, "fatigue_equilibrium.png")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for name, trajectory in trajectories.items():
        axes[0].plot(np.ptp(trajectory, axis=1), label=labels[name])
        axes[1].plot(np.var(trajectory, axis=1), label=labels[name])
    for ax, ylabel in zip(axes, ("Fatigue spread (max-min)", "Fatigue variance")):
        ax.set(xlabel="Weeks at constant term-average load", ylabel=ylabel)
        ax.legend(fontsize=8)
    save(fig, "fairness.png")
