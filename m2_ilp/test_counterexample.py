"""Checks for the two wrong models of req 2.10 (TV2)."""

from fractions import Fraction

from m2_ilp.config import ModelConfig
from m2_ilp.counterexample import (double_bookings, drop_overlap_example, full_data_effect,
                                   relax_integrality_example)
from m2_ilp.fixtures import clique_instance
from m2_ilp.instance import build_instance


def test_relaxed_lp_reports_four_thirds_with_fractional_people():
    result = relax_integrality_example()
    assert result["z_lp"] == "4/3" and result["z_ilp"] == 2
    assert Fraction(result["z_lp"]) < result["z_ilp"]          # Z_LP <= Z_ILP, strictly here
    assert result["lp_loads"] == ["4/3", "4/3", "4/3"]
    assert result["fractional_pairs"] > 0
    assert result["rounded_lp_violations"]                      # rounding breaks capacity
    assert result["ilp_loads"] == [2, 1, 1] and result["ilp_violations"] == []


def test_dropping_h2_double_books_and_looks_fairer():
    tight = build_instance(availability="seeded", flip_rate=0.0)   # M1 Busy reading
    result = drop_overlap_example(tight, ModelConfig(use_soft=False))
    assert result["slice"] is not None
    right, wrong = result["correct"], result["wrong"]
    assert right["violations"] == 0 and wrong["violations"] > 0
    assert (wrong["max_load"], wrong["l1"]) < (right["max_load"], right["l1"])
    assert result["double_booked"]
    assert all(msg.startswith("H2: ") for msg in result["validator"])
    row = result["double_booked"][0]
    assert row["times"][0] == row["times"][1]                    # same shift, two campuses


def test_on_full_data_the_wrong_model_falsely_beats_the_baseline():
    tight = build_instance(availability="seeded", flip_rate=0.0)
    result = full_data_effect(tight, ModelConfig(), baseline_max_load=19)
    assert result["correct"]["max_load"] == 19 and not result["correct_beats_baseline"]
    assert result["wrong_claims_beats_baseline"] and result["wrong"]["violations"] > 0


def test_double_bookings_lists_every_overlapping_pair():
    inst = clique_instance()
    rows = double_bookings(inst, {(1, 0), (1, 1), (1, 2)})
    assert [r["sessions"] for r in rows] == [["S0", "S1"], ["S0", "S2"], ["S1", "S2"]]
    assert {r["staff"] for r in rows} == {"CB2"}
