"""Tests for M1 SAT checking, bounded-time M2/M3/M4 solving and M3 product_min wiring (M5, Hung)."""

from dataclasses import replace
import tempfile
from pathlib import Path

from app.solver_views import compare_schedule_metrics, run_m1_check, solve_schedule_in_app
from m1_logic.prepare_instances import prepare_instances
from m2_ilp.fixtures import week_slice
from m2_ilp.instance import build_instance, toy_instance
from m3_automata.product_min import minimize, product
from m3_automata.regular_to_ilp import combined_dfa, load_rules, roster_strings, violations


def test_combined_dfa_uses_product_min_exact_states():
    rules = load_rules()
    minimal, full = combined_dfa(rules)
    expected_full = product(list(rules.values()))
    expected_min = minimize(expected_full)
    assert full.to_dict() == expected_full.to_dict()
    assert minimal.to_dict() == expected_min.to_dict()
    assert (len(full.states), len(minimal.states)) == (259, 15)


def test_m1_sat_and_unsat_core_checks():
    seed = build_instance().seed
    with tempfile.TemporaryDirectory() as folder:
        cases = prepare_instances(seed, output_dir=Path(folder))

    sat_out = run_m1_check(cases["sat"])
    assert sat_out["satisfiable"] is True
    assert sat_out["unsat_core"] is None
    assert isinstance(sat_out["model"], dict) and len(sat_out["model"]) == len(cases["sat"]["session_ids"])
    assert sat_out["n_cnf_vars"] >= sat_out["n_assign_vars"] > 0
    assert set(sat_out["linear_summary"]) >= {"capacity", "busy"}

    unsat_out = run_m1_check(cases["unsat"])
    assert unsat_out["satisfiable"] is False
    assert unsat_out["model"] is False
    assert unsat_out["unsat_core"] and any("capacity(" in c for c in unsat_out["unsat_core"])


def test_in_app_solver_variants_and_infeasible_diagnosis():
    toy = toy_instance()
    res_m2 = solve_schedule_in_app(toy, time_limit=10)
    assert res_m2["status"] == "optimal"
    assert len(res_m2["assigned"]) == sum(toy.demand) == 4
    assert res_m2["hard_violations"] == []

    res_m4 = solve_schedule_in_app(toy, include_m4_soft=True, time_limit=10)
    assert res_m4["status"] == "optimal"
    assert res_m4["calibrated_m4_from_data"] is False

    short = replace(toy, A=set(toy.A) - {(1, 0)})
    infeas = solve_schedule_in_app(short, time_limit=10)
    assert infeas["status"] == "infeasible"
    assert infeas["assigned"] == frozenset()
    assert infeas["diagnosis"] == [{"session": "Morning", "demand": 2, "missing": 1}]

    w1 = week_slice(build_instance(), 1)
    res_m3 = solve_schedule_in_app(w1, enforce_m3=True, time_limit=15)
    assert res_m3["status"] == "optimal"
    dfa, _ = combined_dfa(load_rules())
    assert violations(roster_strings(w1, res_m3["assigned"]), {"R1xR2xR3": dfa})["any"] == 0

    comp = compare_schedule_metrics(toy, {"Baseline": toy.baseline, "M2": res_m2["assigned"]})
    assert len(comp) == 2 and all(row["hard_violations"] == 0 for row in comp)
