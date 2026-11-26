"""Trang 2 · ILP (Hùng): biến thưa, mục tiêu hai giai đoạn, ràng buộc, so với lịch gốc, mô hình sai."""

from __future__ import annotations

import contextlib
import io
from collections import Counter

import streamlit as st
from pulp import PulpSolverError

from app import experiments, services
from app.ui import charts, parts
from app.ui.stage import Idea, Module, render_module
from app.ui.theme import vn
from m2_ilp.metrics import loads


def fig_availability() -> None:
    inst = services.full()[0]
    parts.text("lab", f"Mỗi ô tô màu là một biến x_ij: {vn(len(inst.A), 0)} trên "
                      f"{vn(len(inst.staff_ids) * len(inst.session_names), 0)} cặp")
    charts.cell_chart([{"j": j, "i": i} for i, j in sorted(inst.A)], "j", "i", height=196,
                      x_title=f"{len(inst.session_names)} ca thi", y_title=f"{len(inst.staff_ids)} cán bộ")


def fig_loads() -> None:
    inst, schedules, _ = services.full()
    counts = {name: Counter(loads(inst, schedules[key])) for name, key in (("Lịch gốc", "Baseline"), ("M2 Optimal", "M2 Optimal"))}
    low, high = min(min(c) for c in counts.values()), max(max(c) for c in counts.values())
    rows = [{"Số ca": k, "Số cán bộ": count.get(k, 0), "Lịch": f"{name} · {min(count)} đến {max(count)} ca"}
            for name, count in counts.items() for k in range(low, high + 1)]
    parts.text("lab", "Số cán bộ theo số ca được xếp")
    charts.column_chart(rows, "Số ca", "Số cán bộ", "Lịch", height=168, x_title="số ca mỗi cán bộ được xếp", y_title="")


def fig_constraints() -> None:
    inst = services.full()[0]
    loc, fat, trv = (vn(w) for w in inst.soft_weights)
    parts.cards([
        ("CỨNG · H1", "Khả dụng", "chỉ tạo x_ij cho (i, j) ∈ A", False),
        ("CỨNG · H2", "Không trùng ca", "Σ x_ij ≤ 1 trên mỗi clique ca trùng giờ", False),
        ("CỨNG · H3", "Đủ định ngạch", "Σ_i x_ij = d_j với mọi ca j", False),
        (f"MỀM · LOC · λ = {loc}", "Nguyện vọng cơ sở", "phạt khi xếp trái nguyện vọng", False),
        (f"MỀM · FAT · λ = {fat}", "Quá tải trong ngày", "phạt phần vượt K = 3 ca một ngày", False),
        (f"MỀM · TRV · λ = {trv}", "Di chuyển liên cơ sở", "phạt ngày làm ở cả CS1 và CS2", False),
    ], columns=3)


def fig_compare() -> None:
    table = services.metrics_table()
    base, best = table["Baseline"], table["M2 Optimal"]
    left, right = st.columns(2)
    for column, (title, key, digits) in zip((left, right, left, right), (
            ("Tải đỉnh", "max_load", 0), ("Độ lệch L1", "l1", 2), ("Trái nguyện vọng (LOC)", "location", 0),
            ("Quá tải ngày (FAT)", "fatigue", 0))):
        with column:
            parts.text("lab", title)
            parts.hbars([("Lịch gốc", base[key], vn(base[key], digits)), ("M2 Optimal", best[key], vn(best[key], digits))])


@st.cache_data(show_spinner=False)
def _wrong_models() -> tuple[dict, dict]:
    inst = services.full()[0]
    with contextlib.redirect_stdout(io.StringIO()):
        return experiments.run_m2_counterexample_lp(inst), experiments.run_m2_counterexample_h2(inst)


def fig_wrong() -> None:
    with st.spinner("Đang dựng hai phản ví dụ…"):
        lp, h2 = _wrong_models()
    left, right = st.columns(2)
    with left:
        parts.text("lab", f"Bỏ tính nguyên: LP cho t = {lp['z_lp']}, ILP cần t = {lp['z_ilp']}")
        parts.table(["", "S1", "S2", "S3", "S4"],
                    [(r["staff_id"], r["S1"], r["S2"], r["S3"], r["S4"]) for r in lp["matrix_rows"]],
                    ("mono", "num", "num", "num", "num"))
    with right:
        parts.text("lab", "Bỏ H2: một người coi hai ca cùng giờ")
        booked = h2["double_booked"][0] if h2.get("double_booked") else None
        if booked:
            parts.html(parts.flag(False, f"{booked['staff']}: {booked['session_a']} và {booked['session_b']}"))
        parts.text("cap", h2.get("note", ""))
        parts.text("cap", "check_schedule() từ chối cả hai lịch này.")


def lab() -> None:
    title, presets, rule, run = st.columns((2.4, 3, 1.8, 1.4))
    with title:
        parts.text("h2", "Thử ngay: giải một lát cắt dữ liệu bằng CBC")
    with presets:
        st.session_state.setdefault("m2_slice", "Tuần 1")
        label = st.radio("Lát cắt", list(services.SLICES), key="m2_slice", horizontal=True, label_visibility="collapsed")
    enforce = rule.checkbox("Bắt buộc R1, R2, R3", key="m2_enforce")
    key = (label, enforce)
    pressed = run.button("Giải bằng CBC", type="primary", key="m2_run", use_container_width=True)
    if pressed or st.session_state.get("m2_result", (None,))[0] != key:
        try:
            with st.spinner("CBC đang giải, tối đa 15 giây mỗi giai đoạn…"), contextlib.redirect_stdout(io.StringIO()):
                st.session_state["m2_result"] = (key, services.solve_slice(label, enforce, 15))
        except (OSError, ValueError, RuntimeError, PulpSolverError):
            st.session_state["m2_result"] = (key, None)
    result = st.session_state["m2_result"][1]
    if result is None or not result["assigned"]:
        short = "; ".join(f"ca {d['session']} cần {d['demand']} người, còn thiếu {d['missing']}"
                          for d in (result or {}).get("diagnosis", []))
        st.warning(f"CBC không trả về lịch hợp lệ ({result['status'] if result else 'lỗi solver'})"
                   + (f": {short}." if short else ". Thử lát cắt nhỏ hơn hoặc bỏ R1, R2, R3."))
        return
    table, status = st.columns((1.8, 1))
    with table:
        parts.table(["Ca thi", "Cơ sở", "Định ngạch", "Cán bộ được xếp"],
                    [(f"{r['date'][8:]}/{r['date'][5:7]} · {r['time'][:5]}", r["campus"], r["demand"], r["invigilators"])
                     for r in result["rows"][:6]], ("", "", "num", "mono"))
        if len(result["rows"]) > 6:
            parts.text("cap", f"Hiện 6 trên {len(result['rows'])} ca của lát cắt này.")
    with status:
        m, b = result["metrics"], result["baseline_metrics"]
        parts.kpis([("Tải đỉnh", str(m["max_load"]), f"lịch gốc {b['max_load']}"),
                    ("Cán bộ tham gia", str(m["staff_used"]), f"lịch gốc {b['staff_used']}"),
                    ("L1", vn(m["l1"]), f"lịch gốc {vn(b['l1'])}")])
        valid, (accepted, staff_count) = not result["hard_violations"], result["dfa"]
        parts.flags([(valid, "0 vi phạm H1, H2, H3" if valid else f"{len(result['hard_violations'])} vi phạm luật cứng"),
                     (accepted == staff_count, f"DFA chấp nhận {accepted}/{staff_count} chuỗi")])
        staff, sessions, pairs = result["size"]
        parts.text("cap", f"{result['status']} · {vn(result['runtime_s'])} giây · {staff} cán bộ · {sessions} ca · {pairs} biến x_ij")


MODULE = Module(
    key="m2", label="Module 2 · ILP", presenter="Hùng", start=1, lab=lab,
    fn=("build_model()", "solve()", "check_schedule()"), ds=("Branch and bound (CBC)", "Maximal cliques"),
    bigo=("x_ij · Space: O(|A|)", "B&B · Time: O(2^|A|) xấu nhất"), note="|A|: số cặp cán bộ–ca khả dụng",
    ideas=(
        Idea("Biến và tập khả dụng", "Chỉ tạo biến cho ", "cặp khả dụng", ".",
             "x_ij nhận 0 hoặc 1 với mỗi cặp (i, j) trong A; w_i là tổng các x_ij của cán bộ i",
             (("x_ij nhị phân", "x_ij = 1 nghĩa là cán bộ i coi ca j."),
              ("Tập khả dụng A", "Giữ lịch gốc, mở thêm 30% cặp chưa quan sát, theo seed."),
              ("Ít biến hơn", "2.593 biến thay vì 6.059, giảm 57%.")), fig_availability),
        Idea("Mục tiêu hai giai đoạn", "Tải đỉnh giảm từ 19 xuống ", "11 ca", ".",
             "Giai đoạn 1: min t. Giai đoạn 2: giữ t ở 11, min L1 + phạt mềm.",
             (("Giai đoạn 1: min t", "t* = 11, so với 19 của lịch gốc."),
              ("Giai đoạn 2: L1 và phạt mềm", "L1 từ 115,40 xuống 36,33. Trái nguyện vọng từ 162 xuống 28."),
              ("Vẫn là ILP", "Min-max và L1 đều tuyến tính, không cần MIQP.")), fig_loads),
        Idea("Ràng buộc cứng và mềm", "Cứng thì ", "không được vi phạm", ". Mềm thì bị phạt.",
             "H1, H2, H3 là ràng buộc; LOC, FAT, TRV vào hàm mục tiêu với trọng số từ seed",
             (("H2 theo clique", "Mỗi người một dòng cho mỗi nhóm ca trùng giờ."),
              ("FAT với K = 3", "K khớp từ lịch gốc: 95% ngày làm việc không quá 3 ca."),
              ("Trọng số từ seed", "Mỗi nhóm một bộ λ riêng, tái lập được.")), fig_constraints),
        Idea("So với lịch gốc", "Cùng 769 lượt, độ trải tải từ 16 còn ", "1 ca", ".",
             "Lịch gốc và M2 Optimal trên cùng dữ liệu, cùng bộ kiểm tra H1, H2, H3",
             (("Tải đỉnh", "19 xuống 11 ca."), ("Độ lệch L1", "115,40 xuống 36,33."),
              ("Phạt mềm", "LOC 162 xuống 28, FAT 7 xuống 0.")), fig_compare),
        Idea("Mô hình sai", "Bỏ tính nguyên, LP xếp ", "1/3 cán bộ", ".",
             "Yêu cầu 2.10: hai mô hình trông hợp lý nhưng sai, kèm phản ví dụ",
             (("Bỏ H2", "Solver xếp một người vào hai ca trùng giờ."),
              ("Bỏ tính nguyên", "LP cho t = 4/3; ILP cần t = 2."),
              ("Bộ kiểm tra độc lập", "check_schedule() bắt được cả hai.")), fig_wrong),
    ),
)


def render() -> None:
    render_module(MODULE)
