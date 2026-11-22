"""Offline M5 artifact precomputation and fast fallback loader (M5 Lead, Thanh)."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from app.data_views import instance_to_m1_data, load_preset_instance, read_team_seed
from app.dynamics_views import evaluate_dynamics
from app.solver_views import compare_schedule_metrics, run_m1_check
from app.temporal_views import (
    compare_temporal_schedules,
    evaluate_temporal_validity,
    load_automata_suite,
)
from m1_logic.data_loader import DEFAULT_PATH, PROJECT_FOLDER
from m2_ilp.config import M2_DIR, ModelConfig
from m2_ilp.instance import Instance, build_instance
from m2_ilp.soft import fit_fatigue_k
from m2_ilp.solve import solve
from m2_ilp.validate import check_schedule
from m3_automata.regular_to_ilp import solve_with_rules
from m4_dynamics.fatigue import calibrate, fit_threshold, simulate_history
from m4_dynamics.planning import refine_schedule
from m4_dynamics.workload import read_schedule, weekly_workload

APP_DIR = Path(__file__).resolve().parent
DEFAULT_BUNDLE = APP_DIR / "m5_bundle.json"


def _dataset_sha256() -> str:
    return hashlib.sha256(Path(DEFAULT_PATH).read_bytes()).hexdigest()


def _strip_runtime(m1_result: dict) -> dict:
    return {k: v for k, v in m1_result.items() if k != "runtime_ms"}


def _load_or_solve_m2(inst: Instance, k: int) -> frozenset[tuple[int, int]]:
    schedule_csv = M2_DIR / "schedule.csv"
    if schedule_csv.is_file():
        return read_schedule(inst, schedule_csv)
    sol = solve(inst, ModelConfig(fatigue_k=k))
    if not sol.assigned or check_schedule(inst, sol.assigned):
        raise RuntimeError("Failed to obtain a valid M2 schedule")
    return sol.assigned


def _load_or_solve_m4(
    inst: Instance,
    m2_assigned: frozenset[tuple[int, int]],
) -> frozenset[tuple[int, int]]:
    m4_csv = PROJECT_FOLDER / "m4_dynamics" / "fatigue_aware_schedule.csv"
    if m4_csv.is_file():
        return read_schedule(inst, m4_csv)
    base_wl = weekly_workload(inst, inst.baseline)
    params, _ = calibrate(base_wl)
    threshold = fit_threshold(simulate_history(base_wl, params))
    refined, _ = refine_schedule(inst, m2_assigned, params, threshold)
    return refined


def run_m5(seed: int, out_dir: Path | None = None, *, weeks: int = 52) -> dict:
    """Precompute and verify the deterministic M5 bundle for the full dataset."""
    inst = build_instance(seed)
    k = fit_fatigue_k(inst)
    suite = load_automata_suite()

    m1_full = _strip_runtime(run_m1_check(instance_to_m1_data(inst)))
    sat_case, _ = load_preset_instance("m1_slice", seed=inst.seed, m1_scenario="sat")
    unsat_case, _ = load_preset_instance("m1_slice", seed=inst.seed, m1_scenario="unsat")
    m1_slice_sat = _strip_runtime(run_m1_check(sat_case))
    m1_slice_unsat = _strip_runtime(run_m1_check(unsat_case))
    if not m1_full["satisfiable"] or not m1_slice_sat["satisfiable"] or m1_slice_unsat["satisfiable"]:
        raise RuntimeError("M1 feasibility verification failed during M5 precompute")

    m2_assigned = _load_or_solve_m2(inst, k)
    sol_m3, _, _ = solve_with_rules(inst, ModelConfig(fatigue_k=k, time_limit=150), suite["minimal"])
    if not sol_m3.assigned:
        raise RuntimeError(f"M2 + R1xR2xR3 failed with status {sol_m3.status}")
    m4_assigned = _load_or_solve_m4(inst, m2_assigned)

    schedules = {
        "Baseline": frozenset(inst.baseline),
        "M2 Optimal": m2_assigned,
        "M2 + R1xR2xR3": sol_m3.assigned,
        "M4 Fatigue-Aware": m4_assigned,
    }
    for name, pairs in schedules.items():
        issues = check_schedule(inst, pairs)
        if issues:
            raise RuntimeError(f"{name} violates hard rules: {issues[:5]}")

    m3_audit = evaluate_temporal_validity(inst, sol_m3.assigned, suite=suite)
    if not m3_audit["schedule_valid"]:
        raise RuntimeError("M2 + R1xR2xR3 schedule failed DFA acceptance verification")

    m2_table = compare_schedule_metrics(inst, schedules, fatigue_k=k)
    m3_table = compare_temporal_schedules(inst, schedules, suite=suite)
    dyn = evaluate_dynamics(inst, schedules, weeks=weeks)
    if any(row["final_max_error"] > 1e-8 for row in dyn["summary_rows"]):
        raise RuntimeError("M4 trajectory failed fixed-point convergence check in M5")

    payload = {
        "seed": inst.seed,
        "dataset_sha256": _dataset_sha256(),
        "staff_count": len(inst.staff_ids),
        "session_count": len(inst.session_names),
        "total_demand": sum(inst.demand),
        "fatigue_k": k,
        "weeks": weeks,
        "m1": {
            "full_satisfiable": m1_full["satisfiable"],
            "full_clauses": m1_full["n_clauses"],
            "slice_sat": m1_slice_sat["satisfiable"],
            "slice_unsat_core": m1_slice_unsat["unsat_core"],
        },
        "m2_comparison": m2_table,
        "m3_comparison": m3_table,
        "m4_parameters": dyn["parameters"],
        "m4_stability": dyn["stability"],
        "m4_threshold": dyn["threshold"],
        "m4_summary": dyn["summary_rows"],
        "schedules": {
            label: [list(pair) for pair in sorted(pairs)]
            for label, pairs in schedules.items()
        },
    }
    clean = json.loads(json.dumps(payload), parse_float=lambda text: round(float(text), 6))
    target_dir = APP_DIR if out_dir is None else Path(out_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    bundle_file = target_dir / DEFAULT_BUNDLE.name
    bundle_file.write_text(
        json.dumps(clean, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"[m5] verified M1 SAT/UNSAT, M2 (t*={sol_m3.t_star}), "
        f"M3 DFA valid ({m3_audit['accepted_count']}/{m3_audit['total_staff']}), "
        f"and M4 {weeks}-week convergence"
    )
    print(f"[m5] wrote {bundle_file}")
    return clean


def _add_live_dfa_schedule(inst: Instance, schedules: dict, k: int) -> bool:
    suite = load_automata_suite()
    solution, _, _ = solve_with_rules(inst, ModelConfig(fatigue_k=k, time_limit=150), suite["minimal"])
    if not solution.assigned or check_schedule(inst, solution.assigned):
        return False
    schedules["M2 + R1xR2xR3"] = solution.assigned
    return True


def load_full_schedules(
    seed: int,
    *,
    compute_m3_live: bool = False,
    bundle_path: Path | None = None,
) -> tuple[Instance, dict[str, frozenset[tuple[int, int]]], str]:
    """Load precomputed full-dataset schedules if current, else fall back cleanly."""
    inst = build_instance(seed)
    path = DEFAULT_BUNDLE if bundle_path is None else Path(bundle_path)
    saved_schedules = None
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if (isinstance(raw, dict) and raw.get("seed") == inst.seed
                    and raw.get("dataset_sha256") == _dataset_sha256()
                    and isinstance(raw.get("schedules"), dict)):
                candidates = {
                    name: frozenset(tuple(pair) for pair in pairs)
                    for name, pairs in raw["schedules"].items()
                }
                if candidates and all(not check_schedule(inst, pairs) for pairs in candidates.values()):
                    saved_schedules = candidates
        except (OSError, TypeError, ValueError):
            pass
    if saved_schedules is not None:
        source = "precomputed bundle (app/m5_bundle.json)"
        if compute_m3_live and "M2 + R1xR2xR3" not in saved_schedules:
            if _add_live_dfa_schedule(inst, saved_schedules, fit_fatigue_k(inst)):
                source = "precomputed bundle + live DFA"
        return inst, saved_schedules, source

    k = fit_fatigue_k(inst)
    m2_assigned = _load_or_solve_m2(inst, k)
    m4_assigned = _load_or_solve_m4(inst, m2_assigned)
    schedules = {
        "Baseline": frozenset(inst.baseline),
        "M2 Optimal": m2_assigned,
        "M4 Fatigue-Aware": m4_assigned,
    }
    if compute_m3_live:
        _add_live_dfa_schedule(inst, schedules, k)
    return inst, schedules, "live repository artifacts"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=None, help="defaults to data/seed.txt")
    parser.add_argument("--out-dir", type=Path, default=APP_DIR)
    parser.add_argument("--weeks", type=int, default=52)
    args = parser.parse_args()
    seed = read_team_seed() if args.seed is None else args.seed
    run_m5(seed, args.out_dir, weeks=args.weeks)


if __name__ == "__main__":
    main()
