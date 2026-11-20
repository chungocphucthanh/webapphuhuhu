"""Tests for M4 dynamical evaluation, perturbation decay and Matplotlib figures (M5, Nguyen)."""

from pathlib import Path

from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np
import pytest

from app.dynamics_views import (
    evaluate_dynamics,
    plot_fairness_over_time,
    plot_fatigue_trajectories,
    plot_workload_distribution,
)
from m2_ilp.instance import build_instance, toy_instance
from m4_dynamics.workload import read_schedule


def test_full_dynamics_matches_m4_calibration_and_equilibrium():
    inst = build_instance()
    m2_path = Path(__file__).resolve().parents[2] / "m2_ilp" / "schedule.csv"
    m2_assigned = read_schedule(inst, m2_path)
    dyn = evaluate_dynamics(inst, {"Baseline": inst.baseline, "M2": m2_assigned}, weeks=52)

    assert dyn["calibrated_from_data"] is True
    assert dyn["stability"]["classification"] == "asymptotically stable"
    assert dyn["parameters"]["a"] == pytest.approx(0.27063439, abs=1e-6)
    assert dyn["threshold"] == pytest.approx(5.6603276, abs=1e-6)

    by_name = {row["scenario"]: row for row in dyn["summary_rows"]}
    assert by_name["Equal-load reference"]["equilibrium_spread"] == pytest.approx(0.0, abs=1e-10)
    assert by_name["M2"]["equilibrium_spread"] < by_name["Baseline"]["equilibrium_spread"]
    assert all(row["final_max_error"] < 1e-8 for row in dyn["summary_rows"])


def test_perturbation_and_toy_fallback_plus_figures():
    inst = build_instance()
    shocked = evaluate_dynamics(
        inst, {"Baseline": inst.baseline}, weeks=52, shock_staff_index=0, shock_amount=5.0
    )
    eq_row = next(r for r in shocked["summary_rows"] if r["scenario"] == "Equal-load reference")
    assert eq_row["final_max_error"] < 1e-8
    eq_traj = shocked["trajectories"]["Equal-load reference"]
    a = shocked["parameters"]["a"]
    np.testing.assert_allclose(
        np.ptp(eq_traj, axis=1),
        np.ptp(eq_traj[0]) * (abs(a) ** np.arange(53)),
        atol=1e-12,
    )

    toy = toy_instance()
    toy_dyn = evaluate_dynamics(toy, {"Baseline": toy.baseline}, weeks=20)
    assert toy_dyn["calibrated_from_data"] is False

    figs = [
        plot_fairness_over_time(shocked),
        plot_fatigue_trajectories(shocked, "Baseline"),
        plot_workload_distribution(inst, {"Baseline": inst.baseline}),
    ]
    for fig in figs:
        assert isinstance(fig, Figure)
        assert len(fig.axes) >= 1
        plt.close(fig)


def test_invalid_dynamics_inputs_raise_value_error():
    from app.dynamics_views import observed_block_summary

    inst = build_instance()
    blocks = observed_block_summary(inst, inst.baseline)
    assert [b["assignments"] for b in blocks] == [15, 103, 339, 312]
    assert [b["days"] for b in blocks] == [7, 7, 7, 6]

    toy = toy_instance()
    with pytest.raises(ValueError, match="positive integer"):
        evaluate_dynamics(toy, {"Baseline": toy.baseline}, weeks=0)
    with pytest.raises(ValueError, match="at least one"):
        evaluate_dynamics(toy, {}, weeks=10)
