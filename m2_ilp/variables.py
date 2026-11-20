"""Sparse assignment variables and workload expressions (req 2.2)."""

import pulp


def create_variables(prob, inst, config):
    """Return (x, w); leave constraints, auxiliary variables and objective to their owners.

    config.relax_integrality selects Binary or Continuous [0, 1].
    Missing pairs in x mean an assignment is forbidden, not an unknown variable.
    """
    if type(config.relax_integrality) is not bool:
        raise ValueError("relax_integrality must be True or False")
    n, m = len(inst.staff_ids), len(inst.session_names)
    for i, j in inst.A:
        if type(i) is not int or type(j) is not int or not 0 <= i < n or not 0 <= j < m:
            raise ValueError("Availability contains an index outside the instance")
    existing_names = {v.name for v in prob.variables()}
    if any(f"x_{i}_{j}" in existing_names for i, j in inst.A):
        raise ValueError("Assignment variables already exist in this problem")

    category = "Continuous" if config.relax_integrality else "Binary"
    x = {}
    by_person = {i: [] for i in range(n)}
    for i, j in sorted(inst.A):
        x[i, j] = pulp.LpVariable(f"x_{i}_{j}", lowBound=0, upBound=1, cat=category)
        by_person[i].append(x[i, j])
    prob.addVariables(x.values())
    w = {i: pulp.lpSum(by_person[i]) for i in range(n)}
    print(f"Assignment variables: {len(x)} sparse / {n*m} dense; category={category}")
    return x, w
