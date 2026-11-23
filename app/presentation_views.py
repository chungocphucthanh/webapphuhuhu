"""Vietnamese presentation views over the existing Module 5 adapters."""

import csv
import io
import re
from html import escape
from urllib.parse import unquote

import numpy as np
import pandas as pd
import streamlit as st
from pulp import PulpSolverError

from app.data_views import staff_workload_rows, week_options, weekly_assignment_rows
from app.dynamics_views import evaluate_dynamics, observed_block_summary
from app.experiments import (
    SAMPLE_TEAM_SEEDS,
    derive_weights_from_seed,
    evaluate_custom_automata,
    pumping_lemma_demo,
    run_m1_what_if,
    run_m2_counterexample_h2,
    run_m2_counterexample_lp,
    run_m2_what_if,
    run_m4_what_if,
    solve_with_custom_automata,
)
from app.presentation import hero, memo, named_rows, schedule_label, spreadsheet_text, table
from app.solver_views import compare_schedule_metrics
from app.temporal_views import (
    compare_temporal_schedules, evaluate_temporal_validity, load_automata_suite, staff_daily_trace_rows, trace_word,
)
from app.theory_content import (
    render_m1_result_guide,
    render_m1_theory,
    render_m2_theory_and_constraints,
    render_m3_theory,
    render_m4_theory,
    render_overview_theory,
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
    with st.expander("Tóm tắt lý thuyết 4 học phần từ Slides CO2011", expanded=False):
        render_overview_theory()


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


def logic_panel(result: dict, *, compact: bool = False, logic_data: dict | None = None) -> None:
    if result["satisfiable"]:
        st.success("SAT — Có lịch thỏa H1–H3. Chưa xét R1–R3 hoặc độ tối ưu.")
    else:
        st.error("UNSAT — Không thể thỏa đồng thời các ràng buộc dưới đây.")
    if compact:
        if not result["satisfiable"]:
            conflict_panel(result["unsat_core"])
        return

    outcome, bridge, theory_tab, lab_tab = st.tabs((
        "Kết quả SAT / UNSAT",
        "Đối chiếu Logic với 0/1",
        "Lý thuyết M1 (Slides)",
        "Thí nghiệm ràng buộc M1",
    ))
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
        with st.expander("Giải thích kết quả theo lý thuyết Logic", expanded=False):
            render_m1_result_guide(result)
    with bridge:
        a, b, c = st.columns(3)
        a.metric("Mệnh đề CNF", result["n_clauses"])
        b.metric("Biến phân công", result["n_assign_vars"], f"{result['n_aux_vars']} biến phụ", delta_color="off")
        c.metric("Ràng buộc tuyến tính 0/1", result["linear_rows"])
        st.markdown(r"$I$: tập giám thị; $J$: tập ca thi; $d_j$: số người cần cho ca $j$. "
                    r"$x_{ij}\in\{0,1\}$ bằng $1$ khi giám thị $i$ được xếp ca $j$. "
                    r"$P,N$: tập chỉ số literal dương và âm; $S$: tập mệnh đề cần đếm.")
        st.markdown(LOGIC_BRIDGE)
    with theory_tab:
        render_m1_theory()
    with lab_tab:
        _m1_experiment_tab(logic_data)


def _m1_experiment_tab(logic_data: dict | None) -> None:
    st.subheader("Thay đổi ràng buộc H1–H3 & quan sát SAT / UNSAT")
    if logic_data is None or not logic_data.get("session_ids"):
        st.info("Chưa có dữ liệu đầu vào để chạy thí nghiệm M1.")
        return

    sessions = [f"{c}_{cp}" for c, cp in logic_data["session_ids"]]
    staff_ids = logic_data["staff_ids"]
    demands = logic_data["shift_demands"]

    c1, c2 = st.columns(2)
    enforce_h1 = c1.checkbox("Áp dụng H1 (lịch bận Busy)", value=True, key="m1_exp_h1")
    enforce_h2 = c2.checkbox("Áp dụng H2 (không trùng giờ Overlap)", value=True, key="m1_exp_h2")

    c3, c4, c5 = st.columns((2, 1.5, 2.5))
    sess_idx = c3.selectbox(
        "Ca thi cần chỉnh",
        range(len(sessions)),
        format_func=lambda j: f"{sessions[j]} (nhu cầu {demands[j]})",
        key="m1_exp_sess",
    )
    demand_delta = c4.slider("Thay đổi nhu cầu Δd_j", -1, 3, 0, 1, key="m1_exp_delta")
    extra_busy_ids = c5.multiselect(
        "Báo bận thêm giám thị cho ca này",
        staff_ids,
        default=[],
        key="m1_exp_busy",
    )
    extra_idx = tuple(staff_ids.index(sid) for sid in extra_busy_ids)

    if st.button("Chạy thí nghiệm M1", type="primary", key="m1_exp_run"):
        try:
            with st.spinner("Đang giải lại SAT trên tập ràng buộc thử nghiệm…"):
                out = run_m1_what_if(
                    logic_data,
                    enforce_h1=enforce_h1,
                    enforce_h2=enforce_h2,
                    session_idx=sess_idx,
                    demand_delta=demand_delta,
                    extra_busy_staff=extra_idx,
                )
            st.session_state["iap_m1_exp"] = out
        except (ValueError, RuntimeError) as exc:
            st.error(f"Không chạy được thí nghiệm M1: {exc}")

    stored = st.session_state.get("iap_m1_exp")
    if stored is None:
        st.write("Bật/tắt H1–H2, tăng nhu cầu ca hoặc đánh dấu thêm giám thị bận rồi bấm **Chạy thí nghiệm M1** để so sánh.")
        return

    table(stored["comparison_rows"], {
        "metric": "Chỉ số kiểm chứng",
        "baseline": "Mô hình chuẩn",
        "experiment": "Thí nghiệm mới",
    })
    exp = stored["experiment"]
    if exp["satisfiable"]:
        ov = stored["orig_violations"]
        if ov["details"]:
            st.warning("Nghiệm SAT mới không còn hợp lệ trên ràng buộc gốc:")
            for msg in ov["details"]:
                st.write(f"- {msg}")
        else:
            st.success("Nghiệm SAT thử nghiệm vẫn thỏa 100% H1–H3 gốc.")
    else:
        st.error("Cấu hình thí nghiệm chuyển sang UNSAT.")
        conflict_panel(exp["unsat_core"])


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
    plan_tab, comparison_tab, theory_tab, lab_tab, ce_tab = st.tabs((
        "Lịch theo ca",
        "So sánh tải",
        "Lý thuyết & Ràng buộc cứng/mềm",
        "Thí nghiệm Seed & Ràng buộc",
        "Phản ví dụ (2.10)",
    ))
    with plan_tab:
        weekly_plan(inst, schedules[active], inspect=True)
    with comparison_tab:
        workload_comparison(inst, schedules[active], comparison)
    with theory_tab:
        render_m2_theory_and_constraints(inst)
    with lab_tab:
        _m2_experiment_tab(inst)
    with ce_tab:
        _m2_counterexample_tab(inst)


def _sync_m2_seed_preset() -> None:
    chosen = st.session_state.get("m2_exp_seed_preset")
    if chosen and chosen != "custom":
        st.session_state["m2_exp_seed"] = int(chosen)


def _m2_experiment_tab(inst) -> None:
    st.subheader("Đổi Seed, Ngưỡng K và Ràng buộc mềm → So sánh nghiệm ILP")
    st.session_state.setdefault("m2_exp_seed", int(inst.seed))

    preset_keys = ["custom", *SAMPLE_TEAM_SEEDS]
    c_pre, c_seed, c_k = st.columns((2.5, 1.5, 1))
    c_pre.selectbox(
        "Chọn nhanh Seed mẫu",
        preset_keys,
        format_func=lambda key: "Nhập tự do ở ô bên cạnh" if key == "custom" else SAMPLE_TEAM_SEEDS[key],
        key="m2_exp_seed_preset",
        on_change=_sync_m2_seed_preset,
    )
    custom_seed = int(c_seed.number_input("Seed thử nghiệm", min_value=0, step=1, key="m2_exp_seed"))
    max_day_load = max(4, max(map(len, inst.sessions_by_day.values()), default=4))
    default_k = min(3, max_day_load)
    if "m2_exp_k" in st.session_state:
        st.session_state["m2_exp_k"] = min(max(1, int(st.session_state["m2_exp_k"])), max_day_load)
    else:
        st.session_state["m2_exp_k"] = default_k
    fatigue_k = int(c_k.slider("Ngưỡng mệt mỏi ngày K", 1, max_day_load, key="m2_exp_k"))

    derived_w = derive_weights_from_seed(custom_seed)
    st.caption(
        f"Trọng số mềm sinh từ seed `{custom_seed}`: "
        f"λ_LOC = `{derived_w[0]:.2f}`, λ_FAT = `{derived_w[1]:.2f}`, λ_TRV = `{derived_w[2]:.2f}`."
    )

    use_soft = st.checkbox("Bật ràng buộc mềm (LOC, FAT, TRV) ở Giai đoạn 2", value=True, key="m2_exp_use_soft")
    s1, s2, s3 = st.columns(3)
    loc_scale = s1.slider("Hệ số nhân λ_LOC", 0.0, 3.0, 1.0, 0.25, disabled=not use_soft, key="m2_exp_loc")
    fat_scale = s2.slider("Hệ số nhân λ_FAT", 0.0, 3.0, 1.0, 0.25, disabled=not use_soft, key="m2_exp_fat")
    trv_scale = s3.slider("Hệ số nhân λ_TRV", 0.0, 3.0, 1.0, 0.25, disabled=not use_soft, key="m2_exp_trv")

    if st.button("Giải lại ILP & so sánh", type="primary", key="m2_exp_run"):
        try:
            with st.spinner("Đang giải CBC hai giai đoạn cho cấu hình chuẩn và thí nghiệm…"):
                out = run_m2_what_if(
                    inst,
                    custom_seed=custom_seed,
                    use_soft=use_soft,
                    fatigue_k=fatigue_k,
                    weight_scale=(loc_scale, fat_scale, trv_scale),
                    time_limit=15,
                )
            st.session_state["iap_m2_exp"] = out
        except (ValueError, RuntimeError, PulpSolverError) as exc:
            st.error(f"Không giải được thí nghiệm M2: {exc}")

    stored = st.session_state.get("iap_m2_exp")
    if stored is None:
        st.write("Đổi seed, bật/tắt ràng buộc mềm hoặc đổi ngưỡng K, rồi bấm **Giải lại ILP & so sánh** để xem bảng chênh lệch.")
        return

    st.success(f"Hoàn tất giải đối chiếu trong {stored['runtime_s']} giây (trạng thái thí nghiệm: {stored['exp_status']}).")
    table(stored["comparison_rows"], {
        "indicator": "Chỉ số đánh giá",
        "standard": "Mô hình chuẩn",
        "experiment": "Thí nghiệm mới",
        "delta": "Chênh lệch",
    })


def _m2_counterexample_tab(inst) -> None:
    st.subheader("Chứng minh phản ví dụ mô hình sai (Mục 2.10)")
    kind = st.radio(
        "Chọn mô hình sai cần kiểm chứng",
        ("h2_drop", "lp_relax"),
        format_func={
            "h2_drop": "(a) Bỏ ràng buộc không trùng giờ H2 (drop_overlap=True)",
            "lp_relax": "(b) Thư giãn biến nhị phân sang LP liên tục (relax_integrality=True)",
        }.__getitem__,
        horizontal=True,
        key="m2_ce_kind",
    )
    if kind == "h2_drop":
        c1, c2 = st.columns(2)
        scope = c1.radio(
            "Phạm vi dữ liệu",
            ("canonical_9day", "current_instance"),
            format_func={
                "canonical_9day": "Lát cắt 9 ngày chuẩn (flip_rate=0, có trùng giờ ràng buộc)",
                "current_instance": "Bộ dữ liệu / lát cắt đang chọn",
            }.__getitem__,
            key="m2_ce_h2_scope",
        )
        use_soft = c2.checkbox("Giữ các khoản phạt mềm (gồm TRV)", value=False, key="m2_ce_h2_soft")
        if st.button("Chạy phản ví dụ bỏ H2", type="primary", key="m2_ce_h2_run"):
            try:
                with st.spinner("Đang giải so sánh mô hình đúng và mô hình bỏ H2…"):
                    st.session_state["iap_m2_ce"] = ("h2", run_m2_counterexample_h2(inst, mode=scope, use_soft=use_soft))
            except (ValueError, RuntimeError, PulpSolverError) as exc:
                st.error(f"Không chạy được phản ví dụ H2: {exc}")
    else:
        scope = st.radio(
            "Phạm vi dữ liệu",
            ("brief_example", "current_instance"),
            format_func={
                "brief_example": "Ví dụ đề bài (3 giám thị, 4 ca nối tiếp)",
                "current_instance": "Bộ dữ liệu / lát cắt đang chọn",
            }.__getitem__,
            key="m2_ce_lp_scope",
        )
        if st.button("Chạy phản ví dụ LP relaxation", type="primary", key="m2_ce_lp_run"):
            try:
                with st.spinner("Đang giải bài toán thư giãn LP và đối chiếu nghiệm nguyên ILP…"):
                    st.session_state["iap_m2_ce"] = ("lp", run_m2_counterexample_lp(inst, mode=scope))
            except (ValueError, RuntimeError, PulpSolverError) as exc:
                st.error(f"Không chạy được phản ví dụ LP: {exc}")

    stored = st.session_state.get("iap_m2_ce")
    if stored is None:
        st.write("Chọn loại phản ví dụ và bấm nút chạy để xem lịch sai cụ thể mà mô hình sai chấp nhận.")
        return

    stored_kind, data = stored
    if stored_kind == "h2":
        if not data["has_example"]:
            st.warning(data["note"])
            return
        st.info(data["note"])
        table(data["comparison_rows"], {
            "model": "Mô hình",
            "t_star": "Tải đỉnh t*",
            "l1": "Độ lệch L1",
            "spread": "Chênh lệch tải",
            "violations": "Số vi phạm H1–H3",
        })
        if data["double_booked"]:
            st.warning("Các trường hợp bị phân công trùng giờ đồng thời:")
            table(data["double_booked"], {
                "staff": "Giám thị",
                "session_a": "Ca thứ nhất",
                "time_a": "Giờ ca 1",
                "session_b": "Ca thứ hai",
                "time_b": "Giờ ca 2",
            })
        if data["validator"]:
            with st.expander("Thông báo từ bộ kiểm tra độc lập (check_schedule)"):
                for msg in data["validator"]:
                    st.write(f"- {msg}")
    else:
        st.info(f"Bài toán: {data['instance']} — Nghiệm thư giãn LP cho Z_LP = {data['z_lp']} "
                f"(chặn dưới) trong khi nghiệm nguyên ILP phải cần Z_ILP = {data['z_ilp']}; "
                f"có {data['fractional_pairs']} biến x_ij bị chia lẻ phân số.")
        if data["mode"] == "brief_example":
            table(data["matrix_rows"], {
                "staff_id": "Giám thị",
                "S1": "S1",
                "S2": "S2",
                "S3": "S3",
                "S4": "S4",
                "lp_load": "Tổng tải LP",
            })
        elif data["matrix_rows"]:
            table(data["matrix_rows"], {
                "staff_id": "Giám thị",
                "session_id": "Ca thi",
                "lp_value": "Giá trị x_ij (LP)",
                "fraction": "Dạng phân số",
            })
        if data["rounded_violations"]:
            st.warning("Làm tròn x_ij > 0.5 lập tức phá vỡ ràng buộc H3:")
            for msg in data["rounded_violations"][:10]:
                st.write(f"- {msg}")


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


def m3_theory_tab() -> None:
    """Render Module 3 slide theory tab."""
    render_m3_theory()


def m3_rules_experiment_tab(inst, schedules: dict, active: str, time_limit: int) -> None:
    """Interactive experiment altering R1/R2/R3/R4 DFA parameters and re-auditing or re-solving."""
    st.subheader("Thay đổi điều kiện DFA (R1–R4) & kiểm chứng lại lịch")
    c1, c2, c3, c4 = st.columns(4)
    use_r1 = c1.checkbox("Bật R1 (liên tiếp)", value=True, key="m3_exp_use_r1")
    r1_max = int(c1.slider("R1: tối đa ngày liền", 1, 5, 2, disabled=not use_r1, key="m3_exp_r1_k"))
    use_r2 = c2.checkbox("Bật R2 (nghỉ sau ca N)", value=True, key="m3_exp_use_r2")
    use_r3 = c3.checkbox("Bật R3 (cửa sổ lăn)", value=True, key="m3_exp_use_r3")
    r3_win = int(c3.slider("R3: cửa sổ (ngày)", 4, 7, 7, disabled=not use_r3, key="m3_exp_r3_w"))
    if "m3_exp_r3_k" in st.session_state:
        st.session_state["m3_exp_r3_k"] = min(max(1, int(st.session_state["m3_exp_r3_k"])), r3_win)
    else:
        st.session_state["m3_exp_r3_k"] = min(4, r3_win)
    r3_max = int(c3.slider("R3: tối đa ngày làm", 1, r3_win, disabled=not use_r3, key="m3_exp_r3_k"))
    use_r4 = c4.checkbox("Bật thêm R4 (|#M−#A|≤c)", value=False, key="m3_exp_use_r4")
    r4_c = int(c4.slider("R4: ngưỡng lệch c", 1, 5, 3, disabled=not use_r4, key="m3_exp_r4_c"))

    try:
        audit = evaluate_custom_automata(
            inst,
            schedules[active],
            enforce_r1=use_r1,
            max_consecutive=r1_max,
            enforce_r2=use_r2,
            enforce_r3=use_r3,
            max_work=r3_max,
            window=r3_win,
            enforce_r4=use_r4,
            r4_bound=r4_c,
        )
    except ValueError as exc:
        st.warning(str(exc))
        return

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Trạng thái tích (chưa tối giản)", audit["product_states"])
    m2.metric("Trạng thái tối giản (Myhill–Nerode)", audit["minimal_states"])
    m3.metric("Chuỗi đạt chuẩn R1–R3", f"{audit['std_accepted']}/{audit['total_staff']}")
    m4.metric("Chuỗi đạt bộ thử nghiệm", f"{audit['custom_accepted']}/{audit['total_staff']}")

    table(audit["per_rule_counts"], {
        "rule": "Quy tắc trong thí nghiệm",
        "dfa_states": "Số trạng thái DFA",
        "accepted_staff": "Số người đạt",
        "rejected_staff": "Số người vi phạm",
    })

    if audit["changed_rows"]:
        st.subheader(f"{len(audit['changed_rows'])} giám thị đổi kết quả so với chuẩn R1(2)·R2·R3(4/7)")
        table(audit["changed_rows"], {
            "staff_id": "Giám thị",
            "roster_string": "Chuỗi ngày",
            "standard_r123": "Chuẩn R1–R3",
            "custom_rules": "Bộ thử nghiệm",
            "broken_custom": "Lỗi ở bộ thử nghiệm",
        })
    else:
        st.info("Tập giám thị đạt/vi phạm giống với bộ chuẩn R1–R3 (hoặc hãy siết/nới k1, k3, bật R4 để thấy sự dịch chuyển).")

    if st.button("Giải lại ILP theo bộ DFA tùy chỉnh (trên lát cắt nhỏ)", type="primary", key="m3_exp_solve_btn"):
        try:
            with st.spinner("Đang dựng đồ thị phân tầng và giải ILP với DFA tùy chỉnh…"):
                res = solve_with_custom_automata(inst, audit["minimal_dfa"], time_limit=time_limit)
            st.session_state["iap_m3_exp_solve"] = res
        except (ValueError, RuntimeError, PulpSolverError) as exc:
            st.warning(str(exc))

    solved = st.session_state.get("iap_m3_exp_solve")
    if solved is not None:
        if not solved["assigned"]:
            st.error(f"ILP với bộ DFA mới chưa tìm thấy lịch khả thi (trạng thái: {solved['status']}).")
        else:
            sm = solved["metrics"]
            st.success(
                f"Giải lại ILP thành công ({solved['status']}): {solved['accepted']}/{solved['total_staff']} giám thị đạt DFA mới · "
                f"Tải đỉnh = {sm['max_load']} · L1 = {sm['l1']:.2f} · Phạt cơ sở = {sm['location']}."
            )


def pumping_lemma_tab() -> None:
    """Interactive Pumping Lemma contradiction workbench for L' = {M^n A^n}."""
    st.subheader("Chứng minh phi chính quy bằng Bổ đề bơm (Pumping Lemma)")
    st.markdown(
        r"Xét quy tắc cân bằng chính xác $L=\{w\in\Sigma^*:\#_M(w)=\#_A(w)\}$. "
        r"Giao với ngôn ngữ chính quy $M^*A^*$ thu được $L'=L\cap M^*A^*=\{M^nA^n:n\ge 0\}$. "
        r"Chọn độ dài bơm $p$, cách chia $s=M^pA^p=xyz$ ($|xy|\le p,\;|y|\ge 1$) và hệ số bơm $i$ để kiểm chứng mâu thuẫn $xy^iz\notin L'$."
    )
    c1, c2, c3, c4 = st.columns(4)
    p = int(c1.slider("Độ dài bơm giả định p", 2, 8, 3, key="pump_p"))
    if "pump_x_len" in st.session_state:
        st.session_state["pump_x_len"] = min(max(0, int(st.session_state["pump_x_len"])), p - 1)
    else:
        st.session_state["pump_x_len"] = 0
    x_len = int(c2.slider("Độ dài tiền tố |x|", 0, p - 1, key="pump_x_len"))
    max_y = p - x_len
    if "pump_y_len" in st.session_state:
        st.session_state["pump_y_len"] = min(max(1, int(st.session_state["pump_y_len"])), max_y)
    else:
        st.session_state["pump_y_len"] = 1
    y_len = int(c3.slider("Độ dài phần bơm |y|", 1, max_y, key="pump_y_len"))
    pump_i = int(c4.slider("Số lần lặp i trong x y^i z", 0, 4, 0, key="pump_i"))

    r4_c = int(st.slider("Đối chiếu với quy tắc chính quy R4: |#M − #A| ≤ c", 1, 5, 3, key="pump_r4_c"))
    res = pumping_lemma_demo(p, x_len, y_len, pump_i, r4_bound=r4_c)

    st.markdown(
        '<div class="iap-pump-row" aria-label="Phân tách s = x y z">'
        f'<span class="iap-pump-seg iap-pump-x"><span class="iap-pump-tag">x</span>{escape(res["x"] or "ε")}</span>'
        f'<span class="iap-pump-seg iap-pump-y"><span class="iap-pump-tag">y</span>{escape(res["y"])}</span>'
        f'<span class="iap-pump-seg iap-pump-z"><span class="iap-pump-tag">z</span>{escape(res["z"])}</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f"**Chuỗi sau khi bơm ($i={pump_i}$):** `{res['pumped'] or 'ε'}` &nbsp;·&nbsp; "
        f"$\\#_M = {res['m_count']}$, $\\#_A = {res['a_count']}$, hiệu $\\#_M - \\#_A = {res['diff_m_a']:+d}$."
    )
    if res["contradiction"]:
        st.error(
            f"Mâu thuẫn Pumping Lemma! Vì |xy| = {res['xy_len']} ≤ p = {p} nên y = '{res['y']}' toàn chữ M. "
            f"Khi bơm i = {pump_i}, số M ({res['m_count']}) ≠ số A ({res['a_count']}) nên xy^{pump_i}z ∉ L'. "
            "Suy ra L không thể là ngôn ngữ chính quy."
        )
    else:
        st.info("Khi i = 1 ta thu lại đúng chuỗi gốc s = xyz ∈ L'. Hãy đổi i = 0 hoặc i ≥ 2 để quan sát mâu thuẫn.")

    table([
        {"check": "Điều kiện 1: |xy| ≤ p", "value": f"|xy| = {res['xy_len']} ≤ {p} → Đạt"},
        {"check": "Điều kiện 2: |y| ≥ 1", "value": f"|y| = {len(res['y'])} ≥ 1 → Đạt"},
        {"check": f"Điều kiện 3: xy^{pump_i}z ∈ L'", "value": "Thuộc L'" if res["in_l_prime"] else "KHÔNG thuộc L' (Mâu thuẫn!)"},
        {"check": f"R4 hữu hạn (|#M−#A| ≤ {r4_c}, {res['r4_states']} trạng thái)", "value": (
            f"Chuỗi s: {'Chấp nhận' if res['r4_accepts_s'] else 'Từ chối'} | "
            f"Chuỗi bơm: {'Chấp nhận' if res['r4_accepts_pumped'] else 'Từ chối'}"
        )},
    ], {"check": "Bước kiểm tra", "value": "Kết quả"})


M4_REGIMES = {
    "custom": "Tùy chỉnh tự do bằng thanh trượt",
    "calibrated": "Hiệu chuẩn từ dữ liệu khoa (a≈0.2706, b=1-a, r=0)",
    "slow_stable": "Ổn định chậm (a=0.80, b=0.20, r=0)",
    "neutral": "Trung hòa / cộng dồn biên (a=1.00, b=1.00, r=0)",
    "oscillating": "Dao động không tắt (a=-1.00, b=1.00, r=0)",
    "unstable": "Mất ổn định / phân kỳ (a=1.08, b=0.50, r=0)",
    "with_rest": "Có hồi phục nghỉ ngơi (a=0.60, b=0.40, r=0.25, ρ=1.0)",
}


def _apply_m4_regime(base_a: float, base_b: float, base_r: float) -> None:
    choice = st.session_state.get("m4_exp_regime")
    presets = {
        "calibrated": (round(base_a, 4), round(base_b, 4), round(base_r, 4), 0.0),
        "slow_stable": (0.80, 0.20, 0.0, 0.0),
        "neutral": (1.00, 1.00, 0.0, 0.0),
        "oscillating": (-1.00, 1.00, 0.0, 0.0),
        "unstable": (1.08, 0.50, 0.0, 0.0),
        "with_rest": (0.60, 0.40, 0.25, 1.0),
    }
    if choice in presets:
        a_v, b_v, r_v, rest_v = presets[choice]
        st.session_state["m4_exp_a"] = a_v
        st.session_state["m4_exp_b"] = b_v
        st.session_state["m4_exp_r"] = r_v
        st.session_state["m4_exp_rest"] = rest_v


def _m4_experiment_tab(inst, schedules: dict, active: str, parameters: dict, weeks: int, index: int, shock: float) -> None:
    st.subheader("Thay đổi hệ số (a, b, r, ρ) và độ phủ ngưỡng H")
    st.session_state.setdefault("m4_exp_a", round(float(parameters["a"]), 4))
    st.session_state.setdefault("m4_exp_b", round(float(parameters["b"]), 4))
    st.session_state.setdefault("m4_exp_r", round(float(parameters["r"]), 4))
    st.session_state.setdefault("m4_exp_rest", 0.0)

    st.selectbox(
        "Chế độ động lực mẫu",
        list(M4_REGIMES),
        format_func=M4_REGIMES.__getitem__,
        key="m4_exp_regime",
        on_change=_apply_m4_regime,
        args=(parameters["a"], parameters["b"], parameters["r"]),
    )
    c1, c2, c3, c4, c5 = st.columns(5)
    exp_a = float(c1.slider("Quán tính a", -1.15, 1.15, step=0.02, key="m4_exp_a"))
    exp_b = float(c2.slider("Tác động tải b", 0.0, 1.5, step=0.05, key="m4_exp_b"))
    exp_r = float(c3.slider("Hệ số nghỉ r", 0.0, 1.0, step=0.05, key="m4_exp_r"))
    exp_rest = float(c4.slider("Mức nghỉ ρ", 0.0, 2.0, step=0.25, key="m4_exp_rest"))
    cov = float(c5.slider("Độ phủ ngưỡng H", 0.50, 0.99, 0.95, 0.01, key="m4_exp_cov"))

    out = run_m4_what_if(
        inst,
        schedules,
        active,
        a=exp_a,
        b=exp_b,
        r=exp_r,
        rest_rate=exp_rest,
        coverage=cov,
        weeks=weeks,
        shock_staff_index=index,
        shock_amount=shock,
    )
    table(out["comparison_rows"], {
        "metric": "Đại lượng đối chiếu",
        "standard": "Mô hình chuẩn",
        "experiment": "Thí nghiệm tham số mới",
    })
    st.caption(out["history_note"])

    left, right = st.columns(2)
    with left:
        st.markdown("**So sánh quỹ đạo cá nhân**")
        st.line_chart(
            out["trajectory_df"],
            x="Tuần",
            y=["Mô hình chuẩn", "Mô hình thí nghiệm"],
            y_label="Fatigue proxy",
            color=["#1b61c9", "#ad6123"],
            height=290,
        )
    with right:
        st.markdown("**So sánh chênh lệch toàn đội (max − min)**")
        st.line_chart(
            out["spread_df"],
            x="Tuần",
            y=["Spread chuẩn", "Spread thí nghiệm"],
            y_label="Spread",
            color=["#076658", "#803a11"],
            height=290,
        )


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
        trajectory_tab, fairness_tab, model_tab, history_tab, exp_tab = st.tabs(
            ("Quỹ đạo cá nhân", "Công bằng toàn đội", "Mô hình và công thức", "Tải lịch sử", "Thí nghiệm tham số (a, b, r, H)"),
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
        render_m4_theory(parameters, dyn["threshold"])
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
    with exp_tab:
        _m4_experiment_tab(inst, schedules, active, parameters, weeks, index, shock)
