"""Cached wrappers over the Module 5 adapters. Views read Modules 1-4 only through this file."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import streamlit as st

from app.data_views import instance_to_m1_data, load_csv_bytes, load_preset_instance, read_team_seed, weekly_assignment_rows
from app.dynamics_views import evaluate_dynamics
from app.precompute import DEFAULT_BUNDLE, load_full_schedules
from app.solver_views import compare_schedule_metrics, run_m1_check, solve_schedule_in_app
from app.temporal_views import compare_temporal_schedules, evaluate_temporal_validity, load_automata_suite, trace_word
from m4_dynamics.fatigue import FatigueParameters, fixed_point, stability
from m4_dynamics.workload import weekly_workload

# Display label -> schedule name used by the adapters.
SCHEDULES = {"Lịch gốc": "Baseline", "M2 Optimal": "M2 Optimal", "M2 + DFA": "M2 + R1xR2xR3",
             "M4 fatigue-aware": "M4 Fatigue-Aware"}
M1_CASES = {"Toy · SAT": ("toy", "sat"), "Toy · UNSAT": ("toy", "unsat"),
            "Lát cắt · SAT": ("m1_slice", "sat"), "Lát cắt · UNSAT": ("m1_slice", "unsat")}
SLICES = {"Toy 3 × 2": "toy", "Tuần 1": "week1", "2 tuần": "week2"}
SOURCE = {"precomputed bundle (app/m5_bundle.json)": "gói tính trước",
          "precomputed bundle + live DFA": "gói tính trước, DFA tính tại chỗ",
          "live repository artifacts": "tệp kết quả trong repo"}


@st.cache_data(show_spinner=False)
def seed() -> int:
    return read_team_seed()


# shortcut: caches are keyed by seed and bundle mtime only, restart the app after replacing data/input.csv.
@st.cache_resource(show_spinner=False)
def _full(team_seed: int, bundle: str, bundle_mtime: int | None):
    return load_full_schedules(team_seed, bundle_path=Path(bundle))


def full():
    """(Instance, {schedule name: pairs}, source label) of the Faculty dataset."""
    mtime = DEFAULT_BUNDLE.stat().st_mtime_ns if DEFAULT_BUNDLE.is_file() else None
    return _full(seed(), str(DEFAULT_BUNDLE), mtime)


def schedule_labels() -> dict[str, str]:
    """Display label -> schedule name, only for schedules that were loaded (M2 + DFA needs the bundle)."""
    return {label: name for label, name in SCHEDULES.items() if name in full()[1]}


@st.cache_data(show_spinner=False)
def bundle_m1() -> dict:
    """Stored full-dataset SAT summary; empty when the bundle is absent."""
    if not DEFAULT_BUNDLE.is_file():
        return {}
    return json.loads(DEFAULT_BUNDLE.read_text(encoding="utf-8")).get("m1", {})


@st.cache_resource(show_spinner=False)
def suite() -> dict:
    return load_automata_suite()


@st.cache_data(show_spinner=False)
def m1_case(label: str) -> tuple[dict, dict]:
    """(M1 input, run_m1_check result) of one preset."""
    preset, scenario = M1_CASES[label]
    data, _ = load_preset_instance(preset, seed=seed(), m1_scenario=scenario)
    return data, run_m1_check(data)


@st.cache_data(show_spinner=False)
def m1_full() -> dict:
    return run_m1_check(instance_to_m1_data(full()[0]))


def solve_slice(label: str, enforce: bool, seconds: int) -> dict:
    """Live CBC solve of one slice, with the table rows the page shows."""
    _, inst = load_preset_instance(SLICES[label], seed=seed())
    result = solve_schedule_in_app(inst, enforce_m3=enforce, time_limit=seconds)
    if not result["assigned"]:
        return {**result, "rows": [], "dfa": None}
    audit = evaluate_temporal_validity(inst, result["assigned"], suite())
    return {**result, "rows": weekly_assignment_rows(inst, result["assigned"]),
            "dfa": (audit["accepted_count"], audit["total_staff"]),
            "size": (len(inst.staff_ids), len(inst.session_names), len(inst.A))}


@st.cache_data(show_spinner=False)
def week_rows(schedule: str, week: int) -> list[dict]:
    inst, schedules, _ = full()
    return weekly_assignment_rows(inst, schedules[schedule], week=week)


@st.cache_data(show_spinner=False)
def metrics_table() -> dict[str, dict]:
    inst, schedules, _ = full()
    return {row["schedule"]: row for row in compare_schedule_metrics(inst, schedules)}


@st.cache_data(show_spinner=False)
def temporal(schedule: str) -> dict:
    inst, schedules, _ = full()
    return evaluate_temporal_validity(inst, schedules[schedule], suite())


@st.cache_data(show_spinner=False)
def temporal_table() -> dict[str, dict]:
    inst, schedules, _ = full()
    return {row["schedule"]: row for row in compare_temporal_schedules(inst, schedules, suite())}


@st.cache_resource(show_spinner=False)
def dynamics(weeks: int = 12) -> dict:
    inst, schedules, _ = full()
    return evaluate_dynamics(inst, schedules, weeks=weeks)


@st.cache_data(show_spinner=False)
def lag_pairs() -> list[dict]:
    """(load this week, load next week) for every staff member and adjacent week blocks."""
    inst, schedules, _ = full()
    rates = weekly_workload(inst, schedules["Baseline"]).rates
    return [{"x": float(a), "y": float(b)} for a, b in zip(rates[:-1].ravel(), rates[1:].ravel())]


def check_word(word: str) -> dict[str, int | None]:
    """First violating day (1-based) of R1, R2, R3 on one roster string; None when accepted."""
    return {name: trace_word(dfa, word)["first_violation_day"] for name, dfa in suite()["rules"].items()}


def regime(a: float) -> tuple[str, float | None]:
    """(classification from M4, mean equilibrium at the calibrated load or None)."""
    params = dynamics()["parameters"]
    candidate = FatigueParameters(a=a, b=params["b"], r=params["r"])
    label = stability(candidate)["classification"]
    mean = float(np.mean(weekly_workload(full()[0], full()[1]["Baseline"]).mean_load))
    return label, (float(fixed_point([mean], candidate)[0]) if a < 1 else None)


def uploaded(raw: bytes) -> dict:
    """Baseline-only audit of an uploaded dataset; raises ValueError on a bad file."""
    if len(raw) > 512 * 1024:
        raise ValueError("file too large")
    data, inst = load_csv_bytes(raw, seed=seed())
    schedules = {"Baseline": frozenset(inst.baseline)}
    return {"inst": inst, "m1": run_m1_check(data), "rows": weekly_assignment_rows(inst, inst.baseline, week=1),
            "metrics": compare_schedule_metrics(inst, schedules)[0],
            "temporal": evaluate_temporal_validity(inst, inst.baseline, suite()),
            "dynamics": evaluate_dynamics(inst, schedules, weeks=12)}
