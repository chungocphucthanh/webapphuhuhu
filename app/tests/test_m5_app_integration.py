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


def test_pipeline_audits_the_selected_full_schedule_across_modules():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=30).run()
    at.radio(key="route").set_value("pipeline").run()
    assert not at.exception
    assert any("73/73" in item.value for item in at.success)
    assert any("Giám thị" in frame.value.columns for frame in at.dataframe)

    at.selectbox(key="active_schedule").select("Baseline").run()
    assert not at.exception
    assert any("không được DFA chấp nhận" in item.value for item in at.warning)
    at.radio(key="route").set_value("m1").run()
    at.radio(key="route").set_value("pipeline").run()
    assert any("không được DFA chấp nhận" in item.value for item in at.warning)


def test_live_solve_is_shared_across_pages_but_not_across_input_changes():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=30).run()
    at.selectbox(key="dataset_preset").select("toy").run()
    at.radio(key="route").set_value("m2").run()
    at.button(key="solve").click().run()
    assert not at.exception
    plan = next(frame.value for frame in at.dataframe if "Đã xếp" in frame.value.columns)
    assert plan["Đã xếp"].tolist() == [2, 2]

    at.radio(key="route").set_value("pipeline").run()
    assert any("3/3" in item.value for item in at.success)
    at.slider(key="time_limit").set_value(20).run()
    at.slider(key="time_limit").set_value(15).run()
    assert at.selectbox(key="active_schedule").value == "Baseline"
    assert "Lịch vừa giải bằng CBC" not in at.selectbox(key="active_schedule").options
    at.button(key="solve").click().run()
    assert any("3/3" in item.value for item in at.success)
    at.radio(key="m1_scenario").set_value("unsat").run()
    assert not at.exception
    assert any("UNSAT" in item.value for item in at.error)
    assert not any("Đã xếp" in frame.value.columns for frame in at.dataframe)
    at.button(key="solve").click().run()
    shortage = next(frame.value for frame in at.dataframe if "Còn thiếu" in frame.value.columns)
    assert shortage["Còn thiếu"].tolist() == [1]


def test_one_week_slice_can_be_solved_with_dfa_constraints():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=30).run()
    at.selectbox(key="dataset_preset").select("week1").run()
    at.radio(key="route").set_value("pipeline").run()
    at.button(key="solve").click().run()
    assert at.selectbox(key="active_schedule").value == "Solved Plan"
    assert not at.exception
    assert any("61/61" in item.value for item in at.success)


def test_presenter_can_advance_and_return_without_losing_the_selected_schedule():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=30).run()
    at.button(key="start_presentation").click().run()
    at.button(key="stage_next").click().run()
    at.selectbox(key="active_schedule").select("Baseline").run()

    at.button(key="stage_next").click().run()
    assert not at.exception
    assert any("không được DFA chấp nhận" in item.value for item in at.warning)
    at.button(key="stage_previous").click().run()
    assert at.selectbox(key="active_schedule").value == "Baseline"


def test_single_session_view_follows_the_current_week_filter():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=30).run()
    at.radio(key="route").set_value("m2").run()
    schedule = next(frame.value for frame in at.dataframe if "Mã ca" in frame.value.columns)
    session = schedule.loc[schedule["Tuần"].eq(1), "Mã ca"].iloc[-1]
    at.selectbox(key="plan_session").select(session).run()
    at.selectbox(key="week_filter").select(1).run()
    assert at.selectbox(key="plan_session").value == session

    at.selectbox(key="week_filter").select(2).run()
    second_week = next(frame.value for frame in at.dataframe if "Mã ca" in frame.value.columns)
    assert not at.exception
    assert at.selectbox(key="plan_session").value in second_week["Mã ca"].tolist()


def test_rule_filter_exposes_the_rule_name_and_only_matching_staff():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=30).run()
    at.radio(key="route").set_value("m3").run()
    at.selectbox(key="active_schedule").select("Baseline").run()
    rules = at.selectbox(key="rule_filter")
    assert "R2 · Nghỉ ngày kế tiếp sau ca tối, nếu còn trong kỳ" in rules.options
    rules.select("R2").run()
    staff = next(frame.value for frame in at.dataframe if "Quy tắc vi phạm" in frame.value.columns)
    assert not staff.empty
    assert all("R2" in value.split(", ") for value in staff["Quy tắc vi phạm"])

    at.selectbox(key="active_schedule").select("M2 + R1xR2xR3").run()
    assert any("Không có giám thị khớp bộ lọc" in item.value for item in at.info)



def test_unsat_reports_the_session_and_people_in_the_conflict():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=30).run()
    at.radio(key="route").set_value("m1").run()
    at.button(key="sat_demo").click().run()
    assert not at.exception
    assert any("UNSAT" in item.value for item in at.error)
    core = " ".join(item.value for item in at.markdown if "iap-conflict" in item.value)
    assert "H3" in core and "H1" in core
    assert "Morning_CS1" in core and "cần 2 giám thị" in core
    assert "CB1" in core and "CB2" in core and "CB3" not in core
    at.button(key="sat_demo").click().run()
    assert at.selectbox(key="sat_witness_session").value == "Morning_CS1"


def test_dfa_lab_rejects_three_consecutive_days_and_accepts_a_break():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=30).run()
    at.radio(key="route").set_value("m3").run()
    at.text_input(key="dfa_word").set_value("MAM").run()
    assert not at.exception
    assert any("ngày 3" in item.value for item in at.warning)
    trace = next(frame.value for frame in at.dataframe if "Ký hiệu" in frame.value.columns)
    assert trace["Ký hiệu"].tolist() == ["M", "A", "M"]

    at.text_input(key="dfa_word").set_value("MA-M").run()
    assert any("được DFA chấp nhận" in item.value for item in at.success)


def test_fatigue_perturbation_changes_initial_state_not_equilibrium():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=30).run()
    at.radio(key="route").set_value("m4").run()
    before = {metric.label: metric.value for metric in at.metric}
    at.slider(key="shock_amount").set_value(4.0).run()
    assert not at.exception
    after = {metric.label: metric.value for metric in at.metric}
    assert float(after["F tại tuần 0"]) - float(before["F tại tuần 0"]) == pytest.approx(4)
    assert after["Điểm cân bằng F*"] == before["Điểm cân bằng F*"]
