"""Checks for the independent validator (TV2, req 2.4)."""

import ast
from pathlib import Path

import pytest

import m2_ilp.validate as validate
from m2_ilp.fixtures import clique_instance
from m2_ilp.instance import build_instance, toy_instance
from m2_ilp.validate import check_schedule


@pytest.mark.parametrize("mode", ["seeded", "day"])
def test_full_baseline_is_valid(mode):
    inst = build_instance(availability=mode)
    assert check_schedule(inst, inst.baseline) == []


def test_messages_name_the_rule_staff_session_and_time():
    toy = toy_instance()
    assert check_schedule(toy, {(0, 0), (1, 0), (2, 0), (1, 1), (2, 1)}) == [
        "H1: CB1 is not available for Morning (2026-05-18 07:00-09:00)",
        "H3: Morning needs 2 staff, got 3",
    ]
    assert check_schedule(toy, {(1, 0)}) == [
        "H3: Morning needs 2 staff, got 1",
        "H3: Afternoon needs 2 staff, got 0",
    ]
    inst = clique_instance()
    assert check_schedule(inst, {(1, 0), (1, 1), (0, 2), (1, 3)}) == [
        "H2: CB2 works S0 and S1, 08:00-10:00 and 09:00-11:00 on 2026-05-18",
    ]


def test_identical_times_are_reported_once_and_bad_indices_do_not_crash():
    inst = build_instance()
    j, k = inst.overlaps[0]
    schedule = set(inst.baseline) | {(0, j), (0, k)}
    h2 = [msg for msg in check_schedule(inst, schedule) if msg.startswith("H2")]
    start, end = inst.intervals[j]
    assert h2 == [f"H2: CB001 works {inst.session_names[j]} and {inst.session_names[k]}, "
                  f"both {start:%H:%M}-{end:%H:%M} on {start:%Y-%m-%d}"]
    assert check_schedule(toy_instance(), {(9, 0)})[0] == "H1: assignment (9, 0) is outside the instance"


def test_validator_stays_independent_of_the_ilp():
    tree = ast.parse(Path(validate.__file__).read_text(encoding="utf-8"))
    imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
                for alias in node.names}
    imported |= {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(name.split(".")[0] == "pulp" or name.endswith("model") or name.endswith("hard")
                   for name in imported)
