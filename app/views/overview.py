"""Trang 0 · Tổng quan: bài toán, bốn câu hỏi, dữ liệu đang dùng."""

from __future__ import annotations

from datetime import timedelta

import streamlit as st

from app import services
from app.ui import charts, parts
from app.ui.theme import vn
from m2_ilp.config import TEAM_ID


def render() -> None:
    inst, _, source = services.full()
    metrics, temporal, dyn = services.metrics_table(), services.temporal_table(), services.dynamics()
    spread = {row["scenario"]: row["equilibrium_spread"] for row in dyn["summary_rows"]}
    total, first, last = sum(inst.demand), min(inst.day), max(inst.day)
    span = (last - first).days + 1
    left, right = st.columns((3, 1))
    with left:
        parts.text("eyebrow", "CO2011 · Mô hình hóa toán học")
    with right:
        parts.html(f'<div class="iap-chip" style="padding:0 14px"><span class="iap-mono">{TEAM_ID}</span></div>')
    parts.headline(f"Từ {total} dòng dữ liệu đến một lịch coi thi ", "công bằng", ".",
                   "Invigilator Assignment Problem · một bài toán thật, bốn mô hình, một web app.")
    clauses = services.bundle_m1().get("full_clauses")
    best = "M2 + R1xR2xR3" if "M2 + R1xR2xR3" in temporal else "Baseline"  # the DFA-linked schedule only ships in the bundle
    parts.cards([
        ("MODULE 1 · LOGIC · VINH", "Có xếp đủ người không?",
         f"SAT · {vn(clauses, 0)} mệnh đề" if clauses else "CNF, Minisat22, lõi UNSAT", False),
        ("MODULE 2 · ILP · HÙNG", "Lịch nào công bằng nhất?",
         f"Tải đỉnh {metrics['Baseline']['max_load']} còn {metrics['M2 Optimal']['max_load']}", False),
        ("MODULE 3 · AUTOMATA · PHÚC", "Lịch có hợp lệ theo thời gian không?",
         f"{temporal[best]['dfa_accepted']} chuỗi được chấp nhận" + (" (lịch gốc)" if best == "Baseline" else ""), False),
        ("MODULE 4 · DYNAMICS · NGUYÊN", "Về lâu dài có công bằng không?",
         f"Độ lệch {vn(spread['Baseline'])} còn {vn(spread['M2 Optimal'])}", False),
        ("MODULE 5 · TÍCH HỢP · THÀNH", "Kết luận của 4 mô hình", "Một trang: SAT, lịch, cờ DFA, fatigue", True),
    ], tall=True)
    with st.container():
        parts.marker("dock")
        numbers, chart = st.columns((1, 1.6))
        with numbers:
            parts.text("h2", "Dữ liệu đang dùng")
            parts.kpis([("giám thị", str(len(inst.staff_ids)), ""), ("ca thi", str(len(inst.session_names)), ""),
                        ("lượt phân công", str(total), ""), ("ngày", str(span), "")])
            weights = " · ".join(f"{name} {vn(value)}" for name, value in zip(("LOC", "FAT", "TRV"), inst.soft_weights))
            parts.text("cap", f"CS1: {inst.campus.count('CS1')} ca · CS2: {inst.campus.count('CS2')} ca · "
                              f"Trọng số mềm: {weights}")
            parts.text("cap", f"{first:%d/%m} – {last:%d/%m/%Y} · {len(inst.sessions_by_day)} ngày có thi · "
                              f"seed {inst.seed} · nguồn lịch: {services.SOURCE.get(source, source)}")
            sample = sorted(inst.baseline, key=lambda pair: (inst.intervals[pair[1]][0], pair[0]))[:4]
            parts.table(["Cán bộ", "Ngày", "Giờ", "Cơ sở"],
                        [(inst.staff_ids[i], f"{inst.intervals[j][0]:%d/%m/%Y}",
                          f"{inst.intervals[j][0]:%H:%M}–{inst.intervals[j][1]:%H:%M}", inst.campus[j]) for i, j in sample],
                        ("mono",))
            parts.text("cap", f"4 trên {total} dòng: mỗi dòng là một lượt coi thi của lịch gốc.")
        with chart:
            need = {day: sum(inst.demand[j] for j in sessions) for day, sessions in inst.sessions_by_day.items()}
            rows = [{"Ngày": f"{first + timedelta(days=k):%d/%m}", "Lượt": need.get(first + timedelta(days=k), 0)}
                    for k in range(span)]
            peak = max(need, key=need.get)
            parts.text("lab", f"Số lượt coi thi cần mỗi ngày · cao nhất {need[peak]} lượt, ngày {peak:%d/%m}")
            labels = [row["Ngày"] for row in rows]
            charts.column_chart(rows, "Ngày", "Lượt", height=272, x_title="", y_title="", sort=labels, ticks=labels[::3])
    _, go = st.columns((6, 1.4))
    go.button("Bắt đầu với Module 1", type="primary", use_container_width=True,
              on_click=st.session_state.update, args=({"route": "m1"},))
