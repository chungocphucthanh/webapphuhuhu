"""Trang 1 · Logic (Vinh): vị từ, CNF, SAT / UNSAT core, cầu nối sang ILP."""

from __future__ import annotations

import re
from html import escape
from math import comb

import streamlit as st
from pysat.card import CardEnc, EncType

from app import services
from app.ui import charts, parts
from app.ui.stage import Idea, Module, render_module
from app.ui.theme import vn


def _session(code: str, campus: str) -> str:
    match = re.fullmatch(r"\d{4}(\d{2})(\d{2})_(\d+)", code)
    return f"{match[2]}/{match[1]} ca {match[3]} {campus}" if match else code


def fig_predicates() -> None:
    data, _ = services.m1_case("Lát cắt · UNSAT")
    names = [_session(*s) for s in data["session_ids"]]
    i, j = data["busy"][0]
    a, b = data["overlaps"][0]
    parts.table(["Luật", "Công thức", "Ví dụ trên lát dữ liệu thật"], [
        ("H1 · Khả dụng", "Busy(i, j) → ¬Assign(i, j)", f"{data['staff_ids'][i]} bận ở {names[j]}"),
        ("H2 · Không trùng ca", "Overlap(j, k) ∧ Assign(i, j) → ¬Assign(i, k)", f"{names[a]} và {names[b]} cùng giờ"),
        ("H3 · Đủ định ngạch", "đúng d_j cán bộ i có Assign(i, j)", f"{names[0]} cần {data['shift_demands'][0]} người"),
    ], ("", "mono", ""))
    parts.text("cap", "Assign(i, j): cán bộ i coi ca j. Overlap đối xứng và không phản xạ.")


@st.cache_data(show_spinner=False)
def _encoding_sizes(d: int = 4) -> list[dict]:
    """Clauses for «exactly d of n»: binomial encoding by formula, sequential counter as M1 builds it."""
    rows = []
    for n in (10, 20, 40, 73):
        counter = CardEnc.equals(lits=list(range(1, n + 1)), bound=d, encoding=EncType.seqcounter)
        rows += [{"n": n, "Mệnh đề": comb(n, d + 1) + comb(n, n - d + 1), "Mã hóa": "Liệt kê tổ hợp"},
                 {"n": n, "Mệnh đề": len(counter.clauses), "Mã hóa": "Sequential counter"}]
    return rows


def fig_encoding() -> None:
    rows = _encoding_sizes()
    parts.text("lab", "Số mệnh đề để viết «đúng 4 trong n người» (trục dọc logarit)")
    charts.column_chart(rows, "n", "Mệnh đề", "Mã hóa", height=150, x_title="số cán bộ n", y_title="", log=True)
    parts.text("cap", f"Với n = 73: liệt kê tổ hợp cần {vn(rows[-2]['Mệnh đề'], 0)} mệnh đề, "
                      f"sequential counter cần {vn(rows[-1]['Mệnh đề'], 0)}.")


def fig_sat() -> None:
    parts.cards([("BƯỚC 1", "CNF", "H1, H2, H3 thành mệnh đề", False), ("BƯỚC 2", "Minisat22", "SAT solver", True),
                 ("SAT", "Một lịch làm nghiệm", "mỗi biến đúng là một lượt phân công", False),
                 ("UNSAT", "Lõi bất khả thỏa cực tiểu", "bỏ một ràng buộc là thỏa được", False)])
    parts.lines(("H1  Busy(i, j) → ¬Assign(i, j)", "H2  Overlap(j, k) ∧ Assign(i, j) → ¬Assign(i, k)",
                 "H3  mỗi ca j có đúng định ngạch d_j"))


# Row of M1's CONVERSION_ROWS -> the label shown on the slide.
BRIDGE = {"H1 Availability": "H1 · Khả dụng", "H2 No double-booking": "H2 · Không trùng ca",
          "H3 Exact capacity": "H3 · Đủ định ngạch", "Clause a v b": "a hoặc b", "Exactly-one": "Đúng một trong S"}


def fig_bridge() -> None:
    rows = services.m1_case("Toy · SAT")[1]["bridge_rows"]
    parts.table(["Luật", "Mệnh đề", "Ràng buộc tuyến tính 0/1"],
                [(BRIDGE[r["rule"]], r["clause"], r["linear"]) for r in rows if r["rule"] in BRIDGE], ("", "mono", "mono"))


def _grid(data: dict, result: dict) -> str:
    labels = [f"{code}_{campus}" for code, campus in data["session_ids"]]
    core = result["unsat_core"] or []
    hot = {j for j, label in enumerate(labels) if any(item.startswith(f"capacity({label})") for item in core)}
    picked = {(person, j) for j, label in enumerate(labels) for person in (result["model"] or {}).get(label, [])}
    busy = set(map(tuple, data["busy"]))
    cells = ['<span class="h">Cán bộ</span>'] + [
        f'<span class="h">{escape(_session(*s))}<br>cần {d}</span>' for s, d in zip(data["session_ids"], data["shift_demands"])]
    for i, person in enumerate(data["staff_ids"]):
        cells.append(f'<span class="h">{escape(person)}</span>')
        for j in range(len(labels)):
            kind = "pick" if (person, j) in picked else "busy" if (i, j) in busy else ""
            text = {"pick": "xếp", "busy": "bận"}.get(kind, "")
            cells.append(f'<span class="{kind}{" hot" if j in hot and kind == "busy" else ""}">{text}</span>')
    return (f'<div class="iap-grid" style="grid-template-columns:72px repeat({len(labels)},minmax(0,1fr))">'
            + "".join(cells) + "</div>")


def lab() -> None:
    title, presets, run = st.columns((2, 5, 1.2))
    with title:
        parts.text("h2", "Thử ngay: đổi kịch bản")
    with presets:
        st.session_state.setdefault("m1_case", "Lát cắt · UNSAT")
        label = st.radio("Kịch bản", list(services.M1_CASES), key="m1_case", horizontal=True, label_visibility="collapsed")
    if run.button("Chạy SAT", type="primary", key="m1_run_button", use_container_width=True):
        services.m1_case.clear()  # drop the cached answer so Minisat22 runs again
    with st.spinner("Đang mã hóa CNF và chạy Minisat22…"):
        data, result = services.m1_case(label)
    grid, status, size = st.columns((1.5, 1.2, 1))
    with grid:
        parts.html(_grid(data, result))
        parts.text("cap", "Ô xanh: được xếp. Ô xám: Busy(i, j), không được xếp.")
    with status:
        if result["satisfiable"]:
            parts.verdict("good", "SAT: có lịch", f"{result['n_sessions']} ca đều đủ người, không ai trùng giờ.")
            parts.text("lab", "Nghiệm SAT")
            parts.lines(f"{session}: {', '.join(people)}" for session, people in list(result["model"].items())[:5])
        else:
            core = result["unsat_core"]
            parts.verdict("bad", "UNSAT: không thể xếp", "Các ràng buộc dưới đây không thể cùng thỏa.")
            parts.text("lab", f"Lõi UNSAT cực tiểu · {len(core)} ràng buộc")
            parts.lines(core[:6] + (["…"] if len(core) > 6 else []))
    with size:
        parts.text("lab", "Cùng bài toán, hai cách viết")
        parts.hbars([("CNF", result["n_clauses"], f"{result['n_clauses']} mệnh đề"),
                     ("Tuyến tính 0/1", result["linear_rows"], f"{result['linear_rows']} dòng")], width=90)
        parts.text("cap", f"{result['n_assign_vars']} biến phân công · {result['n_cnf_vars']} biến CNF · "
                          f"Minisat22 chạy {vn(result['runtime_ms'])} ms")


MODULE = Module(
    key="m1", label="Module 1 · Logic", presenter="Vinh", start=2, lab=lab,
    fn=("encode_invigilator_assignment()", "solve_instance()", "extract_minimal_core()"),
    ds=("Sequential counter", "Deletion-based MUS"),
    bigo=("encode · Space: O(n·D)", "core · Time: O(k²) lần gọi SAT"),
    note="n: số cán bộ · D: tổng định ngạch · k: kích thước lõi ban đầu",
    ideas=(
        Idea("Luật thành vị từ", "Mỗi luật coi thi là một ", "công thức vị từ", ".",
             "Assign, Busy, Overlap và lượng từ ∀ trên cán bộ, ca thi",
             (("Mỗi cặp người–ca là một biến", "Assign(i, j) đúng nghĩa là cán bộ i coi ca j."),
              ("H1, H2 là luật cấm", "Bận thì không xếp; hai ca trùng giờ không cùng một người."),
              ("H3 là luật đếm", "Mỗi ca có đúng định ngạch.")), fig_predicates),
        Idea("Mã hóa CNF", "Đếm đúng d người: ", "không bùng nổ tổ hợp", ".",
             "H3 dùng sequential counter của CardEnc: thêm biến phụ thay vì liệt kê tổ hợp",
             (("Mỗi biến một số", "Assign(i, j) = i·M + j + 1"),
              ("Liệt kê tổ hợp", "C(n, d+1) + C(n, n−d+1) mệnh đề: bùng nổ theo n."),
              ("Sequential counter", "Khoảng 4·n·d mệnh đề, đổi lại có biến phụ.")), fig_encoding),
        Idea("SAT và UNSAT core", "SAT trả về một lịch. UNSAT trả về ", "lõi bất khả thỏa cực tiểu", ".",
             "Minisat22 trên CNF của ba luật cứng H1, H2, H3",
             (("SAT: có nghiệm", "Mỗi biến đúng là một lượt phân công."),
              ("UNSAT: có lõi", "Một tập ràng buộc nhỏ không thể cùng thỏa."),
              ("Lõi là cực tiểu", "Bỏ một ràng buộc bất kỳ trong lõi thì thỏa được.")), fig_sat),
        Idea("Cầu nối sang ILP", "Luật đếm: một ", "đẳng thức", " thay cho hàng chục mệnh đề.",
             "Mỗi clause thành một bất đẳng thức 0/1; luật đếm thành một đẳng thức",
             (("Clause thành bất đẳng thức", "a ∨ b thành x_a + x_b ≥ 1."),
              ("Luật đếm thành đẳng thức", "Đúng d người: Σ x_ij = d_j, không cần biến phụ."),
              ("Đầu vào Module 2", "H1, H2, H3 đi thẳng vào mô hình ILP.")), fig_bridge),
    ),
)


def render() -> None:
    render_module(MODULE)
