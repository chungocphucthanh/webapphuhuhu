from itertools import product

import pytest
from pysat.solvers import Solver

from m1_logic import cnf as encoder
from m1_logic import linear_bridge as bridge


def _valid_schedule(selected, staff_count, demands, busy, overlaps):
    """Check the scheduling rules directly; same checker as test_cnf.py."""
    return (
        all(sum(task == j for _, task in selected) == demand
            for j, demand in enumerate(demands))
        and not selected.intersection(busy)
        and all(not ((i, j) in selected and (i, k) in selected)
                for i in range(staff_count) for j, k in overlaps)
    )


# --------------------------------------------------------------------------
# Clause and cardinality patterns
# --------------------------------------------------------------------------

@pytest.mark.parametrize("clause", [
    [1], [-1], [1, 2], [-1, 2], [-1, -2], [1, 2, 3], [1, -2, 3], [-1, -2, -3],
    [1, 1, 2], [2, 1], [1, -1], [1, -1, 2],
])
def test_clause_bridge_matches_every_truth_assignment(clause):
    assert bridge.check_clause_bridge(clause) == []


def test_empty_clause_becomes_an_infeasible_row():
    # m1_logic/cnf.py appends [] for an impossible demand; the row must match.
    constraint = bridge.clause_to_linear([])
    assert constraint.is_never_true()
    assert not constraint.holds({})


def test_tautological_clause_becomes_an_always_true_row():
    assert bridge.clause_to_linear([1, -1]).is_always_true()


@pytest.mark.parametrize("clause, expected", [
    ([1, 2], ({1: 1, 2: 1}, ">=", 1)),
    ([-1, 2], ({1: -1, 2: 1}, ">=", 0)),
    ([-1, -2], ({1: -1, 2: -1}, ">=", -1)),
    ([-1], ({1: -1}, ">=", 0)),
])
def test_clause_bridge_uses_the_documented_normal_form(clause, expected):
    # The table in the report quotes these rows, so pin them down literally.
    constraint = bridge.clause_to_linear(clause)
    assert (constraint.coefficients, constraint.sense, constraint.rhs) == expected


@pytest.mark.parametrize("builder, bound, predicate", [
    (bridge.at_most, 0, lambda count: count <= 0),
    (bridge.at_most, 2, lambda count: count <= 2),
    (bridge.at_least, 1, lambda count: count >= 1),
    (bridge.at_least, 3, lambda count: count >= 3),
    (bridge.exactly, 0, lambda count: count == 0),
    (bridge.exactly, 2, lambda count: count == 2),
    (bridge.exactly, 4, lambda count: count == 4),
])
def test_cardinality_rows_match_every_truth_assignment(builder, bound, predicate):
    variables = [1, 2, 3]
    constraint = builder(variables, bound)
    mismatches = bridge.check_bridge(
        lambda m: predicate(sum(m[v] for v in variables)), constraint, variables
    )
    assert mismatches == []


def test_exactly_one_is_the_one_hot_row():
    constraint = bridge.exactly_one([1, 2, 3])
    assert (constraint.coefficients, constraint.sense, constraint.rhs) == (
        {1: 1, 2: 1, 3: 1}, "==", 1
    )


def test_documented_patterns_all_check_out():
    assert {label: mismatches
            for label, mismatches in bridge.verify_patterns().items()
            if mismatches} == {}


def test_every_wrong_mapping_is_refuted_by_its_own_witness():
    # A witness that agrees, or a wrong row with no mismatch at all, means the
    # table has gone stale and the report would be quoting a dead example.
    for entry in bridge.wrong_mapping_counterexamples():
        label, _reason, _constraint, _witness, expected, actual, total = entry
        assert expected != actual, label
        assert total > 0, label


def test_the_documented_counterexample_is_the_expected_one():
    # "a v b -> x_a + x_b == 1" must fail exactly on a = b = 1.
    entry = bridge.wrong_mapping_counterexamples()[0]
    label, _reason, constraint, witness, expected, actual, _total = entry
    assert label.startswith("a v b")
    assert (witness, expected, actual) == ({1: 1, 2: 1}, True, False)
    assert constraint.holds({1: 1, 2: 0})


@pytest.mark.parametrize("clause, flipped", [
    ([-1, -2], ({1: 1, 2: 1}, "<=", 1)),
    ([1, 2], ({1: -1, 2: -1}, "<=", -1)),
    ([-1], ({1: 1}, "<=", 0)),
])
def test_flip_gives_the_tidier_form_the_table_shows(clause, flipped):
    constraint = bridge.clause_to_linear(clause)
    other = constraint.flip()
    assert (other.coefficients, other.sense, other.rhs) == flipped
    assert other.flip() == constraint
    variables = sorted(constraint.variables)
    for flags in product((0, 1), repeat=len(variables)):
        assignment = dict(zip(variables, flags))
        assert constraint.holds(assignment) == other.holds(assignment)


# --------------------------------------------------------------------------
# Input validation
# --------------------------------------------------------------------------

@pytest.mark.parametrize("clause", [[0], [1, 0], [1.5], [True], ["1"]])
def test_rejects_invalid_literals(clause):
    with pytest.raises(ValueError):
        bridge.clause_to_linear(clause)


@pytest.mark.parametrize("variables", [[0], [-1], [1, 1], [1.5], [True], ["1"]])
def test_rejects_invalid_variable_lists(variables):
    with pytest.raises(ValueError):
        bridge.at_most(variables, 1)


@pytest.mark.parametrize("bound", [-1, 1.5, True, "2"])
def test_rejects_invalid_bounds(bound):
    with pytest.raises(ValueError):
        bridge.exactly([1, 2], bound)


@pytest.mark.parametrize("sense", ["<", ">", "=", "!=", 1])
def test_rejects_invalid_senses(sense):
    with pytest.raises(ValueError):
        bridge.LinearConstraint({1: 1}, sense, 0)


def test_constraint_copies_its_coefficients():
    coefficients = {1: 1}
    constraint = bridge.LinearConstraint(coefficients, ">=", 1)
    coefficients[2] = 5
    assert constraint.coefficients == {1: 1}


def test_check_bridge_refuses_to_enumerate_too_many_variables():
    variables = list(range(1, bridge.MAX_ENUMERATED_VARIABLES + 2))
    with pytest.raises(ValueError):
        bridge.check_bridge(lambda m: True, bridge.at_most(variables, 1), variables)


# --------------------------------------------------------------------------
# The instance model: agreement with the rules and with the CNF encoder
# --------------------------------------------------------------------------

@pytest.mark.parametrize("staff_count, demands, busy, overlaps", [
    (0, [], [], []),
    (0, [1], [], []),
    (3, [], [], []),
    (3, [0], [], []),
    (3, [2], [], []),
    (3, [4], [], []),
    (3, [1, 1], [(0, 0)], []),
    (3, [1, 1], [], []),
    (3, [1, 1], [], [(0, 1)]),
    (3, [1, 1], [(0, 0)], [(0, 1)]),
    (3, [1, 1], [(0, 0), (0, 0)], [(0, 1), (1, 0)]),
    (2, [2, 1], [], [(1, 0)]),
])
def test_linear_model_matches_the_rule_checker(
    staff_count, demands, busy, overlaps
):
    model = bridge.encode_invigilator_assignment_linear(
        staff_count, demands, busy, overlaps
    )
    pairs = list(product(range(staff_count), range(len(demands))))
    for flags in product((0, 1), repeat=len(pairs)):
        selected = {pair for pair, flag in zip(pairs, flags) if flag}
        assignment = {model.var(i, j): flag
                      for (i, j), flag in zip(pairs, flags)}
        expected = _valid_schedule(
            selected, staff_count, demands, busy, overlaps
        )
        assert model.is_feasible(assignment) == expected, selected


@pytest.mark.parametrize("staff_count, demands, busy, overlaps", [
    (3, [1, 1], [(0, 0)], [(0, 1)]),
    (3, [2, 1], [], []),
    (4, [2, 2], [(0, 0)], [(0, 1)]),
    (2, [1, 1, 1], [(0, 1)], [(0, 2)]),
])
def test_linear_model_matches_the_cnf_encoder(
    staff_count, demands, busy, overlaps
):
    """Same feasible set as M1's CNF, projected onto the Assign variables."""
    cnf = encoder.encode_invigilator_assignment(
        staff_count, demands, busy, overlaps
    )
    model = bridge.encode_invigilator_assignment_linear(
        staff_count, demands, busy, overlaps
    )
    variables = model.assignment_variables()
    with Solver(name="m22", bootstrap_with=cnf.clauses) as solver:
        for flags in product((0, 1), repeat=len(variables)):
            assignment = dict(zip(variables, flags))
            assumptions = [v if flag else -v
                           for v, flag in zip(variables, flags)]
            # The solver may still choose the auxiliary variables freely.
            assert solver.solve(assumptions=assumptions) == model.is_feasible(assignment)


def test_clausewise_bridge_matches_the_cnf_including_auxiliaries():
    """cnf_to_linear is exact clause by clause, auxiliary variables included."""
    cnf = encoder.encode_invigilator_assignment(2, [1], [], [])
    rows = bridge.cnf_to_linear(cnf)
    variables = sorted({abs(literal) for clause in cnf.clauses for literal in clause})
    for flags in product((0, 1), repeat=len(variables)):
        assignment = dict(zip(variables, flags))
        satisfies_cnf = all(bridge.clause_is_true(clause, assignment)
                            for clause in cnf.clauses)
        assert satisfies_cnf == all(row.holds(assignment) for row in rows)


def test_variable_ids_follow_the_shared_row_major_contract():
    model = bridge.encode_invigilator_assignment_linear(2, [1, 1, 1], [], [])
    assert [model.var(i, j) for i in range(2) for j in range(3)] == [1, 2, 3, 4, 5, 6]
    assert [model.pair(v) for v in range(1, 7)] == [
        (0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)
    ]
    with pytest.raises(ValueError):
        model.var(2, 0)
    with pytest.raises(ValueError):
        model.pair(7)


def test_demand_above_the_staff_count_is_an_infeasible_row():
    # The CNF encoder writes the empty clause here; the linear model must agree.
    model = bridge.encode_invigilator_assignment_linear(2, [3], [], [])
    assert any(constraint.is_never_true() for constraint in model.constraints)
    assert not model.is_feasible({1: 1, 2: 1})


def test_constraint_count_and_families():
    model = bridge.encode_invigilator_assignment_linear(
        3, [1, 1], [(0, 0)], [(0, 1)]
    )
    assert model.summary() == {
        "capacity": 2, "busy": 1, "overlap": 3
    }


@pytest.mark.parametrize("use_iterators", [False, True])
def test_encoding_is_repeatable_without_mutating_inputs(use_iterators):
    demands, busy, overlaps = [2, 1], [(0, 1)], [(0, 1)]
    before = (demands[:], busy[:], overlaps[:])
    arguments = (busy, overlaps)
    if use_iterators:
        arguments = tuple(iter(pairs) for pairs in arguments)
    first = bridge.encode_invigilator_assignment_linear(4, demands, *arguments)
    second = bridge.encode_invigilator_assignment_linear(
        4, demands, busy, overlaps
    )
    assert (demands, busy, overlaps) == before
    assert first == second


@pytest.mark.parametrize("pair", [
    (-1, 0), (3, 0), (0, -1), (0, 2), (True, 0), (0, False), (0.5, 0), (0, 0.5),
])
def test_rejects_invalid_assignment_pair(pair):
    with pytest.raises(ValueError):
        bridge.encode_invigilator_assignment_linear(3, [1, 1], [pair], [])


@pytest.mark.parametrize("pair", [
    (-1, 1), (0, 2), (2, 0), (0, -1), (0, 0), (True, 0), (0, False),
    (0.5, 1), (0, 0.5),
])
def test_rejects_invalid_overlap_pair(pair):
    with pytest.raises(ValueError):
        bridge.encode_invigilator_assignment_linear(3, [1, 1], [], [pair])


@pytest.mark.parametrize("staff_count", [-1, 1.5, True, "3"])
def test_rejects_invalid_staff_count(staff_count):
    with pytest.raises(ValueError):
        bridge.encode_invigilator_assignment_linear(staff_count, [1], [], [])


# --------------------------------------------------------------------------
# Real data
# --------------------------------------------------------------------------

def test_real_baseline_capacity_and_overlap_in_the_linear_model():
    """Check historical capacity/overlap only, with explicitly empty Busy."""
    from m1_logic.data_loader import load_dataset

    data = load_dataset()
    model = bridge.encode_invigilator_assignment_linear(
        len(data["staff_ids"]), data["shift_demands"], [], data["overlaps"],
    )
    assignment = {variable: 0 for variable in model.assignment_variables()}
    for i, j in data["baseline"]:
        assignment[model.var(i, j)] = 1
    assert model.violated(assignment) == []


def test_real_model_has_no_auxiliary_variables():
    from m1_logic.data_loader import load_dataset

    data = load_dataset()
    model = bridge.encode_invigilator_assignment_linear(
        len(data["staff_ids"]), data["shift_demands"], [], data["overlaps"],
    )
    highest = len(model.assignment_variables())
    assert all(variable <= highest
               for constraint in model.constraints
               for variable in constraint.variables)


def test_bridge_table_lists_every_hard_rule():
    table = bridge.bridge_table_markdown()
    for rule in ("H1 Availability", "H2 No double-booking", "H3 Exact capacity"):
        assert rule in table
    assert "x_ij + x_ik <= 1" in table
    assert "sum_i x_ij == d_j" in table


def test_unknown_busy_is_rejected():
    with pytest.raises(ValueError, match="Busy is unknown"):
        bridge.encode_invigilator_assignment_linear(3, [2], None, [])
