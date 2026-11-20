"""The threshold is a real soft ILP constraint, checked by separate simulation."""

import numpy as np
import pulp
import pytest

from m2_ilp.config import ModelConfig
from m2_ilp.instance import toy_instance
from m2_ilp.model import build_model
from m2_ilp.solve import run_cbc
from m2_ilp.validate import check_schedule
from m4_dynamics.fatigue import FatigueParameters, simulate_history, threshold_penalty
from m4_dynamics.planning import add_fatigue_soft_constraints
from m4_dynamics.workload import weekly_workload


@pytest.mark.parametrize("threshold,initial", [(0.0, [0, 0, 0]), (0.5, [2, 1, 3]), (100, [0, 0, 0])])
def test_solver_states_and_slacks_equal_independent_recurrence(threshold, initial):
    inst = toy_instance()
    parameters = FatigueParameters(a=0.8, b=0.2)
    config = ModelConfig(stage=2, t_cap=2)
    prob, x, _ = build_model(inst, config)
    for pair, var in x.items():
        prob += var == int(pair in inst.baseline)
    handles = add_fatigue_soft_constraints(prob, x, inst, parameters, threshold, initial)
    prob.setObjective(prob.objective + handles.penalty)
    result = run_cbc(prob, config)
    assert result.status == "optimal"
    assigned = {pair for pair, var in x.items() if var.varValue > 0.5}
    assert check_schedule(inst, assigned) == []
    history = simulate_history(weekly_workload(inst, assigned), parameters, initial)
    modeled = np.array([[pulp.value(handles.states[t, i]) for i in range(3)] for t in range(2)])
    np.testing.assert_allclose(modeled, history, atol=1e-6)
    assert pulp.value(handles.penalty) == pytest.approx(threshold_penalty(history, threshold), abs=1e-6)
    if threshold == 0:
        assert pulp.value(handles.penalty) > 0  # an impossible hard threshold remains feasible
