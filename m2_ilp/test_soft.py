"""Checks for the soft penalties LOC, FAT, TRV (TV5, req 2.5)."""

from dataclasses import replace

import pulp

from m2_ilp.config import ModelConfig
from m2_ilp.fixtures import forced_soft_instance, week_slice
from m2_ilp.instance import build_instance, toy_instance
from m2_ilp.model import build_model
from m2_ilp.soft import (daily_load_distribution, evaluate_soft, fit_fatigue_k,
                         location_cost)
from m2_ilp.solve import run_cbc


def solve_stage2(inst, config, t_cap):
    prob, x, handles = build_model(inst, replace(config, stage=2, t_cap=t_cap))
    result = run_cbc(prob, config)
    assert result.status == "optimal"
    assigned = {pair for pair, var in x.items() if var.varValue > 0.5}
    model_terms = {name: pulp.value(term) for name, term in handles.soft_terms.items()}
    return assigned, model_terms


def test_location_cost_only_penalises_a_campus_preference():
    inst = forced_soft_instance()
    assert [location_cost(inst, 0, j) for j in range(4)] == [0, 1, 0, 1]
    assert [location_cost(inst, 1, j) for j in range(4)] == [0, 0, 0, 0]   # BAL


def test_forced_penalties_match_between_model_and_evaluate_soft():
    inst = forced_soft_instance()
    assigned, terms = solve_stage2(inst, ModelConfig(), t_cap=4)
    assert assigned == {(0, 0), (0, 1), (0, 2), (0, 3)}
    assert evaluate_soft(inst, assigned, 3) == {"location": 2, "fatigue": 1, "travel": 1}
    assert terms == {"location": 2, "fatigue": 1, "travel": 1}


def test_evaluate_soft_equals_the_model_terms_on_a_real_slice():
    inst = week_slice(build_instance(), 3)
    for k in (2, 3):            # K = 2 adds FAT rows and changes the optimum (LOC 19 vs 17)
        config = ModelConfig(fatigue_k=k)
        stage1, x1, h1 = build_model(inst, config)
        run_cbc(stage1, config)
        assigned, terms = solve_stage2(inst, config, round(pulp.value(h1.t)))
        assert evaluate_soft(inst, assigned, k) == {name: round(v) for name, v in terms.items()}


def test_auxiliary_variables_exist_only_where_the_term_can_be_positive():
    inst = build_instance()
    k = ModelConfig().fatigue_k
    prob, x, handles = build_model(inst, ModelConfig(stage=2, t_cap=11))
    per_day, campuses = {}, {}
    for i, j in inst.A:
        per_day[i, inst.day[j]] = per_day.get((i, inst.day[j]), 0) + 1
        campuses.setdefault((i, inst.day[j]), set()).add(inst.campus[j])
    two_campus = sum(len(c) == 2 for c in campuses.values())
    assert handles.n_vars["s"] == handles.n_rows["FAT"] == sum(n > k for n in per_day.values())
    assert handles.n_vars["v"] == handles.n_rows["TRV"] == two_campus
    assert handles.n_vars["z"] == 2 * two_campus
    assert (handles.n_vars["s"], handles.n_vars["z"], handles.n_vars["v"]) == (207, 1002, 501)
    toy_prob, toy_x, toy_handles = build_model(toy_instance(), ModelConfig(stage=2, t_cap=2))
    assert not {"s", "z", "v"} & set(toy_handles.n_vars)


def test_k_is_fitted_from_the_baseline():
    inst = build_instance()
    assert daily_load_distribution(inst) == {1: 246, 2: 162, 3: 57, 4: 7}
    assert fit_fatigue_k(inst) == 3 == ModelConfig().fatigue_k
    assert fit_fatigue_k(inst, coverage=0.8) == 2
    assert evaluate_soft(inst, inst.baseline, 3) == {"location": 162, "fatigue": 7, "travel": 0}
