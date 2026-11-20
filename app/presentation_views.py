"""Vietnamese presentation views over the existing Module 5 adapters."""

import csv
import io

import numpy as np
import pandas as pd
import streamlit as st

from app.data_views import staff_workload_rows, week_options, weekly_assignment_rows
from app.dynamics_views import evaluate_dynamics, observed_block_summary
from app.presentation import hero, memo, named_rows, schedule_label, spreadsheet_text, table
from app.solver_views import compare_schedule_metrics
from app.temporal_views import (
    compare_temporal_schedules, evaluate_temporal_validity, load_automata_suite, staff_daily_trace_rows, trace_word,
)

PLAN_COLUMNS = {
    "week": "Tuần", "date": "Ngày", "time": "Giờ", "class": "Buổi", "session_id": "Mã ca",
    "campus": "Cơ sở", "demand": "Nhu cầu", "assigned": "Đã xếp", "invigilators": "Giám thị",
}
TECHNICAL = {
    "m1": (
        ("encode_invigilator_assignment()", "solve_instance()", "extract_minimal_core()", "clause_to_linear()"),
        ("CNF · Sequential Counter", "Minisat22", "Selector / UNSAT core", "Logic-to-0/1-Linear"),
        ("Thời gian mã hóa: O(C)", "Bộ nhớ CNF: O(C)", "Rút lõi: O(k²) lần gọi SAT"),
        "C là số literal được ghi; k là số selector trong lõi ban đầu. Lõi tối thiểu theo bao hàm: "
        "bỏ một điều kiện bất kỳ thì phần còn lại thỏa được. Cận số lần gọi không phải cận thời gian giải SAT.",
    ),
    "m2": (
        ("Instance", "create_variables()", "build_model()", "solve()", "check_schedule()"),
        ("Sparse dict x[i,j]", "Two-stage ILP", "PuLP / CBC", "Branch-and-cut"),
        ("Bộ nhớ biến phân công: O(|A|)", "Cây nhánh: có thể tăng theo hàm mũ"),
        "A là tập cặp giám thị–ca khả dụng. Giai đoạn 1 giảm tải đỉnh; giai đoạn 2 giữ cận tải "
        "đó rồi giảm độ lệch L1 và phạt mềm. H1: khả dụng; H2: không trùng giờ; H3: đủ người.",
    ),
    "m3": (
        ("DFA.run()", "DFA.accepts()", "product()", "minimize()", "add_regular_constraint()"),
        ("Bảng chuyển trạng thái", "BFS product", "Moore refinement", "Layered graph / unit flow"),
        ("DFA.run: O(D) thời gian", "DFA.run: O(1) bộ nhớ phụ", "Layered graph: tối đa O(D·|Q|·|Σ|) cạnh"),
        "D là số ngày; Q là tập trạng thái; Σ cố định gồm 4 ký hiệu. Bản truy vết lưu thêm một trạng thái mỗi ngày. "
        "Trong ILP, một đơn vị luồng nối các lớp ngày và chỉ kết thúc ở trạng thái chấp nhận.",
    ),
    "m4": (
        ("WeeklyWorkload", "calibrate()", "simulate()", "fixed_point()", "add_fatigue_soft_constraints()"),
        ("Vector fatigue", "NumPy ndarray", "Lag-one OLS", "Soft threshold"),
        ("simulate: O(N·T) thời gian", "Quỹ đạo lưu: O(N·T) bộ nhớ"),
        "N là số người, T là số tuần mô phỏng. Với tải dài hạn cố định, Jacobian là aI. "
        "Quỹ đạo lịch sử dùng tải từng khối và điều chỉnh theo số ngày thực; không dùng nó để suy ra một điểm bất động.",
    ),
}


def overview(inst) -> None:
    hero("CO2011 · Mô hình hóa toán học", "Xếp lịch coi thi, từ quy tắc đến cân bằng",
         "Theo dõi cách bốn mô hình biến dữ liệu ca thi thành lịch phân công có thể kiểm tra.")
    st.caption("Số liệu tham chiếu từ toàn bộ dữ liệu khoa.")
    for column, (label, value) in zip(st.columns(3), (
        ("Giám thị", len(inst.staff_ids)), ("Ca thi", len(inst.session_names)), ("Lượt phân công cần có", sum(inst.demand)),
    )):
        column.metric(label, value)
    st.button("Mở demo đầu-cuối", type="primary", on_click=st.session_state.update, args=({"route": "pipeline"},))
    st.header("Một bài toán, bốn bước")
    st.caption("Dữ liệu CSV được chuẩn hóa thành cùng một tập giám thị, ca thi và nhu cầu.")
    st.markdown(
        '<ol class="iap-flow" role="list" aria-label="Luồng xử lý bốn mô hình">'
        '<li><b>01 · Logic</b>Quy tắc cứng thành CNF và ràng buộc 0/1.<span>Đầu ra: SAT hoặc lõi UNSAT.</span></li>'
        '<li><b>02 · Tối ưu ILP</b>Dùng cùng các ràng buộc để tìm lịch cân bằng.<span>Đầu ra: các cặp giám thị–ca.</span></li>'
        '<li><b>03 · Kiểm tra DFA</b>Đọc chuỗi ngày từ lịch; có thể đưa DFA trở lại ILP.'
        '<span>Đầu ra: kết quả chấp nhận và vết trạng thái.</span></li>'
        '<li><b>04 · Hệ động lực</b>Cộng tải theo tuần rồi mô phỏng fatigue.'
        '<span>Đầu ra: quỹ đạo, phương sai và điểm cân bằng.</span></li></ol>',
        unsafe_allow_html=True,
    )


LOGIC_BRIDGE = r"""
| Quy tắc | Logic vị từ / mệnh đề | Dạng trước khi mã hóa CNF | Ràng buộc tuyến tính 0/1 |
| :--- | :--- | :--- | :--- |
| **H1 · Khả dụng** | $\forall i\in I,\ \forall j\in J:\ \operatorname{Busy}(i,j)\Rightarrow\neg\operatorname{Assign}(i,j)$ | $\neg\operatorname{Assign}(i,j)$ | $x_{ij}=0$ |
| **H2 · Không trùng giờ** | $\operatorname{Overlap}(j,k)\Rightarrow\neg\bigl(\operatorname{Assign}(i,j)\land\operatorname{Assign}(i,k)\bigr)$ | $\neg\operatorname{Assign}(i,j)\lor\neg\operatorname{Assign}(i,k)$ | $x_{ij}+x_{ik}\le 1$ |
| **H3 · Đủ người** | $\forall j\in J:\ \#\{i\in I:\operatorname{Assign}(i,j)\}=d_j$ | $\operatorname{Exactly}_{d_j}\bigl(\{\operatorname{Assign}(i,j):i\in I\}\bigr)$ | $\displaystyle\sum_{i\in I}x_{ij}=d_j$ |
| **Mệnh đề tổng quát** | Tuyển của các literal | $\bigl(\bigvee_{p\in P}v_p\bigr)\lor\bigl(\bigvee_{n\in N}\neg v_n\bigr)$ | $\sum_{p\in P}x_p-\sum_{n\in N}x_n\ge 1-\lvert N\rvert$ |
| **Tuyển** | $a\lor b$ | $a\lor b$ | $x_a+x_b\ge 1$ |
| **Kéo theo** | $a\Rightarrow b$ | $\neg a\lor b$ | $x_b-x_a\ge 0$ |
| **Không cùng đúng** | $\neg(a\land b)$ | $\neg a\lor\neg b$ | $x_a+x_b\le 1$ |
| **Đúng một** | $\#\{s\in S:s\ \text{đúng}\}=1$ | $\operatorname{Exactly}_1(S)$ | $\displaystyle\sum_{s\in S}x_s=1$ |
| **Tối đa $k$** | $\#\{s\in S:s\ \text{đúng}\}\le k$ | $\operatorname{AtMost}_k(S)$ | $\displaystyle\sum_{s\in S}x_s\le k$ |
| **Đúng $k$** | $\#\{s\in S:s\ \text{đúng}\}=k$ | $\operatorname{Exactly}_k(S)$ | $\displaystyle\sum_{s\in S}x_s=k$ |
| **Mệnh đề rỗng** | $\bot$ | $\bigvee\varnothing=\bot$ | $0\ge 1$ (vô nghiệm) |
"""


def logic_panel(result: dict, *, compact: bool = False) -> None:
    if result["satisfiable"]:
        st.success("SAT — Có ít nhất một lịch thỏa các ràng buộc cứng. SAT không chứng minh lịch tối ưu.")
    else:
        st.error("UNSAT — Không tồn tại lịch thỏa đồng thời các ràng buộc cứng trên dữ liệu này.")
    if not compact:
        a, b, c = st.columns(3)
        a.metric("Mệnh đề CNF", result["n_clauses"])
        b.metric("Biến phân công", result["n_assign_vars"], f"{result['n_aux_vars']} biến phụ", delta_color="off")
        c.metric("Ràng buộc tuyến tính 0/1", result["linear_rows"])
        st.caption(f"Mã hóa và kiểm tra bằng Minisat22: {result['runtime_ms']:.1f} ms.")
    if result["unsat_core"]:
        (st.subheader if compact else st.header)("Lõi mâu thuẫn tối thiểu")
        table([{"rule": rule} for rule in result["unsat_core"]], {"rule": "Ràng buộc trong lõi"})
    elif not compact:
        st.header("Lịch chứng minh tính khả thi")
        table([{"session": sid, "staff": ", ".join(people)} for sid, people in result["model"].items()],
              {"session": "Mã ca", "staff": "Giám thị"})
    if not compact:
        with st.expander("Đối chiếu Logic với ràng buộc 0/1"):
            st.markdown(r"$I$: tập giám thị; $J$: tập ca thi; $d_j$: số người cần cho ca $j$. "
                        r"$x_{ij}\in\{0,1\}$ bằng $1$ khi giám thị $i$ được xếp ca $j$. "
                        r"$P,N$: tập chỉ số literal dương và âm; $S$: tập mệnh đề cần đếm.")
            st.markdown(LOGIC_BRIDGE)
            st.caption("H2 áp dụng cho mọi giám thị và mọi cặp ca phân biệt. H1 và H2 chỉ sinh mệnh đề "
                       "cho cặp bận hoặc trùng giờ. H3 dùng Sequential Counter; quy tắc đúng một "
                       "cũng có thể mã hóa bằng các mệnh đề loại trừ từng cặp.")


def solve_status(result: dict) -> None:
    note = f"CBC chạy {result['runtime_s']:g} giây."
    if result["assigned"]:
        metrics = result["metrics"]
        st.caption(f"Đã tìm được lịch thỏa H1–H3. Tải đỉnh: {metrics['max_load']}; "
                   f"độ lệch L1: {metrics['l1']:.3f}. {note}")
        if result["stage_statuses"].get(1) != "optimal":
            st.info("CBC chưa chứng minh tải đỉnh nhỏ nhất; lịch đang xem là lịch khả thi.")
        elif result["status"] != "optimal":
            st.info("CBC đã xác nhận tải đỉnh nhỏ nhất, nhưng chưa chứng minh tối ưu ở giai đoạn 2.")
        if result["include_m4_soft"] and not result["calibrated_m4_from_data"]:
            st.caption("Khi thêm ngưỡng mềm, CBC dùng thông số tham chiếu từ bộ dữ liệu khoa.")
    elif result["status"] == "infeasible":
        st.warning(f"CBC xác nhận mô hình đã chọn vô nghiệm. {note}")
    else:
        st.warning(f"CBC chưa trả về lịch. Đây không phải kết luận vô nghiệm. {note}")
    if result["diagnosis"]:
        st.caption("Chẩn đoán H3 nới lỏng, không xét DFA: số người còn thiếu theo từng ca.")
        table(result["diagnosis"], {"session": "Mã ca", "demand": "Nhu cầu", "missing": "Còn thiếu"})


def plan_csv(rows: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(PLAN_COLUMNS)
    for row in rows:
        writer.writerow([spreadsheet_text(row[col]) for col in PLAN_COLUMNS])
    return buffer.getvalue().encode("utf-8-sig")


def plan_panel(inst, schedules: dict, active: str, *, compact: bool = False) -> None:
    weeks = {None: "Tất cả các tuần", **{
        w["week"]: f"Tuần {w['week']} · {w['start']} đến {w['end']} ({w['days']} ngày)" for w in week_options(inst)
    }}
    left, right = st.columns(2)
    week = left.selectbox("Tuần trong lịch", list(weeks), format_func=weeks.__getitem__, key="week_filter")
    campus = right.selectbox("Cơ sở", ["All", *sorted(set(inst.campus))],
                             format_func=lambda value: "Tất cả cơ sở" if value == "All" else value, key="campus_filter")
    pairs = schedules[active]
    rows = weekly_assignment_rows(inst, pairs, week=week, campus=campus)
    st.caption(f"{schedule_label(active)} · {len(rows)} ca trong bộ lọc đang chọn.")
    table(rows, PLAN_COLUMNS)
    if rows:
        st.download_button("Tải bảng phân công CSV", data=plan_csv(rows), file_name="phan-cong.csv", mime="text/csv")
    if compact:
        return
    st.header("So sánh tải và phạt mềm")
    comparison = memo("comparison", (inst, schedules), lambda: compare_schedule_metrics(inst, schedules))
    table(named_rows(comparison), {
        "schedule": "Lịch", "max_load": "Tải đỉnh", "min_load": "Tải thấp nhất", "l1": "Độ lệch L1",
        "location": "Phạt cơ sở", "fatigue": "Phạt số ca/ngày", "travel": "Phạt di chuyển", "hard_violations": "Vi phạm H1–H3",
        "stage2_objective": "Mục tiêu M2 (không gồm ngưỡng M4)",
    })
    staff_rows = staff_workload_rows(inst, pairs)
    distribution = (pd.Series([row["total_load"] for row in staff_rows]).value_counts().sort_index()
                    .rename_axis("Số ca").rename("Số giám thị").reset_index())
    st.bar_chart(distribution, x="Số ca", y="Số giám thị")
    with st.expander("Số liệu phân bố tải"):
        st.dataframe(distribution, hide_index=True, use_container_width=True)
    with st.expander("Tải của từng giám thị"):
        table(staff_rows, {"staff_id": "Giám thị", "total_load": "Tổng số ca", "cs1_load": "CS1", "cs2_load": "CS2",
                           **{f"W{k}": f"Tuần {k}" for k in weeks if k is not None}})


@st.cache_resource(show_spinner=False)
def automata() -> dict:
    # The suite is only read; never mutate the shared DFA objects.
    return load_automata_suite()


def word_lab() -> None:
    st.header("Thử một chuỗi ngày")
    st.caption("M: sáng · A: chiều · N: tối · -: nghỉ. Ký hiệu N ở ngày cuối không đòi hỏi một ngày ngoài lịch.")
    examples = {"MA-M": "Có ngày nghỉ", "MAM": "Vi phạm R1 · ba ngày liên tiếp",
                "NM": "Vi phạm R2 · đi làm sau ca tối", "MM-MM-M": "Vi phạm R3 · năm ngày trong bảy ngày"}
    st.selectbox("Chọn chuỗi mẫu", list(examples), format_func=examples.__getitem__, key="word_preset",
                 on_change=lambda: st.session_state.update(dfa_word=st.session_state.word_preset))
    st.session_state.setdefault("dfa_word", "MA-M")
    word = st.text_input("Chuỗi ngày cần kiểm tra", key="dfa_word", max_chars=120).strip().upper()
    if not word:
        st.info("Nhập ít nhất một ký hiệu để xem vết chạy.")
        return
    if set(word) - {"M", "A", "N", "-"}:
        st.error("Chỉ nhập M, A, N hoặc dấu gạch ngang (-), không chèn khoảng trắng giữa các ngày.")
        return
    suite = automata()
    machine = suite["minimal"]
    trace = trace_word(machine, word)
    if machine.accepts(word):
        st.success("Chuỗi được DFA chấp nhận: thỏa cả R1, R2 và R3.")
    else:
        failed = ", ".join(name for name, dfa in suite["rules"].items() if not dfa.accepts(word))
        st.warning(f"Chuỗi vi phạm {failed}; phát hiện từ ngày {trace['first_violation_day']}.")
    st.caption(f"Bắt đầu tại trạng thái {machine.start}. Bảng hiển thị trạng thái sau khi đọc mỗi ngày.")
    table([{"day": day, "symbol": symbol, "state": state} for day, (symbol, state) in
           enumerate(zip(word, trace["states"][1:]), start=1)], {"day": "Ngày", "symbol": "Ký hiệu", "state": "Trạng thái DFA tích"})
    with st.expander("Quy tắc, tích và tối giản DFA"):
        st.write("**R1:** tối đa 2 ngày làm liên tiếp. **R2:** sau ca tối phải nghỉ nếu còn ngày tiếp theo. "
                 "**R3:** tối đa 4 ngày làm trong 7 ngày.")
        st.write("**R4** chỉ để tham khảo: giới hạn |#M − #A| ≤ 3 tại mọi tiền tố dùng bộ đếm hữu hạn. "
                 "Cân bằng chính xác cuối kỳ không chính quy: giao với M*A* cho {MⁿAⁿ}.")
        table([{"machine": label, "before": reach, "after": mini} for label, reach, mini in suite["counts_table"]],
              {"machine": "DFA", "before": "Trạng thái tới được", "after": "Sau tối giản"})


def temporal_panel(inst, schedules: dict, active: str, *, compact: bool = False) -> None:
    suite = automata()
    pairs = schedules[active]
    audit = memo("temporal", (inst, pairs), lambda: evaluate_temporal_validity(inst, pairs, suite=suite))
    count = f"{audit['accepted_count']}/{audit['total_staff']}"
    if audit["schedule_valid"]:
        st.success(f"Lịch hợp lệ — {count} chuỗi được DFA chấp nhận, không có vi phạm H1–H3.")
    elif audit["dfa_accepted_all"]:
        st.warning(f"{count} chuỗi được DFA chấp nhận nhưng lịch vi phạm H1–H3.")
    else:
        st.warning(f"Lịch không được DFA chấp nhận — {audit['rejected_count']} chuỗi vi phạm ({count} đạt).")
    if compact:
        return
    rv = audit["rule_violations"]
    for col, rule in zip(st.columns(3), ("R1", "R2", "R3")):
        col.metric(f"{rule} · số người vi phạm", rv[rule])
    st.caption(f"R4 (tham khảo): {rv['R4_prefix']} người vượt ngưỡng ở một tiền tố, {rv['R4_end']} ở cuối kỳ.")
    with st.expander("So sánh DFA giữa các lịch"):
        comparison = memo("temporal_comparison", (inst, schedules), lambda: compare_temporal_schedules(inst, schedules, suite=suite))
        table(named_rows(comparison), {"schedule": "Lịch", "dfa_accepted": "Số chuỗi đạt", "rejected": "Số chuỗi vi phạm",
                                      "R1_violations": "R1", "R2_violations": "R2", "R3_violations": "R3"})
    st.caption("Mỗi ngày trong lịch có một ký hiệu. Nếu có nhiều ca, ưu tiên N, rồi A, rồi M; ngày không có ca là -. "
               "Số ngày làm không phải số ca.")
    only_rejected = st.checkbox("Chỉ hiện giám thị có chuỗi vi phạm", key="only_rejected_staff")
    visible = [{**row, "dfa_accepted": "Đạt" if row["dfa_accepted"] else "Không đạt",
                "broken_rules": "—" if row["dfa_accepted"] else row["broken_rules"]}
               for row in audit["staff_rows"] if not only_rejected or not row["dfa_accepted"]]
    table(visible, {"staff_id": "Giám thị", "roster_string": "Chuỗi ngày", "work_days": "Ngày làm", "dfa_accepted": "DFA",
                    "broken_rules": "Quy tắc vi phạm", "first_violation_date": "Ngày phát hiện"})
    if visible:
        with st.expander("Xem vết trạng thái của một giám thị"):
            staff_id = st.selectbox("Giám thị cần kiểm tra", [row["staff_id"] for row in visible], key="trace_staff_id")
            table(staff_daily_trace_rows(inst, pairs, staff_id, suite=suite),
                  {"date": "Ngày", "symbol": "Ký hiệu lịch", "R1_state": "R1", "R2_state": "R2",
                   "R3_state": "R3", "product_state": "DFA tích"})


def dynamics_panel(inst, schedules: dict, active: str, *, compact: bool = False) -> None:
    if compact:
        weeks, staff, shock = 12, inst.staff_ids[0], 0.0
    else:
        with st.container(border=True):
            st.header("Thử nhiễu tại tuần 0")
            weeks = st.slider("Số tuần mô phỏng", 4, 104, 12, key="sim_weeks")
            staff = st.selectbox("Giám thị được gây nhiễu", inst.staff_ids, key="shock_staff")
            shock = st.slider("Mức tăng fatigue ban đầu", 0.0, 10.0, 0.0, 0.5, key="shock_amount")
    index = inst.staff_ids.index(staff)
    dyn = memo("dynamics", (inst, schedules, weeks, index, shock), lambda: evaluate_dynamics(
        inst, schedules, weeks=weeks, shock_staff_index=index, shock_amount=shock,
    ))
    trajectory, equilibrium = dyn["trajectories"][active], dyn["equilibria"][active]
    parameters = dyn["parameters"]
    st.caption(f"a = {parameters['a']:.4f} · b = {parameters['b']:.4f} · r = {parameters['r']:g} · "
               f"Ngưỡng mềm H = {dyn['threshold']:.3f}. " + ("Hiệu chuẩn từ tải quan sát của dữ liệu đang xem."
               if dyn["calibrated_from_data"] else "Dùng hiệu chuẩn tham chiếu từ dữ liệu khoa."))
    st.caption("Fatigue là đại lượng đại diện quy đổi theo tải tuần, không phải số đo sinh lý.")
    if not compact:
        a, b, c = st.columns(3)
        a.metric("F tại tuần 0", f"{trajectory[0, index]:.4f}")
        b.metric("Điểm cân bằng F*", f"{equilibrium[index]:.4f}")
        c.metric(f"F tại tuần {weeks}", f"{trajectory[-1, index]:.4f}")
        st.latex(r"F_{t+1}=aF_t+b\ell-r\rho,\quad F^*=\frac{b\ell-r\rho}{1-a}")
        st.write("Với tải cố định và |a| < 1, nhiễu ban đầu tắt dần; không làm đổi điểm cân bằng.")
    times = range(weeks + 1)
    section = st.subheader if compact else st.header
    section("Quỹ đạo fatigue theo tuần")
    reference = "Baseline" if "Baseline" in schedules else next(iter(schedules))
    st.text(f"Giám thị: {staff}")
    st.caption(f"Tuần 0 lấy trạng thái cuối kỳ của lịch tham chiếu «{schedule_label(reference)}»"
               " rồi cộng nhiễu nếu có. Các tuần sau dùng tải trung bình của lịch đang xem.")
    fitness = pd.DataFrame({"Tuần": times, "Quỹ đạo": trajectory[:, index], "Điểm cân bằng": equilibrium[index]})
    st.line_chart(fitness, x="Tuần", y=["Quỹ đạo", "Điểm cân bằng"], y_label="Fatigue",
                  color=["#178477", "#bb752f"], height=290)
    section("Công bằng theo thời gian")
    measure = st.radio("Thước đo công bằng", ["Phương sai", "Chênh lệch lớn nhất"], horizontal=True, key="fairness_measure")
    variance = measure == "Phương sai"
    stat = np.var if variance else np.ptp
    fairness = pd.DataFrame({"Tuần": times, **{
        schedule_label(name): stat(values, axis=1) for name, values in dyn["trajectories"].items()
    }})
    st.line_chart(fairness, x="Tuần", y_label=measure, height=280)
    with st.expander("Số liệu quỹ đạo và công bằng"):
        st.dataframe(fitness, hide_index=True, use_container_width=True)
        st.dataframe(fairness, hide_index=True, use_container_width=True)
    if not compact:
        with st.expander("Đối chiếu điểm cân bằng và tải lịch sử"):
            table(named_rows(dyn["summary_rows"], "scenario"), {
                "scenario": "Lịch / tham chiếu", "equilibrium_mean": "F* trung bình", "equilibrium_spread": "Chênh lệch F*",
                "equilibrium_variance": "Phương sai F*", "final_max_error": "Sai số cuối", "observed_threshold_excess": "Tổng vượt H",
            })
            blocks = observed_block_summary(inst, schedules[active], parameters)
            hist = pd.DataFrame({
                "Khối tuần": [row["week"] for row in blocks],
                "Fatigue đỉnh": [row["max_fatigue_end"] for row in blocks], "Ngưỡng mềm H": dyn["threshold"],
            })
            st.scatter_chart(hist, x="Khối tuần", y=["Fatigue đỉnh", "Ngưỡng mềm H"], y_label="Fatigue",
                             color=["#178477", "#bb752f"], height=220)
            table([{**row, "threshold": dyn["threshold"]} for row in blocks], {
                "week": "Tuần", "days": "Số ngày", "assignments": "Lượt xếp", "max_fatigue_end": "Fatigue đỉnh cuối khối",
                "threshold": "Ngưỡng mềm H",
            })
