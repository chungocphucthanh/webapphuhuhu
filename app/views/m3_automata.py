"""Trang 3 · Automata (Phúc): chuỗi ngày, DFA, tích và tối giản, DFA trong ILP, ranh giới chính quy."""

from __future__ import annotations

import streamlit as st

from app import services
from app.ui import charts, parts
from app.ui.stage import Idea, Module, render_module

PRESETS = {"Hợp lệ": "MM--A-N-M", "3 ngày liền": "A-MMM--", "Tối xong vẫn làm": "M-NA---",
           "5 ngày trong tuần": "MM-MM-M", "CB003 · lịch gốc": "-N---A--NNNN---N-----M----A"}
MAX_DAYS = 60

DFA_R1 = """<svg role="img" aria-label="DFA của luật R1 gồm run0, run1, run2 và trạng thái bẫy dead" viewBox="0 0 560 256" style="display:block;width:100%;max-width:470px;height:auto;margin:0 auto">
<defs><marker id="h" orient="auto" markerWidth="5" markerHeight="5" refX="2" refY="2" overflow="visible"><path d="M0 0 L4 2 L0 4 Z" fill="#5E6C84"/></marker>
<marker id="hh" orient="auto" markerWidth="5" markerHeight="5" refX="2" refY="2" overflow="visible"><path d="M0 0 L4 2 L0 4 Z" fill="#B97A00"/></marker></defs>
<g fill="none" stroke="#5E6C84" stroke-width="2" stroke-linecap="round"><path d="M14 130 L45 130" marker-end="url(#h)"/><path d="M66 104 C 38 48, 122 48, 96 100" marker-end="url(#h)"/><path d="M486 104 C 458 48, 542 48, 516 100" marker-end="url(#h)"/><path d="M207 157 Q 150 207 96 160" marker-end="url(#h)"/><path d="M347 157 Q 207 287 70 160" marker-end="url(#h)"/></g>
<g fill="none" stroke="#B97A00" stroke-width="3" stroke-linecap="round"><path d="M110 130 L184 130" marker-end="url(#hh)"/><path d="M250 130 L324 130" marker-end="url(#hh)"/><path d="M390 130 L464 130" marker-end="url(#hh)"/></g>
<g fill="#FFFFFF" stroke="#256ABF" stroke-width="2"><circle cx="80" cy="130" r="30"/><circle cx="80" cy="130" r="24"/><circle cx="220" cy="130" r="30"/><circle cx="220" cy="130" r="24"/><circle cx="360" cy="130" r="30"/><circle cx="360" cy="130" r="24"/><circle cx="500" cy="130" r="30" fill="#FCEBEA" stroke="#C0362C"/></g>
<g font-family="Consolas, monospace" font-size="13" font-weight="600" text-anchor="middle" fill="#0E1726"><text x="80" y="135">run0</text><text x="220" y="135">run1</text><text x="360" y="135">run2</text><text x="500" y="135" fill="#A12A2A">dead</text></g>
<g font-family="Consolas, monospace" font-size="13" text-anchor="middle" fill="#44516A"><text x="148" y="120">M, A, N</text><text x="288" y="120">M, A, N</text><text x="428" y="120">M, A, N</text><text x="81" y="46">-</text><text x="501" y="46">M, A, N, -</text><text x="150" y="201">-</text><text x="207" y="246">-</text></g></svg>"""


def fig_strings() -> None:
    rows = services.temporal("Baseline")["staff_rows"][:6]
    parts.text("lab", "Sáu cán bộ đầu của lịch gốc, mỗi ô một ngày")
    parts.roster([(row["staff_id"], row["roster_string"]) for row in rows])
    parts.text("cap", "M sáng · A chiều · N tối · - nghỉ. Ngày có hai ca lấy ký hiệu ưu tiên cao hơn.")


def fig_dfa() -> None:
    parts.html(DFA_R1)
    parts.text("cap", "Vòng kép là trạng thái chấp nhận. dead là trạng thái bẫy.")


def fig_minimize() -> None:
    rows = []
    for label, reachable, minimal in services.suite()["counts_table"]:
        name = label.replace(" x ", "×")
        rows += [{"DFA": name, "Trạng thái": reachable, "Loại": "Tới được"},
                 {"DFA": name, "Trạng thái": minimal, "Loại": "Tối giản"}]
    parts.text("lab", "Số trạng thái trước và sau tối giản (trục dọc logarit)")
    charts.column_chart(rows, "DFA", "Trạng thái", "Loại", height=164, x_title="", y_title="", log=True,
                        sort=list(dict.fromkeys(row["DFA"] for row in rows)))


def fig_flow() -> None:
    """R1 unfolded over the word A-MM-: one node per (day, state), the accepted path highlighted."""
    states, word, dfa = ("run0", "run1", "run2"), "A-MM-", services.suite()["rules"]["R1"]
    x = lambda t: 70 + 86 * t
    y = lambda q: 40 + 62 * states.index(q)
    edges, path, q = [], [], dfa.start
    for t in range(len(word)):
        for p in states:
            for a in ("M", "-"):
                target = dfa.transitions[p][a]
                if target in states:
                    edges.append(f'<line x1="{x(t)}" y1="{y(p)}" x2="{x(t + 1)}" y2="{y(target)}" stroke="#D5DBE4" stroke-width="1.5"/>')
        target = dfa.transitions[q][word[t]]
        path.append(f'<line x1="{x(t)}" y1="{y(q)}" x2="{x(t + 1)}" y2="{y(target)}" stroke="#B97A00" stroke-width="3"/>'
                    f'<text x="{(x(t) + x(t + 1)) / 2}" y="{(y(q) + y(target)) / 2 - 7}" text-anchor="middle" '
                    f'font-family="Consolas, monospace" font-size="13" font-weight="600" fill="#7A4A00">{word[t]}</text>')
        q = target
    nodes = "".join(f'<circle cx="{x(t)}" cy="{y(p)}" r="7" fill="#FFFFFF" stroke="#256ABF" stroke-width="2"/>'
                    for t in range(len(word) + 1) for p in states)
    labels = "".join(f'<text x="8" y="{y(p) + 4}" font-family="Consolas, monospace" font-size="12" fill="#44516A">{p}</text>' for p in states)
    days = "".join(f'<text x="{x(t)}" y="196" text-anchor="middle" font-size="11" fill="#5E6C84">ngày {t}</text>' for t in range(len(word) + 1))
    parts.html(f'<svg role="img" aria-label="Đồ thị phân tầng của R1 trên 5 ngày; đường tô nổi là chuỗi A-MM-" viewBox="0 0 520 204" '
               f'style="display:block;width:100%;max-width:500px;height:auto;margin:0 auto">{"".join(edges)}{"".join(path)}{nodes}{labels}{days}</svg>')
    parts.text("cap", "Mỗi nút là (ngày, trạng thái). Một đơn vị luồng đi từ run0 tới trạng thái chấp nhận là một lịch hợp lệ; cạnh vào dead bị bỏ.")


def fig_boundary() -> None:
    cells = "".join(f'<span class="{"" if d else "pick"}">{f"{d:+d}" if d else "0"}</span>' for d in range(-3, 4))
    parts.text("lab", "R4 · lệch |#M − #A| ≤ 3: bộ đếm hữu hạn 7 trạng thái và 1 bẫy")
    parts.html(f'<div class="iap-grid" style="grid-template-columns:repeat(8,minmax(0,1fr));max-width:420px">{cells}'
               '<span class="busy hot">dead</span></div>')
    parts.text("cap", "M sang phải, A sang trái; vượt ±3 thì rơi vào dead.")
    parts.text("lab", "#M = #A: bơm phần M của MᵖAᵖ làm lệch số đếm")
    parts.text("mono", "MMMM AAAA  →  bơm y = M  →  MMMMM AAAA  ∉ L")
    counts = services.temporal("Baseline")["rule_violations"]
    parts.text("cap", f"Trên lịch gốc, R4 từ chối {counts['R4_prefix']} trên 73 chuỗi.")


def _use(word: str) -> None:
    st.session_state["m3_word"] = word


def lab() -> None:
    title, presets = st.columns((2, 6))
    with title:
        parts.text("h2", "Thử ngay: gõ một chuỗi ngày")
    st.session_state.setdefault("m3_word", PRESETS["CB003 · lịch gốc"])
    with presets:
        for column, (label, word) in zip(st.columns(len(PRESETS)), PRESETS.items()):
            column.button(label, key=f"m3_preset_{label}", on_click=_use, args=(word,), use_container_width=True)
    typed = st.text_input("Chuỗi ngày (M sáng · A chiều · N tối · - nghỉ)", key="m3_word", max_chars=MAX_DAYS)
    word = "".join(c for c in typed.upper() if c in "MAN-")[:MAX_DAYS]
    if not word:
        st.info("Chuỗi rỗng. Gõ các ký hiệu M, A, N hoặc dấu gạch, hoặc bấm một chuỗi mẫu.")
        return
    hits = services.check_word(word)
    tags: dict[int, str] = {}
    for rule, day in hits.items():
        if day:
            tags[day] = f"{tags[day]}·{rule[1:]}" if day in tags else rule
    parts.strip(word, tags)
    status, rules, scale = st.columns((1.3, 1.3, 1.4))
    broken = sorted((day, rule) for rule, day in hits.items() if day)
    with status:
        if broken:
            parts.verdict("bad", "Bị từ chối", f"Vi phạm đầu tiên ở ngày {broken[0][0]}, theo {broken[0][1]}")
        else:
            parts.verdict("good", "Được chấp nhận", "Cả ba DFA dừng ở trạng thái chấp nhận.")
    with rules:
        parts.text("lab", "Từng luật")
        parts.flags((not day, f"{rule}: vi phạm ở ngày {day}" if day else f"{rule}: đạt") for rule, day in hits.items())
    with scale:
        table = services.temporal_table()
        parts.text("lab", "Trên 73 chuỗi thật: số bị từ chối")
        parts.hbars([(label, table[key]["rejected"],
                      str(table[key]["rejected"]) if table[key]["rejected"] else f"0 · {table[key]['dfa_accepted']} hợp lệ")
                     for label, key in list(services.schedule_labels().items())[:3]])


MODULE = Module(
    key="m3", label="Module 3 · Automata", presenter="Phúc", start=1, lab=lab,
    fn=("class DFA", "DFA.accepts()", "product()", "minimize()", "add_rules_to_m2()"),
    ds=("Moore partition refinement", "Layered flow graph"),
    bigo=("accepts · Time: O(T)", "Space: O(1)", "minimize · Time: O(|Σ|·n²)"),
    note="T: số ngày · n: số trạng thái",
    ideas=(
        Idea("Lịch thành chuỗi", "Lịch của mỗi người là ", "một chuỗi 27 ký hiệu", ".",
             "Mỗi ngày một ký hiệu trên Σ = {M, A, N, -}; ngày có hai ca lấy ưu tiên N > A > M",
             (("Chuỗi lấy từ dữ liệu thật", "73 chuỗi, mỗi chuỗi 27 ngày, từ 18/05 đến 13/06."),
              ("Một ký hiệu mỗi ngày", "Ca 07:00 và 09:30 là M; 13:00 và 15:30 là A; 18:15 là N."),
              ("Ngày không có ca", "Ghi dấu gạch, không bỏ qua ngày.")), fig_strings),
        Idea("Mỗi luật là một DFA", "Làm 3 ngày liên tiếp, DFA rơi vào ", "dead", ".",
             "R1 · Mỗi luật thời gian là một DFA trên Σ = {M, A, N, -}",
             (("Mỗi ngày là một ký hiệu", "M sáng, A chiều, N tối, - nghỉ."),
              ("Đọc từ trái sang phải", "Rơi vào dead là vi phạm."),
              ("Ba luật R1, R2, R3", "Tối đa 2 ngày liền; sau ca tối phải nghỉ; tối đa 4 ngày làm trong 7 ngày.")), fig_dfa),
        Idea("Tích và tối giản", "Ghép ba luật: 259 trạng thái còn ", "15", ".",
             "product() lấy giao ba DFA, minimize() gộp các trạng thái không phân biệt được",
             (("R1 × R2", "11 trạng thái tới được, tối giản còn 4."),
              ("R1 × R2 × R3", "259 trạng thái tới được, tối giản còn 15."),
              ("Thêm R4", "2.072 trạng thái, tối giản còn 99.")), fig_minimize),
        Idea("Đưa DFA vào ILP", "Trải DFA theo 27 ngày thành ", "ràng buộc luồng", ".",
             "Mỗi cán bộ một đơn vị luồng đi từ q0 đến một trạng thái chấp nhận: SRC, FLOW, LINK",
             (("Giải lại M2 kèm luật", "73/73 chuỗi được chấp nhận."),
              ("Cái giá", "Mục tiêu từ 59,85 lên 66,57; trái nguyện vọng từ 28 lên 36."),
              ("Mô hình lớn hơn", "4.377 biến thành 20.600 biến; vẫn giải tối ưu.")), fig_flow),
        Idea("Ranh giới chính quy", "Đếm lệch bị chặn thì ", "chính quy", "; bằng nhau chính xác thì không.",
             "Pumping lemma trên L ∩ M*A* cho thấy #M = #A cần bộ nhớ không giới hạn",
             (("Lệch không quá c", "DFA 2c + 2 trạng thái, tính cả bẫy (R4, c = 3)."),
              ("Số M bằng số A", "Không chính quy: bơm phần M làm lệch số đếm."),
              ("Hệ quả", "Luật đếm chính xác phải viết trong ILP.")), fig_boundary),
    ),
)


def render() -> None:
    render_module(MODULE)
