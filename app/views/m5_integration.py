"""Trang 5 · Tích hợp (Thành): kết luận của bốn mô hình trên cùng một lịch."""

from __future__ import annotations

import csv

import numpy as np
import streamlit as st

from app import services
from app.ui import charts, parts
from app.ui.stage import presenter_chip
from app.ui.theme import vn

FULL, UPLOAD = "Dữ liệu khoa", "Tải CSV lên"


def _tile_m1(result: dict) -> None:
    with st.container():
        parts.marker("tile")
        parts.text("eyebrow", "M1 · Có xếp đủ người không?")
        size = f"{vn(result['n_assign_vars'], 0)} biến · {vn(result['n_clauses'], 0)} mệnh đề"
        if result["satisfiable"]:
            parts.verdict("good", "SAT", f"Có lịch thỏa cả H1, H2, H3 · {size}")
        else:
            parts.verdict("bad", "UNSAT", f"Lõi mâu thuẫn gồm {len(result['unsat_core'])} ràng buộc · {size}")


def _tile_m2(rows: list[dict], metric: dict, base: dict | None, week: int) -> None:
    with st.container():
        parts.marker("tile")
        parts.text("eyebrow", f"M2 · Lịch phân công tuần {week}")
        note = (lambda key, digits: f"lịch gốc {vn(base[key], digits)}") if base else (lambda key, digits: "")
        parts.kpis([("Tải đỉnh", str(metric["max_load"]), note("max_load", 0)), ("L1", vn(metric["l1"]), note("l1", 2)),
                    ("Lệch cơ sở", str(metric["location"]), note("location", 0))])
        parts.table(["Ca thi", "Cơ sở", "Cần", "Giám thị được xếp"],
                    [(f"{r['date'][8:]}/{r['date'][5:7]} · {r['time'][:5]}", r["campus"], r["demand"], r["invigilators"])
                     for r in rows[:5]], ("", "", "num", "mono"))
        if len(rows) > 5:
            parts.text("cap", f"Hiện 5 trên {len(rows)} ca của tuần này.")


def _tile_m3(temporal: dict) -> None:
    with st.container():
        parts.marker("tile")
        parts.text("eyebrow", "M3 · Lịch có hợp lệ theo thời gian không?")
        flag, bars = st.columns((1.2, 1))
        counts = temporal["rule_violations"]
        accepted = f"DFA chấp nhận {temporal['accepted_count']}/{temporal['total_staff']} chuỗi"
        with flag:
            if temporal["schedule_valid"]:
                parts.verdict("good", "Lịch hợp lệ", accepted)
            else:
                parts.verdict("bad", "Lịch chưa hợp lệ", accepted)
        with bars:
            parts.hbars([(rule, counts[rule], str(counts[rule])) for rule in ("R1", "R2", "R3")], width=90)
            parts.text("cap", "số chuỗi vi phạm theo từng luật")


def _tile_m4(dyn: dict, schedule: str) -> None:
    with st.container():
        parts.marker("tile")
        parts.text("eyebrow", "M4 · Về lâu dài có công bằng không?")
        left, right = st.columns(2)
        with left:
            parts.text("lab", "Phương sai fatigue theo tuần")
            charts.line_chart([{"Tuần": n, "Phương sai": round(float(np.var(state)), 4)}
                               for n, state in enumerate(dyn["trajectories"][schedule][:9])],
                              "Tuần", "Phương sai", height=132, x_title="tuần", y_title="")
        with right:
            parts.text("lab", "Fatigue đỉnh theo khối tuần")
            charts.line_chart([{"Khối": k, "Fatigue đỉnh": round(float(state.max()), 4)}
                               for k, state in enumerate(dyn["histories"][schedule])],
                              "Khối", "Fatigue đỉnh", height=132, x_title="khối tuần", y_title="",
                              rules=[(dyn["threshold"], f"H = {vn(dyn['threshold'])}")])
        summary = next(row for row in dyn["summary_rows"] if row["scenario"] == schedule)
        stable = dyn["stability"]["classification"] == "asymptotically stable"
        parts.html(parts.flag(stable, f"|a| = {vn(dyn['stability']['spectral_radius'])}, "
                                      + ("ổn định" if stable else "không ổn định"))
                   + f' <span class="iap-cap">Độ lệch cân bằng {vn(summary["equilibrium_spread"])} · '
                     f'tổng vượt ngưỡng H {vn(summary["observed_threshold_excess"])}</span>')


def render() -> None:
    left, right = st.columns((6, 1.6))
    with left:
        parts.text("eyebrow", "Module 5 · Tích hợp")
    with right:
        presenter_chip("Thành")
    parts.headline("Kết luận của ", "4 mô hình", "",
                   "Chọn dữ liệu, tuần và lịch. Mỗi ô là câu trả lời của một module trên đúng lịch đó.")
    with st.container():
        parts.marker("dock")
        data, week_box, pick, run = st.columns((1.5, 1.2, 4.2, 1.2))
        source = data.selectbox("Dữ liệu", (FULL, UPLOAD), key="m5_data")
        if run.button("Chạy tất cả", type="primary", key="m5_run", use_container_width=True):
            st.cache_data.clear()  # drop every cached answer so all four models run again below
            services.dynamics.clear()
        if source == UPLOAD:
            file = pick.file_uploader("CSV cùng cột với data/input.csv (tối đa 512 KiB)", type="csv", key="m5_file")
            if file is None:
                st.info("Chọn một tệp CSV để kiểm tra lịch gốc của tệp đó bằng cả bốn mô hình.")
                return
            try:
                with st.spinner("Đang kiểm tra dữ liệu tải lên…"):
                    up = services.uploaded(file.getvalue())
            except (ValueError, OSError, csv.Error, UnicodeDecodeError):
                st.error("CSV không hợp lệ. Cần mã hóa UTF-8, đủ cột như data/input.csv, không trùng dòng, tối đa 512 KiB.")
                return
            m1, rows, metric, base = up["m1"], up["rows"], up["metrics"], None
            temporal, dyn, schedule, week = up["temporal"], up["dynamics"], "Baseline", 1
        else:
            inst, _, origin = services.full()
            weeks = (max(inst.day) - min(inst.day)).days // 7 + 1
            week = week_box.selectbox("Tuần", range(1, weeks + 1), key="m5_week", format_func=lambda k: f"Tuần {k}")
            labels = services.schedule_labels()
            if st.session_state.get("m5_schedule") not in labels:
                st.session_state["m5_schedule"] = "M2 + DFA" if "M2 + DFA" in labels else next(iter(labels))
            schedule = labels[pick.radio("Lịch", list(labels), key="m5_schedule", horizontal=True)]
            with st.spinner("Đang chạy bốn mô hình trên lịch đã chọn…"):
                m1 = services.m1_full()
                rows, table = services.week_rows(schedule, week), services.metrics_table()
                metric, base = table[schedule], table["Baseline"]
                temporal, dyn = services.temporal(schedule), services.dynamics()
            parts.text("cap", f"Lịch lấy từ {services.SOURCE.get(origin, origin)}. SAT, DFA và fatigue được tính trực tiếp trên lịch đã chọn.")
        first, second = st.columns((1.25, 1))
        with first:
            _tile_m1(m1)
            _tile_m2(rows, metric, base, week)
        with second:
            _tile_m3(temporal)
            _tile_m4(dyn, schedule)
    parts.callout(("solve_instance()", "solve()", "DFA.accepts()", "simulate()", "check_schedule()"),
                  ("Caching", "Precomputed bundle"), ("check_schedule · Time: O(n·|O| + P)",),
                  "n: số giám thị · |O|: số cặp ca trùng giờ · P: số lượt phân công")
