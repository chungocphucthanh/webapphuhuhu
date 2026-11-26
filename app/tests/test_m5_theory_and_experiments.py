"""Tests for slide-grounded theory integration and interactive M1-M4 experiments (M5)."""

from __future__ import annotations

import pytest

from app.data_views import load_preset_instance
from app.experiments import (
    derive_weights_from_seed,
    evaluate_custom_automata,
    pumping_lemma_demo,
    rebuild_instance_with_seed,
    run_m1_what_if,
    run_m2_counterexample_h2,
    run_m2_counterexample_lp,
    run_m2_what_if,
    run_m4_what_if,
    solve_with_custom_automata,
)
from m2_ilp.fixtures import week_slice
from m2_ilp.instance import build_instance, toy_instance


def test_m1_what_if_flips_sat_unsat_and_tracks_original_violations():
    toy_data, _ = load_preset_instance("toy")
    unsat = run_m1_what_if(toy_data, session_idx=0, extra_busy_staff=(1,))
    assert unsat["baseline"]["satisfiable"] is True
    assert unsat["experiment"]["satisfiable"] is False
    assert unsat["experiment"]["unsat_core"]

    relaxed = run_m1_what_if(toy_data, enforce_h1=False)
    assert relaxed["experiment"]["satisfiable"] is True
    assert relaxed["experiment"]["n_clauses"] < relaxed["baseline"]["n_clauses"]

    slice_data, _ = load_preset_instance("m1_slice", m1_scenario="sat")
    over_demand = run_m1_what_if(slice_data, session_idx=0, demand_delta=1)
    assert over_demand["experiment"]["satisfiable"] is True
    assert over_demand["orig_violations"]["H3"] == 1


def test_m2_seed_soft_and_counterexample_experiments():
    w1 = week_slice(build_instance(), 1)
    w_default = derive_weights_from_seed(w1.seed)
    w_alt = derive_weights_from_seed(1048291731)
    assert w_default == [0.84, 1.9, 1.97]
    assert w_alt != w_default

    rebuilt = rebuild_instance_with_seed(w1, 1048291731)
    assert rebuilt.soft_weights == w_alt
    assert set(w1.baseline) <= rebuilt.A

    res = run_m2_what_if(w1, custom_seed=1048291731, fatigue_k=1, weight_scale=(2.0, 1.0, 1.0))
    assert res["exp_status"] == "optimal"
    assert res["exp_metrics"] is not None
    assert res["exp_weights"] != res["base_weights"]

    no_soft = run_m2_what_if(w1, use_soft=False)
    assert no_soft["exp_weights"] == (0.0, 0.0, 0.0)

    ce_h2 = run_m2_counterexample_h2(w1, mode="canonical_9day", use_soft=False)
    assert ce_h2["has_example"] is True
    assert any(row["staff"] == "CB032" for row in ce_h2["double_booked"])

    ce_lp = run_m2_counterexample_lp(toy_instance(), mode="brief_example")
    assert ce_lp["z_lp"] == "4/3" and ce_lp["z_ilp"] == 2
    assert ce_lp["fractional_pairs"] == 3 and ce_lp["rounded_violations"]


def test_m3_custom_rules_pumping_lemma_and_ilp_resolve():
    w1 = week_slice(build_instance(), 1)
    inst = build_instance()

    strict = evaluate_custom_automata(inst, inst.baseline, enforce_r1=True, max_consecutive=1, enforce_r2=True, enforce_r3=True)
    loose = evaluate_custom_automata(inst, inst.baseline, enforce_r1=True, max_consecutive=4, enforce_r2=False, enforce_r3=False)
    assert strict["minimal_states"] != loose["minimal_states"]
    assert strict["custom_accepted"] < strict["std_accepted"] <= loose["custom_accepted"]

    with_r4 = evaluate_custom_automata(inst, inst.baseline, enforce_r4=True, r4_bound=3)
    assert with_r4["minimal_states"] == 99

    solved = solve_with_custom_automata(w1, evaluate_custom_automata(w1, w1.baseline, max_consecutive=1)["minimal_dfa"])
    assert solved["assigned"] and solved["accepted"] == len(w1.staff_ids)

    pump = pumping_lemma_demo(p=3, x_len=0, y_len=1, pump_i=0, r4_bound=3)
    assert pump["s"] == "MMMAAA" and pump["pumped"] == "MMAAA"
    assert pump["contradiction"] is True and pump["in_l_prime"] is False
    assert pump["r4_accepts_s"] is True and pump["r4_accepts_pumped"] is True


def test_m4_what_if_covers_stable_neutral_and_unstable_regimes():
    inst = build_instance()
    sched = {"Baseline": inst.baseline}

    slow = run_m4_what_if(inst, sched, "Baseline", a=0.80, b=0.20, r=0.0, coverage=0.85, weeks=20)
    assert slow["exp_stability"]["classification"] == "asymptotically stable"
    assert slow["exp_eq"] is not None and slow["exp_threshold"] is not None

    neutral = run_m4_what_if(inst, sched, "Baseline", a=1.0, b=1.0, r=0.0, weeks=10)
    assert neutral["exp_stability"]["classification"] == "neutral"
    assert neutral["exp_eq"] is None

    unstable = run_m4_what_if(inst, sched, "Baseline", a=1.08, b=0.5, r=0.0, weeks=10)
    assert unstable["exp_stability"]["classification"] == "unstable"
