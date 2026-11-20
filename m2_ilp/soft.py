"""Soft constraints LOC, FAT, TRV as penalty terms (TV5, req 2.5).

LOC  location: sum of c_ij x_ij, c_ij = 1 when a CS1/CS2 person works the other campus.
FAT  fatigue:  s_id >= (sessions of i on day d) - K, s_id >= 0.
TRV  travel:   z_idc >= x_ij for j on day d at campus c; v_id >= z_id1 + z_id2 - 1.
The model minimises the weighted sum, so s, z, v stay continuous: at an integer x the
optimum pushes s_id to max(0, load - K) and v_id to 1 exactly on two-campus days.
Run from the repository root: python -m m2_ilp.soft
"""

from __future__ import annotations

from collections import Counter

import pulp

from .config import ModelConfig

CAMPUS_CODE = {"CS1": 1, "CS2": 2}


def day_index(inst) -> dict:
    """Date -> d, the position of the day in sorted order (used in row and variable names)."""
    return {day: d for d, day in enumerate(sorted(inst.sessions_by_day))}


def location_cost(inst, i: int, j: int) -> int:
    """c_ij: 1 if pref(i) is a campus different from campus(j); BAL is never penalised."""
    pref = inst.preferences[i]
    return int(pref in CAMPUS_CODE and pref != inst.campus[j])


def _available_by_day(inst, x):
    """(i, d) -> sessions j of day d with a variable x_ij, in index order."""
    days = day_index(inst)
    by_day = {}
    for i, j in sorted(x):
        by_day.setdefault((i, days[inst.day[j]]), []).append(j)
    return by_day


def add_soft_terms(prob, x, inst, config) -> dict:
    """Return {"location": LOC, "fatigue": FAT, "travel": TRV}; adds FAT, TRVZ, TRV rows.

    s_id is created only when i has more than K available sessions on day d, and z, v only
    when i can reach both campuses on d: otherwise the term is always 0 and the row is dropped.
    """
    k = config.fatigue_k
    location = pulp.lpSum(x[i, j] for i, j in sorted(x) if location_cost(inst, i, j))
    fatigue, travel = [], []
    for (i, d), sessions in sorted(_available_by_day(inst, x).items()):
        if len(sessions) > k:
            s = pulp.LpVariable(f"s_{i}_{d}", lowBound=0)
            prob += s >= pulp.lpSum(x[i, j] for j in sessions) - k, f"FAT_{i}_{d}"
            fatigue.append(s)
        if len({inst.campus[j] for j in sessions}) == 2:
            z = {c: pulp.LpVariable(f"z_{i}_{d}_{c}", lowBound=0, upBound=1) for c in (1, 2)}
            for j in sessions:
                prob += z[CAMPUS_CODE[inst.campus[j]]] >= x[i, j], f"TRVZ_{i}_{j}"
            v = pulp.LpVariable(f"v_{i}_{d}", lowBound=0)
            prob += v >= z[1] + z[2] - 1, f"TRV_{i}_{d}"
            travel.append(v)
    return {"location": location, "fatigue": pulp.lpSum(fatigue), "travel": pulp.lpSum(travel)}


def evaluate_soft(inst, assigned, fatigue_k: int = ModelConfig.fatigue_k) -> dict:
    """Pure Python. {"location", "fatigue", "travel"} of a fixed schedule."""
    assigned = sorted(set(assigned))
    per_day = Counter((i, inst.day[j]) for i, j in assigned)
    campuses = {}
    for i, j in assigned:
        campuses.setdefault((i, inst.day[j]), set()).add(inst.campus[j])
    return {
        "location": sum(location_cost(inst, i, j) for i, j in assigned),
        "fatigue": sum(max(0, count - fatigue_k) for count in per_day.values()),
        "travel": sum(len(c) == 2 for c in campuses.values()),
    }


def daily_load_distribution(inst, assigned=None) -> dict:
    """{sessions per day: number of (person, day) pairs}, over days the person works."""
    assigned = inst.baseline if assigned is None else assigned
    per_day = Counter((i, inst.day[j]) for i, j in set(assigned))
    return dict(sorted(Counter(per_day.values()).items()))


def fit_fatigue_k(inst, coverage: float = 0.95) -> int:
    """TV5-2: smallest K such that at least `coverage` of the baseline's working person-days
    have at most K sessions ("fit, don't fabricate"). K is then a penalty threshold only."""
    distribution = daily_load_distribution(inst)
    total = sum(distribution.values())
    if not total:
        raise ValueError("The baseline has no assignment to fit K from")
    covered = 0
    for k, pairs in distribution.items():
        covered += pairs
        if covered >= coverage * total:
            return k
    return max(distribution)


def main():
    from .instance import build_instance

    inst = build_instance()
    distribution = daily_load_distribution(inst)
    total = sum(distribution.values())
    print(f"Baseline sessions per working person-day ({total} pairs):")
    running = 0
    for k, pairs in distribution.items():
        running += pairs
        print(f"  {k}: {pairs} pairs; share <= {k}: {running / total:.1%}")
    k = fit_fatigue_k(inst)
    print(f"Fitted K = {k} (coverage 95%); baseline soft terms: {evaluate_soft(inst, inst.baseline, k)}")


if __name__ == "__main__":
    main()
