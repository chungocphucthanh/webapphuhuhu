"""Solve prepared M1 scenarios with capacity, Busy and no double-booking."""

import argparse
import json
import sys
from pathlib import Path

from pysat.solvers import Solver

# Support both python -m m1_logic.sat_check and python m1_logic/sat_check.py.
if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from m1_logic.cnf import encode_invigilator_assignment
from m1_logic.data_loader import PROJECT_FOLDER
from m1_logic.prepare_instances import prepare_instances
from m1_logic.unsat_core import encode_with_selectors, extract_minimal_core


def solve_instance(data):
    """Return a schedule or a minimal constraint core; do not generate Busy here."""
    staff_count = len(data["staff_ids"])
    session_count = len(data["session_ids"])
    if session_count != len(data["shift_demands"]):
        raise ValueError("Each session must have exactly one demand")
    labels = [code + "_" + campus for code, campus in data["session_ids"]]
    arguments = (staff_count, data["shift_demands"], data["busy"], data["overlaps"])
    cnf = encode_invigilator_assignment(*arguments)
    with Solver(name="m22", bootstrap_with=cnf.clauses) as solver:
        satisfiable = solver.solve()
        literals = solver.get_model() if satisfiable else []

    result = {
        "satisfiable": satisfiable, "model": False, "unsat_core": None,
    }
    if satisfiable:
        schedule = {label: [] for label in labels}
        for literal in sorted(literals):
            if 0 < literal <= staff_count * session_count:
                i, j = divmod(literal - 1, session_count)
                schedule[labels[j]].append(data["staff_ids"][i])
        result["model"] = schedule
    else:
        guarded_cnf, selectors = encode_with_selectors(
            *arguments, staff_ids=data["staff_ids"], session_labels=labels,
        )
        core = extract_minimal_core(guarded_cnf, selectors)
        if core is None:
            raise RuntimeError("Selector encoding disagrees with the plain CNF")
        result["unsat_core"] = [selectors[s] for s in sorted(core)]
    return result


def main(seed=None):
    if seed is None:
        seed = int((PROJECT_FOLDER / "data/seed.txt").read_text(encoding="utf-8-sig").strip())
    cases = prepare_instances(seed)
    path = PROJECT_FOLDER / "m1_logic" / "sat_result.json"
    # Each case verifies the solver; keep the real SAT schedule in sat_result.json.
    for name in ("unsat", "sat"):
        data = cases[name]
        result = solve_instance(data)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if not result["satisfiable"]:
            print(f"[m1/{name}] UNSAT")
            for constraint in result["unsat_core"]:
                print(f"  {constraint}")
        else:
            print(f"[m1/{name}] SAT -> {path.name}")

    toy = cases["toy"]
    toy_unsat = dict(toy, busy=toy["unsat_busy"])
    print(f"[m1/toy] SAT example: {solve_instance(toy)['satisfiable']}; "
          f"UNSAT example: {solve_instance(toy_unsat)['satisfiable']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int)
    main(parser.parse_args().seed)
