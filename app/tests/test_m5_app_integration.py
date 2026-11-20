"""Integration tests for M5 precomputation and headless Streamlit AppTest UI (M5 Lead, Thanh)."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.data_views import read_team_seed
from app.precompute import load_full_schedules, run_m5
from m1_logic.data_loader import PROJECT_FOLDER
from m2_ilp.validate import check_schedule

APP_SCRIPT = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture(scope="module")
def m5_artifacts(tmp_path_factory):
    folder = tmp_path_factory.mktemp("m5_bundle")
    seed = read_team_seed()
    bundle = run_m5(seed, out_dir=folder, weeks=52)
    return seed, folder, bundle


def test_run_m5_reproducibility_and_input_protection(m5_artifacts, tmp_path):
    seed, first_dir, bundle = m5_artifacts
    m2_csv = PROJECT_FOLDER / "m2_ilp" / "schedule.csv"
    before = m2_csv.read_bytes()

    second_bundle = run_m5(seed, out_dir=tmp_path, weeks=52)
    assert m2_csv.read_bytes() == before
    assert second_bundle == bundle
    assert (first_dir / "m5_bundle.json").read_bytes() == (tmp_path / "m5_bundle.json").read_bytes()

    assert bundle["m1"]["full_satisfiable"] is True
    assert bundle["m1"]["slice_sat"] is True
    assert bundle["m1"]["slice_unsat_core"]

    m3_by_name = {r["schedule"]: r for r in bundle["m3_comparison"]}
    assert m3_by_name["Baseline"]["schedule_valid"] is False
    assert m3_by_name["M2 Optimal"]["schedule_valid"] is False
    assert m3_by_name["M2 + R1xR2xR3"]["schedule_valid"] is True
    assert m3_by_name["M2 + R1xR2xR3"]["dfa_accepted"] == "73/73"

    inst, loaded, source = load_full_schedules(seed, bundle_path=first_dir / "m5_bundle.json")
    assert "precomputed" in source
    assert set(loaded) == {"Baseline", "M2 Optimal", "M2 + R1xR2xR3", "M4 Fatigue-Aware"}
    assert all(check_schedule(inst, pairs) == [] for pairs in loaded.values())

    _, fallback_scheds, fallback_src = load_full_schedules(seed, bundle_path=tmp_path / "missing.json")
    assert "live" in fallback_src
    assert {"Baseline", "M2 Optimal", "M4 Fatigue-Aware"} <= set(fallback_scheds)


def test_streamlit_app_launches_and_renders_all_four_modules_on_one_page():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=30)
    at.run()
    assert not at.exception
    assert len(at.title) == 1
    headers = [h.value for h in at.header]
    assert any("Module 2" in h for h in headers)
    assert any("Module 1" in h for h in headers)
    assert any("Module 3" in h for h in headers)
    assert any("Module 4" in h for h in headers)
    metric_labels = [m.label for m in at.metric]
    assert "Schedule valid (DFA-accepted)" in metric_labels
    assert len(at.dataframe) >= 4


def test_streamlit_app_interactive_presets_and_unsat_diagnosis():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=30)
    at.run()
    assert not at.exception

    # Switch to 1-Week Real Slice (enforces M3 DFA rules live -> DFA-accepted YES).
    at.selectbox(key="dataset_preset").select("week1").run()
    assert not at.exception
    assert any("Schedule valid (DFA-accepted): YES" in s.value for s in at.success)

    # Switch to M1 Seeded Slice in UNSAT mode -> displays M1 UNSAT core + M2 shortage diagnosis.
    at.selectbox(key="dataset_preset").select("m1_slice").run()
    assert not at.exception
    at.radio(key="m1_scenario").set_value("unsat").run()
    assert not at.exception
    assert any("Schedule valid (DFA-accepted): NO" in e.value for e in at.error)
