"""Checks for the infeasibility diagnosis and sensitivity tables (TV5, req 2.8)."""

from dataclasses import replace

from m2_ilp.config import ModelConfig, SOFT_NAMES
from m2_ilp.fixtures import lp_gap_instance
from m2_ilp.instance import build_instance, toy_instance
from m2_ilp.solve import solve
from m2_ilp.tuning import diagnose, k_sensitivity, m1_unsat_demo, weight_sensitivity


def short_toy():
    """Toy with CB2 also busy in the morning: only CB3 is left for a 2-person session."""
    toy = toy_instance()
    return replace(toy, A=toy.A - {(1, 0)})


def test_feasible_instance_has_an_empty_diagnosis():
    assert diagnose(toy_instance(), ModelConfig()) == []


def test_infeasible_solve_reports_the_short_session():
    expected = [{"session": "Morning", "demand": 2, "missing": 1}]
    assert diagnose(short_toy(), ModelConfig()) == expected
    solution = solve(short_toy(), ModelConfig())
    assert solution.status == "infeasible"
    assert solution.assigned == frozenset() and solution.t_star is None
    assert solution.diagnosis == expected


def test_diagnosis_matches_the_m1_unsat_core():
    demo = m1_unsat_demo(build_instance().seed, ModelConfig())
    assert demo["m2_status"] == "infeasible"
    missing = [row["session"] for row in demo["m2_missing"]]
    assert missing and all(name.startswith(demo["shortage_shift"] + "_") for name in missing)
    # The M1 core names the same capacity row that the elastic slack has to cover.
    assert any(f"capacity({name})" in clause for name in missing for clause in demo["m1_unsat_core"])
    assert sum(row["missing"] for row in demo["m2_missing"]) == (
        demo["demand_at_shortage"] - demo["available_at_shortage"])


def test_sensitivity_tables_have_one_row_per_setting():
    inst = lp_gap_instance()
    rows = weight_sensitivity(inst, ModelConfig())
    assert [(r["weight"], r["factor"]) for r in rows] == [
        (name, f) for name in SOFT_NAMES for f in (0.5, 1.0, 2.0)]
    base = [r for r in rows if r["factor"] == 1.0]
    assert all({**r, "weight": None, "lambda": None} == {**base[0], "weight": None, "lambda": None}
               for r in base)
    assert {r["max_load"] for r in rows} == {2}
    ks = k_sensitivity(inst, ModelConfig())
    assert [r["k"] for r in ks] == [2, 3, 4]
    assert set(ks[0]) >= {"k", "value", "max_load", "l1", "location", "fatigue", "travel", "runtime"}
