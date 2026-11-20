"""Tests for dataset presets, upload validation and weekly assignment tables (M5, Vinh)."""

from pathlib import Path

import pytest

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
from m1_logic.data_loader import DEFAULT_PATH, PROJECT_FOLDER


def test_presets_load_without_mutating_tracked_slice():
    slice_file = PROJECT_FOLDER / "data" / "m1_cases" / "real_slice.csv"
    before = slice_file.read_bytes()
    seed = read_team_seed()

    m1_full, full = load_preset_instance("full", seed=seed)
    assert (len(full.staff_ids), len(full.session_names), sum(full.demand)) == (73, 83, 769)
    assert len(m1_full["busy"]) == 73 * 83 - len(full.A)

    _, w1 = load_preset_instance("week1", seed=seed)
    _, w2 = load_preset_instance("week2", seed=seed)
    assert len(w1.session_names) < len(w2.session_names) < len(full.session_names)

    m1_sat, sat_inst = load_preset_instance("m1_slice", seed=seed, m1_scenario="sat")
    m1_unsat, unsat_inst = load_preset_instance("m1_slice", seed=seed, m1_scenario="unsat")
    assert len(m1_unsat["busy"]) > len(m1_sat["busy"])
    assert len(unsat_inst.A) < len(sat_inst.A)

    toy_sat, toy = load_preset_instance("toy", seed=seed, m1_scenario="sat")
    toy_unsat, _ = load_preset_instance("toy", seed=seed, m1_scenario="unsat")
    assert len(toy.staff_ids) == 3 and len(toy_unsat["busy"]) == len(toy_sat["busy"]) + 1
    assert set(DATASET_PRESETS) == {"full", "week1", "week2", "m1_slice", "toy", "upload"}
    assert slice_file.read_bytes() == before


def test_csv_and_schedule_upload_validation():
    raw_csv = Path(DEFAULT_PATH).read_bytes()
    m1_data, inst = load_csv_bytes(raw_csv)
    assert len(inst.staff_ids) == 73 and len(m1_data["session_ids"]) == 83

    sched_bytes = (PROJECT_FOLDER / "m2_ilp" / "schedule.csv").read_bytes()
    assigned = parse_uploaded_schedule(inst, sched_bytes)
    assert len(assigned) == 769

    with pytest.raises(ValueError, match="empty"):
        load_csv_bytes(b"   ")
    with pytest.raises(ValueError, match="Missing columns"):
        load_csv_bytes(b"col_a,col_b\n1,2\n")
    with pytest.raises(ValueError):
        parse_uploaded_schedule(inst, b"invigilator_id,session_id,assigned\nCB001,BAD,1\n")


def test_weekly_and_staff_tables_conserve_assignments():
    _, inst = load_preset_instance("full")
    weeks = week_options(inst)
    assert [w["days"] for w in weeks] == [7, 7, 7, 6]
    assert sum(w["sessions"] for w in weeks) == len(inst.session_names) == 83

    all_rows = weekly_assignment_rows(inst, inst.baseline)
    assert len(all_rows) == 83
    assert all(row["status"] == "OK" for row in all_rows)
    assert sum(row["assigned"] for row in all_rows) == 769

    w1_rows = weekly_assignment_rows(inst, inst.baseline, week=1)
    cs1_rows = weekly_assignment_rows(inst, inst.baseline, campus="CS1")
    assert sum(r["assigned"] for r in w1_rows) == 15
    assert all(r["campus"] == "CS1" for r in cs1_rows)

    staff_rows = staff_workload_rows(inst, inst.baseline)
    assert len(staff_rows) == 73
    assert sum(r["total_load"] for r in staff_rows) == 769
    assert all(r["cs1_load"] + r["cs2_load"] == r["total_load"] for r in staff_rows)
    assert all(sum(r[f"W{k}"] for k in range(1, 5)) == r["total_load"] for r in staff_rows)

    converted = instance_to_m1_data(inst)
    assert [f"{c}_{cp}" for c, cp in converted["session_ids"]] == inst.session_names
