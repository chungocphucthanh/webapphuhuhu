"""simulate_m2_ilp: the entry point that test_m2_ilp.py calls (Lead, req 2.7).

The test passes its own CSV, a list of busy (staff ID, MS Ca thi) pairs and three soft
weights, then reads m2_ilp/schedule.csv and m2_ilp/metrics.json back. This runs the same
model as run_m2 (M1 loader, two-stage CBC solve, check_schedule before writing), with every
pair available except the busy ones, and writes the two files in the test's format: one row
per (staff, shift code) and only max_load, baseline_max_load and beats_baseline.

A shift code held at both campuses is one test session. Both campus sessions run at the same
time, so H2 already keeps a person out of the second one and the merge loses no assignment.
The graded outputs still come from run_all.py (run_m2); calling this overwrites them.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import replace

from m1_logic.data_loader import load_dataset

from .config import M2_DIR, ModelConfig
from .instance import build_instance
from .soft import fit_fatigue_k
from .solve import solve
from .validate import check_schedule


def _max_codes(pairs) -> int:
    """Largest number of shift codes held by one person."""
    return max(Counter(person for person, code in set(pairs)).values())


def simulate_m2_ilp(input_file, availabilities, soft_weights) -> dict:
    """Solve input_file with the busy pairs and weights given; write the two test outputs."""
    if len(soft_weights) != 3:
        raise ValueError("soft_weights needs three values: location, fatigue, travel")
    data = load_dataset(input_file)
    staff = {person: i for i, person in enumerate(data["staff_ids"])}
    sessions_of = {}
    for j, (code, campus) in enumerate(data["session_ids"]):
        sessions_of.setdefault(code, []).append(j)
    unknown = [pair for pair in availabilities if pair[0] not in staff or pair[1] not in sessions_of]
    if unknown:
        raise ValueError(f"Busy pairs not found in {input_file}: {unknown[:5]}")
    # Busy for a shift code covers its sessions at both campuses.
    data["busy"] = sorted({(staff[person], j) for person, code in availabilities
                           for j in sessions_of[code]})

    inst = build_instance(availability="shift", data=data)
    inst = replace(inst, soft_weights=[float(w) for w in soft_weights])
    solution = solve(inst, ModelConfig(fatigue_k=fit_fatigue_k(inst)))
    if not solution.assigned:
        raise RuntimeError(f"No schedule (status {solution.status}); nothing written. "
                           f"Diagnosis: {solution.diagnosis}")
    violations = check_schedule(inst, solution.assigned)
    if violations:
        raise RuntimeError("The schedule breaks hard rules; nothing written:\n"
                           + "\n".join(violations[:20]))

    code_of = [code for code, campus in data["session_ids"]]
    worked = {(inst.staff_ids[i], code_of[j]) for i, j in solution.assigned}
    baseline = {(inst.staff_ids[i], code_of[j]) for i, j in inst.baseline}
    with (M2_DIR / "schedule.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["invigilator_id", "session_id", "assigned"])
        for person in inst.staff_ids:
            for code in sorted(sessions_of):
                writer.writerow([person, code, int((person, code) in worked)])
    max_load, baseline_max_load = _max_codes(worked), _max_codes(baseline)
    metrics = {"max_load": max_load, "baseline_max_load": baseline_max_load,
               "beats_baseline": max_load < baseline_max_load}
    (M2_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(f"[m2] {input_file}: max_load {max_load} vs baseline {baseline_max_load} "
          f"(beats_baseline={metrics['beats_baseline']}); wrote schedule.csv and metrics.json")
    return metrics
