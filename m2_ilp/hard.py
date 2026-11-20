"""Hard constraints H1-H3 of the M2 model (TV2, req 2.4).

H1 availability: x exists only for (i, j) in A, so it is checked, not added as rows.
H2 no double-booking: one row per (person, maximal clique of overlapping sessions).
H3 capacity: exactly r_j people per session (plus slack u_j in the elastic diagnosis).
"""

from __future__ import annotations

import pulp


def maximal_cliques(inst) -> list[tuple[int, ...]]:
    """Maximal cliques of size >= 2 of the overlap graph, each sorted, the list sorted.

    Sweep: at every session start time s, the sessions running at s (start <= s < end)
    pairwise overlap, so they form a clique. Intervals have the Helly property, so every
    clique is inside the set running at its latest start; keeping the sets that are not
    a subset of another one gives exactly the maximal cliques. Touching endpoints
    (end_j == start_k) do not overlap, as in M1 (forum d=33630).
    """
    running_sets = set()
    for start in sorted({s for s, e in inst.intervals}):
        running = tuple(j for j, (s, e) in enumerate(inst.intervals) if s <= start < e)
        if len(running) >= 2:
            running_sets.add(running)
    cliques = sorted(c for c in running_sets
                     if not any(set(c) < set(other) for other in running_sets))
    _check_against_overlaps(inst, cliques)
    return cliques


def _check_against_overlaps(inst, cliques):
    """The cliques must cover inst.overlaps exactly; otherwise intervals and M1 disagree."""
    covered = {(j, k) for c in cliques for a, j in enumerate(c) for k in c[a + 1:]}
    if covered != set(inst.overlaps):
        raise ValueError("Session intervals and inst.overlaps describe different overlap graphs")


def pairwise_rows(inst, x) -> int:
    """Rows of M1's pairwise form x_ij + x_ik <= 1, restricted to pairs that have variables."""
    return sum((i, j) in x and (i, k) in x
               for j, k in inst.overlaps for i in range(len(inst.staff_ids)))


def add_hard_constraints(prob, x, inst, config) -> dict:
    """Add H2 and H3; assert H1. Return cliques, elastic slack and row counts."""
    outside = set(x) - set(inst.A)
    if outside:
        raise AssertionError(f"H1: {len(outside)} variables outside A, e.g. {min(outside)}")
    n, m = len(inst.staff_ids), len(inst.session_names)
    cliques = maximal_cliques(inst)

    h2 = 0
    if not config.drop_overlap:
        for i in range(n):
            for g, clique in enumerate(cliques):
                members = [x[i, j] for j in clique if (i, j) in x]
                if len(members) >= 2:
                    prob += pulp.lpSum(members) <= 1, f"H2_{i}_{g}"
                    h2 += 1

    staff_of = {j: [] for j in range(m)}
    for i, j in sorted(x):
        staff_of[j].append(x[i, j])
    slack = {}
    for j in range(m):
        lhs = pulp.lpSum(staff_of[j])
        if config.elastic:
            slack[j] = pulp.LpVariable(f"u_{j}", lowBound=0)
            lhs = lhs + slack[j]
        prob += lhs == inst.demand[j], f"H3_{j}"

    return {"cliques": cliques, "slack": slack,
            "rows": {"H2": h2, "H3": m, "H2_pairwise": pairwise_rows(inst, x)}}
