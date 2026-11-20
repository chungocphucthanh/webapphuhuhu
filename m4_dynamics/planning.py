"""Direction B's soft fatigue threshold, composed with the completed M2 model."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import pulp

from m2_ilp.config import ModelConfig
from m2_ilp.metrics import compute_metrics
from m2_ilp.model import build_model
from m2_ilp.soft import fit_fatigue_k
from m2_ilp.solve import run_cbc

from .fatigue import block_coefficients, simulate_history, threshold_penalty
from .workload import week_layout, weekly_workload


@dataclass
class FatigueHandles:
    states: dict
    excess: dict
    penalty: object


def add_fatigue_soft_constraints(prob, x, inst, parameters, threshold, initial=None):
    """Add F[k,i]<=H+s[k,i], s>=0, and the exact linear recurrence.

    Returns the unweighted sum of s. The caller adds a positive penalty weight
    to its objective. No assignment is forbidden merely for exceeding H.
    Can also be composed with M3's regular constraints on the same x variables.
    """
    n = len(inst.staff_ids)
    initial = np.zeros(n) if initial is None else np.asarray(initial, dtype=float)
    if (initial.shape != (n,) or not np.isfinite(initial).all()
            or not math.isfinite(threshold) or threshold < 0):
        raise ValueError("Need one finite initial state per staff and a nonnegative threshold")
    _, days, week = week_layout(inst)
    groups = {}
    for (i, j), var in sorted(x.items()):
        groups.setdefault((week[j], i), []).append(var)
    states, excess = {}, {}
    for i in range(n):
        states[0, i] = float(initial[i])
    for k in range(len(days) + 1):
        for i in range(n):
            if k:
                retention, gain = block_coefficients(parameters, int(days[k - 1]))
                load = 7 / int(days[k - 1]) * pulp.lpSum(groups.get((k - 1, i), []))
                states[k, i] = pulp.LpVariable(f"m4F_{k}_{i}", lowBound=None)
                prob += (states[k, i] == retention * states[k - 1, i] + gain * load,
                         f"M4REC_{k}_{i}")
            excess[k, i] = pulp.LpVariable(f"m4excess_{k}_{i}", lowBound=0)
            prob += states[k, i] <= threshold + excess[k, i], f"M4THRESH_{k}_{i}"
    return FatigueHandles(states, excess, pulp.lpSum(excess.values()))


def refine_schedule(inst, original, parameters, threshold):
    """One finite-horizon solve with a fixed M2 max-load cap; no rolling feedback."""
    weekly_workload(inst, original)
    k = fit_fatigue_k(inst)
    before = compute_metrics(inst, original, k)
    config = ModelConfig(stage=2, t_cap=before["max_load"], fatigue_k=k)
    prob, x, _ = build_model(inst, config)
    handles = add_fatigue_soft_constraints(prob, x, inst, parameters, threshold)
    weight = inst.soft_weight_map["fatigue"]
    prob.setObjective(prob.objective + weight * handles.penalty)
    result = run_cbc(prob, config)
    if result.status != "optimal":
        raise RuntimeError(f"M4 threshold refinement is {result.status}; optimality unverified")
    assigned = frozenset(pair for pair, var in x.items() if var.varValue > 0.5)
    workload = weekly_workload(inst, assigned)  # independent H1-H3 validation
    history = simulate_history(workload, parameters)
    measured = threshold_penalty(history, threshold)
    modeled = float(pulp.value(handles.penalty))
    if not math.isclose(modeled, measured, abs_tol=1e-5):
        raise RuntimeError("M4 solver penalty disagrees with independent simulation")
    state_error = max(abs(float(pulp.value(value)) - history[t, i])
                      for (t, i), value in handles.states.items())
    if state_error > 1e-5:
        raise RuntimeError("M4 solver trajectory disagrees with independent simulation")
    info = {
        "status": result.status,
        "max_load_cap": before["max_load"],
        "objective": result.objective,
        "penalty_weight": weight,
        "threshold_penalty": measured,
        "modeled_threshold_penalty": modeled,
        "trajectory_check_max_error": state_error,
        "hard_rule_violations": 0,
        "metrics": compute_metrics(inst, assigned, k),
        "scope": "M2 hard rules and soft objective plus M4 trajectory excess; one solve",
    }
    return assigned, info
