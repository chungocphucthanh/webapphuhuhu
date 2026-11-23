"""CO2011 slide-grounded theory summaries and HTML/LaTeX render helpers for Module 5."""

from __future__ import annotations

from html import escape

import streamlit as st

_CARD_CLASSES = {
    "hard": "iap-theory-card iap-theory-card-hard",
    "soft": "iap-theory-card iap-theory-card-soft",
    "warn": "iap-theory-card iap-theory-card-warn",
    "info": "iap-theory-card iap-theory-card-info",
    "plain": "iap-theory-card",
}

_PILL_CLASSES = {
    "hard": "iap-pill iap-pill-hard",
    "soft": "iap-pill iap-pill-soft",
    "warn": "iap-pill iap-pill-warn",
    "info": "iap-pill iap-pill-info",
}


def theory_box(tag: str, title: str, body: str, *, kind: str = "info") -> None:
    """Render a full-width theory summary box matching the presentation palette."""
    pill_cls = _PILL_CLASSES.get(kind, "iap-pill iap-pill-info")
    st.markdown(
        '<div class="iap-theory">'
        f'<span class="{pill_cls}">{escape(tag)}</span>'
        f"<h4>{escape(title)}</h4>"
        f"<p>{escape(body)}</p>"
        "</div>",
        unsafe_allow_html=True,
    )


def theory_cards(items: list[dict[str, str]]) -> None:
    """Render a two-column grid of theory or constraint cards with escaped text."""
    blocks = []
    for item in items:
        kind = item.get("kind", "plain")
        pill_kind = item.get("pill_kind", kind if kind in _PILL_CLASSES else "info")
        card_cls = _CARD_CLASSES.get(kind, "iap-theory-card")
        pill_cls = _PILL_CLASSES.get(pill_kind, "iap-pill iap-pill-info")
        tag = escape(item["tag"])
        title = escape(item["title"])
        body = escape(item["body"])
        blocks.append(
            f'<article class="{card_cls}">'
            f'<span class="{pill_cls}">{tag}</span>'
            f"<strong>{title}</strong>"
            f"<p>{body}</p>"
            "</article>"
        )
    st.markdown('<div class="iap-theory-grid">' + "".join(blocks) + "</div>", unsafe_allow_html=True)


def render_overview_theory() -> None:
    """Render the four-chapter CO2011 slide-to-project mapping on the overview page."""
    st.markdown(
        """
| Học phần & Slide CO2011 | Khái niệm cốt lõi trên lớp | Câu hỏi giải quyết trong bài toán IAP |
| :--- | :--- | :--- |
| **Ch.1 · Logic & Verification** | Mệnh đề, vị từ ($\\forall, \\exists$), dạng chuẩn hội CNF (`Def. 1.11`), tính thỏa được (`Def. 1.7`), tính đúng/đầy đủ (`Thm. 1.1–1.2`). | Dữ liệu ca thi và tập bận hiện tại có tồn tại nghiệm thỏa cả 3 luật cứng **H1–H3** hay không? Nếu vô nghiệm, lõi mâu thuẫn nằm ở đâu? |
| **Ch.3 · Linear & Integer Optimization** | Mô hình tuyến tính nguyên (`Sec. 3.6`), LP Relaxation & chặn dưới (`Prop. 3.1`), Branch-and-Bound (`Sec. 3.9`). | Tìm phân công $x_{ij}\\in\\{0,1\\}$ giảm tải đỉnh $t^*$ trước rồi giảm độ lệch $L_1$ và phạt mềm **LOC / FAT / TRV**. |
| **Ch.4 · Automata & Formal Languages** | Bảng chữ cái $\\Sigma$, DFA 5-bộ (`Def. 2.10`), tích DFA, tối giản Myhill–Nerode (`Alg. 2.2–2.3`), Pumping Lemma. | Chuỗi 27 ngày $\\{M, A, N, \\texttt{-}\\}^*$ của từng giám thị có đạt các quy tắc tuần tự **R1–R3** không, và đưa flow DFA vào ILP thế nào? |
| **Ch.6 · Discrete Dynamical Systems** | Sai phân tuyến tính $F_{n+1}=aF_n+b\\ell-r\\rho$, điểm cân bằng (`Def. 5.1`, `Thm. 5.1–5.3`), trị riêng & ổn định. | Dưới tải tuần không đổi $\\ell$, quỹ đạo fatigue hội tụ về $F^*$ nhanh cỡ nào và độ phân tán giữa giám thị có co về 0 khi tải đều? |
"""
    )


def render_m1_result_guide(result: dict) -> None:
    """Explain the current SAT/UNSAT output using Ch.1 Logic definitions."""
    if result["satisfiable"]:
        theory_box(
            "Diễn giải kết quả SAT",
            "Tồn tại một định giá L-valuation thỏa toàn bộ tập mệnh đề S",
            f"Theo Def. 1.7 (Satisfiability), tập {result['n_clauses']} mệnh đề CNF ở trên thỏa được vì solver "
            f"Minisat22 tìm ra ít nhất một mô hình gán chân trị cho {result['n_assign_vars']} biến phân công "
            f"(cùng {result['n_aux_vars']} biến phụ Sequential Counter) khiến mọi mệnh đề đều đúng. "
            "Lưu ý: SAT chỉ đảm bảo tính khả thi luật cứng H1–H3, chưa tối ưu công bằng (M2) hay luật tuần tự (M3).",
            kind="soft",
        )
    else:
        theory_box(
            "Diễn giải kết quả UNSAT",
            "Mâu thuẫn logic — Không tồn tại nghiệm thỏa đồng thời H1–H3",
            "Tập mệnh đề S kéo theo hằng sai (⊥). Bằng kỹ thuật xóa dần mệnh đề giả định (deletion-based MUS), "
            f"hàm extract_minimal_core rút ra một lõi bất khả thỏa cực tiểu gồm {len(result['unsat_core'])} điều kiện: "
            "giữ nguyên lõi này thì mọi mục tiêu tối ưu hay thư giãn LP đều vô nghiệm; bỏ bất kỳ một điều kiện nào trong lõi, phần còn lại có thể thỏa được.",
            kind="warn",
        )


def render_m1_theory() -> None:
    """Render Module 1 lecture theory from Slide Advance Logic and Program verification."""
    theory_cards([
        {
            "tag": "Def. 1.1–1.2 · Vị từ & Lượng từ",
            "title": "Từ quy tắc tự nhiên sang First-Order Logic",
            "body": "Vị từ Assign(i, j), Busy(i, j), Overlap(j, k) biến tham số giám thị i và ca thi j thành phát biểu có chân trị. Lượng từ ∀i∀j∀k nối mọi cặp hợp lệ trong phạm vi I × J.",
            "kind": "info",
        },
        {
            "tag": "Def. 1.7 & 1.11 · CNF & SAT",
            "title": "Dạng chuẩn hội (CNF) và phép thử thỏa được",
            "body": "Mọi công thức được khử phép kéo theo (→) và đưa về hội các tuyển literal (CNF). Theo Lemma 1.2 và Theorem 1.1–1.2, chứng minh phi khả thi tương đương kiểm tra tính chất không có model nào làm mọi clause đúng.",
            "kind": "hard",
        },
        {
            "tag": "Mã hóa H3 · Sequential Counter",
            "title": "Tránh bùng nổ tổ hợp khi đếm Exactly d_j",
            "body": "Mã hóa trực tiếp binomial cần O(n^(d_j+1)) mệnh đề khi chọn d_j từ 73 người. Mạch đếm tuần tự CardEnc.seqcounter thêm biến phụ ID > N·M để biểu diễn đúng d_j người chỉ bằng số mệnh đề tuyến tính theo n · d_j.",
            "kind": "soft",
        },
        {
            "tag": "Cầu nối Logic → ILP",
            "title": "Vì sao không đưa nguyên xi CNF sang ILP?",
            "body": "Mỗi clause tuyển (a ∨ ¬b) chuyển đúng thành bất đẳng thức x_a − x_b ≥ 0. Riêng luật đếm H3 nén thành một đẳng thức ∑ x_ij = d_j không cần biến phụ, giúp nghiệm thư giãn LP của Module 2 chặt hơn.",
            "kind": "plain",
        },
    ])
    st.latex(
        r"\begin{aligned}"
        r"\text{H1: } &\forall i,j:\;\operatorname{Busy}(i,j)\Rightarrow\neg\operatorname{Assign}(i,j) \\"
        r"\text{H2: } &\forall i,j\neq k:\;\operatorname{Overlap}(j,k)\land\operatorname{Assign}(i,j)\Rightarrow\neg\operatorname{Assign}(i,k)"
        r"\end{aligned}"
    )
    st.latex(
        r"\begin{aligned}"
        r"\text{H3: } &\forall j\in J:\;\sum_{i\in I}x_{ij}=d_j,\qquad x_{ij}\in\{0,1\} \\"
        r"&\operatorname{ID}(i,j)=i\cdot M + j + 1"
        r"\end{aligned}"
    )


def render_m2_theory_and_constraints(inst) -> None:
    """Render Module 2 lecture theory plus detailed Hard and Soft constraints."""
    w_loc, w_fat, w_trv = inst.soft_weights
    theory_cards([
        {
            "tag": "Sec. 3.6 · Integer Optimization",
            "title": "Biến quyết định nhị phân thưa x_ij ∈ {0, 1}",
            "body": f"Chỉ tạo biến x_ij cho các cặp khả dụng (i, j) ∈ A (hiện có {len(inst.A):,} cặp trên {len(inst.staff_ids)} người × {len(inst.session_names)} ca). Tổng tải từng người w_i = ∑ x_ij là biểu thức tuyến tính.",
            "kind": "info",
        },
        {
            "tag": "Sec. 3.9 & Prop. 3.1 · Branch-and-Bound",
            "title": "LP Relaxation là chặn dưới: Z_LP ≤ Z_ILP",
            "body": "Thư giãn x_ij ∈ [0,1] không bảo đảm nghiệm nguyên vì hàm min-max và ràng buộc H2 theo clique phá vỡ tính toàn đơn mô-đun (Total Unimodularity). Solver CBC phải dùng Branch-and-Bound cắt nhánh để tìm nghiệm nguyên.",
            "kind": "warn",
        },
    ])

    st.markdown("#### 1 · Hàm mục tiêu hai giai đoạn (Lexicographic Optimization)")
    st.latex(
        r"\begin{aligned}"
        r"\text{Giai đoạn 1: } &\min_{x,t}\; t \quad \text{s.t. } t \ge w_i=\sum_{j:(i,j)\in A}x_{ij}\;\;\forall i\in I \\"
        rf"\text{{Giai đoạn 2: }} &\min\; \sum_{{i\in I}} d_i + \lambda_{{\text{{LOC}}}}\cdot\text{{LOC}} + \lambda_{{\text{{FAT}}}}\cdot\text{{FAT}} + \lambda_{{\text{{TRV}}}}\cdot\text{{TRV}} \\"
        rf"&\text{{s.t. }} t\le t^*,\;\; d_i\ge |w_i-\bar{{w}}|,\;\; \lambda=({w_loc:.2f},\,{w_fat:.2f},\,{w_trv:.2f})"
        r"\end{aligned}"
    )

    st.markdown("#### 2 · Ràng buộc cứng (Hard Constraints — Bắt buộc thỏa 100%)")
    theory_cards([
        {
            "tag": "HARD · H1 Khả dụng",
            "title": "x_ij = 0 khi giám thị bận hoặc (i, j) ∉ A",
            "body": "Loại bỏ hoàn toàn biến x_ij ngoài tập A ngay từ bước tạo biến. Nếu giữ biến mà không nằm trong A, hàm check_schedule lập tức báo vi phạm H1.",
            "kind": "hard",
        },
        {
            "tag": "HARD · H2 Không trùng giờ",
            "title": "∑ x_ij ≤ 1 trên từng clique cực đại C",
            "body": "Hai ca thi giao nhau về thời gian (kể cả khác cơ sở CS1/CS2; tiếp giáp đầu-cuối vẫn hợp lệ) không thể cùng do một giám thị coi. Gom theo clique cực đại (Helly property) thay vì từng cặp để rút gọn mô hình.",
            "kind": "hard",
        },
        {
            "tag": "HARD · H3 Đủ người",
            "title": "∑ x_ij = d_j trên mọi (i, j) ∈ A cho từng ca j",
            "body": "Mỗi ca thi phải có đúng đủ d_j giám thị. Khi vô nghiệm, chế độ chẩn đoán nới thành ∑ x_ij + u_j = d_j (u_j ≥ 0) với hệ số phạt 1000 để chỉ ra chính xác ca nào thiếu người.",
            "kind": "hard",
        },
    ])

    st.markdown("#### 3 · Ràng buộc mềm (Soft Constraints — Phạt vào mục tiêu giai đoạn 2)")
    theory_cards([
        {
            "tag": f"SOFT · LOC (λ = {w_loc:.2f})",
            "title": "Sở thích cơ sở: LOC = ∑ c_ij x_ij",
            "body": "Mỗi giám thị có sở thích giả lập từ seed (CS1, CS2 hoặc BAL). Nếu người thích CS1 bị xếp sang CS2 (hoặc ngược lại) thì c_ij = 1; nhóm BAL không bị phạt (c_ij = 0).",
            "kind": "soft",
        },
        {
            "tag": f"SOFT · FAT (λ = {w_fat:.2f})",
            "title": "Quá tải trong ngày: s_id ≥ (số ca ngày d) − K",
            "body": "Ngưỡng K được khớp tại phân vị 95% số ngày làm việc của lịch gốc (K = 3, bao phủ 98,5% cặp người-ngày). Biến liên tục s_id ≥ 0 đo phần vượt quá K ca trong cùng một ngày.",
            "kind": "soft",
        },
        {
            "tag": f"SOFT · TRV (λ = {w_trv:.2f})",
            "title": "Di chuyển liên cơ sở: v_id ≥ z_id1 + z_id2 − 1",
            "body": "Nếu trong cùng ngày d giám thị i làm cả ở CS1 (z_id1 = 1) và CS2 (z_id2 = 1) thì v_id = 1 và bị phạt. Lưu ý: TRV chỉ phạt di chuyển khác ca trong ngày, KHÔNG thay thế được H2 khi trùng giờ.",
            "kind": "soft",
        },
    ])


def render_m3_theory() -> None:
    """Render Module 3 lecture theory from Slide Automat(new) and pumping.md."""
    theory_cards([
        {
            "tag": "Def. 2.10 · DFA 5-bộ",
            "title": "M = (Q, Σ, q0, δ, F) trên Σ = {M, A, N, -}",
            "body": "Mỗi ngày của giám thị i nén thành đúng 1 ký hiệu theo thứ tự ưu tiên N > A > M (nghỉ là -). DFA hoàn chỉnh luôn có trạng thái bẫy dead (không thuộc F, mọi mũi tên tự lặp về chính nó) để bắt chính xác ngày đầu tiên vi phạm.",
            "kind": "info",
        },
        {
            "tag": "Alg. 2.2–2.3 · Tích & Myhill–Nerode",
            "title": "Giao DFA và tối giản lớp tương đương",
            "body": "Giao R1 ∩ R2 ∩ R3 cho máy tích 259 trạng thái tới được. Thuật toán tinh chỉnh phân hoạch gộp các trạng thái không phân biệt được (bắt đầu từ {F, Q\\F}) xuống còn đúng 15 trạng thái tối giản, giúp mô hình flow ILP nhỏ hơn ~17 lần.",
            "kind": "soft",
        },
        {
            "tag": "Regular Constraint → ILP",
            "title": "Đồ thị phân tầng T ngày & bảo toàn luồng",
            "body": "Đặt biến luồng y(i,t,q,a) ∈ [0,1] trên các cạnh không đi vào dead, nối với biến ngày z(i,t,a) (chọn ưu tiên N > A > M từ u(i,t,a) và x_ij): 1 đơn vị luồng xuất phát từ (0, q0) và đi qua đúng các cạnh hợp lệ.",
            "kind": "hard",
        },
        {
            "tag": "Pumping Lemma · Ranh giới bộ nhớ",
            "title": "Vì sao |#M − #A| ≤ c chính quy còn #M = #A thì không?",
            "body": "Hiệu bị chặn |#M − #A| ≤ c chỉ cần bộ nhớ hữu hạn 2c+2 trạng thái (R4). Ngược lại, L = {w : #M(w) = #A(w)} giao với ngôn ngữ chính quy M*A* cho L' = {MⁿAⁿ}. Bơm chuỗi MᵖAᵖ (|xy| ≤ p) làm lệch #M và #A nên L không chính quy và buộc phải viết bằng ràng buộc tuyến tính trong ILP.",
            "kind": "warn",
        },
    ])
    st.latex(
        r"\begin{aligned}"
        r"\text{SRC: } &\sum_a y_{i,0,q_0,a}=1,\qquad "
        r"\text{LINK: }\sum_q y_{i,t,q,a}=z_{i,t,a} \\"
        r"\text{FLOW: } &\sum_a y_{i,t,q,a}=\sum_{(p,a):\delta(p,a)=q}y_{i,t-1,p,a}"
        r"\end{aligned}"
    )


def render_m4_theory(parameters: dict[str, float], threshold: float) -> None:
    """Render Module 4 lecture theory from MM5-DYNAMICAL SYSTEMS-landscape."""
    a_val = parameters["a"]
    b_val = parameters["b"]
    r_val = parameters["r"]
    theory_cards([
        {
            "tag": "Def. 5.1 & Thm. 5.2 · Điểm cân bằng",
            "title": "Hệ thức sai phân tuyến tính Hướng B",
            "body": "Thay vì cộng dồn tuyến tính w(n+1) = w(n) + A(n)·x(n) (trị riêng bằng 1, không có điểm cân bằng), mô hình vector fatigue đặt F(n+1) = a·F(n) + b·ℓ − r·ρ. Khi a ≠ 1, tồn tại điểm cân bằng duy nhất F* = (b·ℓ − r·ρ) / (1 − a).",
            "kind": "info",
        },
        {
            "tag": "Thm. 5.1 & 5.3 · Ma trận Jacobi J = a I",
            "title": "Phân loại ổn định theo bán kính phổ |a|",
            "body": f"Nghiệm đóng là F(n) = F* + aⁿ·(F(0) − F*). Do J = aI có mọi trị riêng bằng a (hiện tại |a| = {abs(a_val):.4f}), hệ ổn định tiệm cận toàn cục khi |a| < 1, trung hòa khi |a| = 1 và phân kỳ khi |a| > 1.",
            "kind": "hard",
        },
        {
            "tag": "Liên kết Công bằng",
            "title": "Tải đều đẩy spread(F_n) và Var(F_n) về 0",
            "body": "Khi mọi giám thị có cùng tải tuần ℓ_i = μ, sai khác giữa hai người co theo F(n,i) − F(n,j) = aⁿ·(F(0,i) − F(0,j)), kéo spread(F_n) = |a|ⁿ·spread(F_0) → 0. Công bằng chính là điểm cân bằng hút của hệ động lực.",
            "kind": "soft",
        },
        {
            "tag": "Hiệu chuẩn Proxy & Ngưỡng H",
            "title": f"a={a_val:.4f}, b={b_val:.4f}, r={r_val:g}, H={threshold:.3f}",
            "body": "Do dữ liệu không có phép đo mệt mỏi sinh lý, a được ước lượng bằng OLS độ trễ 1 trên suất tuần lịch sử, đặt r = 0 và chuẩn hóa b = 1 − a để F* = μ. Ngưỡng mềm H lấy tại phân vị 95% của lịch gốc làm chỉ báo quá tải (không phải ngưỡng y tế).",
            "kind": "warn",
        },
    ])
    st.latex(
        r"\begin{aligned}"
        r"F_{n+1} &= aF_n + b\ell - r\rho,\qquad "
        r"F^* = \frac{b\ell - r\rho}{1-a}\;(a\neq 1) \\"
        r"\operatorname{spread}(F_n) &= |a|^n\operatorname{spread}(F_0),\qquad "
        r"\operatorname{Var}(F_n) = a^{2n}\operatorname{Var}(F_0)"
        r"\end{aligned}"
    )


def render_pipeline_theory(inst, active_label: str) -> None:
    """Render concise end-to-end theoretical summary linking M1-M4 on the active schedule."""
    theory_box(
        "Mạch lý thuyết 4 học phần",
        f"Kết nối Logic → ILP → DFA → Hệ động lực trên «{active_label}»",
        f"Bộ dữ liệu hiện có {len(inst.staff_ids)} giám thị và {len(inst.session_names)} ca thi (tổng nhu cầu {sum(inst.demand)} lượt). "
        "M1 chứng minh tập luật cứng H1–H3 là khả thi (SAT) hay chỉ ra lõi mâu thuẫn cực tiểu (UNSAT). "
        "M2 dùng chính miền khả dụng A và clique H2 để tối thiểu tải đỉnh t* rồi giảm L1 và phạt mềm LOC/FAT/TRV. "
        "M3 đọc chuỗi ngày của lịch đã chọn qua DFA tối giản 15 trạng thái (R1×R2×R3) để tách biệt tính hợp lệ luật cứng với tính hợp lệ theo thời gian. "
        "Cuối cùng, M4 chuyển tải phân công thành vector suất tuần để kiểm chứng độ chênh lệch cân bằng F* và tổng vượt ngưỡng H.",
        kind="info",
    )
