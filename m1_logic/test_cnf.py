from itertools import product

import pytest
from pysat.formula import CNF
from pysat.solvers import Solver

from m1_logic import cnf as encoder


def _valid_schedule(selected, staff_count, demands, busy, overlaps):
    """Check the scheduling rules directly, without inspecting CNF clauses."""
    return (
        all(sum(task == j for _, task in selected) == demand
            for j, demand in enumerate(demands))
        and not selected.intersection(busy)
        and all(not ((i, j) in selected and (i, k) in selected)
                for i in range(staff_count) for j, k in overlaps)
    )


def _assert_equivalent(staff_count, demands, busy=(), overlaps=()):
    cnf = encoder.encode_invigilator_assignment(
        staff_count, demands, busy, overlaps
    )
    assert isinstance(cnf, CNF)
    # Row-major order is the public ID contract, independent of encoder helpers.
    pairs = list(product(range(staff_count), range(len(demands))))
    with Solver(name="m22", bootstrap_with=cnf.clauses) as solver:
        for flags in product((False, True), repeat=len(pairs)):
            selected = {pair for pair, flag in zip(pairs, flags) if flag}
            assumptions = [v if flag else -v
                           for v, flag in enumerate(flags, start=1)]
            expected = _valid_schedule(
                selected, staff_count, demands, busy, overlaps
            )
            assert solver.solve(assumptions=assumptions) == expected, selected


@pytest.mark.parametrize("staff_count, demands", [
    (0, []),
    (0, [0]),
    (0, [1]),
    (3, []),
    (3, [0]),
    (3, [1]),
    (3, [2]),
    (3, [3]),
    (3, [4]),
    (3, [2, 1]),
    (4, [2, 2]),
])
def test_capacity_matches_every_small_assignment(staff_count, demands):
    # Both under-filling and over-filling must fail; tasks must not share auxiliaries.
    _assert_equivalent(staff_count, demands)


@pytest.mark.parametrize("busy, overlaps", [
    ([(0, 0)], []),
    ([], [(0, 1)]),
    ([(0, 0)], [(0, 1)]),
    ([(0, 0), (0, 0)], [(0, 1), (1, 0)]),
])
def test_rules_match_every_small_assignment(busy, overlaps):
    _assert_equivalent(3, [1, 1], busy, overlaps)


@pytest.mark.parametrize("staff_count, demands, busy, overlaps, expected", [
    (3, [2], [(0, 0), (1, 0)], [], False),
    (1, [1, 1], [], [(0, 1)], False),
    (1, [1, 1], [], [], True),
    (3, [2, 2], [(0, 0)], [], True),
])
def test_feasibility_examples(staff_count, demands, busy, overlaps, expected):
    cnf = encoder.encode_invigilator_assignment(staff_count, demands, busy, overlaps)
    with Solver(name="m22", bootstrap_with=cnf.clauses) as solver:
        assert solver.solve() == expected


@pytest.mark.parametrize("use_iterators", [False, True])
def test_decoded_model_uses_row_major_ids(use_iterators):
    busy, overlaps = [(0, 1), (1, 2)], [(0, 2)]
    if use_iterators:
        busy, overlaps = map(iter, (busy, overlaps))
    cnf = encoder.encode_invigilator_assignment(2, [1, 1, 1], busy, overlaps)
    with Solver(name="m22", bootstrap_with=cnf.clauses) as solver:
        assert solver.solve()
        assert {v for v in solver.get_model() if 0 < v <= 6} == {3, 4, 5}


@pytest.mark.parametrize("staff_count", [-1, 1.5, True, "3"])
def test_rejects_invalid_staff_count(staff_count):
    with pytest.raises(ValueError):
        encoder.encode_invigilator_assignment(staff_count, [1], [], [])


@pytest.mark.parametrize("demand", [-1, 1.5, True, "2"])
def test_rejects_invalid_demand(demand):
    with pytest.raises(ValueError):
        encoder.encode_invigilator_assignment(3, [demand], [], [])


@pytest.mark.parametrize("pair", [
    (-1, 0), (3, 0), (0, -1), (0, 2), (True, 0), (0, False), (0.5, 0), (0, 0.5),
])
def test_rejects_invalid_assignment_pair(pair):
    with pytest.raises(ValueError):
        encoder.encode_invigilator_assignment(3, [1, 1], [pair], [])


@pytest.mark.parametrize("pair", [
    (-1, 1), (0, 2), (2, 0), (0, -1), (0, 0), (True, 0), (0, False),
    (0.5, 1), (0, 0.5),
])
def test_rejects_invalid_overlap_pair(pair):
    with pytest.raises(ValueError):
        encoder.encode_invigilator_assignment(3, [1, 1], [], [pair])


def test_encoding_is_repeatable_without_mutating_inputs():
    demands = [2, 1]
    busy = [(0, 1)]
    overlaps = [(0, 1)]
    before = (demands[:], busy[:], overlaps[:])
    first = encoder.encode_invigilator_assignment(4, demands, busy, overlaps)
    second = encoder.encode_invigilator_assignment(4, demands, busy, overlaps)
    assert (demands, busy, overlaps) == before
    assert first.clauses == second.clauses
    assert first.nv == second.nv


def test_real_baseline_capacity_and_overlap():
    # Raw CSV contains no Busy matrix; this check explicitly uses no Busy restrictions.
    from m1_logic.data_loader import load_dataset

    data = load_dataset()
    assert data["busy"] is None
    assert data["source_rows"] == 769
    assert len(data["staff_ids"]) == 73
    assert len(data["session_ids"]) == 83
    assert sum(data["shift_demands"]) == 769
    assert all(len(key) == 2 for key in data["session_ids"])
    # The source has 4 invigilators + 3 secretaries here; one session needs 7 people.
    assert data["capacity_by_session"][("20260604_2", "CS1")] == 7
    baseline = set(data["baseline"])
    staff_count = len(data["staff_ids"])
    session_count = len(data["session_ids"])
    assert _valid_schedule(baseline, staff_count, data["shift_demands"], [], data["overlaps"])
    cnf = encoder.encode_invigilator_assignment(
        staff_count, data["shift_demands"], [], data["overlaps"])
    assumptions = []
    for i in range(staff_count):
        for j in range(session_count):
            variable = i * session_count + j + 1
            assumptions.append(variable if (i, j) in baseline else -variable)
    with Solver(name="m22", bootstrap_with=cnf.clauses) as solver:
        assert solver.solve(assumptions=assumptions)


def test_unknown_busy_is_not_silently_treated_as_free():
    with pytest.raises(ValueError, match="Busy is unknown"):
        encoder.encode_invigilator_assignment(3, [2], None, [])


@pytest.mark.parametrize("demands, busy, overlaps, expected", [
    ([2, 2], [(0, 0)], [], True),
    ([2, 2], [(0, 0), (1, 0)], [], False),
    ([2, 2], [], [(0, 1)], False),
    ([4], [], [], False),
])
def test_selector_encoding_and_minimal_core(demands, busy, overlaps, expected):
    from m1_logic.unsat_core import encode_with_selectors, extract_minimal_core

    cnf, selectors = encode_with_selectors(3, demands, busy, overlaps)
    with Solver(name="m22", bootstrap_with=cnf.clauses) as solver:
        assert solver.solve(assumptions=list(selectors)) == expected
        core = extract_minimal_core(cnf, selectors)
        if expected:
            assert core is None
        else:
            assert core and not solver.solve(assumptions=core)
            for removed in core:
                assert solver.solve(assumptions=[s for s in core if s != removed])


def test_seeded_cases_solve_without_role_constraints(tmp_path):
    from m1_logic.prepare_instances import prepare_instances
    from m1_logic.sat_check import solve_instance

    cases = prepare_instances(1358677812, tmp_path)
    for name, expected in (("sat", True), ("unsat", False), ("toy", True)):
        data = cases[name]
        result = solve_instance(data)
        assert set(result) == {"satisfiable", "model", "unsat_core"}
        assert result["satisfiable"] == expected
        if expected:
            staff = data["staff_ids"]
            selected = set()
            for j, (code, campus) in enumerate(data["session_ids"]):
                for person in result["model"][code + "_" + campus]:
                    selected.add((staff.index(person), j))
            assert _valid_schedule(selected, len(staff), data["shift_demands"],
                                   data["busy"], data["overlaps"])
            assert result["unsat_core"] is None
        else:
            assert result["model"] is False
            assert result["unsat_core"]


@pytest.mark.parametrize("data, expected_core", [
    ({"staff_ids": ["CB001", "CB002"], "session_ids": [("S01", "CS1")],
      "shift_demands": [2], "busy": [(0, 0)], "overlaps": []},
     {"Busy(CB001,S01_CS1)", "capacity(S01_CS1)=2"}),
    ({"staff_ids": ["CB001"], "session_ids": [("S01", "CS1"), ("S01", "CS2")],
      "shift_demands": [1, 1], "busy": [], "overlaps": [(0, 1)]},
     {"capacity(S01_CS1)=1", "capacity(S01_CS2)=1",
      "NoDoubleBooking(CB001,S01_CS1,S01_CS2)"}),
])
def test_core_names_the_people_sessions_and_constraints(data, expected_core):
    from m1_logic.sat_check import solve_instance

    result = solve_instance(data)
    assert result["satisfiable"] is False
    assert result["model"] is False
    assert set(result["unsat_core"]) == expected_core


def test_runner_writes_both_cases_to_one_result_file(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    from m1_logic import sat_check
    from m1_logic.prepare_instances import prepare_instances

    (tmp_path / "m1_logic").mkdir()
    output = tmp_path / "m1_logic/sat_result.json"
    monkeypatch.setattr(sat_check, "PROJECT_FOLDER", tmp_path)
    monkeypatch.setattr(sat_check, "prepare_instances",
                        lambda seed: prepare_instances(seed, tmp_path / "data"))
    written = []
    write_text = Path.write_text

    def record_write(path, text, **kwargs):
        if path == output:
            written.append(json.loads(text))
        return write_text(path, text, **kwargs)

    monkeypatch.setattr(Path, "write_text", record_write)
    sat_check.main(1358677812)
    assert [result["satisfiable"] for result in written] == [False, True]
    assert written[0]["model"] is False and written[0]["unsat_core"]
    assert written[1]["model"] and written[1]["unsat_core"] is None
    assert all(set(result) == {"satisfiable", "model", "unsat_core"} for result in written)
    assert json.loads(output.read_text(encoding="utf-8")) == written[1]
    assert list((tmp_path / "m1_logic").glob("*.json")) == [output]
