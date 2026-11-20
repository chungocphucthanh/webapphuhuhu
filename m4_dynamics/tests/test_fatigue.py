"""Independent numerical checks of the recurrence and its mathematical claims."""

from dataclasses import replace
from datetime import date, datetime

import numpy as np
import pytest

from m2_ilp.instance import build_instance, toy_instance
from m4_dynamics.fatigue import (FatigueParameters, calibrate, fit_threshold,
                                fixed_point, simulate, simulate_history, stability,
                                step, threshold_penalty)
from m4_dynamics.workload import WeeklyWorkload, weekly_workload


def test_brief_worked_example_and_nonzero_rest():
    parameters = FatigueParameters(a=0.8, b=2)
    history = simulate([1], parameters, weeks=100)
    assert history[:4, 0] == pytest.approx([0, 2, 3.6, 4.88])
    assert fixed_point([1], parameters) == pytest.approx([10])
    assert history[-1] == pytest.approx([10], abs=1e-8)
    parameters = FatigueParameters(a=0.75, b=2, r=0.5)
    equilibrium = fixed_point([4], parameters, rest=[1])
    assert equilibrium == pytest.approx([30])
    assert step(equilibrium, [4], parameters, rest=[1]) == pytest.approx(equilibrium)


def test_equal_load_contracts_spread_and_variance_from_unequal_states():
    parameters = FatigueParameters(a=0.8, b=0.2)
    initial = np.array([0, 3, 9, 1])
    history = simulate([2] * 4, parameters, initial=initial, weeks=100)
    time = np.arange(101)
    np.testing.assert_allclose(np.ptp(history, axis=1), np.ptp(initial) * 0.8 ** time, atol=1e-14)
    np.testing.assert_allclose(np.var(history, axis=1), np.var(initial) * 0.8 ** (2*time), atol=1e-14)
    np.testing.assert_allclose(history[-1], [2] * 4, atol=2e-9)


def test_unequal_loads_have_different_fixed_points():
    parameters = FatigueParameters(a=0.8, b=0.2)
    load = [1, 2, 5]
    equilibrium = fixed_point(load, parameters)
    np.testing.assert_allclose(equilibrium, load)
    np.testing.assert_allclose(simulate(load, parameters, weeks=150)[-1], equilibrium, atol=1e-12)
    assert np.ptp(equilibrium) == pytest.approx(4)


@pytest.mark.parametrize("a,label", [(0.8, "asymptotically stable"), (-0.8, "asymptotically stable"),
                                    (1, "neutral"), (-1, "neutral"), (1.1, "unstable"),
                                    (-1.1, "unstable")])
def test_classification_agrees_with_perturbation_growth(a, label):
    parameters = FatigueParameters(a=a, b=1)
    history = simulate([0], parameters, initial=[0.001], weeks=20)
    assert stability(parameters)["classification"] == label
    assert abs(history[-1, 0]) == pytest.approx(0.001 * abs(a) ** 20)
    if a == 1:
        with pytest.raises(ValueError, match="no unique fixed point"):
            fixed_point([1], parameters)


def test_known_regression_is_estimated_then_equilibrium_is_calibrated():
    # Each person's next load is 0.5 * previous + 4.
    workload = WeeklyWorkload((date(2026, 1, 1),) * 3, np.array([7, 7, 7]),
                              np.array([[0, 8], [4, 8], [6, 8]]))
    parameters, evidence = calibrate(workload)
    assert parameters == FatigueParameters(a=0.5, b=0.5, r=0)
    assert evidence["workload_intercept"] == pytest.approx(4)
    assert evidence["workload_rmse"] == pytest.approx(0)
    assert evidence["observations"] == 4
    assert evidence["calibrated_mean_equilibrium"] == pytest.approx(workload.mean_load.mean())


def test_unsupported_data_cannot_silently_produce_stable_parameters():
    workload = WeeklyWorkload((date(2026, 1, 1),) * 3, np.array([7, 7, 7]),
                              np.array([[0, 2], [0, 4], [0, 8]]))
    with pytest.raises(ValueError, match="not clipped"):
        calibrate(workload)
    with pytest.raises(ValueError, match="cannot identify"):
        calibrate(replace(workload, counts=np.ones((3, 2))))
    with pytest.raises(ValueError, match="at least two"):
        calibrate(replace(workload, counts=workload.counts[:1]))


def test_calendar_gaps_and_partial_week_preserve_real_counts():
    toy = toy_instance()
    days = [date(2026, 1, 1), date(2026, 1, 16)]
    inst = replace(toy, day=days,
                   intervals=[(datetime(2026, 1, 1, 7), datetime(2026, 1, 1, 9)),
                              (datetime(2026, 1, 16, 13), datetime(2026, 1, 16, 15))])
    workload = weekly_workload(inst, inst.baseline)
    assert workload.days.tolist() == [7, 7, 2]
    assert workload.counts.sum(axis=1).tolist() == [2, 0, 2]
    np.testing.assert_allclose(workload.mean_load, np.array([1, 2, 1]) * 7 / 16)
    np.testing.assert_array_equal(workload.cumulative[-1], [1, 2, 1])
    with pytest.raises(ValueError, match="Duplicate assignments"):
        weekly_workload(inst, inst.baseline + inst.baseline[:1])


def test_partial_week_has_the_same_equilibrium_and_elapsed_time():
    workload = WeeklyWorkload((date(2026, 1, 1), date(2026, 1, 8)), np.array([7, 6]),
                              np.array([[7], [6]]))
    parameters = FatigueParameters(a=0.8, b=0.2)
    history = simulate_history(workload, parameters)
    assert history[-1, 0] == pytest.approx(7 * (1 - 0.8 ** (13 / 7)))
    np.testing.assert_allclose(simulate_history(workload, parameters, initial=[7]), [[7], [7], [7]])


def test_real_data_conservation_calibration_and_threshold():
    inst = build_instance()
    workload = weekly_workload(inst, inst.baseline)
    assert workload.days.tolist() == [7, 7, 7, 6]
    assert workload.counts.sum() == sum(inst.demand) == 769
    assert workload.counts.sum(axis=1).tolist() == [15, 103, 339, 312]
    parameters, _ = calibrate(workload)
    assert parameters.a == pytest.approx(0.2706343878437049, abs=1e-7)
    assert workload.mean_load.mean() == pytest.approx(769 * 7 / (73 * 27))
    history = simulate_history(workload, parameters)
    threshold = fit_threshold(history)
    assert (history[1:] <= threshold).mean() >= 0.95
    assert threshold_penalty(history, threshold) > 0
    assert threshold_penalty(history, history.max()) == 0


def test_bad_shapes_and_nonfinite_values_are_rejected():
    parameters = FatigueParameters(a=0.8, b=0.2)
    with pytest.raises(ValueError, match="matching sizes"):
        step([0, 1], [2], parameters)
    with pytest.raises(ValueError, match="finite"):
        FatigueParameters(a=float("nan"), b=1)
    with pytest.raises(ValueError, match="nonnegative integer"):
        simulate([1], parameters, weeks=-1)
    with pytest.raises(ValueError, match="coverage"):
        fit_threshold([[0], [1]], coverage=0)
