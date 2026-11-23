"""Interactive what-if solvers, counterexamples, custom DFAs, and dynamics experiments (M5)."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
import math
from random import Random
import time
from urllib.parse import quote, unquote

import numpy as np
import pandas as pd

from app.data_views import instance_to_m1_data
from app.dynamics_views import evaluate_dynamics
from app.solver_views import run_m1_check
from app.temporal_views import build_roster_strings, evaluate_temporal_validity
from m2_ilp.config import ModelConfig
from m2_ilp.counterexample import (
    compare as m2_compare_drop,
    double_bookings,
    drop_overlap_example,
    relax_integrality_example,
)
from m2_ilp.instance import DEFAULT_FLIP_RATE, Instance, build_instance, simulate_preferences
from m2_ilp.metrics import compute_metrics
from m2_ilp.model import build_model
from m2_ilp.soft import fit_fatigue_k
from m2_ilp.solve import run_cbc, solve
from m2_ilp.validate import check_schedule
from m3_automata.dfa import ALPHABET, DFA
from m3_automata.product_min import minimize, product
from m3_automata.regular_to_ilp import solve_with_rules
from m3_automata.rules import r2, r4
from m4_dynamics.fatigue import (
    FatigueParameters,
    fit_threshold,
    fixed_point,
    simulate,
    simulate_history,
    stability,
    threshold_penalty,
)
from m4_dynamics.workload import weekly_workload

SAMPLE_TEAM_SEEDS: dict[str, str] = {
    "1358677812": "CO2011-261-A01-2551896 (Seed gốc của nhóm)",
    "1048291731": "CO2011-261-L-2252107 (Seed mẫu đề bài)",
    "2026112201": "Seed tùy chỉnh A (ưu tiên khác về LOC/FAT/TRV)",
    "987654321": "Seed tùy chỉnh B (đảo tỷ trọng ràng buộc mềm)",
}


def _model_to_pairs(m1_data: dict, model: dict[str, list[str]]) -> set[tuple[int, int]]:
    staff_idx = {sid: i for i, sid in enumerate(m1_data["staff_ids"])}
    sess_idx = {
        f"{code}_{campus}": j for j, (code, campus) in enumerate(m1_data["session_ids"])
    }
    pairs: set[tuple[int, int]] = set()
    for sess_label, people in model.items():
        if sess_label not in sess_idx:
            continue
        j = sess_idx[sess_label]
        for person in people:
            if person in staff_idx:
                pairs.add((staff_idx[person], j))
    return pairs


def _run_m1_quoted(data: dict) -> dict:
    encoded = {
        **data,
        "staff_ids": [quote(person, safe="") for person in data["staff_ids"]],
        "session_ids": [
            (quote(code, safe=""), quote(campus, safe=""))
            for code, campus in data["session_ids"]
        ],
    }
    res = run_m1_check(encoded)
    if res["satisfiable"]:
        res["model"] = {
            unquote(session): [unquote(person) for person in people]
            for session, people in res["model"].items()
        }
    return res


def run_m1_what_if(
    m1_data: dict,
    *,
    enforce_h1: bool = True,
    enforce_h2: bool = True,
    session_idx: int = 0,
    demand_delta: int = 0,
    extra_busy_staff: tuple[int, ...] = (),
) -> dict:
    """Compare baseline M1 SAT check against modified H1/H2/H3/Busy assumptions."""
    demands = list(m1_data["shift_demands"])
    if not demands:
        raise ValueError("Dataset must contain at least one session")
    if not 0 <= session_idx < len(demands):
        raise ValueError("session_idx is out of range")

    new_demands = list(demands)
    new_demands[session_idx] = max(0, demands[session_idx] + int(demand_delta))

    orig_busy = {tuple(pair) for pair in m1_data["busy"]}
    if enforce_h1:
        exp_busy_set = set(orig_busy) | {(int(i), session_idx) for i in extra_busy_staff}
        exp_busy = sorted(exp_busy_set)
    else:
        exp_busy = []

    orig_overlaps = {tuple(sorted(pair)) for pair in m1_data["overlaps"]}
    exp_overlaps = list(m1_data["overlaps"]) if enforce_h2 else []

    exp_data = {
        **m1_data,
        "shift_demands": new_demands,
        "busy": exp_busy,
        "overlaps": exp_overlaps,
    }

    base_res = _run_m1_quoted(m1_data)
    exp_res = _run_m1_quoted(exp_data)

    orig_violations = {"H1": 0, "H2": 0, "H3": 0, "details": []}
    if exp_res["satisfiable"]:
        pairs = _model_to_pairs(m1_data, exp_res["model"])
        h1_bad = sorted(pair for pair in pairs if pair in orig_busy)
        h2_bad = []
        by_staff: dict[int, set[int]] = {}
        for i, j in pairs:
            by_staff.setdefault(i, set()).add(j)
        for i, sessions in sorted(by_staff.items()):
            for j, k in sorted(orig_overlaps):
                if j in sessions and k in sessions:
                    h2_bad.append((i, j, k))
        h3_bad = []
        for j, req in enumerate(demands):
            got = sum(1 for i, sess in pairs if sess == j)
            if got != req:
                h3_bad.append((j, got, req))

        orig_violations["H1"] = len(h1_bad)
        orig_violations["H2"] = len(h2_bad)
        orig_violations["H3"] = len(h3_bad)
        for i, j in h1_bad[:5]:
            code, camp = m1_data["session_ids"][j]
            orig_violations["details"].append(
                f"H1: {m1_data['staff_ids'][i]} bị xếp vào {code}_{camp} dù đang Busy ở dữ liệu gốc"
            )
        for i, j, k in h2_bad[:5]:
            c1, cp1 = m1_data["session_ids"][j]
            c2, cp2 = m1_data["session_ids"][k]
            orig_violations["details"].append(
                f"H2: {m1_data['staff_ids'][i]} bị trùng giờ giữa {c1}_{cp1} và {c2}_{cp2}"
            )
        for j, got, req in h3_bad[:5]:
            code, camp = m1_data["session_ids"][j]
            orig_violations["details"].append(
                f"H3: Ca {code}_{camp} cần {req} người theo dữ liệu gốc nhưng nhận {got}"
            )

    def _status_txt(res: dict) -> str:
        return "SAT (Khả thi)" if res["satisfiable"] else "UNSAT (Vô nghiệm)"

    comparison_rows = [
        {"metric": "Trạng thái SAT", "baseline": _status_txt(base_res), "experiment": _status_txt(exp_res)},
        {"metric": "Số mệnh đề CNF", "baseline": str(base_res["n_clauses"]), "experiment": str(exp_res["n_clauses"])},
        {"metric": "Số biến CNF (gồm phụ)", "baseline": str(base_res["n_cnf_vars"]), "experiment": str(exp_res["n_cnf_vars"])},
        {"metric": "Số ràng buộc tuyến tính 0/1", "baseline": str(base_res["linear_rows"]), "experiment": str(exp_res["linear_rows"])},
        {
            "metric": "Số cặp Busy(i, j)",
            "baseline": str(len(m1_data["busy"])),
            "experiment": str(len(exp_busy)),
        },
        {
            "metric": "Số cặp trùng giờ Overlap(j, k)",
            "baseline": str(len(m1_data["overlaps"])),
            "experiment": str(len(exp_overlaps)),
        },
        {
            "metric": "Vi phạm luật gốc (H1 / H2 / H3)",
            "baseline": "0 / 0 / 0" if base_res["satisfiable"] else "Vô nghiệm",
            "experiment": (
                f"{orig_violations['H1']} / {orig_violations['H2']} / {orig_violations['H3']}"
                if exp_res["satisfiable"]
                else "Vô nghiệm"
            ),
        },
    ]

    return {
        "baseline": base_res,
        "experiment": exp_res,
        "comparison_rows": comparison_rows,
        "orig_violations": orig_violations,
    }


def derive_weights_from_seed(seed: int) -> list[float]:
    """Derive deterministic [LOC, FAT, TRV] soft weights in [0.5, 2.0] matching make_seed.py."""
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    rng = Random(seed)
    return [round(rng.uniform(0.5, 2.0), 2) for _ in range(3)]


def rebuild_instance_with_seed(inst: Instance, custom_seed: int) -> Instance:
    """Create a modified M2 Instance using custom_seed for weights, preferences, and seeded A."""
    if isinstance(custom_seed, bool) or not isinstance(custom_seed, int) or custom_seed < 0:
        raise ValueError("custom_seed must be a non-negative integer")
    if custom_seed == inst.seed:
        return inst

    m1_data = instance_to_m1_data(inst)
    prefs = simulate_preferences(m1_data, custom_seed)
    weights = derive_weights_from_seed(custom_seed)

    new_a = set(inst.A)
    if inst.availability == "seeded":
        flip_rate = DEFAULT_FLIP_RATE if inst.flip_rate is None else inst.flip_rate
        codes = sorted({code for code, _ in m1_data["session_ids"]})
        observed = {(i, m1_data["session_ids"][j][0]) for i, j in inst.baseline}
        avail_shifts = set(observed)
        rng = Random(custom_seed)
        for i in sorted(range(len(inst.staff_ids)), key=lambda idx: inst.staff_ids[idx]):
            for code in codes:
                if (i, code) not in observed and rng.random() < flip_rate:
                    avail_shifts.add((i, code))
        new_a = {
            (i, j)
            for i in range(len(inst.staff_ids))
            for j, (code, _) in enumerate(m1_data["session_ids"])
            if (i, code) in avail_shifts
        }

    return replace(
        inst,
        seed=custom_seed,
        A=new_a,
        preferences=prefs,
        soft_weights=weights,
    )


def _stage2_objective(inst: Instance, metrics: dict, cfg: ModelConfig) -> float:
    lam = cfg.lambdas(inst)
    return (
        metrics["l1"]
        + lam[0] * metrics["location"]
        + lam[1] * metrics["fatigue"]
        + lam[2] * metrics["travel"]
    )


def run_m2_what_if(
    inst: Instance,
    *,
    custom_seed: int | None = None,
    use_soft: bool = True,
    fatigue_k: int | None = None,
    weight_scale: tuple[float, float, float] = (1.0, 1.0, 1.0),
    time_limit: int = 15,
) -> dict:
    """Solve standard M2 ILP vs modified seed / soft constraints / K / weight scales."""
    t0 = time.perf_counter()
    base_k = fit_fatigue_k(inst) if inst.baseline else ModelConfig.fatigue_k
    base_cfg = ModelConfig(fatigue_k=base_k, time_limit=time_limit)
    base_sol = solve(inst, base_cfg)

    exp_seed = inst.seed if custom_seed is None else int(custom_seed)
    exp_inst = rebuild_instance_with_seed(inst, exp_seed)
    exp_k = base_k if fatigue_k is None else int(fatigue_k)
    exp_cfg = ModelConfig(
        use_soft=bool(use_soft),
        fatigue_k=exp_k,
        weight_scale=tuple(float(s) for s in weight_scale),
        time_limit=time_limit,
    )
    exp_sol = solve(exp_inst, exp_cfg)
    runtime_s = round(time.perf_counter() - t0, 3)

    base_m = compute_metrics(inst, base_sol.assigned, base_k) if base_sol.assigned else None
    exp_m = compute_metrics(exp_inst, exp_sol.assigned, exp_k) if exp_sol.assigned else None
    base_obj = round(_stage2_objective(inst, base_m, base_cfg), 4) if base_m else None
    exp_obj = (
        round(
            _stage2_objective(exp_inst, exp_m, exp_cfg)
            if use_soft
            else exp_m["l1"],
            4,
        )
        if exp_m
        else None
    )

    def _fmt(val, decimals=2):
        if val is None:
            return "—"
        if isinstance(val, int):
            return str(val)
        return f"{val:.{decimals}f}"

    def _delta(b_val, e_val, decimals=2):
        if b_val is None or e_val is None:
            return "—"
        diff = e_val - b_val
        if isinstance(b_val, int) and isinstance(e_val, int):
            return f"{diff:+d}"
        return f"{diff:+.{decimals}f}"

    b_lam = base_cfg.lambdas(inst)
    e_lam = exp_cfg.lambdas(exp_inst) if use_soft else (0.0, 0.0, 0.0)
    rows = [
        {
            "indicator": "Trọng số (LOC / FAT / TRV)",
            "standard": f"{b_lam[0]:.2f} / {b_lam[1]:.2f} / {b_lam[2]:.2f}",
            "experiment": f"{e_lam[0]:.2f} / {e_lam[1]:.2f} / {e_lam[2]:.2f}" if use_soft else "Tắt phạt mềm (0 / 0 / 0)",
            "delta": "Đổi seed/tỉ trọng" if (e_lam != b_lam) else "Giữ nguyên",
        },
        {
            "indicator": "Miền khả dụng |A| & Ngưỡng K",
            "standard": f"{len(inst.A):,} cặp | K={base_k}",
            "experiment": f"{len(exp_inst.A):,} cặp | K={exp_k}",
            "delta": f"{len(exp_inst.A) - len(inst.A):+d} cặp | ΔK={exp_k - base_k:+d}",
        },
        {
            "indicator": "Tải đỉnh (max_load)",
            "standard": _fmt(base_m["max_load"] if base_m else None),
            "experiment": _fmt(exp_m["max_load"] if exp_m else None),
            "delta": _delta(base_m["max_load"] if base_m else None, exp_m["max_load"] if exp_m else None),
        },
        {
            "indicator": "Chênh lệch tải (spread)",
            "standard": _fmt(base_m["spread"] if base_m else None),
            "experiment": _fmt(exp_m["spread"] if exp_m else None),
            "delta": _delta(base_m["spread"] if base_m else None, exp_m["spread"] if exp_m else None),
        },
        {
            "indicator": "Độ lệch L1",
            "standard": _fmt(base_m["l1"] if base_m else None, 4),
            "experiment": _fmt(exp_m["l1"] if exp_m else None, 4),
            "delta": _delta(base_m["l1"] if base_m else None, exp_m["l1"] if exp_m else None, 4),
        },
        {
            "indicator": "Phạt cơ sở (LOC)",
            "standard": _fmt(base_m["location"] if base_m else None),
            "experiment": _fmt(exp_m["location"] if exp_m else None),
            "delta": _delta(base_m["location"] if base_m else None, exp_m["location"] if exp_m else None),
        },
        {
            "indicator": f"Phạt quá tải ngày (FAT, K={exp_k})",
            "standard": _fmt(base_m["fatigue"] if base_m else None),
            "experiment": _fmt(exp_m["fatigue"] if exp_m else None),
            "delta": _delta(base_m["fatigue"] if base_m else None, exp_m["fatigue"] if exp_m else None),
        },
        {
            "indicator": "Phạt di chuyển (TRV)",
            "standard": _fmt(base_m["travel"] if base_m else None),
            "experiment": _fmt(exp_m["travel"] if exp_m else None),
            "delta": _delta(base_m["travel"] if base_m else None, exp_m["travel"] if exp_m else None),
        },
        {
            "indicator": "Mục tiêu giai đoạn 2",
            "standard": _fmt(base_obj, 4),
            "experiment": _fmt(exp_obj, 4),
            "delta": _delta(base_obj, exp_obj, 4),
        },
    ]

    return {
        "base_status": base_sol.status,
        "exp_status": exp_sol.status,
        "base_metrics": base_m,
        "exp_metrics": exp_m,
        "base_weights": b_lam,
        "exp_weights": e_lam,
        "comparison_rows": rows,
        "exp_assigned": exp_sol.assigned,
        "runtime_s": runtime_s,
    }


def run_m2_counterexample_h2(
    inst: Instance,
    *,
    mode: str = "canonical_9day",
    use_soft: bool = False,
    time_limit: int = 15,
) -> dict:
    """Demonstrate dropping H2 (drop_overlap=True) admitting double-booking."""
    if mode == "canonical_9day":
        tight = build_instance(inst.seed, "seeded", flip_rate=0.0)
        res = drop_overlap_example(tight, ModelConfig(use_soft=use_soft, time_limit=time_limit))
        if res.get("slice") is None:
            return {
                "has_example": False,
                "note": "Không tìm thấy lát cắt tiền tố mà bỏ H2 làm giảm mục tiêu nghiêm ngặt khi bật ràng buộc mềm.",
                "comparison_rows": [],
                "double_booked": [],
                "validator": [],
            }
        right, wrong, sl = res["correct"], res["wrong"], res["slice"]
        return {
            "has_example": True,
            "note": (
                f"Lát cắt {sl['n_days']} ngày đầu (flip_rate=0): {sl['staff']} giám thị, "
                f"{sl['sessions']} ca, {sl['overlap_pairs']} cặp trùng giờ."
            ),
            "comparison_rows": [
                {"model": "Mô hình đúng (có H2)", **right},
                {"model": "Mô hình sai (bỏ H2)", **wrong},
            ],
            "double_booked": [
                {
                    "staff": row["staff"],
                    "session_a": row["sessions"][0],
                    "session_b": row["sessions"][1],
                    "time_a": row["times"][0],
                    "time_b": row["times"][1],
                }
                for row in res["double_booked"]
            ],
            "validator": res["validator"],
        }

    if not inst.overlaps:
        return {
            "has_example": False,
            "note": "Bộ dữ liệu/lát cắt hiện tại không có cặp ca nào trùng giờ (overlaps = 0). Hãy chọn 'Lát cắt 9 ngày chuẩn' hoặc bộ dữ liệu có trùng giờ.",
            "comparison_rows": [],
            "double_booked": [],
            "validator": [],
        }

    cfg = ModelConfig(
        fatigue_k=fit_fatigue_k(inst) if inst.baseline else 3,
        use_soft=use_soft,
        time_limit=time_limit,
    )
    res = m2_compare_drop(inst, cfg)
    wrong_assigned = res.pop("_wrong_assigned")
    booked = double_bookings(inst, wrong_assigned)
    msgs = check_schedule(inst, wrong_assigned)
    return {
        "has_example": True,
        "note": f"Trên lát cắt đang chọn ({len(inst.staff_ids)} người, {len(inst.session_names)} ca, {len(inst.overlaps)} cặp trùng giờ).",
        "comparison_rows": [
            {"model": "Mô hình đúng (có H2)", **res["correct"]},
            {"model": "Mô hình sai (bỏ H2)", **res["wrong"]},
        ],
        "double_booked": [
            {
                "staff": row["staff"],
                "session_a": row["sessions"][0],
                "session_b": row["sessions"][1],
                "time_a": row["times"][0],
                "time_b": row["times"][1],
            }
            for row in booked[:25]
        ],
        "validator": msgs[:25],
    }


def run_m2_counterexample_lp(
    inst: Instance,
    *,
    mode: str = "brief_example",
    time_limit: int = 15,
) -> dict:
    """Demonstrate relaxing integrality x in [0, 1] yielding fractional people."""
    if mode == "brief_example":
        res = relax_integrality_example()
        matrix_rows = []
        staff = ("CB1", "CB2", "CB3")
        sessions = ("S1", "S2", "S3", "S4")
        for idx, person in enumerate(staff):
            row = {"staff_id": person}
            for sess in sessions:
                row[sess] = res["lp_x"].get(f"{person},{sess}", "0")
            row["lp_load"] = res["lp_loads"][idx]
            matrix_rows.append(row)
        return {
            "mode": mode,
            "instance": res["instance"],
            "z_lp": res["z_lp"],
            "z_lp_value": res["z_lp_value"],
            "z_ilp": res["z_ilp"],
            "fractional_pairs": res["fractional_pairs"],
            "matrix_rows": matrix_rows,
            "rounded_violations": res["rounded_lp_violations"],
            "ilp_loads": res["ilp_loads"],
        }

    cfg_lp = ModelConfig(stage=1, relax_integrality=True, time_limit=time_limit)
    prob_lp, x_lp, _ = build_model(inst, cfg_lp)
    lp_res = run_cbc(prob_lp, cfg_lp)
    ilp_res = solve(inst, ModelConfig(fatigue_k=fit_fatigue_k(inst) if inst.baseline else 3, time_limit=time_limit))

    vals = {pair: float(var.varValue or 0.0) for pair, var in x_lp.items()}
    frac_pairs = [
        {
            "staff_id": inst.staff_ids[i],
            "session_id": inst.session_names[j],
            "lp_value": round(v, 4),
            "fraction": str(Fraction(v).limit_denominator(24)),
        }
        for (i, j), v in sorted(vals.items())
        if 1e-4 < v < 1.0 - 1e-4
    ]
    rounded = {pair for pair, v in vals.items() if v > 0.5}
    rounded_msgs = check_schedule(inst, rounded)
    return {
        "mode": mode,
        "instance": f"{len(inst.staff_ids)} giám thị, {len(inst.session_names)} ca thi",
        "z_lp": f"{lp_res.objective:.4f}" if lp_res.objective is not None else "—",
        "z_lp_value": round(float(lp_res.objective), 4) if lp_res.objective is not None else None,
        "z_ilp": ilp_res.t_star,
        "fractional_pairs": len(frac_pairs),
        "matrix_rows": frac_pairs[:30],
        "rounded_violations": rounded_msgs[:20],
        "ilp_loads": [],
    }


def build_custom_r1(max_consecutive: int = 2) -> DFA:
    """Build R1 DFA allowing at most `max_consecutive` working days in a row."""
    if type(max_consecutive) is not int or not 1 <= max_consecutive <= 5:
        raise ValueError("max_consecutive must be an integer in 1..5")
    live = [f"run{k}" for k in range(max_consecutive + 1)]
    transitions = {}
    for k, name in enumerate(live):
        nxt = live[k + 1] if k < max_consecutive else "dead"
        transitions[name] = {"M": nxt, "A": nxt, "N": nxt, "-": "run0"}
    transitions["dead"] = {sym: "dead" for sym in ALPHABET}
    return DFA(live + ["dead"], ALPHABET, "run0", live, transitions)


def build_custom_r3(max_work: int = 4, window: int = 7) -> DFA:
    """Build sliding-window DFA allowing at most `max_work` work days per `window` days."""
    if type(window) is not int or not 3 <= window <= 7:
        raise ValueError("window must be an integer in 3..7")
    if type(max_work) is not int or not 1 <= max_work <= window:
        raise ValueError("max_work must be in 1..window")

    from itertools import product as bit_product

    histories = [
        "w" + "".join(bits)
        for bits in bit_product("01", repeat=window - 1)
        if bits.count("1") <= max_work
    ]
    transitions = {}
    for hist in histories:
        transitions[hist] = {}
        for sym in ALPHABET:
            worked = 0 if sym == "-" else 1
            if hist.count("1") + worked > max_work:
                transitions[hist][sym] = "dead"
            else:
                transitions[hist][sym] = "w" + hist[2:] + str(worked)
    transitions["dead"] = {sym: "dead" for sym in ALPHABET}
    return DFA(histories + ["dead"], ALPHABET, "w" + "0" * (window - 1), histories, transitions)


def evaluate_custom_automata(
    inst: Instance,
    assigned,
    *,
    enforce_r1: bool = True,
    max_consecutive: int = 2,
    enforce_r2: bool = True,
    enforce_r3: bool = True,
    max_work: int = 4,
    window: int = 7,
    enforce_r4: bool = False,
    r4_bound: int = 3,
) -> dict:
    """Audit `assigned` under customizable R1-R4 DFAs and compare with standard R1(2)xR2xR3(4/7)."""
    rules: dict[str, DFA] = {}
    if enforce_r1:
        rules[f"R1 (≤{max_consecutive} ngày liền)"] = build_custom_r1(max_consecutive)
    if enforce_r2:
        rules["R2 (nghỉ sau N)"] = r2()
    if enforce_r3:
        rules[f"R3 (≤{max_work}/{window} ngày)"] = build_custom_r3(max_work, window)
    if enforce_r4:
        rules[f"R4 (|#M-#A|≤{r4_bound})"] = r4(r4_bound)
    if not rules:
        raise ValueError("Phải bật ít nhất một quy tắc DFA (R1, R2, R3 hoặc R4).")

    prod_dfa = product(list(rules.values()))
    min_dfa = minimize(prod_dfa)

    std_audit = evaluate_temporal_validity(inst, assigned)
    std_by_staff = {row["staff_id"]: row for row in std_audit["staff_rows"]}

    _, strings = build_roster_strings(inst, assigned)
    per_rule_counts = [
        {
            "rule": label,
            "dfa_states": len(dfa.states),
            "rejected_staff": sum(not dfa.accepts(w) for w in strings.values()),
            "accepted_staff": sum(dfa.accepts(w) for w in strings.values()),
        }
        for label, dfa in rules.items()
    ]

    accepted_custom = 0
    changed_rows = []
    for person in inst.staff_ids:
        word = strings[person]
        ok_custom = min_dfa.accepts(word)
        if ok_custom:
            accepted_custom += 1
        ok_std = std_by_staff[person]["dfa_accepted"]
        broken_custom = [label for label, dfa in rules.items() if not dfa.accepts(word)]
        if ok_custom != ok_std:
            changed_rows.append({
                "staff_id": person,
                "roster_string": word,
                "standard_r123": "Đạt" if ok_std else "Không đạt",
                "custom_rules": "Đạt" if ok_custom else "Không đạt",
                "broken_custom": ", ".join(broken_custom) if broken_custom else "—",
            })

    total = len(inst.staff_ids)
    return {
        "rules": rules,
        "product_states": len(prod_dfa.states),
        "minimal_states": len(min_dfa.states),
        "minimal_dfa": min_dfa,
        "total_staff": total,
        "std_accepted": std_audit["accepted_count"],
        "std_rejected": std_audit["rejected_count"],
        "custom_accepted": accepted_custom,
        "custom_rejected": total - accepted_custom,
        "per_rule_counts": per_rule_counts,
        "changed_rows": changed_rows,
    }


def solve_with_custom_automata(
    inst: Instance,
    custom_minimal: DFA,
    *,
    time_limit: int = 15,
) -> dict:
    """Re-solve M2 ILP constrained to custom minimized DFA flow on small/medium slices."""
    horizon = (max(inst.day) - min(inst.day)).days + 1
    if len(inst.staff_ids) * horizon > 5_000:
        raise ValueError("Bộ dữ liệu quá lớn (> 5.000 ô người-ngày) để giải trực tiếp DFA trên trình duyệt; hãy chọn lát cắt 1–2 tuần hoặc ví dụ nhỏ.")
    if len(custom_minimal.states) > 60:
        raise ValueError(f"DFA tích sau tối giản có {len(custom_minimal.states)} trạng thái (> 60), quá lớn để giải trực tiếp trong demo.")

    k = fit_fatigue_k(inst) if inst.baseline else 3
    sol, info, _ = solve_with_rules(
        inst,
        ModelConfig(fatigue_k=k, time_limit=time_limit),
        custom_minimal,
    )
    if not sol.assigned:
        return {
            "status": sol.status,
            "assigned": frozenset(),
            "metrics": None,
            "accepted": 0,
            "total_staff": len(inst.staff_ids),
            "solver_info": info,
        }
    metrics = compute_metrics(inst, sol.assigned, k)
    _, strings = build_roster_strings(inst, sol.assigned)
    acc = sum(custom_minimal.accepts(w) for w in strings.values())
    return {
        "status": sol.status,
        "assigned": sol.assigned,
        "metrics": metrics,
        "accepted": acc,
        "total_staff": len(inst.staff_ids),
        "solver_info": info,
    }


def pumping_lemma_demo(
    p: int,
    x_len: int,
    y_len: int,
    pump_i: int,
    r4_bound: int = 3,
) -> dict:
    """Interactive verification of the Pumping Lemma contradiction on L' = {M^n A^n}."""
    if type(p) is not int or not 1 <= p <= 10:
        raise ValueError("p must be in 1..10")
    if type(x_len) is not int or not 0 <= x_len < p:
        raise ValueError("x_len must satisfy 0 <= |x| < p")
    if type(y_len) is not int or not 1 <= y_len <= p - x_len:
        raise ValueError("y_len must satisfy |y| >= 1 and |xy| <= p")
    if type(pump_i) is not int or not 0 <= pump_i <= 5:
        raise ValueError("pump_i must be in 0..5")

    s = "M" * p + "A" * p
    x = s[:x_len]
    y = s[x_len : x_len + y_len]
    z = s[x_len + y_len :]
    pumped = x + (y * pump_i) + z
    m_count = pumped.count("M")
    a_count = pumped.count("A")
    in_l_prime = (m_count == a_count) and ("AM" not in pumped)

    r4_dfa = r4(r4_bound)
    return {
        "p": p,
        "s": s,
        "x": x,
        "y": y,
        "z": z,
        "xy_len": len(x) + len(y),
        "pump_i": pump_i,
        "pumped": pumped,
        "m_count": m_count,
        "a_count": a_count,
        "diff_m_a": m_count - a_count,
        "in_l_prime": in_l_prime,
        "contradiction": (pump_i != 1) and (not in_l_prime),
        "r4_bound": r4_bound,
        "r4_states": len(r4_dfa.states),
        "r4_accepts_s": r4_dfa.accepts(s),
        "r4_accepts_pumped": r4_dfa.accepts(pumped),
    }


def run_m4_what_if(
    inst: Instance,
    schedules: dict[str, object],
    active: str,
    *,
    a: float,
    b: float,
    r: float = 0.0,
    rest_rate: float = 0.0,
    coverage: float = 0.95,
    weeks: int = 24,
    shock_staff_index: int = 0,
    shock_amount: float = 0.0,
) -> dict:
    """Compare calibrated Direction B dynamics against custom (a, b, r, rho, coverage)."""
    std = evaluate_dynamics(
        inst,
        schedules,
        weeks=weeks,
        shock_staff_index=shock_staff_index,
        shock_amount=shock_amount,
    )
    ref_label = "Baseline" if "Baseline" in schedules else next(iter(schedules))
    initial = std["histories"][ref_label][-1].copy()
    if shock_amount != 0.0 and 0 <= shock_staff_index < initial.size:
        initial[shock_staff_index] = max(0.0, initial[shock_staff_index] + float(shock_amount))

    active_wl = weekly_workload(inst, schedules[active])
    load_vec = active_wl.mean_load
    rest_vec = np.full_like(load_vec, float(rest_rate))

    exp_params = FatigueParameters(a=float(a), b=float(b), r=float(r))
    exp_stab = stability(exp_params)
    exp_traj = simulate(load_vec, exp_params, initial=initial, weeks=weeks, rest=rest_vec)
    eq_exists = not math.isclose(exp_params.a, 1.0, abs_tol=1e-9)
    exp_eq = fixed_point(load_vec, exp_params, rest=rest_vec) if eq_exists else None

    exp_threshold = None
    exp_excess = None
    history_note = ""
    if 0.0 <= exp_params.a < 1.0 and math.isclose(exp_params.r, 0.0, abs_tol=1e-9):
        ref_wl = weekly_workload(inst, schedules[ref_label])
        if ref_wl.counts.shape[0] >= 2:
            ref_hist = simulate_history(ref_wl, exp_params)
            exp_threshold = fit_threshold(ref_hist, coverage=coverage)
            act_hist = simulate_history(active_wl, exp_params)
            exp_excess = threshold_penalty(act_hist, exp_threshold)
            history_note = f"Khớp ngưỡng H mới tại độ phủ {coverage:.0%} từ lịch sử tuần."
        else:
            history_note = "Lát cắt có ít hơn 2 khối tuần nên không khớp lại H từ lịch sử."
    else:
        history_note = (
            "Phép nội suy khối tuần lịch sử của M4 chỉ định nghĩa trên 0 ≤ a < 1 và r = 0; "
            "biểu đồ bên dưới vẫn mô phỏng đầy đủ hệ thức tự trị 52/N tuần."
        )

    std_traj = std["trajectories"][active]
    std_eq = std["equilibria"][active]
    idx = shock_staff_index if 0 <= shock_staff_index < len(inst.staff_ids) else 0
    times = list(range(weeks + 1))

    trajectory_df = pd.DataFrame({
        "Tuần": times,
        "Mô hình chuẩn": std_traj[:, idx],
        "Mô hình thí nghiệm": exp_traj[:, idx],
    })
    spread_df = pd.DataFrame({
        "Tuần": times,
        "Spread chuẩn": np.ptp(std_traj, axis=1),
        "Spread thí nghiệm": np.ptp(exp_traj, axis=1),
    })

    stab_vn = {
        "asymptotically stable": "Ổn định tiệm cận (|a| < 1)",
        "neutral": "Trung hòa (|a| = 1)",
        "unstable": "Mất ổn định (|a| > 1)",
    }
    std_p = std["parameters"]
    comparison_rows = [
        {
            "metric": "Tham số (a, b, r)",
            "standard": f"a={std_p['a']:.4f}, b={std_p['b']:.4f}, r={std_p['r']:g}",
            "experiment": f"a={exp_params.a:.4f}, b={exp_params.b:.4f}, r={exp_params.r:g} (ρ={rest_rate:g})",
        },
        {
            "metric": "Phân loại ổn định",
            "standard": stab_vn.get(std["stability"]["classification"], std["stability"]["classification"]),
            "experiment": stab_vn.get(exp_stab["classification"], exp_stab["classification"]),
        },
        {
            "metric": f"Điểm cân bằng F* ({inst.staff_ids[idx]})",
            "standard": f"{std_eq[idx]:.4f}",
            "experiment": f"{exp_eq[idx]:.4f}" if exp_eq is not None else "Không tồn tại (a = 1)",
        },
        {
            "metric": f"Giá trị tại tuần {weeks} ({inst.staff_ids[idx]})",
            "standard": f"{std_traj[-1, idx]:.4f}",
            "experiment": f"{exp_traj[-1, idx]:.4f}",
        },
        {
            "metric": f"Chênh lệch đội tại tuần {weeks}",
            "standard": f"{np.ptp(std_traj[-1]):.6f}",
            "experiment": f"{np.ptp(exp_traj[-1]):.6f}",
        },
        {
            "metric": "Ngưỡng mềm H & Tổng vượt ngưỡng",
            "standard": f"H={std['threshold']:.3f} | Vượt={next(r['observed_threshold_excess'] for r in std['summary_rows'] if r['scenario'] == active):.3f}",
            "experiment": (
                f"H={exp_threshold:.3f} | Vượt={exp_excess:.3f}"
                if exp_threshold is not None and exp_excess is not None
                else "Không áp dụng khi |a|≥1 hoặc r>0"
            ),
        },
    ]

    return {
        "standard": std,
        "exp_params": exp_params,
        "exp_stability": exp_stab,
        "exp_eq": exp_eq,
        "exp_traj": exp_traj,
        "exp_threshold": exp_threshold,
        "exp_excess": exp_excess,
        "history_note": history_note,
        "comparison_rows": comparison_rows,
        "trajectory_df": trajectory_df,
        "spread_df": spread_df,
    }
