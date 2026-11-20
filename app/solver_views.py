"""M1 SAT feasibility check and bounded-time M2/M3/M4 solver services (M5, Hung)."""

from __future__ import annotations

from dataclasses import replace
import math
import time

import pulp

from m1_logic.cnf import encode_invigilator_assignment
from m1_logic.linear_bridge import CONVERSION_ROWS, encode_invigilator_assignment_linear
from m1_logic.sat_check import solve_instance
from m2_ilp.config import ModelConfig
from m2_ilp.instance import Instance
from m2_ilp.metrics import compute_metrics
from m2_ilp.model import build_model
from m2_ilp.soft import fit_fatigue_k
from m2_ilp.solve import Solution, _value, run_cbc, solve
from m2_ilp.tuning import diagnose
from m2_ilp.validate import check_schedule
from m3_automata.regular_to_ilp import add_rules_to_m2, combined_dfa, load_rules, solve_with_rules
from m4_dynamics.fatigue import (
    FatigueParameters,
    calibrate,
    fit_threshold,
    simulate_history,
)
from m4_dynamics.planning import add_fatigue_soft_constraints
from m4_dynamics.workload import weekly_workload

# Reference M4 calibration on the 27-day Faculty dataset, used only when a short
# slice or toy instance has fewer than two weekly blocks for lag-one OLS.
DEFAULT_M4_PARAMS = FatigueParameters(a=0.27063439282332274, b=0.7293656071766772, r=0.0)
DEFAULT_M4_THRESHOLD = 5.660327617142248


def run_m1_check(m1_data: dict) -> dict:
    """Encode CNF + linear bridge and run the Minisat22 SAT/UNSAT-core check."""
    t0 = time.perf_counter()
    staff_count = len(m1_data["staff_ids"])
    demands = m1_data["shift_demands"]
    busy = m1_data["busy"]
    overlaps = m1_data["overlaps"]

    cnf = encode_invigilator_assignment(staff_count, demands, busy, overlaps)
    sat_res = solve_instance(m1_data)
    linear = encode_invigilator_assignment_linear(staff_count, demands, busy, overlaps)
    runtime_ms = (time.perf_counter() - t0) * 1000.0

    assign_vars = staff_count * len(demands)
    baseline_map = {linear.var(i, j): 1 for i, j in m1_data.get("baseline", ())}
    return {
        "satisfiable": sat_res["satisfiable"],
        "model": sat_res["model"],
        "unsat_core": sat_res["unsat_core"],
        "n_staff": staff_count,
        "n_sessions": len(demands),
        "n_assign_vars": assign_vars,
        "n_cnf_vars": cnf.nv,
        "n_aux_vars": max(0, cnf.nv - assign_vars),
        "n_clauses": len(cnf.clauses),
        "linear_summary": linear.summary(),
        "linear_rows": len(linear.constraints),
        "baseline_linear_violations": (
            len(linear.violated(baseline_map)) if m1_data.get("baseline") else 0
        ),
        "bridge_rows": [
            {"rule": r, "fol": fol, "clause": cl, "dimacs": dm, "linear": ln}
            for r, fol, cl, dm, ln in CONVERSION_ROWS
        ],
        "runtime_ms": round(runtime_ms, 2),
    }


def _m4_params_for_instance(inst: Instance) -> tuple[FatigueParameters, float, bool]:
    """Calibrate (a, b, r) and H from inst.baseline when identifiable, else use defaults."""
    if inst.baseline:
        try:
            wl = weekly_workload(inst, inst.baseline)
            params, _ = calibrate(wl)
            hist = simulate_history(wl, params)
            return params, fit_threshold(hist), True
        except ValueError:
            pass
    return DEFAULT_M4_PARAMS, DEFAULT_M4_THRESHOLD, False


def _solve_with_m4_soft(
    inst: Instance,
    config: ModelConfig,
    *,
    enforce_m3: bool,
) -> tuple[Solution, bool]:
    """Two-stage solve adding M4's soft fatigue threshold (and optional M3 DFA flow)."""
    dfa = combined_dfa(load_rules())[0] if enforce_m3 else None
    prob1, x1, h1 = build_model(inst, replace(config, stage=1, t_cap=None))
    if dfa is not None:
        add_rules_to_m2(prob1, x1, inst, dfa)
    stage1 = run_cbc(prob1, config)
    if stage1.status not in ("optimal", "feasible"):
        return Solution(stage1.status, frozenset(), None, {}, {1: stage1}, diagnose(inst, config)), False

    t_star = round(pulp.value(h1.t))
    if not math.isclose(pulp.value(h1.t), t_star, abs_tol=1e-6):
        raise RuntimeError(f"Stage 1 returned fractional max load {pulp.value(h1.t)}")

    params, threshold, calibrated_live = _m4_params_for_instance(inst)
    prob2, x2, h2 = build_model(inst, replace(config, stage=2, t_cap=t_star))
    if dfa is not None:
        add_rules_to_m2(prob2, x2, inst, dfa)
    fh = add_fatigue_soft_constraints(prob2, x2, inst, params, threshold)
    prob2.setObjective(prob2.objective + config.lambdas(inst)[1] * fh.penalty)
    stage2 = run_cbc(prob2, config)

    if stage2.status in ("optimal", "feasible"):
        x, handles, status, kept = x2, h2, stage2.status, stage2
    else:
        x, handles, status, kept = x1, h1, "feasible", stage1
    assigned = frozenset(p for p, var in x.items() if (var.varValue or 0.0) > 0.5)
    terms = handles.soft_terms or {}
    obj = {
        "max_load": max((_value(w) for w in handles.w.values()), default=0.0),
        "l1": _value(handles.l1),
        "location": _value(terms.get("location")),
        "fatigue": _value(terms.get("fatigue")),
        "travel": _value(terms.get("travel")),
        "m4_excess": _value(fh.penalty) if x is x2 else 0.0,
        "total": kept.objective,
    }
    return Solution(status, assigned, t_star, obj, {1: stage1, 2: stage2}, None), calibrated_live


def solve_schedule_in_app(
    inst: Instance,
    *,
    enforce_m3: bool = False,
    include_m4_soft: bool = False,
    time_limit: int = 15,
    fatigue_k: int | None = None,
    weight_scale: tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> dict:
    """Run bounded-time CBC solve for M2, M2+M3 or M2(+M3)+M4 and validate H1-H3."""
    t0 = time.perf_counter()
    k = fit_fatigue_k(inst) if fatigue_k is None else fatigue_k
    config = ModelConfig(fatigue_k=k, time_limit=time_limit, weight_scale=weight_scale)
    calibrated_live = True

    if include_m4_soft:
        solution, calibrated_live = _solve_with_m4_soft(inst, config, enforce_m3=enforce_m3)
    elif enforce_m3:
        dfa, _ = combined_dfa(load_rules())
        solution, _, _ = solve_with_rules(inst, config, dfa)
        if not solution.assigned and solution.diagnosis is None:
            solution = replace(solution, diagnosis=diagnose(inst, config))
    else:
        solution = solve(inst, config)

    runtime_s = time.perf_counter() - t0
    if not solution.assigned:
        return {
            "status": solution.status,
            "assigned": frozenset(),
            "t_star": None,
            "fatigue_k": k,
            "metrics": None,
            "baseline_metrics": None,
            "beats_baseline": False,
            "hard_violations": [],
            "diagnosis": solution.diagnosis or [],
            "runtime_s": round(runtime_s, 3),
            "enforce_m3": enforce_m3,
            "include_m4_soft": include_m4_soft,
            "calibrated_m4_from_data": calibrated_live,
        }

    hard_violations = check_schedule(inst, solution.assigned)
    if hard_violations:
        raise RuntimeError("Solver produced hard-rule violations:\n" + "\n".join(hard_violations[:10]))

    metrics = compute_metrics(inst, solution.assigned, k)
    baseline_valid = (
        bool(inst.baseline)
        and len(inst.baseline) == sum(inst.demand)
        and not check_schedule(inst, inst.baseline)
    )
    baseline_metrics = compute_metrics(inst, inst.baseline, k) if baseline_valid else None
    beats = bool(baseline_metrics and metrics["max_load"] < baseline_metrics["max_load"])
    return {
        "status": solution.status,
        "assigned": solution.assigned,
        "t_star": solution.t_star,
        "fatigue_k": k,
        "metrics": metrics,
        "baseline_metrics": baseline_metrics,
        "beats_baseline": beats,
        "hard_violations": hard_violations,
        "diagnosis": [],
        "runtime_s": round(runtime_s, 3),
        "enforce_m3": enforce_m3,
        "include_m4_soft": include_m4_soft,
        "calibrated_m4_from_data": calibrated_live,
    }


def compare_schedule_metrics(
    inst: Instance,
    schedules: dict[str, object],
    *,
    fatigue_k: int | None = None,
) -> list[dict]:
    """Build a side-by-side M2 fairness and soft-penalty table across schedules."""
    k = fit_fatigue_k(inst) if fatigue_k is None else fatigue_k
    lambdas = ModelConfig(fatigue_k=k).lambdas(inst)
    base_max = (
        compute_metrics(inst, inst.baseline, k)["max_load"]
        if inst.baseline
        and len(inst.baseline) == sum(inst.demand)
        and not check_schedule(inst, inst.baseline)
        else None
    )
    rows = []
    for label, pairs in schedules.items():
        assigned = frozenset(pairs)
        m = compute_metrics(inst, assigned, k)
        stage2_obj = (
            m["l1"]
            + lambdas[0] * m["location"]
            + lambdas[1] * m["fatigue"]
            + lambdas[2] * m["travel"]
        )
        rows.append({
            "schedule": label,
            "assignments": len(assigned),
            "max_load": m["max_load"],
            "min_load": m["min_load"],
            "spread": m["spread"],
            "l1": round(m["l1"], 4),
            "location": m["location"],
            "fatigue": m["fatigue"],
            "travel": m["travel"],
            "stage2_objective": round(stage2_obj, 4),
            "hard_violations": len(check_schedule(inst, assigned)),
            "beats_baseline": bool(base_max is not None and m["max_load"] < base_max),
        })
    return rows
