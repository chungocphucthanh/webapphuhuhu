"""Real-data entry point, artifact reproducibility and input protection."""

import json
from pathlib import Path

import pytest

from m2_ilp.instance import build_instance
from m4_dynamics.run import run_m4
from m4_dynamics.workload import read_schedule


@pytest.fixture(scope="module")
def artifacts(tmp_path_factory):
    folder = tmp_path_factory.mktemp("m4")
    inst = build_instance()
    result = run_m4(inst.seed, folder)
    return inst, folder, result


def test_real_data_outputs_back_every_claim(artifacts):
    inst, folder, result = artifacts
    assert result == json.loads((folder / "results.json").read_text())
    assert result["source"]["weekly_days"] == [7, 7, 7, 6]
    assert result["stability"]["classification"] == "asymptotically stable"
    assert result["verification"]["all_fixed_points_converged"] is True
    for name, info in result["scenarios"].items():
        assert info["converged"] is True
        assert info["final_max_error"] <= result["simulation"]["tolerance"]
        if name != "equal_load":
            assert info["assignments"] == sum(inst.demand)
    assert result["scenarios"]["equal_load"]["equilibrium_spread"] < 1e-10
    assert (result["scenarios"]["m2"]["equilibrium_spread"]
            < result["scenarios"]["baseline"]["equilibrium_spread"])
    refined = read_schedule(inst, folder / "fatigue_aware_schedule.csv")
    assert len(refined) == sum(inst.demand)
    assert result["planning"]["hard_rule_violations"] == 0
    assert result["planning"]["metrics"]["max_load"] <= result["planning"]["max_load_cap"]
    assert result["planning"]["threshold_penalty"] == pytest.approx(
        result["scenarios"]["fatigue_aware"]["observed_threshold_penalty"])
    for name in ("fairness.png", "fatigue_equilibrium.png", "observed_fatigue.png"):
        assert (folder / name).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_all_artifacts_are_reproducible_and_m2_is_unchanged(artifacts, tmp_path):
    inst, first, _ = artifacts
    source = Path(__file__).resolve().parents[2] / "m2_ilp" / "schedule.csv"
    before = source.read_bytes()
    run_m4(inst.seed, tmp_path)
    assert source.read_bytes() == before
    assert {p.name for p in first.iterdir()} == {p.name for p in tmp_path.iterdir()}
    for path in first.iterdir():
        assert path.read_bytes() == (tmp_path / path.name).read_bytes(), path.name


def test_missing_schedule_fails_without_output(tmp_path):
    with pytest.raises(FileNotFoundError, match="run stage m2 first"):
        run_m4(build_instance().seed, tmp_path / "output", schedule_path=tmp_path / "missing.csv")
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("rows", [
    "invigilator_id,session_id,assigned\nCB1,Morning,2\n",
    "invigilator_id,session_id,assigned\nCB1,Morning,0\nCB1,Morning,0\n",
    "invigilator_id,session_id,assigned\nCB1,Morning,0\n",
    "invigilator_id,session_id,assigned\nCB1,Unknown,1\n",
    "invigilator_id,session_id,assigned\nCB1,Morning,0,extra\n",
])
def test_malformed_schedule_is_rejected(rows, tmp_path):
    from m2_ilp.instance import toy_instance

    path = tmp_path / "schedule.csv"
    path.write_text(rows)
    with pytest.raises(ValueError):
        read_schedule(toy_instance(), path)
