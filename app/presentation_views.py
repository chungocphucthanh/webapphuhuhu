"""Vietnamese presentation views over the existing Module 5 adapters."""

import csv
import io
import re
from html import escape
from urllib.parse import unquote

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


def overview(inst) -> None:
    hero("CO2011 · Mô hình hóa toán học", "Xếp lịch coi thi, từ quy tắc đến cân bằng",
         "Theo dõi cách bốn mô hình biến dữ liệu ca thi thành lịch phân công có thể kiểm tra.")
    st.subheader("Dữ liệu khoa")
    for column, (label, value) in zip(st.columns(3), (
        ("Giám thị", len(inst.staff_ids)), ("Ca thi", len(inst.session_names)), ("Lượt phân công cần có", sum(inst.demand)),
    )):
        column.metric(label, value)
    start, demo = st.columns(2)
    start.button("Bắt đầu trình chiếu", type="primary", key="start_presentation", use_container_width=True,
                 on_click=st.session_state.update, args=({"route": "m1"},))
    demo.button("Mở demo đầu-cuối", use_container_width=True,
                on_click=st.session_state.update, args=({"route": "pipeline"},))
    st.header("Một bài toán, bốn bước")
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
        st.success("SAT — Có lịch thỏa H1–H3. Chưa xét R1–R3 hoặc độ tối ưu.")
    else:
        st.error("UNSAT — Không thể thỏa đồng thời các ràng buộc dưới đây.")
    if compact:
        if not result["satisfiable"]:
            conflict_panel(result["unsat_core"])
        return

    outcome, bridge = st.tabs(("Kết quả SAT / UNSAT", "Đối chiếu Logic với 0/1"))
    with outcome:
        if result["satisfiable"]:
            witness = result["model"]
            total_sessions, total_assignments, inspect = st.columns((1, 1, 2))
            total_sessions.metric("Ca trong lịch khả thi", len(witness))
            total_assignments.metric("Lượt phân công", sum(map(len, witness.values())))
            session = inspect.selectbox("Xem một ca", tuple(witness), key="sat_witness_session")
            if session is not None:
                people = witness[session]
                roster = "".join(f"<li>{escape(person)}</li>" for person in people)
                st.markdown(
                    f'<section class="iap-session"><h3>Ca {escape(session)}</h3>'
                    f'<p><strong>{len(people)}</strong> giám thị trong lịch chứng minh</p>'
                    f'<ul class="iap-people" role="list">{roster}</ul></section>',
                    unsafe_allow_html=True,
                )
        else:
            conflict_panel(result["unsat_core"])
    with bridge:
        a, b, c = st.columns(3)
        a.metric("Mệnh đề CNF", result["n_clauses"])
        b.metric("Biến phân công", result["n_assign_vars"], f"{result['n_aux_vars']} biến phụ", delta_color="off")
        c.metric("Ràng buộc tuyến tính 0/1", result["linear_rows"])
        st.markdown(r"$I$: tập giám thị; $J$: tập ca thi; $d_j$: số người cần cho ca $j$. "
                    r"$x_{ij}\in\{0,1\}$ bằng $1$ khi giám thị $i$ được xếp ca $j$. "
                    r"$P,N$: tập chỉ số literal dương và âm; $S$: tập mệnh đề cần đếm.")
        st.markdown(LOGIC_BRIDGE)


def conflict_panel(core: list[str]) -> None:
    st.subheader("Mâu thuẫn nằm ở đâu?")
    st.write("Các điều kiện bên dưới tạo thành một lõi mâu thuẫn: bỏ bất kỳ một điều kiện nào, "
             "phần còn lại của lõi có thể thỏa được.")
    busy_by_session: dict[str, list[str]] = {}
    cards: list[tuple[str, str, str]] = []
    for member in core:
        if match := re.fullmatch(r"capacity\((.+)\)=(\d+)", member):
            session, demand = map(unquote, match.groups())
            cards.append(("H3 · Đủ người", f"Ca {session}", f"Ca này cần {demand} giám thị."))
        elif match := re.fullmatch(r"Busy\(([^,]+),([^,]+)\)", member):
            person, session = map(unquote, match.groups())
            busy_by_session.setdefault(session, []).append(person)
        elif match := re.fullmatch(r"NoDoubleBooking\(([^,]+),([^,]+),([^,]+)\)", member):
            person, first, second = map(unquote, match.groups())
            cards.append(("H2 · Không trùng giờ", f"Giám thị {person}",
                          f"Không thể coi cả ca {first} và ca {second} vì hai ca trùng giờ."))
        else:
            cards.append(("Điều kiện trong lõi", unquote(member), ""))
    cards.extend(("H1 · Khả dụng", f"Ca {session}", f"Giám thị không thể coi ca này: {', '.join(people)}.")
                 for session, people in busy_by_session.items())
    content = "".join(
        f'<li><strong>{escape(rule)}</strong><b>{escape(title)}</b><span>{escape(detail)}</span></li>'
        for rule, title, detail in cards
    )
    st.markdown(f'<ul class="iap-conflict" role="list" aria-label="Lõi mâu thuẫn">{content}</ul>',
                unsafe_allow_html=True)


def solve_status(result: dict) -> None:
    if result["assigned"]:
        if result["stage_statuses"].get(1) != "optimal":
            st.info("CBC chưa chứng minh tải đỉnh nhỏ nhất; lịch đang xem là lịch khả thi.")
        elif result["status"] != "optimal":
            st.info("CBC đã xác nhận tải đỉnh nhỏ nhất, nhưng chưa chứng minh tối ưu ở giai đoạn 2.")
        if result["include_m4_soft"] and not result["calibrated_m4_from_data"]:
            with st.expander("Thông số CBC"):
                st.write("Ngưỡng mềm dùng thông số tham chiếu của bộ dữ liệu khoa.")
    elif result["status"] == "infeasible":
        st.warning("Mô hình đã chọn vô nghiệm.")
    else:
        st.warning("Chưa tìm được lịch. Đây không phải kết luận vô nghiệm.")
    if result["diagnosis"]:
        st.write("Số người còn thiếu theo từng ca khi nới H3 (không xét DFA).")
        table(result["diagnosis"], {"session": "Mã ca", "demand": "Nhu cầu", "missing": "Còn thiếu"})


def plan_csv(rows: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(PLAN_COLUMNS)
    for row in rows:
        writer.writerow([spreadsheet_text(row[col]) for col in PLAN_COLUMNS])
    return buffer.getvalue().encode("utf-8-sig")


def plan_panel(inst, schedules: dict, active: str, *, compact: bool = False) -> None:
    comparison = memo("comparison", (inst, schedules), lambda: compare_schedule_metrics(inst, schedules))
    result = next(row for row in comparison if row["schedule"] == active)
    peak, balance, hard = st.columns(3)
    baseline = next((row["max_load"] for row in comparison if row["schedule"] == "Baseline"), None)
    delta = None if baseline is None or active == "Baseline" else result["max_load"] - baseline
    peak.metric("Tải đỉnh · ca/người", result["max_load"], delta=delta, delta_color="inverse",
                help="So với lịch gốc khi có. Tính trên toàn bộ lịch, không chỉ các ca đang lọc.")
    balance.metric("Độ lệch tải L1", f"{result['l1']:g}")
    hard.metric("Vi phạm H1–H3", result["hard_violations"])
    if compact:
        weekly_plan(inst, schedules[active], inspect=False)
        return
    plan_tab, comparison_tab = st.tabs(("Lịch theo ca", "So sánh tải"))
    with plan_tab:
        weekly_plan(inst, schedules[active], inspect=True)
    with comparison_tab:
        workload_comparison(inst, schedules[active], comparison)


def weekly_plan(inst, pairs, *, inspect: bool) -> None:
    weeks = {None: "Tất cả các tuần", **{
        w["week"]: f"Tuần {w['week']} · {w['start']} đến {w['end']} ({w['days']} ngày)" for w in week_options(inst)
    }}
    controls = st.columns((2, 1, 3)) if inspect else st.columns(2)
    left, right = controls[:2]
    week = left.selectbox("Tuần trong lịch", list(weeks), format_func=weeks.__getitem__, key="week_filter")
    campus = right.selectbox("Cơ sở", ["All", *sorted(set(inst.campus))],
                             format_func=lambda value: "Tất cả cơ sở" if value == "All" else value, key="campus_filter")
    rows = weekly_assignment_rows(inst, pairs, week=week, campus=campus)
    if not rows:
        st.info("Không có ca nào trong bộ lọc này. Đổi tuần hoặc cơ sở để xem lịch.")
        return
    if inspect:
        by_session = {row["session_id"]: row for row in rows}
        widget_key = "plan_session"
        preferred = st.session_state.get("iap_plan_session")
        st.session_state[widget_key] = preferred if preferred in by_session else next(iter(by_session))
        selected = controls[2].selectbox(
            "Xem một ca", list(by_session), key=widget_key,
            format_func=lambda sid: f"{by_session[sid]['date']} · {by_session[sid]['time']} · {sid}",
            on_change=lambda: st.session_state.update(iap_plan_session=st.session_state[widget_key]),
        )
        st.session_state["iap_plan_session"] = selected
        row = by_session[selected]
        j = inst.session_names.index(selected)
        people = [inst.staff_ids[i] for i in sorted(i for i, session in pairs if session == j)]
        chips = "".join(f"<li>{escape(person)}</li>" for person in people)
        st.markdown(
            '<div class="iap-session">'
            f'<h3>{escape(row["campus"])} · {escape(row["date"])} · {escape(row["time"])}</h3>'
            f'<p><strong>{row["assigned"]}/{row["demand"]}</strong> giám thị đã xếp</p>'
            f'<ul class="iap-people" role="list" aria-label="Giám thị được phân công">{chips}</ul></div>',
            unsafe_allow_html=True,
        )
    st.subheader(f"Danh sách {len(rows)} ca")
    table(rows, PLAN_COLUMNS)
    st.download_button("Tải bảng phân công CSV", data=plan_csv(rows), file_name="phan-cong.csv", mime="text/csv")


def workload_comparison(inst, pairs, comparison: list[dict]) -> None:
    st.header("Mỗi giám thị được xếp bao nhiêu ca?")
    staff_rows = staff_workload_rows(inst, pairs)
    distribution = (pd.Series([row["total_load"] for row in staff_rows]).value_counts().sort_index()
                    .rename_axis("Số ca").rename("Số giám thị").reset_index())
    st.bar_chart(distribution, x="Số ca", y="Số giám thị")
    with st.expander("Số liệu phân bố tải"):
        st.dataframe(distribution, hide_index=True, use_container_width=True)
    with st.expander("Đối chiếu các lịch và phạt mềm"):
        table(named_rows(comparison), {
            "schedule": "Lịch", "max_load": "Tải đỉnh", "min_load": "Tải thấp nhất", "l1": "Độ lệch L1",
            "location": "Phạt cơ sở", "fatigue": "Phạt số ca/ngày", "travel": "Phạt di chuyển",
            "hard_violations": "Vi phạm H1–H3", "stage2_objective": "Mục tiêu M2 (không gồm ngưỡng M4)",
        })
    with st.expander("Tải của từng giám thị"):
        table(staff_rows, {"staff_id": "Giám thị", "total_load": "Tổng số ca", "cs1_load": "CS1", "cs2_load": "CS2",
                           **{f"W{w['week']}": f"Tuần {w['week']}" for w in week_options(inst)}})


@st.cache_resource(show_spinner=False)
def automata() -> dict:
    # The suite is only read; never mutate the shared DFA objects.
    return load_automata_suite()


RULES = {
    "R1": "Tối đa 2 ngày làm liên tiếp",
    "R2": "Nghỉ ngày kế tiếp sau ca tối, nếu còn trong kỳ",
    "R3": "Tối đa 4 ngày làm trong bất kỳ 7 ngày liên tiếp",
}


def rule_legend(counts: dict | None = None) -> None:
    cards = []
    for rule, description in RULES.items():
        detail = "" if counts is None else f'<span><strong>{counts[rule]}</strong> giám thị vi phạm</span>'
        cards.append(f'<li><b>{rule}</b><span>{description}</span>{detail}</li>')
    st.markdown('<ul class="iap-rules" role="list" aria-label="Ba quy tắc DFA">' + "".join(cards) + "</ul>",
                unsafe_allow_html=True)


def word_lab() -> None:
    st.header("Thử một chuỗi ngày")
    st.write("**M** Sáng · **A** Chiều · **N** Tối · **-** Nghỉ")
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
        failed = "; ".join(f"{rule} — {RULES[rule]}" for rule, dfa in suite["rules"].items() if not dfa.accepts(word))
        st.warning(f"Chuỗi bắt đầu vi phạm ở ngày {trace['first_violation_day']}. Quy tắc bị vi phạm: {failed}.")
    rule_legend()
    table([{"day": day, "symbol": symbol, "state": state} for day, (symbol, state) in
           enumerate(zip(word, trace["states"][1:]), start=1)], {"day": "Ngày", "symbol": "Ký hiệu", "state": "Trạng thái DFA tích"})
    with st.expander("Cách đọc trạng thái và tối giản DFA"):
        st.write(f"Bắt đầu tại `{machine.start}`; bảng hiện trạng thái sau khi đọc từng ngày. "
                 "R2 không yêu cầu một ngày nghỉ ngoài phạm vi chuỗi.")
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
    rv = audit["rule_violations"]
    rule_legend(rv)
    if compact:
        return
    staff_filter = st.selectbox(
        "Lọc giám thị theo kết quả", ["Tất cả", "Vi phạm bất kỳ", *RULES],
        format_func=lambda item: f"{item} · {RULES[item]}" if item in RULES else item, key="rule_filter",
    )
    visible = [
        {**row, "dfa_accepted": "Đạt" if row["dfa_accepted"] else "Không đạt",
         "broken_rules": ", ".join(rule for rule in RULES if not row[f"{rule}_ok"]) or "—"}
        for row in audit["staff_rows"]
        if staff_filter == "Tất cả" or (staff_filter == "Vi phạm bất kỳ" and not row["dfa_accepted"])
        or (staff_filter in RULES and not row[f"{staff_filter}_ok"])
    ]
    if visible:
        st.subheader(f"{len(visible)} giám thị")
        table(visible, {"staff_id": "Giám thị", "roster_string": "Chuỗi ngày", "work_days": "Ngày làm", "dfa_accepted": "DFA",
                        "broken_rules": "Quy tắc vi phạm", "first_violation_date": "Vi phạm đầu tiên (R1–R3)"})
        with st.expander("Xem vết trạng thái của một giám thị"):
            staff_id = st.selectbox("Giám thị cần kiểm tra", [row["staff_id"] for row in visible], key="trace_staff_id")
            table(staff_daily_trace_rows(inst, pairs, staff_id, suite=suite),
                  {"date": "Ngày", "symbol": "Ký hiệu lịch", "R1_state": "R1", "R2_state": "R2",
                   "R3_state": "R3", "product_state": "DFA tích"})
    else:
        st.info("Không có giám thị khớp bộ lọc. Chọn Tất cả để xem lại danh sách.")
    with st.expander("So sánh lịch và cách đọc chuỗi"):
        st.write("Mỗi ngày có một ký hiệu. Nếu có nhiều ca, ưu tiên N, rồi A, rồi M. Ngày không có ca là dấu gạch ngang.")
        st.write(f"R4 (tham khảo): {rv['R4_prefix']} người vượt ngưỡng trong kỳ, {rv['R4_end']} người ở cuối kỳ.")
        comparison = memo("temporal_comparison", (inst, schedules), lambda: compare_temporal_schedules(inst, schedules, suite=suite))
        table(named_rows(comparison), {"schedule": "Lịch", "dfa_accepted": "Số chuỗi đạt", "rejected": "Số chuỗi vi phạm",
                                      "R1_violations": "R1", "R2_violations": "R2", "R3_violations": "R3"})


def dynamics_panel(inst, schedules: dict, active: str, *, compact: bool = False) -> None:
    if compact:
        weeks, staff, shock = 12, inst.staff_ids[0], 0.0
    else:
        staff_control, shock_control, horizon_control = st.columns(3)
        staff = staff_control.selectbox("Giám thị được gây nhiễu", inst.staff_ids, key="shock_staff")
        shock = shock_control.slider("Mức tăng fatigue ban đầu", 0.0, 10.0, 0.0, 0.5, key="shock_amount")
        weeks = horizon_control.slider("Số tuần mô phỏng", 4, 104, 12, key="sim_weeks")
    index = inst.staff_ids.index(staff)
    dyn = memo("dynamics", (inst, schedules, weeks, index, shock), lambda: evaluate_dynamics(
        inst, schedules, weeks=weeks, shock_staff_index=index, shock_amount=shock,
    ))
    trajectory, equilibrium = dyn["trajectories"][active], dyn["equilibria"][active]
    parameters = dyn["parameters"]
    if not compact:
        st.write("Nhiễu ban đầu tắt dần khi giữ tải cố định; điểm cân bằng không đổi.")
        a, b, c = st.columns(3)
        a.metric("F tại tuần 0", f"{trajectory[0, index]:.4f}")
        b.metric("Điểm cân bằng F*", f"{equilibrium[index]:.4f}")
        c.metric(f"F tại tuần {weeks}", f"{trajectory[-1, index]:.4f}")
    else:
        st.metric("Điểm cân bằng F* của giám thị đầu tiên", f"{equilibrium[index]:.4f}")
    times = range(weeks + 1)
    if compact:
        trajectory_tab, fairness_tab = st.tabs(("Quỹ đạo cá nhân", "Công bằng toàn đội"))
    else:
        trajectory_tab, fairness_tab, model_tab, history_tab = st.tabs(
            ("Quỹ đạo cá nhân", "Công bằng toàn đội", "Mô hình và công thức", "Tải lịch sử"),
        )
    fitness = pd.DataFrame({"Tuần": times, "Quỹ đạo": trajectory[:, index], "Điểm cân bằng": equilibrium[index]})
    with trajectory_tab:
        st.subheader("Fatigue tiến về điểm cân bằng")
        st.line_chart(fitness, x="Tuần", y=["Quỹ đạo", "Điểm cân bằng"], y_label="Fatigue (quy đổi theo tải tuần)",
                      color=["#1b61c9", "#ad6123"], height=325)
        with st.popover("Xem số liệu quỹ đạo"):
            st.dataframe(fitness, hide_index=True, use_container_width=True)
    with fairness_tab:
        st.subheader("Chênh lệch fatigue giữa các giám thị")
        measure = st.radio("Thước đo công bằng", ["Phương sai", "Chênh lệch lớn nhất"], horizontal=True, key="fairness_measure")
    variance = measure == "Phương sai"
    stat = np.var if variance else np.ptp
    fairness = pd.DataFrame({"Tuần": times, **{
        schedule_label(name): stat(values, axis=1) for name, values in dyn["trajectories"].items()
    }})
    with fairness_tab:
        st.line_chart(fairness, x="Tuần", y_label=measure, height=325)
        with st.popover("Xem số liệu công bằng"):
            st.dataframe(fairness, hide_index=True, use_container_width=True)
    if compact:
        return
    with model_tab:
        st.subheader("Khi nào fatigue ổn định?")
        st.latex(r"F_{t+1}=aF_t+b\ell-r\rho,\quad F^*=\frac{b\ell-r\rho}{1-a}")
        for column, (label, value) in zip(st.columns(4), (
            ("Hệ số quán tính a", f"{parameters['a']:.4f}"),
            ("Tác động tải b", f"{parameters['b']:.4f}"),
            ("Hệ số hồi phục r", f"{parameters['r']:g}"),
            ("Ngưỡng mềm H", f"{dyn['threshold']:.3f}"),
        )):
            column.metric(label, value)
        st.write("Hiệu chuẩn từ tải quan sát của bộ dữ liệu đang xem." if dyn["calibrated_from_data"]
                 else "Dùng hiệu chuẩn tham chiếu từ dữ liệu khoa.")
        reference = "Baseline" if "Baseline" in schedules else next(iter(schedules))
        st.write(f"Tuần 0 lấy trạng thái cuối kỳ của «{schedule_label(reference)}», cộng nhiễu nếu có. "
                 "Các tuần sau dùng tải trung bình của lịch đang xem. Đây là mô phỏng, không phải số đo sinh lý.")
    with history_tab:
        blocks = observed_block_summary(inst, schedules[active], parameters)
        hist = pd.DataFrame({
            "Khối tuần": [row["week"] for row in blocks],
            "Fatigue đỉnh": [row["max_fatigue_end"] for row in blocks], "Ngưỡng mềm H": dyn["threshold"],
        })
        st.subheader("Fatigue đỉnh từng khối tuần")
        st.scatter_chart(hist, x="Khối tuần", y=["Fatigue đỉnh", "Ngưỡng mềm H"], y_label="Fatigue",
                         color=["#178477", "#bb752f"], height=260)
        with st.popover("Xem chi tiết theo tuần"):
            table([{**row, "threshold": dyn["threshold"]} for row in blocks], {
                "week": "Tuần", "days": "Số ngày", "assignments": "Lượt xếp", "max_fatigue_end": "Fatigue đỉnh cuối khối",
                "threshold": "Ngưỡng mềm H",
            })
        with st.popover("So sánh điểm cân bằng giữa các lịch"):
            table(named_rows(dyn["summary_rows"], "scenario"), {
                "scenario": "Lịch / tham chiếu", "equilibrium_mean": "F* trung bình", "equilibrium_spread": "Chênh lệch F*",
                "equilibrium_variance": "Phương sai F*", "final_max_error": "Sai số cuối", "observed_threshold_excess": "Tổng vượt H",
            })
