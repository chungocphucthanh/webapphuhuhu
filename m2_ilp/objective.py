"""Two-stage fairness objective (req 2.3).

Stage 1 minimizes the maximum load t. Stage 2 caps t at the stage-1
optimum and minimizes L1 load deviation plus weighted soft penalties.
Exact session demand makes the mean load a constant.
"""

from __future__ import annotations

import math

import pulp


def mean_load(inst) -> float:
    """Mean workload under exact demand: sum_j r_j / |I|."""
    return sum(inst.demand) / len(inst.staff_ids)


def l1_chord(w_bar: float):
    """Return (low, intercept, slope) for the chord around the mean.

    The line joins |w - w_bar| at floor(w_bar) and ceil(w_bar). It is a
    valid lower bound at integer loads, but strengthens the LP relaxation.
    Its summed bound is attainable if loads can all be floor/ceil(w_bar);
    scheduling constraints may require a larger L1 value.
    Return None for an integer mean.
    """
    low = math.floor(w_bar)
    if low == w_bar:
        return None
    intercept = w_bar - low
    slope = (low + 1 - w_bar) - intercept
    return low, intercept, slope


def add_objective(prob, x, w, inst, config, soft_terms, slack=None) -> dict:
    """Set the objective for config.stage and return t/dev/L1/soft handles.

    Call once per problem. Stage 2 requires config.t_cap from stage 1.
    x is kept in the API; w already contains its workload expressions.
    """
    if config.stage not in (1, 2):
        raise ValueError("Stage must be 1 or 2")
    if config.stage == 2 and config.t_cap is None:
        raise ValueError("Stage 2 needs config.t_cap (the stage-1 optimum t*)")

    t = pulp.LpVariable("t", lowBound=0)
    for i in range(len(inst.staff_ids)):
        prob += t >= w[i], f"MAX_{i}"
    penalty = config.elastic_penalty * pulp.lpSum(slack.values()) if slack else 0

    dev, l1, soft = {}, None, None
    if config.stage == 1:
        objective = t + penalty
    else:
        prob += t <= config.t_cap, "TCAP"
        w_bar = mean_load(inst)
        chord = l1_chord(w_bar) if config.l1_chord else None
        for i in range(len(inst.staff_ids)):
            dev[i] = pulp.LpVariable(f"dev_{i}", lowBound=0)
            prob += dev[i] >= w[i] - w_bar, f"DEVP_{i}"
            prob += dev[i] >= w_bar - w[i], f"DEVN_{i}"
            if chord is not None:
                low, intercept, slope = chord
                prob += dev[i] >= intercept + slope * (w[i] - low), f"DEVC_{i}"
        l1 = pulp.lpSum(dev.values())
        objective = l1 + penalty
        if soft_terms is not None:
            lam_loc, lam_fat, lam_trv = config.lambdas(inst)
            soft = (lam_loc * soft_terms["location"] + lam_fat * soft_terms["fatigue"]
                    + lam_trv * soft_terms["travel"])
            objective = objective + soft
    objective = pulp.lpSum([objective])
    prob.setObjective(objective)
    return {"t": t, "dev": dev, "l1": l1, "soft": soft, "objective": objective}
