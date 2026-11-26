"""Integration tests for M5 precomputation (M5 Lead, Thanh). UI tests live in test_m5_ui.py."""

import pytest

from app.data_views import read_team_seed
from app.precompute import load_full_schedules, run_m5
from m1_logic.data_loader import PROJECT_FOLDER
from m2_ilp.validate import check_schedule


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
