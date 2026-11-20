"""M2 entry point for run_all.py (Lead, req 2.7).

python run_all.py --seed $(cat data/seed.txt) --stage m2
Writes m2_ilp/schedule.csv and m2_ilp/metrics.json only after the independent validator
accepts the schedule, then regenerates the report artifacts (counterexample.json,
tuning.json, performance.json). schedule.csv and metrics.json carry no runtime, gap or
timestamp, so two runs from a clean clone hash identically.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .config import DEFAULT_AVAILABILITY, M2_DIR, ModelConfig
from .instance import build_instance, write_preferences
from .metrics import compute_metrics
from .soft import fit_fatigue_k
from .solve import solve
from .validate import check_schedule


def write_schedule(inst, assigned, path: Path) -> None:
    """One row per (i, j) in I x J, ordered by i then j; UTF-8 without BOM, LF endings."""
    assigned = set(assigned)
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["invigilator_id", "session_id", "assigned"])
        for i, person in enumerate(inst.staff_ids):
            for j, session in enumerate(inst.session_names):
                writer.writerow([person, session, int((i, j) in assigned)])


def write_metrics(metrics: dict, path: Path) -> None:
    """Sorted keys, floats rounded to 6 decimals, indent 2, trailing newline."""
    clean = {key: round(value, 6) if isinstance(value, float) else value
             for key, value in metrics.items()}
    Path(path).write_text(json.dumps(clean, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_m2(seed: int, out_dir: Path | None = None, extras: bool = True) -> dict:
    """Build, solve, validate and write the M2 outputs; return the metrics dict.

    out_dir=None writes to m2_ilp/ and regenerates data/simulated_preferences.csv.
    extras=False skips the report artifacts (used by the reproducibility test).
    """
    inst = build_instance(seed, DEFAULT_AVAILABILITY)
    if out_dir is None:
        out_dir = M2_DIR
        write_preferences(inst)
    k = fit_fatigue_k(inst)
    config = ModelConfig(fatigue_k=k)
    solution = solve(inst, config)
    if not solution.assigned:
        raise RuntimeError(f"M2 found no schedule (status {solution.status}); nothing written. "
                           f"Diagnosis: {solution.diagnosis}")
    violations = check_schedule(inst, solution.assigned)
    if violations:
        raise RuntimeError("The M2 schedule breaks hard rules; nothing written:\n"
                           + "\n".join(violations[:20]))

    baseline = compute_metrics(inst, inst.baseline, k)
    metrics = compute_metrics(inst, solution.assigned, k)
    metrics.update({
        "baseline_max_load": baseline["max_load"],
        "beats_baseline": metrics["max_load"] < baseline["max_load"],
        "t_star": solution.t_star, "availability_mode": inst.availability,
        "flip_rate": inst.flip_rate, "fatigue_k": k, "seed": inst.seed,
        "status": solution.status,
    })
    out_dir = Path(out_dir)
    write_schedule(inst, solution.assigned, out_dir / "schedule.csv")
    write_metrics(metrics, out_dir / "metrics.json")
    n, m = len(inst.staff_ids), len(inst.session_names)
    print(f"[m2] |I|={n}, |J|={m}, sum r_j={sum(inst.demand)}; x_ij for {len(inst.A)} pairs in A "
          f"instead of {n * m} (|I| x |J|)")
    print(f"[m2] {inst.availability} availability, |A|={len(inst.A)}, K={k}: status "
          f"{solution.status}, t*={solution.t_star}, max_load {metrics['max_load']} vs baseline "
          f"{baseline['max_load']} (beats_baseline={metrics['beats_baseline']}), "
          f"L1 {metrics['l1']:.3f} vs {baseline['l1']:.3f}")
    where = out_dir.name if out_dir == M2_DIR else out_dir
    print(f"[m2] validator: 0 violations; wrote schedule.csv and metrics.json in {where}/")

    if extras:
        from . import counterexample, performance, tuning

        counterexample.main(inst.seed)
        tuning.main(inst.seed)
        performance.main(inst.seed, solution)
    return metrics


if __name__ == "__main__":
    import argparse

    from m1_logic.data_loader import PROJECT_FOLDER

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, help="defaults to data/seed.txt")
    parser.add_argument("--no-extras", action="store_true", help="only schedule.csv and metrics.json")
    args = parser.parse_args()
    if args.seed is None:
        args.seed = int((PROJECT_FOLDER / "data/seed.txt").read_text(encoding="utf-8-sig").strip())
    run_m2(args.seed, extras=not args.no_extras)
