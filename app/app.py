"""Streamlit entry point for the CO2011 Module 5 presentation."""

from __future__ import annotations

import csv
import logging
import sys
from datetime import date
from hashlib import sha256
from io import StringIO
from pathlib import Path
from urllib.parse import quote, unquote

ROOT_DIR = Path(__file__).resolve().parents[1]
# Streamlit prepends app/; the package must win over the sibling app.py.
if sys.path[0] != str(ROOT_DIR):
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
import streamlit.components.v1 as components
from pulp import PulpSolverError

from app.data_views import load_csv_bytes, load_preset_instance, parse_uploaded_schedule, read_team_seed
from app.precompute import DEFAULT_BUNDLE, load_full_schedules
from app.presentation import PRESETS, apply_style, hero, memo, schedule_label
from app.presentation_views import (
    dynamics_panel,
    logic_panel,
    m3_rules_experiment_tab,
    m3_theory_tab,
    overview,
    plan_panel,
    pumping_lemma_tab,
    solve_status,
    temporal_panel,
    word_lab,
)
from app.solver_views import run_m1_check, solve_schedule_in_app
from app.theory_content import render_pipeline_theory
from m1_logic.data_loader import REQUIRED_COLUMNS, STAFF_COLUMN
from m2_ilp.config import TEAM_ID
from m2_ilp.validate import check_schedule

LOGGER = logging.getLogger(__name__)
ROUTES = {
    "overview": "Tổng quan kiến trúc",
    "m1": "1 · Logic và SAT",
    "m2": "2 · Tối ưu lịch ILP",
    "m3": "3 · Quy tắc thời gian DFA",
    "m4": "4 · Fatigue và công bằng",
    "pipeline": "Demo đầu-cuối",
}
NAV_LABELS = {
    "overview": "Tổng quan", "m1": "1 · Logic", "m2": "2 · Xếp lịch",
    "m3": "3 · DFA", "m4": "4 · Fatigue", "pipeline": "Demo đầu-cuối",
}
HEADLINES = {
    "m1": ("Có thể xếp đủ người không?", "Đổi kịch bản SAT / UNSAT để xem lịch chứng minh hoặc lõi mâu thuẫn."),
    "m2": ("Chọn lịch cân bằng hơn", "Giảm tải đỉnh trước, rồi tối ưu độ lệch L1 và các khoản phạt mềm."),
    "m3": ("Lịch có hợp lệ theo thời gian?", "Đọc từng ngày bằng DFA và chỉ ra trạng thái phát hiện vi phạm."),
    "m4": ("Nhiễu ban đầu có tắt dần?", "Đổi mức nhiễu và quan sát fatigue tiến về điểm cân bằng."),
    "pipeline": ("Từ dữ liệu đến một lịch đã kiểm tra", "Theo dõi bốn bước trên cùng bộ dữ liệu và cùng lịch được chọn."),
}


def stage_navigation() -> str:
    stages = tuple(ROUTES)
    with st.container():
        st.markdown('<span class="iap-nav-marker" hidden></span>', unsafe_allow_html=True)
        section, previous, following = st.columns((6.5, 1, 1))
        route = section.radio("Phần trình chiếu", stages, format_func=NAV_LABELS.__getitem__,
                              key="route", horizontal=True, label_visibility="collapsed")
        if route != "overview":
            position = stages.index(route)
            previous_route = stages[position - 1]
            next_route = stages[(position + 1) % len(stages)]
            previous.button("Phần trước", help=ROUTES[previous_route], key="stage_previous", use_container_width=True,
                            on_click=st.session_state.update, args=({"route": previous_route},))
            following.button("Phần tiếp", help=ROUTES[next_route], key="stage_next", use_container_width=True,
                             type="primary", on_click=st.session_state.update, args=({"route": next_route},))
        return route


@st.cache_data(show_spinner=False)
def cached_preset(seed: int, preset: str, scenario: str):
    return load_preset_instance(preset, seed=seed, m1_scenario=scenario)


@st.cache_data(show_spinner=False)
def cached_full(seed: int, compute_m3: bool, bundle_mtime: int | None):
    # The timestamp invalidates the cache when offline precomputation replaces the bundle.
    return load_full_schedules(seed, compute_m3_live=compute_m3)


def uploaded_dataset(raw: bytes, seed: int):
    if len(raw) > 512 * 1024:
        raise ValueError("The dataset exceeds the byte limit")
    rows = csv.DictReader(StringIO(raw.decode("utf-8-sig"), newline=""))
    if not set(REQUIRED_COLUMNS) <= set(rows.fieldnames or ()):
        raise ValueError("Required dataset columns are missing")
    staff, sessions, dates = set(), set(), set()
    for index, row in enumerate(rows, 1):
        if index > 2_000:
            raise ValueError("Too many CSV records")
        if not any(row.values()):
            continue
        person = (row[STAFF_COLUMN] or "").strip()
        session = (row["MS Ca thi"] or "").strip()
        if any(ord(char) < 32 for char in person + session):
            raise ValueError("An identifier contains a control character")
        staff.add(person)
        sessions.add((session, (row["Nhiệm vụ"] or "").strip().partition("_")[0]))
        dates.add(date.fromisoformat((row["Ngày"] or "").strip()[:10]))
        if len(staff) > 150 or len(sessions) > 150:
            raise ValueError("Too many staff or sessions")
    if not dates or (max(dates) - min(dates)).days >= 120:
        raise ValueError("The dataset has no dates or spans more than 120 days")
    data, inst = load_csv_bytes(raw, seed=seed)
    if len(inst.staff_ids) * len(inst.overlaps) > 15_000:
        raise ValueError("Too many overlap constraints for a live demo")
    return data, inst


def presentation_logic(data: dict) -> dict:
    # M1 serializes core labels with delimiters. Encode user-supplied identifiers first.
    encoded = {
        **data,
        "staff_ids": [quote(person, safe="") for person in data["staff_ids"]],
        "session_ids": [(quote(code, safe=""), quote(campus, safe="")) for code, campus in data["session_ids"]],
    }
    result = run_m1_check(encoded)
    if result["satisfiable"]:
        result["model"] = {
            unquote(session): [unquote(person) for person in people]
            for session, people in result["model"].items()
        }
    return result


def main() -> None:
    st.set_page_config(page_title="CO2011 · Xếp lịch coi thi", layout="wide", initial_sidebar_state="collapsed")
    apply_style()
    try:
        seed = read_team_seed()
    except (OSError, ValueError):
        LOGGER.exception("Could not load the team seed")
        st.error("Không đọc được seed của nhóm. Kiểm tra tệp data/seed.txt rồi tải lại trang.")
        return

    route = stage_navigation()
    # Streamlit retains the scroll position across reruns, even on section changes.
    components.html(
        f"""<script>
        const main = frameElement?.closest("section.main");
        if (main && main.dataset.iapRoute !== "{route}") {{
            main.dataset.iapRoute = "{route}";
            main.scrollTo(0, 0);
        }}
        </script>""",
        height=0,
    )

    if route != "overview":
        title, description = HEADLINES[route]
        hero(ROUTES[route], title, description, compact=True)
    with st.container():
        st.markdown('<span class="iap-controls-marker" hidden></span>', unsafe_allow_html=True)
        source_column, schedule_slot, action_column, settings_column = st.columns((3, 3, 2, 2))
    preset = source_column.selectbox("Nguồn dữ liệu", list(PRESETS), format_func=PRESETS.__getitem__, key="dataset_preset")
    scenario = "sat"
    dataset_file, schedule_file = None, None
    live_m3, enforce, fatigue, seconds = False, False, False, 15
    with settings_column:
        with st.popover("Tùy chọn dữ liệu", use_container_width=True):
            if preset in ("m1_slice", "toy"):
                scenario = st.radio("Kịch bản", ("sat", "unsat"), horizontal=True, key="m1_scenario",
                                    format_func={"sat": "SAT", "unsat": "UNSAT"}.__getitem__)
            if preset == "upload":
                dataset_file = st.file_uploader("Dữ liệu ca thi CSV", type="csv", key="dataset_uploader")
            if preset == "full":
                schedule_file = st.file_uploader("Lịch phân công CSV để kiểm tra", type="csv", key="schedule_uploader")
                live_m3 = st.checkbox("Tính bổ sung lịch DFA nếu thiếu bản tính trước", key="compute_m3_full")
            else:
                enforce = st.checkbox("Bắt buộc thỏa R1, R2, R3", value=preset in ("week1", "week2"), key=f"enforce_{preset}")
                fatigue = st.checkbox("Thêm ngưỡng fatigue mềm", key="include_m4_soft")
                seconds = st.slider("Giới hạn mỗi lần gọi CBC (giây)", 5, 120, 15, key="time_limit")
            st.write(f"**Nhóm:** {TEAM_ID} · **Seed:** `{seed}`")
            result_source = st.empty()

    if dataset_file is not None and dataset_file.size > 512 * 1024:
        st.error("CSV dữ liệu vượt quá 512 KiB. Chọn lát cắt nhỏ hơn.")
        return
    data_id = (seed, preset, scenario, sha256(dataset_file.getbuffer()).digest() if dataset_file is not None else None)
    if st.session_state.get("iap_input") != data_id:
        st.session_state["iap_input"] = data_id
        st.session_state["iap_results"] = {}
        st.session_state.pop("iap_solved", None)
        st.session_state.pop("iap_active", None)
        for exp_key in ("iap_m1_exp", "iap_m2_exp", "iap_m2_ce", "iap_m3_exp_solve"):
            st.session_state.pop(exp_key, None)

    solve_id = (data_id, enforce, fatigue, seconds)
    if st.session_state.get("iap_solver_input") != solve_id:
        st.session_state["iap_solver_input"] = solve_id
        st.session_state.pop("iap_solved", None)

    # Keep each route in its own container block so st.tabs never mounts onto stale column blocks in Streamlit 1.36.
    route_slots = {name: st.container() for name in ROUTES}
    active_slot = route_slots[route]

    if route == "overview":
        with active_slot:
            overview(cached_preset(seed, "full", "sat")[1])
        return

    if preset == "upload":
        if dataset_file is None:
            with active_slot:
                st.info("Mở **Tùy chọn dữ liệu** để tải CSV cùng cấu trúc với `data/input.csv`.")
                if route == "m3":
                    word_lab()
            return
        try:
            logic_data, inst = memo("upload", data_id, lambda: uploaded_dataset(dataset_file.getvalue(), seed))
        except (ValueError, OSError, csv.Error):
            with active_slot:
                st.error("CSV không hợp lệ. Kiểm tra mã hóa UTF-8, tiêu đề và các dòng trùng. "
                         "Demo nhận tối đa 512 KiB, 2.000 dòng, 150 người, 150 ca và 120 ngày.")
                if route == "m3":
                    word_lab()
            return
    else:
        logic_data, inst = cached_preset(seed, preset, scenario)

    if route == "pipeline":
        with active_slot:
            sat_tab, plan_tab, dfa_tab, fatigue_tab = st.tabs(
                ("1 · Khả thi", "2 · Lịch phân công", "3 · Quy tắc DFA", "4 · Fatigue"),
            )

    if route in ("m1", "pipeline"):
        with st.spinner("Đang kiểm tra các ràng buộc cứng…"):
            result = memo("logic", data_id, lambda: presentation_logic(logic_data))
        if route == "pipeline":
            with sat_tab:
                logic_panel(result, compact=True)
        if route == "m1":
            target = "sat" if scenario == "unsat" else "unsat"
            demo_preset = preset if preset in ("m1_slice", "toy") else "toy"
            action_column.button(
                f"Thử {target.upper()}", key="sat_demo", use_container_width=True,
                on_click=st.session_state.update,
                args=({"dataset_preset": demo_preset, "m1_scenario": target},),
            )
            with active_slot:
                logic_panel(result, logic_data=logic_data)
            return

    source_text = "Lịch gốc của bộ dữ liệu; chưa chạy CBC."
    if preset == "full":
        try:
            mtime = DEFAULT_BUNDLE.stat().st_mtime_ns if DEFAULT_BUNDLE.is_file() else None
            with st.spinner("Đang nạp các lịch trên bộ dữ liệu khoa…"):
                inst, schedules, source = cached_full(seed, live_m3, mtime)
        except (OSError, ValueError, RuntimeError, PulpSolverError):
            LOGGER.exception("Could not load the full-dataset schedules")
            with active_slot:
                st.error("Không nạp được lịch toàn bộ. Tạo lại gói tính trước theo app/README.md hoặc chọn lát cắt.")
            return
        source_label = {
            "precomputed bundle (app/m5_bundle.json)": "gói ngoại tuyến đã tính trước",
            "precomputed bundle + live DFA": "gói ngoại tuyến đã tính trước",
            "live repository artifacts": "tệp trong repo hoặc lịch được tính tại chỗ khi thiếu tệp",
        }
        source_text = source_label[source].capitalize() + "."
        if "M2 + R1xR2xR3" not in schedules:
            with active_slot:
                st.info("Chưa có lịch M2 + DFA trong nguồn hiện tại. Tạo gói ngoại tuyến hoặc bật tính bổ sung.")
        if schedule_file is not None:
            if schedule_file.size > 2 * 1024 * 1024:
                with active_slot:
                    st.error("CSV lịch vượt quá 2 MiB. Chọn tệp lịch gọn hơn.")
                return
            try:
                identity = sha256(schedule_file.getbuffer()).digest()
                pairs = memo("schedule_upload", (inst, identity), lambda: parse_uploaded_schedule(inst, schedule_file.getvalue()))
                schedules = {**schedules, "Uploaded Schedule": pairs}
            except (OSError, ValueError, csv.Error):
                with active_slot:
                    st.error("CSV lịch bị từ chối. Cần đủ cặp giám thị–ca, cột invigilator_id, session_id, assigned (0/1) và lịch thỏa H1–H3.")
    else:
        schedules = memo("baseline", data_id, lambda: {"Baseline": frozenset(inst.baseline)}
                         if inst.baseline and not check_schedule(inst, inst.baseline) else {})
        if action_column.button("Giải lịch bằng CBC", type="primary", key="solve", use_container_width=True):
            if preset == "upload" and enforce and len(inst.staff_ids) * ((max(inst.day) - min(inst.day)).days + 1) > 5_000:
                with active_slot:
                    st.warning("Dữ liệu quá lớn để dựng mô hình DFA trực tiếp. Chọn lát cắt nhỏ hơn hoặc bỏ tùy chọn R1–R3.")
                return
            try:
                solved = solve_schedule_in_app(inst, enforce_m3=enforce, include_m4_soft=fatigue, time_limit=seconds)
                st.session_state["iap_solved"] = solved
                if solved["assigned"]:
                    st.session_state["active_schedule"] = "Solved Plan"
            except (OSError, ValueError, RuntimeError, PulpSolverError):
                st.session_state.pop("iap_solved", None)
                LOGGER.exception("CBC live solve failed")
                with active_slot:
                    st.error("Không chạy được CBC hoặc lịch không vượt qua kiểm tra. Thử ví dụ nhỏ và kiểm tra cấu hình CBC.")
        stored = st.session_state.get("iap_solved")
        if stored is not None:
            with active_slot:
                solve_status(stored)
            if stored["assigned"]:
                schedules = {**schedules, "Solved Plan": stored["assigned"]}

    if not schedules:
        schedule_slot.selectbox("Lịch đang phân tích", ["Chưa có lịch"], disabled=True, key="empty_schedule")
        with active_slot:
            if route == "pipeline":
                for tab in (plan_tab, dfa_tab, fatigue_tab):
                    tab.info("Chưa có lịch để phân tích. Chọn dữ liệu khả thi hoặc bấm Giải lịch bằng CBC.")
            else:
                st.info("Chưa có lịch để phân tích.")
            if route == "m3":
                word_lab()
        result_source.write("**Nguồn kết quả:** chưa có lịch.")
        return
    preferred = next(name for name in ("Uploaded Schedule", "M2 + R1xR2xR3", "Solved Plan", *schedules) if name in schedules)
    names = list(schedules)
    default = st.session_state.get("iap_active")
    if default not in schedules:
        default = preferred
    if st.session_state.get("active_schedule") not in schedules:
        st.session_state["active_schedule"] = default
    active = schedule_slot.selectbox("Lịch đang phân tích", names, format_func=schedule_label, key="active_schedule")
    st.session_state["iap_active"] = active

    if route == "pipeline":
        with plan_tab:
            plan_panel(inst, schedules, active, compact=True)
        with dfa_tab:
            temporal_panel(inst, schedules, active, compact=True)
        with fatigue_tab:
            dynamics_panel(inst, schedules, active, compact=True)
        with active_slot:
            with st.expander("Mạch lý thuyết kết nối 4 mô hình trên lịch đang chọn", expanded=False):
                render_pipeline_theory(inst, schedule_label(active))
    elif route == "m2":
        with active_slot:
            plan_panel(inst, schedules, active)
    elif route == "m3":
        with active_slot:
            audit_tab, lab_tab, theory_tab, rules_tab, pump_tab = st.tabs((
                "Kiểm tra lịch",
                "Thử chuỗi ngày",
                "Lý thuyết M3 (Slides)",
                "Thí nghiệm R1–R4",
                "Pumping Lemma",
            ))
            with audit_tab:
                temporal_panel(inst, schedules, active)
            with lab_tab:
                word_lab()
            with theory_tab:
                m3_theory_tab()
            with rules_tab:
                m3_rules_experiment_tab(inst, schedules, active, seconds)
            with pump_tab:
                pumping_lemma_tab()
    elif route == "m4":
        with active_slot:
            dynamics_panel(inst, schedules, active)
    if active == "Uploaded Schedule":
        source_text = "Lịch CSV tải lên đã được kiểm tra H1–H3."
    elif active == "Solved Plan":
        source_text = "Lịch được giải trực tiếp."
    elif preset == "full" and source == "precomputed bundle + live DFA" and active == "M2 + R1xR2xR3":
        source_text = "Lịch DFA được tính bổ sung."
    result_source.write(f"**Nguồn lịch:** {source_text}")


if __name__ == "__main__":
    main()
