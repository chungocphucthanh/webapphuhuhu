"""Tests for M3 temporal validity flag, violation counts and DFA trace (M5, Phuc)."""

from datetime import date, datetime
from pathlib import Path

from app.temporal_views import (
    build_roster_strings,
    compare_temporal_schedules,
    evaluate_temporal_validity,
    load_automata_suite,
    trace_word,
)
from m2_ilp.config import ModelConfig, TEAM_ID
from m2_ilp.fixtures import week_slice
from m2_ilp.instance import Instance, build_instance
from m3_automata.encode_strings import encode_strings
from m3_automata.regular_to_ilp import solve_with_rules
from m4_dynamics.workload import read_schedule
from tools.make_seed import seed_for, soft_weights


def test_baseline_and_m2_schedule_temporal_flags_match_m3_numbers():
    inst = build_instance()
    suite = load_automata_suite()
    _, strings = build_roster_strings(inst, inst.baseline)
    assert strings == encode_strings()

    base_audit = evaluate_temporal_validity(inst, inst.baseline, suite=suite)
    assert base_audit["schedule_valid"] is False
    assert base_audit["dfa_accepted_all"] is False
    assert (base_audit["accepted_count"], base_audit["rejected_count"]) == (41, 32)
    assert base_audit["rule_violations"] == {
        "R1": 28,
        "R2": 5,
        "R3": 3,
        "any": 32,
        "accepted": 41,
        "R4_prefix": 20,
        "R4_end": 19,
    }

    m2_path = Path(__file__).resolve().parents[2] / "m2_ilp" / "schedule.csv"
    m2_assigned = read_schedule(inst, m2_path)
    m2_audit = evaluate_temporal_validity(inst, m2_assigned, suite=suite)
    assert m2_audit["schedule_valid"] is False
    assert (m2_audit["accepted_count"], m2_audit["rejected_count"]) == (24, 49)
    assert (
        m2_audit["rule_violations"]["R1"],
        m2_audit["rule_violations"]["R2"],
        m2_audit["rule_violations"]["R3"],
    ) == (44, 6, 14)


def test_dfa_enforced_schedule_sets_valid_flag_and_traces_violations():
    suite = load_automata_suite()
    w1 = week_slice(build_instance(), 1)
    sol, _, _ = solve_with_rules(w1, ModelConfig(time_limit=15), suite["minimal"])
    audit = evaluate_temporal_validity(w1, sol.assigned, suite=suite)
    assert audit["schedule_valid"] is True
    assert audit["dfa_accepted_all"] is True
    assert audit["rejected_count"] == 0
    assert all(row["dfa_accepted"] and row["first_violation_day"] is None for row in audit["staff_rows"])

    bad_trace = trace_word(suite["rules"]["R1"], "-MMM-")
    assert bad_trace["accepted"] is False
    assert bad_trace["first_violation_day"] == 4
    good_trace = trace_word(suite["rules"]["R2"], "N-M-")
    assert good_trace["accepted"] is True
    assert good_trace["first_violation_day"] is None

    table = compare_temporal_schedules(w1, {"Baseline": w1.baseline, "M2+M3": sol.assigned}, suite=suite)
    assert len(table) == 2 and table[1]["schedule_valid"] is True


def test_custom_start_hours_and_hard_violation_invalidate_schedule_flag():
    custom = Instance(
        seed=seed_for(TEAM_ID),
        availability="explicit",
        staff_ids=["CB1", "CB2"],
        session_names=["S_morning", "S_evening"],
        demand=[1, 1],
        campus=["CS1", "CS2"],
        day=[date(2026, 5, 18), date(2026, 5, 19)],
        intervals=[
            (datetime(2026, 5, 18, 8, 0), datetime(2026, 5, 18, 10, 0)),
            (datetime(2026, 5, 19, 19, 0), datetime(2026, 5, 19, 21, 0)),
        ],
        overlaps=[],
        baseline=[(0, 0), (1, 1)],
        A={(0, 0), (1, 1)},
        preferences=["BAL", "BAL"],
        soft_weights=soft_weights(TEAM_ID),
    )
    valid_audit = evaluate_temporal_validity(custom, [(0, 0), (1, 1)])
    assert valid_audit["schedule_valid"] is True
    by_staff = {r["staff_id"]: r["roster_string"] for r in valid_audit["staff_rows"]}
    assert by_staff == {"CB1": "M-", "CB2": "-N"}

    missing_demand = evaluate_temporal_validity(custom, [(0, 0)])
    assert missing_demand["dfa_accepted_all"] is True
    assert missing_demand["schedule_valid"] is False
    assert len(missing_demand["hard_violations"]) == 1

    from app.temporal_views import staff_daily_trace_rows
    import pytest

    daily = staff_daily_trace_rows(custom, [(0, 0), (1, 1)], "CB1")
    assert [r["symbol"] for r in daily] == ["M", "-"]
    assert daily[0]["R1_state"] == "run1" and daily[1]["R1_state"] == "run0"
    with pytest.raises(ValueError, match="Unknown staff_id"):
        staff_daily_trace_rows(custom, [(0, 0), (1, 1)], "MISSING")
