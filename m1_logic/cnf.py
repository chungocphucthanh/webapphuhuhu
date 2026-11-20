from pysat.card import CardEnc, EncType
from pysat.formula import CNF, IDPool


def _check_nonnegative_int(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def encode_invigilator_assignment(
    invigilator_count, shift_demands, busy, overlaps
) -> CNF:
    """Encode capacity, Busy and overlap without modifying inputs.

    Indices start at 0. Each session j needs exactly shift_demands[j] staff.
    Pass scenario busy (i,j), not busy_by_shift. Availability must be explicit.
    overlaps contains distinct task pairs (j,k), in either order. Pair inputs
    may be one-pass iterables. Non-overlapping tasks may share the same staff.

    Assign(i,j) has ID i*M+j+1, with M=len(shift_demands); IDs above N*M
    are auxiliary variables, not assignments. Clauses are added in order:
    capacity, Busy, overlap, preserving input order in each group.
    Invalid counts/indices raise ValueError; excessive demands encode UNSAT.
    """
    _check_nonnegative_int(invigilator_count, "invigilator_count")
    if busy is None:
        raise ValueError("Busy is unknown; supply a seeded scenario or an explicit empty list")
    task_count = len(shift_demands)
    cnf = CNF()
    # Reserve every assignment ID, including tasks not encoded yet.
    pool = IDPool(start_from=invigilator_count * task_count + 1)

    def var(i, j):
        return i * task_count + j + 1

    for j, demand in enumerate(shift_demands):
        _check_nonnegative_int(demand, f"shift_demands[{j}]")
        if demand > invigilator_count:
            cnf.append([])  # A well-formed but impossible demand is UNSAT.
        else:
            variables = [var(i, j) for i in range(invigilator_count)]
            cnf.extend(CardEnc.equals(
                lits=variables, bound=demand, vpool=pool,
                encoding=EncType.seqcounter,
            ).clauses)

    for i, j in busy:
        _check_nonnegative_int(i, "busy staff index")
        _check_nonnegative_int(j, "busy session index")
        if i >= invigilator_count or j >= task_count:
            raise ValueError(f"busy pair {(i, j)} is outside the instance")
        cnf.append([-var(i, j)])

    for j, k in overlaps:
        _check_nonnegative_int(j, "overlap task index")
        _check_nonnegative_int(k, "overlap task index")
        if j >= task_count or k >= task_count or j == k:
            raise ValueError(f"overlap pair {(j, k)} must refer to two distinct tasks")
        for i in range(invigilator_count):
            cnf.append([-var(i, j), -var(i, k)])
    return cnf
