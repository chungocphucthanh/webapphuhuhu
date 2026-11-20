"""Single-page Streamlit decision-support app integrating M1-M4 (M5 Lead, Thanh)."""

from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from app.data_views import (
    DATASET_PRESETS,
    instance_to_m1_data,
    load_csv_bytes,
    load_preset_instance,
    parse_uploaded_schedule,
    read_team_seed,
    staff_workload_rows,
    week_options,
    weekly_assignment_rows,
)
from app.dynamics_views import (
    evaluate_dynamics,
    observed_block_summary,
    plot_fairness_over_time,
    plot_fatigue_trajectories,
    plot_workload_distribution,
)
from app.precompute import load_full_schedules
from app.solver_views import compare_schedule_metrics, run_m1_check, solve_schedule_in_app
from app.temporal_views import (
    compare_temporal_schedules,
    evaluate_temporal_validity,
    load_automata_suite,
    staff_daily_trace_rows,
)
from m2_ilp.config import TEAM_ID
from m2_ilp.validate import check_schedule


@st.cache_data(show_spinner=False)
def _cached_full_context(seed: int, compute_m3_live: bool):
    inst, schedules, source = load_full_schedules(seed, compute_m3_live=compute_m3_live)
    return instance_to_m1_data(inst), inst, schedules, source


@st.cache_data(show_spinner=False)
def _cached_preset(preset: str, seed: int, m1_scenario: str):
    return load_preset_instance(preset, seed=seed, m1_scenario=m1_scenario)


@st.cache_data(show_spinner=False)
def _cached_upload(raw_bytes: bytes, seed: int):
    return load_csv_bytes(raw_bytes, seed=seed)


@st.cache_data(show_spinner=False)
def _cached_m1(cache_key: tuple, _m1_data: dict) -> dict:
    return run_m1_check(_m1_data)


@st.cache_data(show_spinner=False)
def _cached_solve(
    cache_key: tuple,
    _inst,
    enforce_m3: bool,
    include_m4_soft: bool,
    time_limit: int,
) -> dict:
    return solve_schedule_in_app(
        _inst,
        enforce_m3=enforce_m3,
        include_m4_soft=include_m4_soft,
        time_limit=time_limit,
    )


@st.cache_data(show_spinner=False)
def _cached_temporal(cache_key: tuple, _inst, _assigned, _schedules: dict):
    suite = load_automata_suite()
    audit = evaluate_temporal_validity(_inst, _assigned, suite=suite)
    comparison = compare_temporal_schedules(_inst, _schedules, suite=suite)
    return audit, comparison


@st.cache_data(show_spinner=False)
def _cached_dynamics(cache_key: tuple, _inst, _schedules: dict, weeks: int, shock: float):
    return evaluate_dynamics(_inst, _schedules, weeks=weeks, shock_staff_index=0, shock_amount=shock)


def _rows_to_csv_bytes(rows: list[dict]) -> bytes:
    if not rows:
        return b""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def _m3_reference_summary() -> dict | None:
    path = ROOT_DIR / "m3_automata" / "extra" / "regular_to_ilp.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("variants", {}).get("m2_rules")
    except (OSError, ValueError):
        return None


def main() -> None:
    st.set_page_config(page_title="CO2011 IAP Decision Support", layout="wide")
    seed = read_team_seed()

    with st.sidebar:
        st.markdown(f"### `{TEAM_ID}`")
        st.caption(f"Deterministic seed: `{seed}`")
        preset = st.selectbox(
            "Dataset Source",
            options=list(DATASET_PRESETS.keys()),
            format_func=lambda k: DATASET_PRESETS[k],
            key="dataset_preset",
        )

        m1_scenario = "sat"
        if preset in ("m1_slice", "toy"):
            m1_scenario = st.radio(
                "Availability Scenario (M1 / M2)",
                options=["sat", "unsat"],
                format_func=lambda s: "Feasible (SAT)" if s == "sat" else "Shortage (UNSAT)",
                horizontal=True,
                key="m1_scenario",
            )

        uploaded_dataset = None
        if preset == "upload":
            uploaded_dataset = st.file_uploader(
                "Upload Faculty Dataset CSV", type=["csv"], key="dataset_uploader"
            )

        uploaded_schedule_file = None
        if preset == "full":
            uploaded_schedule_file = st.file_uploader(
                "Audit Custom Schedule CSV (optional)", type=["csv"], key="schedule_uploader"
            )

        st.divider()
        st.markdown("#### Solver & Schedule Options")
        compute_m3_full = False
        enforce_m3 = False
        include_m4_soft = False
        time_limit = 15

        if preset == "full":
            compute_m3_full = st.checkbox(
                "Solve M2 + R1xR2xR3 live if not precomputed (~8s)",
                value=False,
                key="compute_m3_full",
            )
        else:
            time_limit = st.slider(
                "CBC Time Limit (s)", min_value=5, max_value=120, value=15, key="time_limit"
            )
            enforce_m3 = st.checkbox(
                "Enforce M3 DFA Rules (R1xR2xR3)",
                value=(preset in ("week1", "week2")),
                key="enforce_m3",
            )
            include_m4_soft = st.checkbox(
                "Include M4 Soft Fatigue Threshold",
                value=False,
                key="include_m4_soft",
            )

        st.divider()
        st.markdown("#### M4 Dynamics Controls")
        sim_weeks = st.slider(
            "Simulation Horizon (weeks)", min_value=12, max_value=104, value=52, key="sim_weeks"
        )
        shock_amount = st.slider(
            "Initial Perturbation Shock (staff #1)",
            min_value=0.0,
            max_value=10.0,
            value=0.0,
            step=0.5,
            key="shock_amount",
        )

    st.title("CO2011 Invigilator Assignment Problem — Integrated Decision Support")

    schedules: dict[str, frozenset[tuple[int, int]]] = {}
    solve_info = None
    source_note = ""

    if preset == "upload":
        if uploaded_dataset is None:
            st.info("Upload a CSV file matching the Faculty dataset columns in the sidebar to run M1-M4.")
            return
        raw_bytes = uploaded_dataset.getvalue()
        try:
            m1_data, inst = _cached_upload(raw_bytes, seed)
        except ValueError as err:
            st.error(f"Invalid dataset CSV: {err}")
            return
        data_tag = ("upload", hash(raw_bytes), seed)
    elif preset == "full":
        m1_data, inst, schedules, source_note = _cached_full_context(seed, compute_m3_full)
        if uploaded_schedule_file is not None:
            try:
                custom_sched = parse_uploaded_schedule(inst, uploaded_schedule_file.getvalue())
                schedules = {**schedules, "Uploaded Schedule": custom_sched}
            except ValueError as err:
                st.sidebar.error(f"Invalid schedule CSV: {err}")
        data_tag = ("full", seed, compute_m3_full, len(schedules))
    else:
        m1_data, inst = _cached_preset(preset, seed, m1_scenario)
        data_tag = (preset, seed, m1_scenario)

    if preset != "full":
        solve_info = _cached_solve(data_tag, inst, enforce_m3, include_m4_soft, time_limit)
        if (
            inst.baseline
            and len(inst.baseline) == sum(inst.demand)
            and not check_schedule(inst, inst.baseline)
        ):
            schedules["Baseline"] = frozenset(inst.baseline)
        if solve_info["assigned"]:
            label = "Solved Plan"
            if enforce_m3 and include_m4_soft:
                label = "Solved (M2 + M3 + M4)"
            elif enforce_m3:
                label = "Solved (M2 + R1xR2xR3)"
            elif include_m4_soft:
                label = "Solved (M2 + M4 Soft)"
            schedules[label] = solve_info["assigned"]
        source_note = f"in-app CBC solver ({solve_info['status']}, {solve_info['runtime_s']}s)"

    weights_str = ", ".join(f"{k}={v}" for k, v in inst.soft_weight_map.items())
    st.caption(
        f"**Dataset:** {DATASET_PRESETS[preset]} · **Staff:** `{len(inst.staff_ids)}` · "
        f"**Sessions:** `{len(inst.session_names)}` · **Total demand:** `{sum(inst.demand)}` · "
        f"**Soft weights:** `{weights_str}` · **Source:** {source_note}"
    )

    m1_res = _cached_m1(data_tag, m1_data)

    with st.sidebar:
        st.divider()
        st.markdown("#### View Filters")
        schedule_names = list(schedules.keys())
        default_idx = 0
        for preferred in ("M2 + R1xR2xR3", "Uploaded Schedule", "M2 Optimal", "Solved (M2 + R1xR2xR3)", "Solved Plan"):
            if preferred in schedule_names:
                default_idx = schedule_names.index(preferred)
                break
        active_schedule_name = (
            st.selectbox(
                "Active Schedule",
                options=schedule_names,
                index=default_idx,
                key="active_schedule",
            )
            if schedule_names
            else None
        )
        weeks_meta = week_options(inst)
        week_choices = [None] + [w["week"] for w in weeks_meta]
        week_labels = {None: f"All weeks ({len(weeks_meta)} blocks)"} | {
            w["week"]: w["label"] for w in weeks_meta
        }
        selected_week = st.selectbox(
            "Week Picker",
            options=week_choices,
            format_func=lambda w: week_labels[w],
            key="week_filter",
        )
        selected_campus = st.selectbox(
            "Campus Filter", options=["All", "CS1", "CS2"], key="campus_filter"
        )

    if not schedules or active_schedule_name is None:
        st.error(
            "Schedule valid (DFA-accepted): NO — Instance is INFEASIBLE under hard rules H1-H3."
        )
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Module 1 — Minimal UNSAT Core (Logic)")
            st.write(f"CNF variables: `{m1_res['n_cnf_vars']}` · Clauses: `{m1_res['n_clauses']}`")
            if m1_res["unsat_core"]:
                st.dataframe(
                    pd.DataFrame({"Minimal UNSAT Core Constraint": m1_res["unsat_core"]}),
                    use_container_width=True,
                    hide_index=True,
                )
        with col_b:
            st.subheader("Module 2 — Elastic Shortage Diagnosis (ILP)")
            if solve_info and solve_info["diagnosis"]:
                st.dataframe(
                    pd.DataFrame(solve_info["diagnosis"]),
                    use_container_width=True,
                    hide_index=True,
                )
        return

    active_pairs = schedules[active_schedule_name]
    temporal_audit, m3_comparison = _cached_temporal(
        (data_tag, active_schedule_name), inst, active_pairs, schedules
    )
    m2_comparison = compare_schedule_metrics(inst, schedules)
    dyn = _cached_dynamics((data_tag, tuple(schedules.keys())), inst, schedules, sim_weeks, shock_amount)

    active_m2 = next(r for r in m2_comparison if r["schedule"] == active_schedule_name)
    active_dyn = next(r for r in dyn["summary_rows"] if r["scenario"] == active_schedule_name)

    if temporal_audit["schedule_valid"]:
        st.success(
            f"**Schedule valid (DFA-accepted): YES** — `{active_schedule_name}` satisfies all hard rules "
            f"(0 H1-H3 violations) and all `{temporal_audit['accepted_count']}/{temporal_audit['total_staff']}` "
            "invigilator strings are accepted by `R1 x R2 x R3`."
        )
    else:
        st.warning(
            f"**Schedule valid (DFA-accepted): NO** — `{active_schedule_name}` has "
            f"`{len(temporal_audit['hard_violations'])}` hard-rule violations and "
            f"`{temporal_audit['rejected_count']}/{temporal_audit['total_staff']}` staff strings rejected by "
            f"`R1 x R2 x R3` (`R1={temporal_audit['rule_violations']['R1']}`, "
            f"`R2={temporal_audit['rule_violations']['R2']}`, `R3={temporal_audit['rule_violations']['R3']}`)."
        )

    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    kpi1.metric(
        "M1 SAT Feasibility",
        "SAT" if m1_res["satisfiable"] else "UNSAT",
        f"{m1_res['n_clauses']:,} CNF clauses",
    )
    base_row = next((r for r in m2_comparison if r["schedule"] == "Baseline"), None)
    max_delta = (
        f"{active_m2['max_load'] - base_row['max_load']} vs baseline ({base_row['max_load']})"
        if base_row and active_schedule_name != "Baseline"
        else ("Beats baseline" if active_m2["beats_baseline"] else "Reference")
    )
    kpi2.metric("M2 Max Load", f"{active_m2['max_load']}", max_delta, delta_color="inverse" if base_row and active_schedule_name != "Baseline" else "off")
    kpi3.metric("M2 L1 Deviation", f"{active_m2['l1']:.3f}", f"Spread = {active_m2['spread']}")
    kpi4.metric(
        "Schedule valid (DFA-accepted)",
        "YES" if temporal_audit["schedule_valid"] else "NO",
        f"{temporal_audit['accepted_count']}/{temporal_audit['total_staff']} accepted",
    )
    kpi5.metric(
        "M4 Equilibrium Spread",
        f"{active_dyn['equilibrium_spread']:.3f}",
        f"{dyn['stability']['classification']} (a={dyn['parameters']['a']:.3f})",
    )

    st.divider()
    st.header("1. Weekly Assignment Plan & ILP Fairness (Module 2)")
    plan_rows = weekly_assignment_rows(
        inst, active_pairs, week=selected_week, campus=selected_campus
    )
    top_l, top_r = st.columns([4, 1])
    top_l.caption(
        f"Showing **{len(plan_rows)}** sessions for **{active_schedule_name}** "
        f"({week_labels[selected_week]}, campus: `{selected_campus}`)."
    )
    top_r.download_button(
        "Download Plan CSV",
        data=_rows_to_csv_bytes(plan_rows),
        file_name=f"plan_{preset}_{active_schedule_name.lower().replace(' ', '_')}.csv",
        mime="text/csv",
        key="download_plan_csv",
    )
    st.dataframe(pd.DataFrame(plan_rows), use_container_width=True, hide_index=True)

    col_m2_table, col_m2_chart = st.columns([1.15, 1.0])
    with col_m2_table:
        st.subheader("Schedule Fairness & Soft-Penalty Comparison")
        st.dataframe(pd.DataFrame(m2_comparison), use_container_width=True, hide_index=True)
    with col_m2_chart:
        fig_loads = plot_workload_distribution(inst, schedules)
        st.pyplot(fig_loads, clear_figure=True)
        plt.close(fig_loads)

    with st.expander("Inspect Per-Invigilator Total, Campus & Weekly Loads"):
        st.dataframe(
            pd.DataFrame(staff_workload_rows(inst, active_pairs)),
            use_container_width=True,
            hide_index=True,
        )

    st.divider()
    st.header("2. Predicate Logic Specification & SAT Check (Module 1)")
    m1_c1, m1_c2, m1_c3, m1_c4 = st.columns(4)
    m1_c1.metric("Verdict (Minisat22)", "SATISFIABLE" if m1_res["satisfiable"] else "UNSATISFIABLE")
    m1_c2.metric("Assignment Variables", f"{m1_res['n_assign_vars']:,}", f"Aux: {m1_res['n_aux_vars']:,}")
    m1_c3.metric("CNF Clauses", f"{m1_res['n_clauses']:,}", f"{m1_res['runtime_ms']:.1f} ms")
    m1_c4.metric("0/1 Linear Rows", f"{m1_res['linear_rows']:,}", str(m1_res["linear_summary"]))

    if m1_res["satisfiable"] and isinstance(m1_res["model"], dict):
        sample_rows = [
            {"session": sess, "sat_witness_staff": ", ".join(people)}
            for sess, people in list(m1_res["model"].items())[:10]
        ]
        with st.expander("View Sample SAT Witness Assignments & Logic-to-LP Bridge Table"):
            st.dataframe(pd.DataFrame(sample_rows), use_container_width=True, hide_index=True)
            st.dataframe(pd.DataFrame(m1_res["bridge_rows"]), use_container_width=True, hide_index=True)
    elif m1_res["unsat_core"]:
        st.error("Minimal UNSAT Core extracted via assumption selectors:")
        st.dataframe(
            pd.DataFrame({"Minimal UNSAT Core": m1_res["unsat_core"]}),
            use_container_width=True,
            hide_index=True,
        )

    st.divider()
    st.header("3. Automaton-Based Temporal Validity (Module 3)")
    rv = temporal_audit["rule_violations"]
    r_c1, r_c2, r_c3, r_c4, r_c5 = st.columns(5)
    r_c1.metric("Schedule Valid Flag", "VALID" if temporal_audit["schedule_valid"] else "INVALID")
    r_c2.metric("R1 (>2 Consecutive Work)", f"{rv['R1']} staff")
    r_c3.metric("R2 (Night Without Rest)", f"{rv['R2']} staff")
    r_c4.metric("R3 (>4 Work in 7 Days)", f"{rv['R3']} staff")
    r_c5.metric("R4 Info (|#M-#A| > 3)", f"{rv['R4_prefix']} prefix / {rv['R4_end']} end")

    if preset == "full" and "M2 + R1xR2xR3" not in schedules:
        m3_ref = _m3_reference_summary()
        if m3_ref:
            st.info(
                f"Offline M3 flow-ILP benchmark (`extra/regular_to_ilp.json`): `M2 + R1xR2xR3` achieves "
                f"`max_load = {m3_ref['max_load']}`, `L1 = {m3_ref['l1']:.3f}`, stage-2 objective "
                f"`{m3_ref['weighted_objective']:.3f}`, and **{m3_ref['violations']['accepted']}/73** "
                "DFA-accepted rosters (`0` violations). Run `python run_all.py --seed 1358677812 --stage m5` "
                "or enable the sidebar checkbox to load its full session table."
            )

    col_m3_left, col_m3_right = st.columns([1.3, 1.0])
    with col_m3_left:
        st.subheader("Cross-Schedule DFA Acceptance")
        st.dataframe(pd.DataFrame(m3_comparison), use_container_width=True, hide_index=True)
    with col_m3_right:
        st.subheader("Product & Myhill-Nerode Minimization")
        st.dataframe(
            pd.DataFrame(temporal_audit["state_counts"]),
            use_container_width=True,
            hide_index=True,
        )

    only_rejected = st.checkbox(
        "Show only staff rejected by R1xR2xR3", value=False, key="only_rejected_staff"
    )
    roster_rows = [
        r for r in temporal_audit["staff_rows"] if (not only_rejected or not r["dfa_accepted"])
    ]
    st.subheader(f"Invigilator Daily Strings over {{M, A, N, -}} ({temporal_audit['calendar_days']} days)")
    st.dataframe(pd.DataFrame(roster_rows), use_container_width=True, hide_index=True)
    with st.expander("Inspect Day-by-Day DFA State Trace for One Invigilator"):
        trace_person = st.selectbox(
            "Select Invigilator", options=inst.staff_ids, key="trace_staff_id"
        )
        st.dataframe(
            pd.DataFrame(staff_daily_trace_rows(inst, active_pairs, trace_person)),
            use_container_width=True,
            hide_index=True,
        )

    st.divider()
    st.header("4. Vector Fatigue Dynamics, Fairness & Equilibrium (Module 4 — Direction B)")
    d_c1, d_c2, d_c3, d_c4 = st.columns(4)
    d_c1.metric(
        "Calibrated (a, b, r)",
        f"({dyn['parameters']['a']:.4f}, {dyn['parameters']['b']:.4f}, {dyn['parameters']['r']:.1f})",
    )
    d_c2.metric(
        "Stability (Jacobian aI)",
        dyn["stability"]["classification"],
        f"|a| = {dyn['stability']['spectral_radius']:.4f} < 1",
    )
    d_c3.metric("95% Soft Threshold H", f"{dyn['threshold']:.4f}")
    d_c4.metric(
        f"Observed Excess ({active_schedule_name})",
        f"{active_dyn['observed_threshold_excess']:.4f}"
        if active_dyn["observed_threshold_excess"] is not None
        else "N/A",
    )

    fig_fairness = plot_fairness_over_time(dyn)
    st.pyplot(fig_fairness, clear_figure=True)
    plt.close(fig_fairness)

    fig_traj = plot_fatigue_trajectories(dyn, active_schedule_name)
    st.pyplot(fig_traj, clear_figure=True)
    plt.close(fig_traj)

    st.subheader("Long-Run Equilibrium & Convergence Verification")
    st.dataframe(pd.DataFrame(dyn["summary_rows"]), use_container_width=True, hide_index=True)
    with st.expander("Inspect Observed Weekly Block Assignments & End-of-Block Fatigue"):
        st.dataframe(
            pd.DataFrame(observed_block_summary(inst, active_pairs, dyn["parameters"])),
            use_container_width=True,
            hide_index=True,
        )


if __name__ == "__main__":
    main()
