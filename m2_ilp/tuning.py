"""Infeasibility diagnosis and sensitivity analysis (TV5, req 2.8).

Relax: when stage 1 is infeasible, H3 becomes sum_i x_ij + u_j = r_j with u_j >= 0 and
the objective t + M_el * sum_j u_j. The sessions with u_j > 0 are the M2 analogue of the
M1 unsat core: they name the capacity rows that cannot hold together with H1 and H2.
Re-weight: re-solve with each soft weight scaled by 0.5, 1, 2 and with K-1, K, K+1.
Run from the repository root: python -m m2_ilp.tuning  (writes m2_ilp/tuning.json)
"""

from __future__ import annotations

import json
from dataclasses import replace

import pulp

from .config import M2_DIR, SOFT_NAMES, ModelConfig
from .metrics import compute_metrics
from .model import build_model
from .solve import run_cbc, solve


def diagnose(inst, config: ModelConfig) -> list[dict]:
    """Solve stage 1 with elastic=True. Return [{"session", "demand", "missing"}] for every
    u_j > 0, sorted by label; empty if the instance is feasible."""
    prob, x, handles = build_model(inst, replace(config, stage=1, t_cap=None, elastic=True))
    result = run_cbc(prob, config)
    if result.status not in ("optimal", "feasible"):
        raise RuntimeError(f"The elastic model must be feasible, got {result.status}")
    rows = []
    for j, u in handles.slack.items():
        missing = pulp.value(u) or 0.0
        if missing > 1e-6:
            rows.append({"session": inst.session_names[j], "demand": inst.demand[j],
                         "missing": int(round(missing))})
    return sorted(rows, key=lambda row: row["session"])


def _row(inst, config, solution):
    metrics = compute_metrics(inst, solution.assigned, config.fatigue_k)
    runtime = sum(stage.runtime for stage in solution.stages.values())
    return {"max_load": metrics["max_load"], "l1": round(metrics["l1"], 6),
            "location": metrics["location"], "fatigue": metrics["fatigue"],
            "travel": metrics["travel"], "runtime": round(runtime, 3),
            "status": solution.status}


def weight_sensitivity(inst, config: ModelConfig, factors=(0.5, 1.0, 2.0)) -> list[dict]:
    """Scale one weight at a time; the factor-1 run is shared by the three weights."""
    cache = {}
    rows = []
    for w, name in enumerate(SOFT_NAMES):
        for factor in factors:
            scale = [1.0, 1.0, 1.0]
            scale[w] = float(factor)
            key = tuple(scale)
            if key not in cache:
                variant = replace(config, weight_scale=key)
                cache[key] = _row(inst, variant, solve(inst, variant))
            rows.append({"weight": name, "factor": float(factor),
                         "lambda": round(config.lambdas(inst)[w] * factor, 6), **cache[key]})
    return rows


def k_sensitivity(inst, config: ModelConfig) -> list[dict]:
    """K-1, K, K+1; each schedule is measured with its own K."""
    rows = []
    for k in (config.fatigue_k - 1, config.fatigue_k, config.fatigue_k + 1):
        if k < 0:
            continue
        variant = replace(config, fatigue_k=k)
        rows.append({"k": k, "value": k, **_row(inst, variant, solve(inst, variant))})
    return rows


def m1_unsat_demo(seed: int, config: ModelConfig) -> dict:
    """Run solve() on M1's UNSAT slice (one shift kept at demand - 1 available staff) and
    put the elastic diagnosis next to M1's minimal unsat core for the same data."""
    from m1_logic.prepare_instances import prepare_instances
    from m1_logic.sat_check import solve_instance

    from .instance import build_instance

    case = prepare_instances(seed)["unsat"]
    inst = build_instance(seed, "shift", data=case)
    print("[m2/tuning] infeasible demo on M1's UNSAT slice (expected to be infeasible):")
    solution = solve(inst, config)
    return {
        "instance": "M1 UNSAT slice from m1_logic.prepare_instances(seed)",
        "staff": len(inst.staff_ids), "sessions": len(inst.session_names),
        "shortage_shift": case["shortage_shift"],
        "available_at_shortage": case["available_at_shortage"],
        "demand_at_shortage": case["demand_at_shortage"],
        "m2_status": solution.status,
        "m2_missing": solution.diagnosis,
        "m1_unsat_core": solve_instance(case)["unsat_core"],
    }


HORIZONS = (("1 week", 1), ("2 weeks", 2), ("3 weeks", 3), ("full", None))


def main(seed: int | None = None) -> dict:
    from .fixtures import week_slice
    from .instance import build_instance
    from .soft import daily_load_distribution, fit_fatigue_k

    full = build_instance(seed)
    k = fit_fatigue_k(full)
    config = ModelConfig(fatigue_k=k)
    weights, ks = [], []
    # Same horizons as performance.py; slices are prefixes, never chosen by their result.
    for name, weeks in HORIZONS:
        inst = full if weeks is None else week_slice(full, weeks)
        weights += [{"horizon": name, **row} for row in weight_sensitivity(inst, config)]
        ks += [{"horizon": name, **row} for row in k_sensitivity(inst, config)]
    result = {
        "fatigue_k": {"rule": "smallest K covering >= 95% of baseline working person-days",
                      "distribution": {str(n): c for n, c in daily_load_distribution(full).items()},
                      "k": k},
        "infeasible_demo": m1_unsat_demo(full.seed, config),
        "weight_sensitivity": weights,
        "k_sensitivity": ks,
    }
    demo = result["infeasible_demo"]
    print(f"[m2/tuning] M1 UNSAT slice: status {demo['m2_status']}, missing {demo['m2_missing']}")
    keys = ("max_load", "l1", "location", "fatigue", "travel")
    for name, weeks in HORIZONS:   # print the base run and only the settings that change it
        rows = [r for r in weights if r["horizon"] == name]
        base = next(r for r in rows if r["factor"] == 1.0)
        print(f"  {name}: base " + ", ".join(f"{key} {base[key]}" for key in keys))
        for row in rows + [r for r in ks if r["horizon"] == name]:
            if any(row[key] != base[key] for key in keys):
                setting = f"{row['weight']} x{row['factor']}" if "weight" in row else f"K={row['k']}"
                print(f"    {setting}: " + ", ".join(f"{key} {row[key]}" for key in keys))
    path = M2_DIR / "tuning.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[m2/tuning] wrote {path.name}")
    return result


if __name__ == "__main__":
    main()
