"""Model size, runtime, LP bounds and baseline comparison (req 2.9).

Run explicitly from the repository root: python -m m2_ilp.performance.
The command measures the configured models and writes performance.json.
Importing the module does not run a benchmark.
"""

from __future__ import annotations

import json
from dataclasses import replace
from itertools import product
from pathlib import Path
from typing import TYPE_CHECKING

from .metrics import compute_metrics, loads

if TYPE_CHECKING:
    from .config import ModelConfig


def size_table(inst, config: ModelConfig) -> list[dict]:
    """Count variables and rows by family in each stage, without solving."""
    from .model import build_model

    rows = []
    for stage in (1, 2):
        t_cap = None if stage == 1 else (config.t_cap if config.t_cap is not None else 10**6)
        variant = replace(config, stage=stage, t_cap=t_cap)
        prob, x, handles = build_model(inst, variant)
        for kind, counts in (("variable", handles.n_vars), ("constraint", handles.n_rows)):
            for family, count in counts.items():
                rows.append({"stage": stage, "kind": kind, "family": family, "count": count})
            rows.append({"stage": stage, "kind": kind, "family": "total",
                         "count": sum(counts.values())})
        if stage == 1:
            n, m = len(inst.staff_ids), len(inst.session_names)
            rows += [
                {"stage": 1, "kind": "reference", "family": "x_dense", "count": n * m},
                {"stage": 1, "kind": "reference", "family": "H2_pairwise", "count": handles.h2_pairwise},
                {"stage": 1, "kind": "reference", "family": "H2_pairwise_dense",
                 "count": n * len(inst.overlaps)},
                {"stage": 1, "kind": "reference", "family": "cliques", "count": len(handles.cliques)},
            ]
    return rows


def lp_bound(inst, config: ModelConfig, t_cap=None) -> dict:
    """Solve the LP relaxation of stage 1, or stage 2 with the given cap."""
    from .model import build_model
    from .solve import run_cbc

    stage = 1 if t_cap is None else 2
    variant = replace(config, stage=stage, t_cap=t_cap, relax_integrality=True)
    prob, x, handles = build_model(inst, variant)
    result = run_cbc(prob, variant)
    return {"status": result.status, "value": result.objective, "runtime": result.runtime}


def runtime_table(seed: int | None = None) -> list[dict]:
    """Measure both stages and LP relaxations on day/week/full horizons."""
    from .config import ModelConfig
    from .fixtures import week_slice
    from .instance import build_instance, small_slice
    from .solve import solve
    from .soft import fit_fatigue_k

    full = build_instance(seed)
    config = ModelConfig(fatigue_k=fit_fatigue_k(full))
    horizons = [("1 day", small_slice(full, 1)), ("1 week", week_slice(full, 1)),
                ("2 weeks", week_slice(full, 2)), ("3 weeks", week_slice(full, 3)),
                ("full", full)]
    rows = []
    for name, inst in horizons:
        solution = solve(inst, config)
        sizes = size_table(inst, replace(config, t_cap=solution.t_star))
        total = {(r["stage"], r["kind"]): r["count"] for r in sizes if r["family"] == "total"}
        lp1 = lp_bound(inst, config)
        lp2 = (lp_bound(inst, config, t_cap=solution.t_star) if solution.t_star is not None
               else {"status": "not_run", "value": None})
        stage2 = solution.stages.get(2)
        rows.append({
            "horizon": name, "days": len(inst.sessions_by_day), "staff": len(inst.staff_ids),
            "sessions": len(inst.session_names), "demand": sum(inst.demand), "pairs_A": len(inst.A),
            "stage1_vars": total[1, "variable"], "stage1_rows": total[1, "constraint"],
            "stage2_vars": total[2, "variable"], "stage2_rows": total[2, "constraint"],
            "z_lp_stage1": round(lp1["value"], 6) if lp1["value"] is not None else None,
            "z_ilp_stage1": solution.t_star,
            "z_lp_stage2": round(lp2["value"], 6) if lp2["value"] is not None else None,
            "z_ilp_stage2": (round(stage2.objective, 6)
                             if stage2 is not None and stage2.objective is not None else None),
            "stage1_runtime": round(solution.stages[1].runtime, 3),
            "stage2_runtime": round(stage2.runtime, 3) if stage2 is not None else None,
            "stage1_gap": solution.stages[1].gap, "stage2_gap": stage2.gap if stage2 is not None else None,
            "stage1_nodes": solution.stages[1].nodes,
            "stage2_nodes": stage2.nodes if stage2 is not None else None,
            "status": solution.status,
            "lp_stage1_status": lp1["status"], "lp_stage2_status": lp2["status"],
        })
    return rows


def chord_ablation(inst, config: ModelConfig, t_star: int, time_limit: int = 30) -> list[dict]:
    """Compare stage 2 with and without DEVC using the same cap and time limit."""
    from .model import build_model
    from .solve import run_cbc

    rows = []
    for chord in (True, False):
        variant = replace(config, stage=2, t_cap=t_star, l1_chord=chord, time_limit=time_limit)
        prob, x, handles = build_model(inst, variant)
        result = run_cbc(prob, variant)
        lp = lp_bound(inst, variant, t_cap=t_star)
        rows.append({"l1_chord": chord, "time_limit": time_limit, "status": result.status,
                     "objective": round(result.objective, 6) if result.objective is not None else None,
                     "gap": result.gap, "nodes": result.nodes, "runtime": round(result.runtime, 3),
                     "lp_bound": round(lp["value"], 6) if lp["value"] is not None else None,
                     "lp_status": lp["status"]})
    return rows


def baseline_comparison(inst, solution) -> list[dict]:
    """Compare both schedules with the same K and default instance weights."""
    from .config import ModelConfig
    from .soft import fit_fatigue_k

    k = fit_fatigue_k(inst)
    config = ModelConfig(fatigue_k=k)
    lam = config.lambdas(inst)
    rows = []
    measured = {name: compute_metrics(inst, assigned, k)
                for name, assigned in (("baseline", inst.baseline), ("m2", solution.assigned))}
    for metrics in measured.values():
        metrics["weighted_objective"] = (metrics["l1"] + lam[0] * metrics["location"]
                                         + lam[1] * metrics["fatigue"] + lam[2] * metrics["travel"])
    for metric in measured["baseline"]:
        old, new = measured["baseline"][metric], measured["m2"][metric]
        rows.append({"metric": metric, "baseline": round(old, 6), "m2": round(new, 6),
                     "change": round(new - old, 6)})
    return rows


def worked_example() -> dict:
    """Enumerate the brief's small example and compare with the two-stage solve."""
    from .config import ModelConfig
    from .fixtures import lp_gap_instance
    from .solve import solve

    inst = lp_gap_instance()
    n, m = len(inst.staff_ids), len(inst.session_names)
    w_bar = sum(inst.demand) / n
    profiles = {}
    for owners in product(range(n), repeat=m):
        w = loads(inst, [(i, j) for j, i in enumerate(owners)])
        if max(w) > 2:
            continue
        key = tuple(sorted(w, reverse=True))
        profiles[key] = {"t": max(w), "l1": round(sum(abs(v - w_bar) for v in w), 6)}
    t_best = min(p["t"] for p in profiles.values())
    l1_best = min(p["l1"] for p in profiles.values() if p["t"] == t_best)
    solution = solve(inst, ModelConfig())
    lp = lp_bound(inst, ModelConfig())
    return {
        "profiles": [{"loads": list(k), **v} for k, v in sorted(profiles.items())],
        "min_max_optima": [list(k) for k, v in sorted(profiles.items()) if v["t"] == t_best],
        "lexicographic_optima": [list(k) for k, v in sorted(profiles.items())
                                 if v["t"] == t_best and v["l1"] == l1_best],
        "two_stage_loads": sorted(loads(inst, solution.assigned), reverse=True),
        "t_star": solution.t_star,
        "z_lp": round(lp["value"], 6) if lp["value"] is not None else None,
        "lp_status": lp["status"],
    }


def main(seed: int | None = None, solution=None) -> dict:
    from .config import ModelConfig
    from .instance import build_instance
    from .solve import solve
    from .soft import fit_fatigue_k

    inst = build_instance(seed)
    config = ModelConfig(fatigue_k=fit_fatigue_k(inst))
    if solution is None:
        solution = solve(inst, config)
    result = {
        "size_full": size_table(inst, replace(config, t_cap=solution.t_star)),
        "runtime": runtime_table(inst.seed),
        "chord_ablation": (chord_ablation(inst, config, solution.t_star)
                           if solution.t_star is not None else []),
        "baseline_comparison": baseline_comparison(inst, solution),
        "worked_example": worked_example(),
    }
    for row in result["runtime"]:
        print(f"[m2/perf] {row['horizon']}: |A|={row['pairs_A']}, stage-2 vars={row['stage2_vars']}, "
              f"rows={row['stage2_rows']}, Z_LP={row['z_lp_stage1']} vs t*={row['z_ilp_stage1']}, "
              f"time {row['stage1_runtime']}+{row['stage2_runtime']} s")
    for row in result["chord_ablation"]:
        print(f"[m2/perf] stage 2 l1_chord={row['l1_chord']}: {row['status']}, gap {row['gap']}, "
              f"{row['runtime']} s, LP bound {row['lp_bound']}")
    path = Path(__file__).resolve().parent / "performance.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[m2/perf] wrote {path.name}")
    return result


if __name__ == "__main__":
    main()
