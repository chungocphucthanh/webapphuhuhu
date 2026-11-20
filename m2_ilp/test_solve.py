"""Checks for the two-stage CBC solve (Lead, req 2.7)."""

import pulp
import pytest

from m2_ilp.config import ModelConfig
from m2_ilp.instance import build_instance, toy_instance
from m2_ilp.metrics import loads
from m2_ilp.solve import _read_gap, _read_nodes, run_cbc, solve
from m2_ilp.validate import check_schedule


def test_toy_end_to_end_matches_the_brief():
    toy = toy_instance()
    solution = solve(toy)
    assert solution.status == "optimal" and solution.t_star == 2
    assert sorted(loads(toy, solution.assigned), reverse=True) == [2, 1, 1]
    assert check_schedule(toy, solution.assigned) == []
    # L1 breaks the min-max tie: CB1 must take the afternoon, giving (1, 2, 1), not (0, 2, 2).
    assert (0, 1) in solution.assigned
    assert solution.objective["l1"] == pytest.approx(4 / 3, abs=1e-6)
    assert set(solution.stages) == {1, 2} and solution.diagnosis is None


def test_full_data_two_stage_solve():
    inst = build_instance()
    solution = solve(inst, ModelConfig())
    assert solution.status == "optimal"
    assert 11 <= solution.t_star <= 19
    assert sum(loads(inst, solution.assigned)) == 769
    assert check_schedule(inst, solution.assigned) == []
    assert all(stage.status == "optimal" and stage.gap == 0 for stage in solution.stages.values())
    assert all(isinstance(stage.nodes, int) for stage in solution.stages.values())
    assert max(loads(inst, solution.assigned)) == solution.t_star == solution.objective["max_load"]


def test_run_cbc_statuses_and_gap_parsing():
    prob = pulp.LpProblem("infeasible", pulp.LpMinimize)
    y = pulp.LpVariable("y", lowBound=0, upBound=1, cat="Binary")
    prob += y
    prob += y >= 2, "impossible"
    assert run_cbc(prob, ModelConfig()).status == "infeasible"
    assert _read_gap("Result - Stopped on time limit\nGap:  0.08\n", "feasible") == 0.08
    assert _read_gap("", "optimal") == 0.0 and _read_gap("", "not_solved") is None
    assert _read_nodes("Enumerated nodes:               12\n") == 12 and _read_nodes("") is None
    with pytest.raises(ValueError, match="integer"):
        solve(toy_instance(), ModelConfig(relax_integrality=True))
