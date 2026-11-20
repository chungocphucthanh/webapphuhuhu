"""Independent schedule checker (TV2, req 2.4).

Pure Python on the Instance data: it never imports pulp or the model, so a bug in the
ILP cannot hide itself. H2 is checked pair by pair on inst.overlaps, exactly as M1 states
it, not with the cliques that hard.py uses.
"""

from __future__ import annotations

from collections import Counter


def _when(inst, j):
    start, end = inst.intervals[j]
    return f"{start:%Y-%m-%d %H:%M}-{end:%H:%M}"


def check_schedule(inst, assigned) -> list[str]:
    """Return every violated hard rule as a readable message; an empty list means valid.

    'H1: CB012 is not available for 20260518_5_CS1 (2026-05-18 18:15-20:45)'
    'H2: CB012 works 20260520_2_CS1 and 20260520_2_CS2, both 09:00-11:00'
    'H3: 20260518_5_CS1 needs 2 staff, got 1'
    """
    n, m = len(inst.staff_ids), len(inst.session_names)
    messages = []
    pairs = set()
    for pair in assigned:
        i, j = pair
        if type(i) is not int or type(j) is not int or not (0 <= i < n and 0 <= j < m):
            messages.append(f"H1: assignment {pair} is outside the instance")
        else:
            pairs.add((i, j))
    for i, j in sorted(pairs - set(inst.A)):
        messages.append(f"H1: {inst.staff_ids[i]} is not available for "
                        f"{inst.session_names[j]} ({_when(inst, j)})")
    for i in range(n):
        for j, k in sorted(inst.overlaps):
            if (i, j) in pairs and (i, k) in pairs:
                (sj, ej), (sk, ek) = inst.intervals[j], inst.intervals[k]
                when = (f"both {sj:%H:%M}-{ej:%H:%M}" if (sj, ej) == (sk, ek)
                        else f"{sj:%H:%M}-{ej:%H:%M} and {sk:%H:%M}-{ek:%H:%M}")
                messages.append(f"H2: {inst.staff_ids[i]} works {inst.session_names[j]} and "
                                f"{inst.session_names[k]}, {when} on {sj:%Y-%m-%d}")
    staffed = Counter(j for i, j in pairs)
    for j in range(m):
        if staffed[j] != inst.demand[j]:
            messages.append(f"H3: {inst.session_names[j]} needs {inst.demand[j]} staff, "
                            f"got {staffed[j]}")
    return messages


def main():
    from .instance import build_instance

    for mode in ("seeded", "day"):
        inst = build_instance(availability=mode)
        violations = check_schedule(inst, inst.baseline)
        print(f"Baseline under {mode} availability: {len(violations)} violations")


if __name__ == "__main__":
    main()
