"""Trang 4 · Dynamics (Nguyên): hệ truy hồi fatigue, khớp tham số, ổn định, công bằng, ngưỡng mềm."""

from __future__ import annotations

import numpy as np
import streamlit as st

from app import services
from app.ui import charts, parts
from app.ui.stage import Idea, Module, render_module
from app.ui.theme import vn

REGIMES = {"Ổn định · a = 0,27": 0.27, "Trung hòa · a = 1": 1.0, "Phân kỳ · a = 1,05": 1.05}
VERDICT = {"asymptotically stable": ("good", "Ổn định tiệm cận", "Nhiễu tắt dần, quỹ đạo quay về F*."),
           "neutral": ("warn", "Trung hòa", "Nhiễu giữ nguyên, không quay về."),
           "unstable": ("bad", "Phân kỳ", "Nhiễu lớn dần theo từng tuần.")}
NAMES = (("Lịch gốc", "Baseline"), ("M2 Optimal", "M2 Optimal"), ("Tải đều", "Equal-load reference"))


def fig_recurrence() -> None:
    value, rows = 0.0, []
    for n in range(13):
        rows.append({"Tuần": n, "F": round(value, 4)})
        value = 0.8 * value + 2
    parts.text("lab", "Ví dụ của đề: F[n+1] = 0,8·F[n] + 2, F[0] = 0")
    charts.line_chart(rows, "Tuần", "F", height=160, x_title="tuần n", y_title="", rules=[(10, "F* = 2 / (1 − 0,8) = 10")])


def fig_calibration() -> None:
    cal, params = services.dynamics()["calibration"], services.dynamics()["parameters"]
    parts.text("lab", f"Tải tuần sau theo tải tuần trước · {cal['observations']} cặp · hệ số góc a = {vn(params['a'], 4)}")
    rows = [{"Tải tuần này": pair["x"], "Tải tuần sau": round(pair["y"], 4)} for pair in services.lag_pairs()]
    charts.scatter_chart(rows, "Tải tuần này", "Tải tuần sau", height=160, x_title="tải tuần này", y_title="tải tuần sau",
                         line=(cal["workload_intercept"], params["a"]))


def fig_regimes() -> None:
    rows = [{"Tuần": n, "Nhiễu": round(a ** n, 4), "a": label.split(" · ")[1]} for label, a in REGIMES.items() for n in range(11)]
    parts.text("lab", "Nhiễu còn lại sau n tuần (mức ban đầu = 1)")
    charts.line_chart(rows, "Tuần", "Nhiễu", "a", height=160, x_title="tuần n", y_title="")


def fig_fairness() -> None:
    trajectories = services.dynamics()["trajectories"]
    rows = [{"Tuần": n, "Độ lệch": round(float(np.ptp(state)), 4), "Lịch": f"{label} · còn {vn(float(np.ptp(trajectories[key][8])))}"}
            for label, key in NAMES for n, state in enumerate(trajectories[key][:9])]
    parts.text("lab", "Độ lệch fatigue (max − min) giữa 73 giám thị")
    charts.line_chart(rows, "Tuần", "Độ lệch", "Lịch", height=160, x_title="tuần, với tải tuần không đổi", y_title="")


def fig_threshold() -> None:
    dyn = services.dynamics()
    rows = [{"Khối": k, "Fatigue đỉnh": round(float(state.max()), 4),
             "Lịch": f"{label} · cuối kỳ {vn(float(dyn['histories'][key][-1].max()))}"}
            for label, key in (("Lịch gốc", "Baseline"), ("M2 Optimal", "M2 Optimal"), ("M4 fatigue-aware", "M4 Fatigue-Aware"))
            for k, state in enumerate(dyn["histories"][key])]
    parts.text("lab", "Fatigue đỉnh cuối mỗi khối tuần")
    charts.line_chart(rows, "Khối", "Fatigue đỉnh", "Lịch", height=160, x_title="khối tuần", y_title="",
                      rules=[(dyn["threshold"], f"H = {vn(dyn['threshold'])}")])


def _use(a: float) -> None:
    st.session_state["m4_a"] = a


def lab() -> None:
    title, presets = st.columns((3, 5))
    with title:
        parts.text("h2", "Thử ngay: đổi a và xem nhiễu tắt hay lớn lên")
    st.session_state.setdefault("m4_a", 0.27)
    with presets:
        for column, (label, a) in zip(st.columns(len(REGIMES)), REGIMES.items()):
            column.button(label, key=f"m4_preset_{a}", on_click=_use, args=(a,), use_container_width=True)
    control, chart, status = st.columns((1, 1.5, 1.2))
    with control:
        a = st.slider("Hệ số giữ lại a", 0.0, 1.2, key="m4_a", step=0.01)
        parts.kpis([("", f"a = {vn(a)}", "a = 1 là ranh giới ổn định")])
        parts.text("mono", "F[n] − F* = aⁿ · (F[0] − F*)")
    with chart:
        charts.line_chart([{"Tuần": n, "Nhiễu": round(a ** n, 4)} for n in range(11)], "Tuần", "Nhiễu", height=128,
                          x_title="tuần n", y_title="nhiễu còn lại")
    with status:
        label, equilibrium = services.regime(a)
        parts.verdict(*VERDICT[label])
        parts.kpis([("Sau 4 tuần, nhiễu còn", f"{vn(a ** 4 * 100, 1)}%", ""),
                    ("Điểm cân bằng F*", vn(equilibrium) if equilibrium is not None else "không hút", "")])


MODULE = Module(
    key="m4", label="Module 4 · Dynamics", presenter="Nguyên", start=3, lab=lab,
    fn=("calibrate()", "fixed_point()", "simulate()", "stability()"), ds=("Linear recurrence", "Pooled lag-one OLS"),
    bigo=("simulate · Time: O(n·W)", "Space: O(n·W)"), note="n: số giám thị · W: số tuần mô phỏng",
    ideas=(
        Idea("Fatigue là hệ truy hồi", "Fatigue tuần sau tính từ ", "tuần này", ".",
             "F[n+1] = a·F[n] + b·ℓ − r·ρ · hướng B: cả nhóm là một vector, mỗi giám thị một thành phần",
             (("a · phần giữ lại", "Tỷ lệ fatigue còn lại sau một tuần."),
              ("b · phần cộng thêm", "Tải tuần ℓ càng cao, fatigue cộng thêm càng nhiều."),
              ("Vì sao không dùng tổng tải", "Tổng tải cộng dồn có trị riêng 1, không có điểm cân bằng.")), fig_recurrence),
        Idea("Khớp tham số", "Tham số được ", "khớp từ dữ liệu", ", không tự đặt.",
             "OLS độ trễ 1 trên tải tuần của 73 giám thị qua 4 khối tuần",
             (("a = 0,2706", "Hệ số góc của hồi quy tải tuần sau theo tải tuần trước."),
              ("b = 1 − a = 0,7294", "Chọn để điểm cân bằng trung bình bằng tải tuần trung bình 2,73."),
              ("r = 0, và khớp yếu", "Dữ liệu không đo được phần hồi phục. R² = 0,06.")), fig_calibration),
        Idea("Cân bằng và ổn định", "Mọi quỹ đạo tiến về ", "điểm cân bằng F*", ".",
             "F* = b·ℓ / (1 − a) · Jacobian là a·I nên mọi trị riêng bằng a",
             (("|a| < 1: ổn định", "Khoảng cách tới F* nhân với a sau mỗi tuần."),
              ("|a| = 1: trung hòa", "Nhiễu không tắt, cũng không lớn lên."),
              ("|a| > 1: phân kỳ", "Đã kiểm chứng bằng số tại a = 1,05.")), fig_regimes),
        Idea("Công bằng là điểm hút", "Tải đều thì độ lệch fatigue tự ", "co về 0", ".",
             "Khi mọi người cùng tải: spread(F[n]) = |a|ⁿ · spread(F[0]), với a = 0,2706",
             (("Điểm cân bằng theo tải", "Ai có tải tuần cao hơn thì F* cao hơn."),
              ("Ổn định vì |a| < 1", "Mỗi tuần nhiễu chỉ còn 27%."),
              ("Lệch ít là công bằng", "Lịch gốc lệch 4,15. M2 còn 0,26. Tải đều về 0.")), fig_fairness),
        Idea("Ngưỡng mềm trong ILP", "Thêm ngưỡng H, phần vượt ngưỡng về ", "0", ".",
             "H = 5,66 là phân vị 95% của fatigue lịch gốc; vượt H thì bị phạt, không bị cấm",
             (("Lịch gốc", "Tổng vượt ngưỡng 16,31; fatigue đỉnh 13,12."),
              ("M2 Optimal", "Tổng vượt ngưỡng 3,29."),
              ("M4 fatigue-aware", "Tổng vượt ngưỡng 0; tải đỉnh vẫn là 11.")), fig_threshold),
    ),
)


def render() -> None:
    render_module(MODULE)
