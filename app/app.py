"""Streamlit entry point for the CO2011 Module 5 presentation."""

from __future__ import annotations

import csv
import logging
import sys
from datetime import date
from hashlib import sha256
from io import StringIO
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
# Streamlit prepends app/; the package must win over the sibling app.py.
if sys.path[0] != str(ROOT_DIR):
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
from pulp import PulpSolverError

from app.data_views import load_csv_bytes, load_preset_instance, parse_uploaded_schedule, read_team_seed
from app.precompute import DEFAULT_BUNDLE, load_full_schedules
from app.presentation import PRESETS, apply_style, hero, memo, schedule_label, technical
from app.presentation_views import (
    TECHNICAL,
    dynamics_panel,
    logic_panel,
    overview,
    plan_panel,
    solve_status,
    temporal_panel,
    word_lab,
)
from app.solver_views import run_m1_check, solve_schedule_in_app
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
HEADLINES = {
    "m1": ("Có thể xếp đủ người không?", "Đổi kịch bản SAT / UNSAT để xem lịch chứng minh hoặc lõi mâu thuẫn."),
    "m2": ("Chọn lịch cân bằng hơn", "Giảm tải đỉnh trước, rồi tối ưu độ lệch L1 và các khoản phạt mềm."),
    "m3": ("Lịch có hợp lệ theo thời gian?", "Đọc từng ngày bằng DFA và chỉ ra trạng thái phát hiện vi phạm."),
    "m4": ("Nhiễu ban đầu có tắt dần?", "Đổi mức nhiễu và quan sát fatigue tiến về điểm cân bằng."),
    "pipeline": ("Từ dữ liệu đến một lịch đã kiểm tra", "Theo dõi bốn bước trên cùng bộ dữ liệu và cùng lịch được chọn."),
}


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


def main() -> None:
    st.set_page_config(page_title="CO2011 · Xếp lịch coi thi", layout="wide")
    apply_style()
    try:
        seed = read_team_seed()
    except (OSError, ValueError):
        LOGGER.exception("Could not load the team seed")
        st.error("Không đọc được seed của nhóm. Kiểm tra tệp data/seed.txt rồi tải lại trang.")
        return

    with st.sidebar:
        st.markdown("## Bảng điều phối")
        st.caption(f"CO2011 · {TEAM_ID} · Seed `{seed}`")
        route = st.radio("Chọn màn hình trình chiếu", list(ROUTES), format_func=ROUTES.__getitem__, key="route")
        st.divider()
        preset = st.selectbox("Nguồn dữ liệu", list(PRESETS), format_func=PRESETS.__getitem__, key="dataset_preset")
        scenario = "sat"
        if preset in ("m1_slice", "toy"):
            scenario = st.radio("Kịch bản khả dụng", ("sat", "unsat"), horizontal=True, key="m1_scenario",
                                format_func={"sat": "SAT · đủ người", "unsat": "UNSAT · thiếu người"}.__getitem__)
        dataset_file = st.file_uploader("Dữ liệu ca thi CSV", type="csv", key="dataset_uploader") if preset == "upload" else None
        schedule_file = st.file_uploader("Lịch phân công CSV để kiểm tra", type="csv", key="schedule_uploader") if preset == "full" else None
        live_m3 = (st.checkbox("Tính bổ sung lịch DFA nếu thiếu bản tính trước", key="compute_m3_full")
                   if preset == "full" else False)
        enforce, fatigue, seconds = False, False, 15
        if preset != "full":
            with st.expander("Tùy chọn CBC"):
                enforce = st.checkbox("Bắt buộc thỏa R1, R2, R3", value=preset in ("week1", "week2"), key=f"enforce_{preset}")
                fatigue = st.checkbox("Thêm ngưỡng fatigue mềm", key="include_m4_soft")
                seconds = st.slider("Giới hạn mỗi lần gọi CBC (giây)", 5, 120, 15, key="time_limit")

    if dataset_file is not None and dataset_file.size > 512 * 1024:
        st.error("CSV dữ liệu vượt quá 512 KiB. Chọn lát cắt nhỏ hơn.")
        return
    data_id = (seed, preset, scenario, sha256(dataset_file.getbuffer()).digest() if dataset_file is not None else None)
    if st.session_state.get("iap_input") != data_id:
        st.session_state["iap_input"] = data_id
        st.session_state["iap_results"] = {}
        st.session_state.pop("iap_solved", None)
        st.session_state.pop("iap_active", None)

    solve_id = (data_id, enforce, fatigue, seconds)
    if st.session_state.get("iap_solver_input") != solve_id:
        st.session_state["iap_solver_input"] = solve_id
        st.session_state.pop("iap_solved", None)

    if route == "overview":
        overview(cached_preset(seed, "full", "sat")[1])
        return

    title, description = HEADLINES[route]
    hero(ROUTES[route], title, description)
    if route in TECHNICAL:
        technical(*TECHNICAL[route])
    if route == "m3":
        word_lab()

    if preset == "upload":
        if dataset_file is None:
            st.info("Tải CSV ở thanh bên. Dùng cùng cấu trúc với data/input.csv.")
            return
        try:
            logic_data, inst = memo("upload", data_id, lambda: uploaded_dataset(dataset_file.getvalue(), seed))
        except (ValueError, OSError, csv.Error):
            st.error("CSV không hợp lệ. Kiểm tra mã hóa UTF-8, tiêu đề và các dòng trùng. "
                     "Demo nhận tối đa 512 KiB, 2.000 dòng, 150 người, 150 ca và 120 ngày.")
            return
    else:
        logic_data, inst = cached_preset(seed, preset, scenario)
    st.caption(f"{PRESETS[preset]} · {len(inst.staff_ids)} giám thị · {len(inst.session_names)} ca · {sum(inst.demand)} lượt cần xếp")

    if route in ("m1", "pipeline"):
        if route == "pipeline":
            st.header("1. Kiểm tra SAT")
        with st.spinner("Đang kiểm tra các ràng buộc cứng…"):
            result = memo("logic", data_id, lambda: run_m1_check(logic_data))
        logic_panel(result, compact=route == "pipeline")
        if route == "m1":
            return

    if route == "pipeline":
        st.header("2. Lịch phân công ILP")
    if preset == "full":
        try:
            mtime = DEFAULT_BUNDLE.stat().st_mtime_ns if DEFAULT_BUNDLE.is_file() else None
            with st.spinner("Đang nạp các lịch trên bộ dữ liệu khoa…"):
                inst, schedules, source = cached_full(seed, live_m3, mtime)
        except (OSError, ValueError, RuntimeError, PulpSolverError):
            LOGGER.exception("Could not load the full-dataset schedules")
            st.error("Không nạp được lịch toàn bộ. Tạo lại gói tính trước theo app/README.md hoặc chọn lát cắt.")
            return
        source_label = {
            "precomputed bundle (app/m5_bundle.json)": "gói ngoại tuyến đã tính trước",
            "precomputed bundle + live DFA": "gói ngoại tuyến và lịch DFA vừa tính",
            "live repository artifacts": "tệp trong repo hoặc lịch được tính tại chỗ khi thiếu tệp",
        }
        st.caption(f"Nguồn lịch: {source_label[source]}.")
        if "M2 + R1xR2xR3" not in schedules:
            st.info("Chưa có lịch M2 + DFA trong nguồn hiện tại. Tạo gói ngoại tuyến hoặc bật tính bổ sung.")
        if schedule_file is not None:
            if schedule_file.size > 2 * 1024 * 1024:
                st.error("CSV lịch vượt quá 2 MiB. Chọn tệp lịch gọn hơn.")
                return
            try:
                identity = sha256(schedule_file.getbuffer()).digest()
                pairs = memo("schedule_upload", (inst, identity), lambda: parse_uploaded_schedule(inst, schedule_file.getvalue()))
                schedules = {**schedules, "Uploaded Schedule": pairs}
            except (OSError, ValueError, csv.Error):
                st.error("CSV lịch bị từ chối. Cần đủ cặp giám thị–ca, cột invigilator_id, session_id, assigned (0/1) và lịch thỏa H1–H3.")
    else:
        schedules = memo("baseline", data_id, lambda: {"Baseline": frozenset(inst.baseline)}
                         if inst.baseline and not check_schedule(inst, inst.baseline) else {})
        if st.button("Giải lịch bằng CBC", type="primary", key="solve"):
            if preset == "upload" and enforce and len(inst.staff_ids) * ((max(inst.day) - min(inst.day)).days + 1) > 5_000:
                st.warning("Dữ liệu quá lớn để dựng mô hình DFA trực tiếp. Chọn lát cắt nhỏ hơn hoặc bỏ tùy chọn R1–R3.")
                return
            try:
                with st.spinner("Đang chạy CBC và kiểm tra lịch trả về…"):
                    solved = solve_schedule_in_app(inst, enforce_m3=enforce, include_m4_soft=fatigue, time_limit=seconds)
                st.session_state["iap_solved"] = solved
            except (OSError, ValueError, RuntimeError, PulpSolverError):
                st.session_state.pop("iap_solved", None)
                LOGGER.exception("CBC live solve failed")
                st.error("Không chạy được CBC hoặc lịch không vượt qua kiểm tra. Thử ví dụ nhỏ và kiểm tra cấu hình CBC.")
        stored = st.session_state.get("iap_solved")
        if stored is not None:
            solve_status(stored)
            if stored["assigned"]:
                schedules = {**schedules, "Solved Plan": stored["assigned"]}

    if not schedules:
        st.info("Chưa có lịch để kiểm tra theo DFA hoặc mô phỏng fatigue.")
        return
    preferred = next(name for name in ("Uploaded Schedule", "M2 + R1xR2xR3", "Solved Plan", *schedules) if name in schedules)
    names = list(schedules)
    default = st.session_state.get("iap_active")
    if default not in schedules:
        default = preferred
    if st.session_state.get("active_schedule") not in schedules:
        st.session_state["active_schedule"] = default
    active = st.selectbox("Lịch đang phân tích", names, format_func=schedule_label, key="active_schedule")
    st.session_state["iap_active"] = active

    if route in ("m2", "pipeline"):
        plan_panel(inst, schedules, active, compact=route == "pipeline")
    if route in ("m3", "pipeline"):
        st.header("3. Kiểm tra lịch bằng DFA" if route == "pipeline" else "Kiểm tra chuỗi ngày của lịch đã chọn")
        temporal_panel(inst, schedules, active, compact=route == "pipeline")
    if route in ("m4", "pipeline"):
        if route == "pipeline":
            st.header("4. Mô phỏng fatigue và công bằng")
        dynamics_panel(inst, schedules, active, compact=route == "pipeline")


if __name__ == "__main__":
    main()
