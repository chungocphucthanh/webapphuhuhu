# AGENTS.md — Module 5 Frontend / UI-UX Rebuild (Streamlit Presentation App)

## 1. Mục tiêu nhiệm vụ (Mission)

Đập đi xây lại hoàn toàn toàn bộ Frontend và UI/UX của **Module 5** thành một ứng dụng **Streamlit** hiện đại, trực quan, dễ nhìn và tối ưu hóa cho việc **thuyết trình trực tiếp (live presentation)**.

Ứng dụng phải phản ánh đầy đủ kiến trúc, thuật toán, cấu trúc dữ liệu và luồng hoạt động của toàn bộ dự án (Modules 1–4), được phân chia rõ ràng theo từng module để nhóm dễ dàng trình bày, tương tác demo và chỉ trực tiếp vào các thuật ngữ/hàm cốt lõi trên màn hình chiếu.

---

## 2. Quy tắc bất di bất dịch (Hard Guardrails)

1. **TUYỆT ĐỐI KHÔNG CHẠM VÀO MODULES 1–4:**
   - **Cấm tuyệt đối** mọi hành động chỉnh sửa, format lại, đổi tên, di chuyển hoặc xóa bất kỳ file nào thuộc Modules 1–4 và các module trước đó.
   - Chỉ được phép **đọc (read-only)** code của Modules 1–4 để nắm cấu trúc, chữ ký hàm, class, kiểu dữ liệu đầu vào/đầu ra và kết nối API.
2. **BẢO TOÀN 100% LOGIC LÕI:**
   - Không làm hỏng logic xử lý, kết nối API, pipeline dữ liệu hoặc thuật toán gốc của Modules 1–4.
   - Nếu cần chuyển đổi dữ liệu để hiển thị lên UI, caching hoặc xử lý lỗi giao diện, **bắt buộc viết lớp adapter/wrapper riêng bên trong thư mục của Module 5**.
3. **PHẠM VI CHỈNH SỬA HỢP LỆ:**
   - Chỉ được tạo/sửa/xóa file trong phạm vi thư mục của **Module 5** (cùng cấu hình skill nếu repo yêu cầu lưu trong `.claude/skills/` hoặc `.agents/skills/`, và bổ sung thư viện UI cần thiết nếu có).
   - Trước khi commit, bắt buộc chạy `git status` và `git diff --name-only` để xác nhận **0 file** thuộc Modules 1–4 bị thay đổi.

---

## 3. Giai đoạn 0 — Cài đặt & Kích hoạt AI / Claude Skills

Trước khi bắt đầu thiết kế hoặc viết code, hãy kiểm tra và cài đặt toàn bộ các Claude Skills / Agent Skills cần thiết cho bài toán UI/UX, Frontend Design, kiểm thử web app và quy trình kỹ thuật vào thư mục skills của dự án (`.claude/skills/` hoặc `.agents/skills/` tùy cấu trúc agent đang chạy):

1. **Kiểm tra công cụ quản lý skill hiện có** (ưu tiên `npx skills` hoặc cấu hình skill có sẵn của OpenCode / Claude Code):
   ```bash
   # Tìm và cài đặt các skill cốt lõi cho UI/UX, Frontend Design & Testing
   npx skills add anthropics/skills --skill frontend-design -y
   npx skills add anthropics/skills --skill webapp-testing -y
   npx skills add nextlevelbuilder/ui-ux-pro-max-skill -y
   npx skills add obra/superpowers --skill verification-before-completion -y
   npx skills add obra/superpowers --skill systematic-debugging -y
   ```
2. **Cơ chế dự phòng (Fallback):**
   - Nếu bất kỳ lệnh `npx skills add` nào thất bại (do đổi tên repo, giới hạn mạng hoặc cấu trúc CLI khác), hãy dùng `npx skills find <keyword>` (với các từ khóa: `frontend-design`, `ui-ux`, `streamlit`, `testing`, `verification`) để cài skill tương đương.
   - Nếu môi trường hoàn toàn không có CLI skill, hãy tạo các file `SKILL.md` chuẩn hóa trong `.claude/skills/` (bao gồm `streamlit-presentation-ui/SKILL.md` và `module5-verification/SKILL.md`) để áp dụng xuyên suốt quá trình xây dựng.
3. **Áp dụng Skill:** Đọc và tuân thủ các nguyên tắc thiết kế từ skill vừa cài (typography, color hierarchy, spacing, component modularity, verification before completion) xuyên suốt Giai đoạn 2 và 3.

---

## 4. Giai đoạn 1 — Khám phá & Đọc hiểu toàn bộ Project (Read-Only)

**Không viết bất kỳ dòng code UI nào** trước khi hoàn thành các bước đọc hiểu sau:

1. Đọc toàn bộ đề bài chính thức: `CO2011-SEM261_IAP_Assignment-Brief_v1.0_STUDENTS` (kiểm tra tất cả định dạng `.pdf`, `.docx`, `.md`, `.txt` trong repo).
2. Đọc tất cả file `README.md`, tài liệu hướng dẫn, `requirements.txt` / `pyproject.toml`, file cấu hình và cấu trúc thư mục toàn repo.
3. Khảo sát chi tiết mã nguồn của **Modules 1–4** (chỉ đọc) và lập bản đồ kỹ thuật nội bộ cho từng module gồm:
   - Mục tiêu và chức năng chính của module.
   - Tên **class / hàm / method gốc** chính xác trong code.
   - Tên **cấu trúc dữ liệu** và **thuật toán** được sử dụng.
   - Độ phức tạp **Big-O** (Time & Space Complexity) tương ứng.
   - Đầu vào (input), đầu ra (output), trạng thái lỗi và kết nối API/database (nếu có).
4. Kiểm tra mã nguồn cũ của **Module 5** để biết điểm khởi chạy (entry point), cách import Modules 1–4 và các biến môi trường đang dùng, sau đó thiết kế lại toàn bộ cấu trúc Module 5 sạch sẽ, module hóa (ví dụ: `app.py`, `styles/`, `components/`, `views/`).

---

## 5. Giai đoạn 2 — Đập đi xây lại toàn bộ UI/UX cho Module 5 (Streamlit)

### 5.1. Nguyên tắc thiết kế cho thuyết trình (Presentation-First UI/UX)
- **Giao diện sạch, hiện đại, độ tương phản cao:** Tối ưu để chiếu lên máy chiếu/màn hình lớn (font chữ rõ ràng, khoảng trắng hợp lý, phân cấp thị giác mạch lạc, không nhồi nhét text dày đặc).
- **Custom CSS tinh gọn:** Inject CSS riêng qua `st.markdown(..., unsafe_allow_html=True)` để nâng cấp thẩm mỹ mặc định của Streamlit (card bố cục dạng grid, metric card nổi bật, header gọn đẹp, sidebar điều hướng trực quan).
- **Phân chia rõ theo từng Module:**
  - Sidebar điều hướng cố định, phân tách rõ ràng:
    - **Tổng quan hệ thống (Overview & Architecture):** Sơ đồ luồng dữ liệu kết nối từ Module 1 → Module 4, KPI/thông số nhanh.
    - **Module 1** → **Module 2** → **Module 3** → **Module 4** (mỗi module là một trang/view riêng biệt, có phần demo tương tác trực tiếp + bảng giải thích kỹ thuật).
    - **Tích hợp đầu-cuối (End-to-End Demo / Pipeline)** (nếu phù hợp với luồng bài tập trong brief).
- **Trải nghiệm tương tác mượt mà:**
  - Dùng `st.session_state`, `@st.cache_data` / `@st.cache_resource` hợp lý để tránh tính toán lại không cần thiết khi chuyển tab thuyết trình.
  - Có sẵn dữ liệu mẫu (sample/preset inputs) chọn bằng 1 click để trình bày nhanh trước hội đồng mà không tốn thời gian nhập tay.
  - Xử lý ngoại lệ bằng `st.error` / `st.warning` thân thiện, có spinner/progress bar khi gọi API hoặc chạy thuật toán nặng.

### 5.2. Quy chuẩn Ngôn ngữ & Badge thuật ngữ (Bắt buộc)
- **Ngôn ngữ hiển thị:** 100% tiêu đề, nhãn nút, mô tả, giải thích luồng xử lý và hướng dẫn thao tác phải viết bằng **Tiếng Việt** tự nhiên, súc tích, dễ đọc khi thuyết trình.
- **Giữ nguyên thuật ngữ chuyên ngành & mã nguồn gốc:**
  - Tuyệt đối không dịch gượng ép các thuật ngữ quốc tế (VD: *Binary Search Tree*, *Hash Table*, *Graph*, *BFS/DFS*, *REST API*, *Caching*, *Dynamic Programming*, v.v.).
  - Giữ nguyên **tên cấu trúc dữ liệu**, **độ phức tạp Big-O** (VD: `O(1)`, `O(log n)`, `O(n log n)`) và **tên hàm / class gốc trong code** của Modules 1–4.
- **Hệ thống Code / Badge nổi bật để dễ chỉ tay khi thuyết trình:**
  - Tạo sẵn helper render HTML badge/pill trong Module 5 với màu sắc phân biệt rõ ràng:
    - **Badge Hàm/Class gốc** (VD: `class BinarySearchTree`, `def search_node()`): nền tối/xanh dương đậm, font monospace, viền rõ.
    - **Badge Cấu trúc dữ liệu / Thuật toán** (VD: `AVL Tree`, `Priority Queue`, `Dijkstra`): màu tím/chàm nổi bật.
    - **Badge Độ phức tạp Big-O** (VD: `Time: O(log n)`, `Space: O(n)`): màu cam/xanh ngọc nổi bật, dễ nhận diện từ xa.
  - Mỗi trang module nên có một khu vực **"Góc Kỹ Thuật / Technical Callout"** (hoặc panel thu gọn/mở rộng) tổng hợp các badge tên hàm/class gốc + cấu trúc dữ liệu + Big-O gắn với chính thao tác đang demo.

---

## 6. Giai đoạn 3 — Kiểm thử toàn diện (Verification Gate)

Sau khi xây dựng xong Module 5, **bắt buộc** thực hiện đủ các bước kiểm tra sau và sửa triệt để mọi lỗi trước khi báo cáo:

1. **Kiểm tra biên dịch / cú pháp (Static Check):**
   - Chạy `python -m py_compile` cho toàn bộ file `.py` thuộc Module 5.
   - Kiểm tra import giữa Module 5 và Modules 1–4 đảm bảo không lỗi `ModuleNotFoundError`, `ImportError` hay circular import.
2. **Kiểm tra chạy thực tế (Runtime Smoke Test):**
   - Khởi chạy ứng dụng Streamlit ở chế độ headless (`streamlit run <entry_point> --server.headless true`) hoặc dùng `streamlit.testing.v1.AppTest` / script kiểm thử tự động để duyệt qua **tất cả các trang/module**.
   - Xác nhận không có lỗi runtime, không có traceback đỏ trên giao diện, không có warning nghiêm trọng do API Streamlit đã deprecated.
   - Kiểm tra các luồng tương tác chính gọi xuống Modules 1–4 hoạt động đúng kết quả gốc.
3. **Kiểm tra bảo toàn Modules 1–4 (Boundary Audit):**
   - Chạy `git status` và `git diff --name-only`.
   - Nếu phát hiện bất kỳ file nào thuộc Modules 1–4 bị sửa nhầm, lập tức khôi phục lại bằng `git checkout -- <file>` và kiểm thử lại.

---

## 7. Giai đoạn 4 — Tự động Commit & Push lên Git

Sau khi vượt qua 100% bước kiểm thử ở Giai đoạn 3:

1. Kiểm tra nhánh hiện tại và remote:
   ```bash
   git branch --show-current
   git remote -v
   git status
   ```
2. Đảm bảo không stage các file rác (`__pycache__/`, `.venv/`, `.env`, file tạm, log kiểm thử).
3. Chỉ stage các file hợp lệ (Module 5 + thư mục skills/config cần thiết nếu được phép theo `.gitignore`).
4. Commit theo chuẩn Conventional Commits với mô tả rõ ràng:
   ```bash
   git commit -m "feat(module-5): rebuild Streamlit presentation UI/UX and integrate AI skills"
   ```
5. Tự động push lên remote nhánh hiện tại:
   ```bash
   git push origin $(git branch --show-current)
   ```
   - **An toàn Git:** Không bao giờ dùng `--force` trên `main`/`master`. Nếu remote có commit mới hơn gây từ chối push, báo rõ trạng thái hoặc `git pull --rebase` an toàn nếu không xung đột với Modules 1–4 rồi push lại.

---

## 8. Giai đoạn 5 — Báo cáo tổng kết đầu ra

Khi hoàn tất mọi bước trên, trả về một bản tóm tắt **ngắn gọn, có cấu trúc bằng Tiếng Việt** bao gồm:

1. **Danh sách Skills đã cài đặt & áp dụng.**
2. **Tóm tắt thay đổi UI/UX theo từng phần Module:**
   - Tổng quan & Cấu trúc mới của Module 5.
   - Giao diện & tính năng hiển thị cho **Module 1**, **Module 2**, **Module 3**, **Module 4** (kèm các tên hàm/class, cấu trúc dữ liệu và độ phức tạp Big-O đã gắn badge).
3. **Kết quả kiểm thử:** Xác nhận 0 lỗi biên dịch/runtime và xác nhận Modules 1–4 hoàn toàn nguyên vẹn (`git diff` sạch).
4. **Thông tin Git:** Tên nhánh, commit hash và trạng thái push lên remote.