"""Headless AppTest coverage of the six Module 5 pages; every check runs the real Modules 1-4 adapters."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from app import services
from app.ui import parts

ROOT = Path(__file__).resolve().parents[2]
APP_SCRIPT = str(ROOT / "app" / "app.py")
IDEAS = {"m1": 4, "m2": 5, "m3": 5, "m4": 5}
LANDMARK = {"overview": "Dữ liệu đang dùng", "m1": "Thử ngay: đổi kịch bản", "m2": "Thử ngay: giải một lát dữ liệu bằng CBC",
            "m3": "Thử ngay: gõ một chuỗi ngày", "m4": "Thử ngay: đổi a", "m5": "<mark>4 mô hình</mark>"}


def page(route: str, **state) -> AppTest:
    at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    at.session_state["route"] = route
    for key, value in state.items():
        at.session_state[key] = value
    return at.run()


def text(at: AppTest) -> str:
    """Everything the page wrote as HTML or markdown, without the injected stylesheet."""
    return " ".join(item.value for item in at.markdown if not item.value.startswith("<style>"))


def healthy(at: AppTest) -> bool:
    return not at.exception and not at.error


@pytest.mark.parametrize("route", list(LANDMARK))
def test_every_route_renders_its_own_page(route):
    at = page(route)
    assert healthy(at)
    assert LANDMARK[route] in text(at)
    if route != "overview":
        assert all(f'class="iap-badge-{kind}"' in text(at) for kind in parts.BADGE_KINDS)


def test_module5_headline_reads_ket_luan_cua_4_mo_hinh():
    assert 'Kết luận của <mark>4 mô hình</mark></h1>' in text(page("m5"))


def test_badge_kinds_are_distinct_and_escaped():
    assert "&lt;b&gt;" in parts.badge("fn", "<b>") and "<b>" not in parts.badge("fn", "<b>")
    assert len({parts.badge(kind, "x") for kind in parts.BADGE_KINDS}) == 3
    with pytest.raises(ValueError):
        parts.badge("other", "x")


@pytest.mark.parametrize("route", list(IDEAS))
def test_every_idea_has_its_own_headline_and_draws_its_figure(route):
    at, headlines = page(route), set()
    for index in range(IDEAS[route]):
        at.radio(key=f"idea_{route}").set_value(index).run()
        assert healthy(at), (route, index)
        headlines.add(next(item.value for item in at.markdown if item.value.startswith('<h1 class="iap-h1">')))
    assert len(headlines) == IDEAS[route]


def test_idea_buttons_change_the_headline_and_keep_the_lab_input():
    at = page("m3")
    at.text_input(key="m3_word").set_value("MAM").run()
    assert "DFA rơi vào" in text(at)
    at.button(key="next_m3").click().run()
    assert "259 trạng thái còn" in text(at)
    assert at.text_input(key="m3_word").value == "MAM"
    at.button(key="prev_m3").click().run()
    assert "DFA rơi vào" in text(at)


def test_choices_survive_leaving_the_page_and_coming_back():
    at = page("m5")
    at.radio(key="m5_schedule").set_value("Lịch gốc").run()
    at.radio(key="route").set_value("m1").run()
    at.radio(key="route").set_value("m5").run()
    assert healthy(at) and not at.warning
    assert at.radio(key="m5_schedule").value == "Lịch gốc"
    assert "Lịch chưa hợp lệ" in text(at)


def test_m1_reports_sat_witness_and_minimal_unsat_core():
    at = page("m1")
    body = text(at)
    assert "UNSAT: không thể xếp" in body and "6 ràng buộc" in body
    assert "capacity(20260610_2_CS2)=1" in body and "Busy(CB066,20260610_2_CS2)" in body

    at.radio(key="m1_case").set_value("Toy · UNSAT").run()
    body = text(at)
    assert "Busy(CB1,Morning_CS1)" in body and "Busy(CB2,Morning_CS1)" in body and "Busy(CB3" not in body

    at.radio(key="m1_case").set_value("Toy · SAT").run()
    at.button(key="m1_run_button").click().run()
    assert healthy(at)
    assert "SAT: có lịch" in text(at) and "UNSAT: không thể xếp" not in text(at)


def test_m2_solves_real_slices_with_cbc_and_links_the_dfa_rules():
    at = page("m2")
    body = text(at)
    assert "<small>Tải đỉnh</small><b>1</b><em>lịch gốc 3</em>" in body
    assert "0 vi phạm H1, H2, H3" in body and "Giám thị được xếp" in body

    at.radio(key="m2_slice").set_value("2 tuần").run()
    at.checkbox(key="m2_enforce").check().run()
    body = text(at)
    assert healthy(at) and not at.warning
    assert "Hiện 6 trên 26 ca" in body and "DFA chấp nhận 73/73 chuỗi" in body and "0 vi phạm H1, H2, H3" in body


def test_m2_infeasible_slice_warns_instead_of_showing_a_plan(monkeypatch):
    real = services.load_preset_instance  # same loader, toy case where Morning needs 2 but only 1 person is free
    monkeypatch.setattr(services, "load_preset_instance", lambda preset, **kw: real(preset, **{**kw, "m1_scenario": "unsat"}))
    at = page("m2", m2_slice="Toy 3 × 2")
    assert healthy(at)
    assert any("infeasible" in item.value and "ca Morning cần 2 người, còn thiếu 1" in item.value for item in at.warning)
    assert "Giám thị được xếp" not in text(at)


def test_m3_word_lab_flags_the_first_violating_day():
    at = page("m3")
    assert "R2: vi phạm ở ngày 10" in text(at)  # CB003 of the original schedule

    at.text_input(key="m3_word").set_value("MAM").run()
    assert "Bị từ chối" in text(at) and "R1: vi phạm ở ngày 3" in text(at)
    at.text_input(key="m3_word").set_value("MA-M").run()
    assert "Được chấp nhận" in text(at)

    at.text_input(key="m3_word").set_value("mm-x!").run()  # lower case and foreign characters
    assert "Được chấp nhận" in text(at) and "<small>3</small>" in text(at) and "<small>4</small>" not in text(at)
    at.text_input(key="m3_word").set_value("xyz").run()
    assert healthy(at) and any("Chuỗi rỗng" in item.value for item in at.info)

    at.button(key="m3_preset_Đêm rồi đi làm").click().run()
    assert at.text_input(key="m3_word").value == "M-NA---" and "R2: vi phạm ở ngày 4" in text(at)


def test_m4_slider_moves_between_the_three_stability_regimes():
    at = page("m4")
    assert "<b>Ổn định tiệm cận</b>" in text(at) and "<b>2,73</b>" in text(at)
    at.slider(key="m4_a").set_value(0.5).run()
    assert "<b>Ổn định tiệm cận</b>" in text(at) and "<b>3,98</b>" in text(at)  # F* = b·ℓ / (1 − a) moves with a
    at.slider(key="m4_a").set_value(1.0).run()
    assert "<b>Trung hòa</b>" in text(at)
    at.slider(key="m4_a").set_value(1.05).run()
    assert healthy(at) and "<b>Phân kỳ</b>" in text(at) and "không hút" in text(at)
    at.button(key="m4_preset_0.27").click().run()
    assert at.slider(key="m4_a").value == 0.27 and "<b>Ổn định tiệm cận</b>" in text(at)


def test_m4_scatter_shows_the_data_the_calibration_used():
    pairs, dyn = services.lag_pairs(), services.dynamics()
    slope, intercept = np.polyfit([pair["x"] for pair in pairs], [pair["y"] for pair in pairs], 1)
    assert len(pairs) == dyn["calibration"]["observations"] == 219
    assert slope == pytest.approx(dyn["parameters"]["a"])
    assert intercept == pytest.approx(dyn["calibration"]["workload_intercept"])


def test_m5_shows_all_four_answers_for_the_selected_schedule():
    at = page("m5")
    body = text(at)
    assert "<b>SAT</b>" in body and "Lịch phân công tuần 1" in body
    assert "Lịch hợp lệ" in body and "DFA chấp nhận 73/73 chuỗi" in body and "ổn định" in body

    at.radio(key="m5_schedule").set_value("Lịch gốc").run()
    body = text(at)
    assert "Lịch chưa hợp lệ" in body and "DFA chấp nhận 41/73 chuỗi" in body
    assert "<small>Tải đỉnh</small><b>19</b>" in body

    at.selectbox(key="m5_week").select(3).run()
    at.button(key="m5_run").click().run()
    assert healthy(at) and "Lịch phân công tuần 3" in text(at) and "DFA chấp nhận 41/73 chuỗi" in text(at)


def test_uploaded_dataset_is_audited_and_bad_files_are_rejected():
    audit = services.uploaded((ROOT / "data" / "input.csv").read_bytes())
    assert audit["m1"]["satisfiable"] is True
    assert (audit["temporal"]["accepted_count"], audit["temporal"]["total_staff"]) == (41, 73)
    assert audit["metrics"]["max_load"] == 19 and audit["rows"]
    for bad in (b"", b"hello,world\n1,2\n", b"\xff\xfe\x00\x01", b"x" * (600 * 1024)):
        with pytest.raises(ValueError):
            services.uploaded(bad)


@pytest.fixture
def no_bundle(monkeypatch, tmp_path):
    monkeypatch.setattr(services, "DEFAULT_BUNDLE", tmp_path / "missing.json")
    st.cache_data.clear()
    st.cache_resource.clear()
    yield
    st.cache_data.clear()
    st.cache_resource.clear()


def test_missing_bundle_falls_back_to_repository_artifacts(no_bundle):
    at = page("overview")
    assert healthy(at) and "tệp kết quả trong repo" in text(at)
    at = page("m5")
    assert healthy(at) and "M2 + DFA" not in at.radio(key="m5_schedule").options
    assert healthy(page("m3"))
