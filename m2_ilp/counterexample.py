"""Two plausible but wrong models and the invalid schedules they admit (TV2, req 2.10).

(a) drop_overlap=True removes H2. The solver then double-books a person and reports a
    fairer schedule than the correct model; the independent validator rejects it.
(b) relax_integrality=True makes x continuous. On the brief's example the LP reports a
    maximum load of 4/3 with fractional x ("1/3 of an invigilator"); the ILP needs 2.
Every number is generated here. Run from the repository root:
python -m m2_ilp.counterexample  (writes m2_ilp/counterexample.json)
"""

from __future__ import annotations

import json
from dataclasses import replace
from fractions import Fraction

from .config import M2_DIR, ModelConfig
from .fixtures import lp_gap_instance
from .metrics import compute_metrics, loads
from .model import build_model
from .solve import run_cbc, solve
from .validate import check_schedule

TOL = 1e-6


def _fairness(metrics):
    return {"max_load": metrics["max_load"], "l1": round(metrics["l1"], 6),
            "spread": metrics["spread"]}


def double_bookings(inst, assigned) -> list[dict]:
    """Every person in two overlapping sessions: staff ID, both session IDs and times."""
    assigned = set(assigned)
    rows = []
    for i, person in enumerate(inst.staff_ids):
        for j, k in sorted(inst.overlaps):
            if (i, j) in assigned and (i, k) in assigned:
                rows.append({"staff": person,
                             "sessions": [inst.session_names[j], inst.session_names[k]],
                             "times": [f"{s:%Y-%m-%d %H:%M}-{e:%H:%M}"
                                       for s, e in (inst.intervals[j], inst.intervals[k])]})
    return rows


def compare(inst, config: ModelConfig) -> dict:
    """Solve the correct model and the drop_overlap model with the same config."""
    right = solve(inst, config)
    wrong = solve(inst, replace(config, drop_overlap=True))
    m_right = compute_metrics(inst, right.assigned, config.fatigue_k)
    m_wrong = compute_metrics(inst, wrong.assigned, config.fatigue_k)
    return {
        "correct": {"t_star": right.t_star, "objective": round(right.objective["total"], 6),
                    **_fairness(m_right), "violations": len(check_schedule(inst, right.assigned))},
        "wrong": {"t_star": wrong.t_star, "objective": round(wrong.objective["total"], 6),
                  **_fairness(m_wrong), "violations": len(check_schedule(inst, wrong.assigned))},
        "_wrong_assigned": wrong.assigned,
    }


def drop_overlap_example(inst, config: ModelConfig = ModelConfig(use_soft=False)) -> dict:
    """(a) On the shortest prefix small_slice(inst, n) where it happens, the drop_overlap
    optimum double-books someone and is strictly fairer, by (max_load, L1), than the
    correct optimum. Prefixes are scanned in order, so the slice is not hand-picked."""
    from .instance import small_slice

    for n in range(1, len(inst.sessions_by_day) + 1):
        piece = small_slice(inst, n)
        if not piece.overlaps:
            continue
        result = compare(piece, config)
        right, wrong = result["correct"], result["wrong"]
        fairer = (wrong["max_load"], wrong["l1"] + TOL) < (right["max_load"], right["l1"])
        if wrong["violations"] and fairer:
            assigned = result.pop("_wrong_assigned")
            return {
                "slice": {"n_days": n, "staff": len(piece.staff_ids),
                          "sessions": len(piece.session_names),
                          "overlap_pairs": len(piece.overlaps)},
                "use_soft": config.use_soft, **result,
                "double_booked": double_bookings(piece, assigned),
                "validator": check_schedule(piece, assigned),
            }
    return {"slice": None, "note": "no prefix slice where dropping H2 is strictly fairer"}


def full_data_effect(inst, config: ModelConfig, baseline_max_load: int) -> dict:
    """(a) on the whole instance: does the wrong model 'beat the baseline'?"""
    result = compare(inst, config)
    assigned = result.pop("_wrong_assigned")
    result["baseline_max_load"] = baseline_max_load
    result["wrong_claims_beats_baseline"] = result["wrong"]["max_load"] < baseline_max_load
    result["correct_beats_baseline"] = result["correct"]["max_load"] < baseline_max_load
    result["double_booked_staff"] = len({row["staff"] for row in double_bookings(inst, assigned)})
    return result


def relax_integrality_example() -> dict:
    """(b) brief p.5 example: LP stage 1 gives t = 4/3 with fractional x; ILP gives t* = 2."""
    inst = lp_gap_instance()
    config = ModelConfig()
    prob, x, handles = build_model(inst, replace(config, relax_integrality=True))
    lp = run_cbc(prob, config)
    values = {pair: Fraction(var.varValue).limit_denominator(12) for pair, var in x.items()}
    rounded = {pair for pair, value in values.items() if value > Fraction(1, 2)}
    ilp = solve(inst, config)
    return {
        "instance": "3 staff, 4 back-to-back sessions, r_j = 1 (brief p.5)",
        "z_lp": str(Fraction(lp.objective).limit_denominator(12)), "z_lp_value": round(lp.objective, 6),
        "z_ilp": ilp.t_star,
        "lp_loads": [str(sum((values[i, j] for j in range(4)), Fraction(0))) for i in range(3)],
        "lp_x": {f"{inst.staff_ids[i]},{inst.session_names[j]}": str(v)
                 for (i, j), v in sorted(values.items())},
        "fractional_pairs": sum(0 < v < 1 for v in values.values()),
        "rounded_lp_violations": check_schedule(inst, rounded),
        "ilp_loads": sorted(loads(inst, ilp.assigned), reverse=True),
        "ilp_violations": check_schedule(inst, ilp.assigned),
    }


def main(seed: int | None = None) -> dict:
    from .instance import build_instance
    from .soft import fit_fatigue_k

    default = build_instance(seed)
    k = fit_fatigue_k(default)
    baseline_max = compute_metrics(default, default.baseline, k)["max_load"]
    # M1 Busy reading of forum d=33734: i is free only for shift codes it worked in the
    # baseline (= seeded with flip_rate 0). Free people per code equal its capacity, so H2
    # binds and dropping it visibly changes the optimum.
    tight = build_instance(default.seed, "seeded", flip_rate=0.0)
    fairness_only = ModelConfig(fatigue_k=k, use_soft=False)
    full_model = ModelConfig(fatigue_k=k)
    result = {
        "a_drop_overlap": {
            "availability": "M1 Busy reading: seeded, flip_rate=0 (forum d=33734)",
            "pairs_A": len(tight.A),
            "slice_example": drop_overlap_example(tight, fairness_only),
            "full_data": full_data_effect(tight, full_model, baseline_max),
        },
        "a_default_instance": {
            "availability": f"default: seeded, flip_rate={default.flip_rate}",
            "pairs_A": len(default.A),
            "with_soft": {key: value for key, value in compare(default, full_model).items()
                          if not key.startswith("_")},
            "fairness_only": {key: value for key, value in compare(default, fairness_only).items()
                              if not key.startswith("_")},
        },
        "b_relax_integrality": relax_integrality_example(),
    }
    example = result["a_drop_overlap"]["slice_example"]
    for row in example.get("double_booked", []):
        print(f"[m2/counterexample] (a) {row['staff']} works {row['sessions'][0]} and "
              f"{row['sessions'][1]} at {row['times'][0]}")
    print(f"[m2/counterexample] (a) correct {example.get('correct')}, wrong {example.get('wrong')}")
    lp = result["b_relax_integrality"]
    print(f"[m2/counterexample] (b) Z_LP = {lp['z_lp']}, Z_ILP = {lp['z_ilp']}, "
          f"{lp['fractional_pairs']} fractional x")
    path = M2_DIR / "counterexample.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    print(f"[m2/counterexample] wrote {path.name}")
    return result


if __name__ == "__main__":
    main()
