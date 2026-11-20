"""Checks for the regular-to-ILP flow model and its link to M2 (Hung, req 3.3).

Run from the repository root: python -m pytest m3_automata/tests/test_regular_to_ilp.py
"""

from datetime import date, datetime
from itertools import product
from random import Random

import pulp
import pytest

from m2_ilp.config import ModelConfig, TEAM_ID
from m2_ilp.instance import Instance, build_instance
from m2_ilp.solve import solve
from m2_ilp.validate import check_schedule
from m3_automata.dfa import ALPHABET
from m3_automata.encode_strings import encode_strings
from m3_automata.regular_to_ilp import (
    add_regular_constraint, brute_force_best, brute_force_check, calendar, check_rule_solution,
    class_summary, combined_dfa, flow_ilp_best, full_graph_edges, layered_edges, live_states,
    load_rules, random_case, roster_strings, sessions_by_class, solve_with_rules, violations)
from tools.make_seed import seed_for, soft_weights

SEED = seed_for(TEAM_ID)


@pytest.fixture(scope="module")
def machines():
    rules = load_rules()
    return {**rules, "R1xR2xR3": combined_dfa(rules)[0]}


def test_session_classes_match_the_data():
    inst = build_instance()
    summary = class_summary(inst)
    assert summary["baseline_rows"] == {"M": 347, "A": 395, "N": 27}
    assert summary["sessions"] == {"M": 35, "A": 37, "N": 11}
    assert (summary["calendar_days"], summary["exam_days"], summary["staff_with_night"]) == (27, 23, 9)
    groups = sessions_by_class(inst)
    assert sorted(j for js in groups.values() for j in js) == list(range(len(inst.session_names)))
    days = calendar(inst)
    assert all(inst.day[j] == days[t] for (t, a), js in groups.items() for j in js)
    # The M2 view of the baseline is the CSV encoder's view, symbol for symbol.
    assert roster_strings(inst, inst.baseline) == encode_strings()


def test_product_counts_and_equivalence(machines):
    rules = load_rules()
    minimal, full = combined_dfa(rules)
    assert (len(full.states), len(minimal.states), minimal.trap_states()) == (259, 15, ["dead"])
    pair_min, pair_full = combined_dfa({k: rules[k] for k in ("R1", "R2")})
    assert (len(pair_full.states), len(pair_min.states)) == (11, 4)
    rng = Random(SEED)
    words = [w for n in range(7) for w in product(ALPHABET, repeat=n)]
    words += ["".join(rng.choice(ALPHABET) for _ in range(rng.randint(7, 30))) for _ in range(3000)]
    for w in words:
        assert minimal.accepts(w) == all(m.accepts(w) for m in rules.values()), w


def test_layered_graph_drops_trap_and_non_accepting_edges(machines):
    r1 = machines["R1"]
    edges = layered_edges(r1, [list(ALPHABET)] * 4)
    assert all(r1.transitions[q][a] != "dead" for t, q, a in edges)
    # Day 3 from run2 can only rest: run2 reached by two working days, a third one enters the trap.
    assert {a for t, q, a in edges if (t, q) == (3, "run2")} == {"-"}
    assert live_states(r1) == {"run0", "run1", "run2"}
    # Layers 0..3 hold 1, 2, 3, 3 live nodes; each has 4 edges minus 3 into the trap from run2.
    assert len(edges) == full_graph_edges(r1, 4) == 4 + 8 + (12 - 3) + (12 - 3)


def test_flow_equals_brute_force_on_random_cases(machines):
    rng = Random(SEED + 1)
    for name, dfa in machines.items():
        for _ in range(10):
            horizon = rng.randint(1, 6)
            cost, allowed = random_case(rng, horizon, rng.choice(["random", "max_work"]),
                                        horizon >= 2 and rng.random() < 0.5)
            brute, _ = brute_force_best(dfa, cost, allowed)
            ilp, word = flow_ilp_best(dfa, cost, allowed)
            assert ilp == pytest.approx(brute, abs=1e-6), (name, cost, allowed)
            assert dfa.accepts(word)


def test_sixteen_reported_cases_match(machines):
    rows = brute_force_check(SEED, machines)
    assert len(rows) == 16 and all(row["match"] for row in rows)
    assert {row["dfa"] for row in rows} == set(machines)


def test_infeasible_word_gives_infeasible_ilp(machines):
    forced = [["M"], ["A"], ["N"], list(ALPHABET)]
    cost = [{a: 0 for a in ALPHABET}] * 4
    assert brute_force_best(machines["R1"], cost, forced) == (None, None)
    assert flow_ilp_best(machines["R1"], cost, forced) == (None, None)
    # R2 alone accepts N on the last day, but not N followed by work.
    assert flow_ilp_best(machines["R2"], cost[:2], [["N"], ["M"]]) == (None, None)
    assert flow_ilp_best(machines["R2"], cost[:2], [["M"], ["N"]])[1] == "MN"


def test_bad_input_is_rejected(machines):
    prob = pulp.LpProblem("bad", pulp.LpMinimize)
    with pytest.raises(ValueError):
        add_regular_constraint(prob, machines["R1"], [])
    with pytest.raises(ValueError):
        add_regular_constraint(prob, machines["R1"], [{"W": 1}])


def small_instance(sessions, staff=1, available=None):
    """One CS1 session per (day of May 2026, start hour, demand); every staff member available
    unless `available` lists the (i, j) pairs."""
    starts = [datetime(2026, 5, d, h, 0 if h != 9 else 30) for d, h, r in sessions]
    starts = [s.replace(minute=15) if s.hour == 18 else s for s in starts]
    intervals = [(s, s.replace(hour=s.hour + 2)) for s in starts]
    pairs = available if available is not None else {(i, j) for i in range(staff)
                                                     for j in range(len(sessions))}
    return Instance(
        seed=SEED, availability="explicit", staff_ids=[f"CB{i + 1}" for i in range(staff)],
        session_names=[f"S{j}" for j in range(len(sessions))], demand=[r for d, h, r in sessions],
        campus=["CS1"] * len(sessions), day=[date(2026, 5, d) for d, h, r in sessions],
        intervals=intervals, overlaps=[], baseline=[], A=set(pairs),
        preferences=["BAL"] * staff, soft_weights=soft_weights(TEAM_ID))


def test_two_shift_day_keeps_the_afternoon_symbol(machines):
    # One person must take both sessions of 18 May: morning and afternoon -> symbol A, feasible.
    inst = small_instance([(18, 7, 1), (18, 13, 1), (20, 9, 1)])
    solution, info, rules = solve_with_rules(inst, ModelConfig(), machines["R1xR2xR3"])
    assert solution.status == "optimal" and check_schedule(inst, solution.assigned) == []
    assert roster_strings(inst, solution.assigned) == {"CB1": "A-M"}
    assert check_rule_solution(inst, solution.assigned, rules, machines["R1xR2xR3"]) == []
    assert round(rules.u[0, 0, "M"].varValue) == round(rules.u[0, 0, "A"].varValue) == 1
    assert (round(rules.z[0, 0, "A"].varValue), round(rules.z[0, 0, "M"].varValue)) == (1, 0)


def test_rules_cut_schedules_that_m2_accepts(machines):
    dfa = machines["R1xR2xR3"]
    three_days = small_instance([(18, 7, 1), (19, 7, 1), (20, 7, 1)])
    assert solve(three_days).status == "optimal"  # M2 alone: MMM
    assert solve_with_rules(three_days, ModelConfig(), dfa)[0].status == "infeasible"
    night_then_work = small_instance([(18, 18, 1), (19, 7, 1)])
    assert roster_strings(night_then_work, solve(night_then_work).assigned) == {"CB1": "NM"}
    assert solve_with_rules(night_then_work, ModelConfig(), dfa)[0].status == "infeasible"
    # With a second person the rules split the days instead.
    shared = small_instance([(18, 7, 1), (19, 7, 1), (20, 7, 1)], staff=2)
    solution, info, rules = solve_with_rules(shared, ModelConfig(), dfa)
    strings = roster_strings(shared, solution.assigned)
    assert solution.status == "optimal" and violations(strings, machines)["accepted"] == 2
    assert check_rule_solution(shared, solution.assigned, rules, dfa) == []


def test_full_data_with_rules(machines):
    inst = build_instance()
    solution, info, rules = solve_with_rules(inst, ModelConfig(fatigue_k=3, time_limit=150),
                                             machines["R1xR2xR3"])
    assert solution.status == "optimal" and solution.t_star == 11
    assert check_schedule(inst, solution.assigned) == []
    assert check_rule_solution(inst, solution.assigned, rules, machines["R1xR2xR3"]) == []
    assert violations(roster_strings(inst, solution.assigned), machines)["accepted"] == 73
    assert solution.objective["total"] == pytest.approx(66.568767, abs=1e-5)
    assert info[2]["m3_vars"] == {"ucls": 1622, "zsym": 1622, "yflow": 12979}
