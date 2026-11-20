"""Checks for the hard constraints H1-H3 (TV2, req 2.4)."""

from itertools import product
from types import SimpleNamespace

import pulp
import pytest

from m1_logic.linear_bridge import encode_invigilator_assignment_linear
from m2_ilp.config import ModelConfig
from m2_ilp.fixtures import clique_instance
from m2_ilp.hard import add_hard_constraints, maximal_cliques
from m2_ilp.instance import build_instance, toy_instance
from m2_ilp.validate import check_schedule
from m2_ilp.variables import create_variables


def hard_model(inst, config=ModelConfig()):
    prob = pulp.LpProblem("hard", pulp.LpMinimize)
    x, w = create_variables(prob, inst, config)
    info = add_hard_constraints(prob, x, inst, config)
    return prob, x, info


def test_sweep_finds_the_three_clique_and_ignores_touching_endpoints():
    inst = clique_instance()
    assert maximal_cliques(inst) == [(0, 1, 2)]
    prob, x, info = hard_model(inst)
    # One clique row per person instead of three pairwise rows; no row touches S3.
    assert info["rows"] == {"H2": 3, "H3": 4, "H2_pairwise": 7}
    assert sorted(n for n in prob.constraints if n.startswith("H2")) == ["H2_0_0", "H2_1_0", "H2_2_0"]


def test_inconsistent_overlaps_are_rejected():
    inst = clique_instance()
    broken = SimpleNamespace(**{**vars(inst), "overlaps": [(0, 1)]})
    with pytest.raises(ValueError, match="overlap"):
        maximal_cliques(broken)


def test_real_data_cliques_are_the_18_cross_campus_pairs():
    inst = build_instance()
    cliques = maximal_cliques(inst)
    assert len(cliques) == 18 and all(len(c) == 2 for c in cliques)
    assert {tuple(c) for c in cliques} == set(inst.overlaps)
    for j, k in cliques:   # every overlap is the two campuses of one shift code
        assert inst.session_names[j].rsplit("_", 1)[0] == inst.session_names[k].rsplit("_", 1)[0]
    prob, x, info = hard_model(inst)
    # Every clique is a pair, so clique and pairwise rows coincide on the real data.
    assert info["rows"]["H2"] == info["rows"]["H2_pairwise"] == 642
    assert info["rows"]["H3"] == 83


def test_h1_is_asserted_and_flags_change_the_rows():
    inst = toy_instance()
    prob = pulp.LpProblem("h1", pulp.LpMinimize)
    x = {(0, 0): pulp.LpVariable("x_0_0", cat="Binary")}   # CB1 is busy in the morning
    with pytest.raises(AssertionError, match="H1"):
        add_hard_constraints(prob, x, inst, ModelConfig())
    prob, x, info = hard_model(clique_instance(), ModelConfig(drop_overlap=True))
    assert info["rows"]["H2"] == 0 and not any(n.startswith("H2") for n in prob.constraints)
    prob, x, info = hard_model(clique_instance(), ModelConfig(elastic=True))
    assert sorted(v.name for v in info["slack"].values()) == ["u_0", "u_1", "u_2", "u_3"]
    assert "u_0" in str(prob.constraints["H3_0"])


def test_hard_py_m1_bridge_and_validator_accept_the_same_schedules():
    """TV2-3: enumerate all 2^12 schedules of the 12-pair instance."""
    inst = clique_instance()
    n, m = len(inst.staff_ids), len(inst.session_names)
    prob, x, info = hard_model(inst)
    busy = [(i, j) for i in range(n) for j in range(m) if (i, j) not in inst.A]
    m1 = encode_invigilator_assignment_linear(n, inst.demand, busy, inst.overlaps)
    pairs = [(i, j) for i in range(n) for j in range(m)]
    by_hard, by_m1, by_validator = set(), set(), set()
    for bits in product((0, 1), repeat=len(pairs)):
        schedule = frozenset(p for p, bit in zip(pairs, bits) if bit)
        if schedule <= inst.A:      # H1: a pair outside A has no variable at all
            for pair, var in x.items():
                var.varValue = int(pair in schedule)
            if all(c.valid() for c in prob.constraints.values()):
                by_hard.add(schedule)
        if m1.is_feasible({m1.var(i, j): int((i, j) in schedule) for i, j in pairs}):
            by_m1.add(schedule)
        if not check_schedule(inst, schedule):
            by_validator.add(schedule)
    assert by_hard == by_m1 == by_validator
    assert 0 < len(by_hard) < 2 ** len(pairs)


def test_clique_row_is_tighter_than_pairwise_rows_for_the_lp():
    """x = 1/2 on the three overlapping sessions satisfies every pairwise row of M1
    (1/2 + 1/2 <= 1) but not the clique row (3/2 > 1): same integers, smaller LP."""
    inst = clique_instance()
    prob, x, info = hard_model(inst)
    half = {(1, 0): 0.5, (1, 1): 0.5, (1, 2): 0.5}
    for pair, var in x.items():
        var.varValue = half.get(pair, 0)
    assert all(half[1, j] + half[1, k] <= 1 for j, k in inst.overlaps)
    assert not prob.constraints["H2_1_0"].valid()
