"""Assumption-based (minimal) UNSAT core extraction for the invigilator model.

Each business-level constraint (one session's capacity requirement, one Busy
pair, one staff/Overlap constraint) gets its own selector variable
s. We add clauses (-s OR original_clause), then solve under assumptions
= all selectors. If UNSAT, solver.get_core() returns the offending
selectors directly (cheap: no per-clause probing needed). We then shrink
that core to a minimal one via deletion-based minimization.
"""
from pysat.card import CardEnc, EncType
from pysat.formula import CNF, IDPool
from pysat.solvers import Solver

if __package__:
    from .cnf import _check_nonnegative_int
else:
    from cnf import _check_nonnegative_int


def encode_with_selectors(invigilator_count, shift_demands, busy, overlaps,
                          *, staff_ids=None, session_labels=None):
    """Encode the same capacity, Busy and overlap rules as cnf.py.

    Session indices refer to (shift code, campus), with all roles pooled.
    Each selector enables one complete constraint, including all clauses of
    a capacity encoding. Assume every selector true to solve the full instance.
    Optional labels make the core readable without a separate index lookup.
    """
    _check_nonnegative_int(invigilator_count, "invigilator_count")
    if busy is None:
        raise ValueError("Busy is unknown; supply a seeded scenario or an explicit empty list")
    task_count = len(shift_demands)
    if staff_ids is None:
        staff_ids = [f"staff[{i}]" for i in range(invigilator_count)]
    if session_labels is None:
        session_labels = [f"session[{j}]" for j in range(task_count)]
    if len(staff_ids) != invigilator_count or len(session_labels) != task_count:
        raise ValueError("Core labels must match the staff and session counts")
    pool = IDPool(start_from=invigilator_count * task_count + 1)
    cnf = CNF()
    selectors = {}  # selector var -> human-readable description

    def var(i, j):
        return i * task_count + j + 1

    for j, demand in enumerate(shift_demands):
        _check_nonnegative_int(demand, f"shift_demands[{j}]")
        sel = pool.id(("cap", j))
        selectors[sel] = f"capacity({session_labels[j]})={demand}"
        if demand > invigilator_count:
            cnf.append([-sel])  # assuming sel true is immediately impossible
            continue
        variables = [var(i, j) for i in range(invigilator_count)]
        clauses = CardEnc.equals(
            lits=variables, bound=demand, vpool=pool, encoding=EncType.seqcounter
        ).clauses
        for clause in clauses:
            cnf.append([-sel] + clause)

    for i, j in busy:
        _check_nonnegative_int(i, "busy staff index")
        _check_nonnegative_int(j, "busy session index")
        if i >= invigilator_count or j >= task_count:
            raise ValueError(f"busy pair {(i, j)} is outside the instance")
        sel = pool.id(("busy", i, j))
        selectors[sel] = f"Busy({staff_ids[i]},{session_labels[j]})"
        cnf.append([-sel, -var(i, j)])

    for j, k in overlaps:
        _check_nonnegative_int(j, "overlap session index")
        _check_nonnegative_int(k, "overlap session index")
        if j >= task_count or k >= task_count or j == k:
            raise ValueError(f"overlap pair {(j, k)} must refer to two distinct sessions")
        for i in range(invigilator_count):
            sel = pool.id(("overlap", i, j, k))
            selectors[sel] = (f"NoDoubleBooking({staff_ids[i]},"
                              f"{session_labels[j]},{session_labels[k]})")
            cnf.append([-sel, -var(i, j), -var(i, k)])

    return cnf, selectors


def extract_minimal_core(cnf, selectors):
    """Return None for SAT, otherwise an inclusion-minimal list of selectors.

    Use the guarded CNF returned by encode_with_selectors. Removing any one
    selector from the returned core makes it SAT. This does not claim the
    smallest possible number of constraints, or a clause-level minimal core.
    """
    assumptions = list(selectors.keys())
    with Solver(name="m22", bootstrap_with=cnf.clauses) as solver:
        if solver.solve(assumptions=assumptions):
            return None
        core = list(solver.get_core())

    shrunk = True
    while shrunk:
        shrunk = False
        for lit in list(core):
            trial = [l for l in core if l != lit]
            with Solver(name="m22", bootstrap_with=cnf.clauses) as solver:
                if not solver.solve(assumptions=trial):
                    core = trial
                    shrunk = True
                    break
    return core


def demo():
    staff_count = 73
    shift_demands = [2]
    busy = [(i, 0) for i in range(staff_count)]

    cnf, selectors = encode_with_selectors(staff_count, shift_demands, busy, [])
    core = extract_minimal_core(cnf, selectors)

    print("UNSAT slice: task J=0 needs 2 people\n")
    print("Core:")
    for sel in core:
        print(f"  - {selectors[sel]}")
    print(f"\nCause:")
    busy_in_core = sum(1 for sel in core if selectors[sel].startswith("Busy"))
    free = staff_count - busy_in_core
    print(f"  Only {free} people remain available for task J=0, "
          f"but 2 are needed.")
    print(f"\nVerification:")
    with Solver(name="m22", bootstrap_with=cnf.clauses) as solver:
        print(f"  Full core: "
              f"{'UNSAT' if not solver.solve(assumptions=core) else 'SAT'}")
    all_min = True
    for sel in core:
        trial = [s for s in core if s != sel]
        with Solver(name="m22", bootstrap_with=cnf.clauses) as solver:
            if not solver.solve(assumptions=trial):
                all_min = False
    print(f"  Removing each constraint from the core individually: all "
          f"{'become SAT' if all_min else 'still UNSAT in at least one case!!'}")
    print(f"  => Core is {'minimal' if all_min else 'NOT minimal'}")
    print(f"\n  (Core size = {len(core)} out of {len(selectors)} "
          f"total constraints)")


if __name__ == "__main__":
    demo()
