# M5 Patch Series (Equal 20% Split for 5 Members)

Base commit: `79b7743756a6722f99ab9f129c27125f5539081f` (post-M4 `main`, before M5).

Bộ 5 patch `git apply` này tách toàn bộ Module 5 (`app/`, `run_all.py`, kiểm thử và tài liệu) thành **5 phần tuần tự có khối lượng bằng nhau (~20% tổng số dòng thêm mới cho mỗi thành viên)** để từng bạn áp dụng trên repo chính (private), tạo Pull Request và merge lần lượt vào `main`.

> **Các file được loại trừ khỏi 5 patch code:**
> - `app/m5_bundle.json` (12.514 dòng sinh tự động — nếu gộp vào sẽ làm lệch rubric % LOC; sinh lại sau Patch 5 bằng `run_all.py --stage m5`).
> - `app/.open-design.json`, `.agents/`, `AGENTS.md`, `__pycache__/`, `.pytest_cache/` (file cấu hình cục bộ / cache không thuộc source repo private).

---

## Bảng phân chia khối lượng (20% mỗi thành viên)

| Thứ tự | Thành viên (MSSV & Tên) | Patch | Files & Phạm vi | LOC (`+ / -`) | Tỷ lệ | Commit message |
| :---: | --- | --- | --- | :---: | :---: | --- |
| 1 | `2551931 Dinh Hoang Quang Vinh` | [0001-load-datasets-and-presentation-shell.patch](0001-load-datasets-and-presentation-shell.patch) | `app/__init__.py`, `app/.streamlit/config.toml`, `app/data_views.py`, `app/tests/test_m5_data_views.py`, `app/presentation.py`, `app/presentation.css` (1/3), `app/presentation_views.py` (1/4: `overview`) | `+568 / -0` | **19.89%** | `m5: load datasets, weekly tables and presentation shell` |
| 2 | `2551896 Nguyen Quoc Hung` | [0002-solve-m1-m2-and-plan-views.patch](0002-solve-m1-m2-and-plan-views.patch) | `app/solver_views.py`, `app/tests/test_m5_solver_views.py`, `app/presentation.css` (2/3), `app/presentation_views.py` (2/4: `logic_panel`, `plan_panel`) | `+575 / -1` | **20.13%** | `m5: add M1/M2 solver services and Logic/ILP presentation views` |
| 3 | `2551919 Dang Nguyen Thien Phuc` | [0003-verify-m3-automata-and-navigation-core.patch](0003-verify-m3-automata-and-navigation-core.patch) | `app/temporal_views.py`, `app/tests/test_m5_temporal_views.py`, `app/presentation.css` (3/3), `app/presentation_views.py` (3/4: `word_lab`, `temporal_panel`), `app/app.py` (1/2) | `+593 / -0` | **20.76%** | `m5: add M3 automata audit, DFA word lab and app navigation core` |
| 4 | `2551913 Vo Nguyen Vi Nguyen` | [0004-simulate-m4-dynamics-and-precompute.patch](0004-simulate-m4-dynamics-and-precompute.patch) | `app/dynamics_views.py`, `app/tests/test_m5_dynamics_views.py`, `app/presentation_views.py` (4/4: `dynamics_panel`), `app/precompute.py` (1/2: `run_m5`), `run_all.py` | `+559 / -1` | **19.57%** | `m5: add M4 vector fatigue dynamics, fatigue view and run_m5 precompute` |
| 5 | `2551922 Chu Ngoc Phuc Thanh` | [0005-wire-streamlit-app-tests-and-docs.patch](0005-wire-streamlit-app-tests-and-docs.patch) | `app/precompute.py` (2/2: `load_full_schedules`), `app/app.py` (2/2: `main`), `app/tests/test_m5_app_integration.py`, `app/README.md`, `README.md`, `DECISIONS.md` | `+561 / -3` | **19.64%** | `m5: wire Streamlit presentation app, integration tests and docs` |
| **Tổng** | **5 thành viên** | **5 patches** | **19 files (15 Python, 1 CSS, 1 TOML, 3 Markdown)** | **`+2856 / -5`** | **100%** | Trung bình mục tiêu: **571.2 LOC (20.0%)** |

> Lưu ý: Từng patch sau khi áp dụng theo đúng thứ tự đều **compile và pass pytest độc lập** (`3`, `6`, `9`, `12`, rồi `22 passed`), giúp mỗi PR trên GitHub luôn xanh CI và tách bạch quyền sở hữu theo đúng rubric CO2011.

---

## Quy trình giải nén & Pull Request lên Repo chính (Private)

> **Nguyên tắc bắt buộc:** Giữ thư mục `patch_m5/` ở **ngoài** cây git repo private (hoặc không commit thư mục patch vào repo private). Thực hiện tuần tự từ **1 -> 5**: thành viên sau phải `git pull origin main` sau khi PR của thành viên trước đã được merge.

Trước khi commit, mỗi thành viên kiểm tra git identity theo đúng quy định của môn học:

```sh
git config user.name "<StudentID> <Full Name>"
git config user.email "<StudentID>@hcmut.edu.vn"
```

Thay `/path/to/patch_m5` bằng đường dẫn tới thư mục chứa 5 file `.patch`.

### Bước 0 — Kiểm tra toàn vẹn SHA-256 (tùy chọn nhưng khuyến khích)

- Linux / macOS / Git Bash:
  ```sh
  cd /path/to/patch_m5
  sha256sum -c SHA256SUMS
  ```
- Windows PowerShell:
  ```powershell
  Get-Content SHA256SUMS | ForEach-Object { $h, $f = $_ -split '  ', 2; $actual = (Get-FileHash $f -Algorithm SHA256).Hash.ToLower(); "$f : $($actual -eq $h)" }
  ```

### Bước 1 — `2551931 Dinh Hoang Quang Vinh` (Patch 1)

```sh
git checkout main && git pull origin main
git checkout -b feat/m5-p1-data-and-shell
git config user.name "2551931 Dinh Hoang Quang Vinh"
git config user.email "2551931@hcmut.edu.vn"

git apply --check /path/to/patch_m5/0001-load-datasets-and-presentation-shell.patch
git apply /path/to/patch_m5/0001-load-datasets-and-presentation-shell.patch
git add -- app/__init__.py app/.streamlit/config.toml app/data_views.py app/tests/test_m5_data_views.py app/presentation.py app/presentation.css app/presentation_views.py
git commit -m "m5: load datasets, weekly tables and presentation shell"

python -m pytest app/tests -q   # kỳ vọng: 3 passed
git push -u origin feat/m5-p1-data-and-shell
# Mở PR vào main -> Review -> Merge
```

### Bước 2 — `2551896 Nguyen Quoc Hung` (Patch 2 — sau khi PR 1 đã merge)

```sh
git checkout main && git pull origin main
git checkout -b feat/m5-p2-solvers-and-plan
git config user.name "2551896 Nguyen Quoc Hung"
git config user.email "2551896@hcmut.edu.vn"

git apply --check /path/to/patch_m5/0002-solve-m1-m2-and-plan-views.patch
git apply /path/to/patch_m5/0002-solve-m1-m2-and-plan-views.patch
git add -- app/solver_views.py app/tests/test_m5_solver_views.py app/presentation.css app/presentation_views.py
git commit -m "m5: add M1/M2 solver services and Logic/ILP presentation views"

python -m pytest app/tests -q   # kỳ vọng: 6 passed
git push -u origin feat/m5-p2-solvers-and-plan
# Mở PR vào main -> Review -> Merge
```

### Bước 3 — `2551919 Dang Nguyen Thien Phuc` (Patch 3 — sau khi PR 2 đã merge)

```sh
git checkout main && git pull origin main
git checkout -b feat/m5-p3-temporal-and-nav
git config user.name "2551919 Dang Nguyen Thien Phuc"
git config user.email "2551919@hcmut.edu.vn"

git apply --check /path/to/patch_m5/0003-verify-m3-automata-and-navigation-core.patch
git apply /path/to/patch_m5/0003-verify-m3-automata-and-navigation-core.patch
git add -- app/temporal_views.py app/tests/test_m5_temporal_views.py app/presentation.css app/presentation_views.py app/app.py
git commit -m "m5: add M3 automata audit, DFA word lab and app navigation core"

python -m pytest app/tests -q   # kỳ vọng: 9 passed
git push -u origin feat/m5-p3-temporal-and-nav
# Mở PR vào main -> Review -> Merge
```

### Bước 4 — `2551913 Vo Nguyen Vi Nguyen` (Patch 4 — sau khi PR 3 đã merge)

```sh
git checkout main && git pull origin main
git checkout -b feat/m5-p4-dynamics-and-precompute
git config user.name "2551913 Vo Nguyen Vi Nguyen"
git config user.email "2551913@hcmut.edu.vn"

git apply --check /path/to/patch_m5/0004-simulate-m4-dynamics-and-precompute.patch
git apply /path/to/patch_m5/0004-simulate-m4-dynamics-and-precompute.patch
git add -- app/dynamics_views.py app/tests/test_m5_dynamics_views.py app/presentation_views.py app/precompute.py run_all.py
git commit -m "m5: add M4 vector fatigue dynamics, fatigue view and run_m5 precompute"

python -m pytest app/tests -q   # kỳ vọng: 12 passed
git push -u origin feat/m5-p4-dynamics-and-precompute
# Mở PR vào main -> Review -> Merge
```

### Bước 5 — `2551922 Chu Ngoc Phuc Thanh` (Patch 5 — sau khi PR 4 đã merge)

```sh
git checkout main && git pull origin main
git checkout -b feat/m5-p5-app-wiring-and-docs
git config user.name "2551922 Chu Ngoc Phuc Thanh"
git config user.email "2551922@hcmut.edu.vn"

git apply --check /path/to/patch_m5/0005-wire-streamlit-app-tests-and-docs.patch
git apply /path/to/patch_m5/0005-wire-streamlit-app-tests-and-docs.patch
git add -- app/precompute.py app/app.py app/tests/test_m5_app_integration.py app/README.md README.md DECISIONS.md
git commit -m "m5: wire Streamlit presentation app, integration tests and docs"

# Sinh app/m5_bundle.json trước khi chạy integration AppTest (bắt buộc cho test_m5_app_integration.py)
# Linux / macOS / Git Bash:
python run_all.py --seed "$(cat data/seed.txt)" --stage m5
# Windows PowerShell:
# python run_all.py --seed (Get-Content data/seed.txt -Raw).Trim() --stage m5
python -m pytest app/tests -q   # kỳ vọng: 22 passed
git push -u origin feat/m5-p5-app-wiring-and-docs
# Mở PR vào main -> Review -> Merge
```

### Bước 6 — Sinh `app/m5_bundle.json` (tùy chọn commit cho Streamlit Community Cloud)

`app/m5_bundle.json` được tách khỏi 5 patch code để giữ nguyên tỷ lệ đóng góp 20% cho mỗi thành viên. Sau khi 5 PR đã vào `main`:

- Khi chạy local hoặc kiểm tra tái lập kết quả:
  ```sh
  # Linux / macOS / Git Bash:
  python run_all.py --seed "$(cat data/seed.txt)" --stage m5
  ```
  ```powershell
  # Windows PowerShell:
  python run_all.py --seed (Get-Content data/seed.txt -Raw).Trim() --stage m5
  ```
- Nếu nhóm deploy app trực tiếp lên **Streamlit Community Cloud** (để trang mở tức thì không phải tính lại `M2 + R1xR2xR3` 150s khi khởi động): có thể commit riêng `app/m5_bundle.json` (ghi rõ `chore(app): add precomputed m5_bundle.json for Streamlit deploy`) hoặc chạy `run_all.py --stage m5` trước khi tag `m5` / `submission`.
- Lưu ý cấu hình entry point trên Streamlit Cloud: đặt `Main file path` là `app/app.py`. Nếu muốn dùng theme trong `app/.streamlit/config.toml` khi chạy local, chạy từ `cd app && python -m streamlit run app.py` (hoặc copy cấu hình vào `.streamlit/config.toml` ở root nếu deploy cloud).

---

## Lệnh kiểm thử toàn bộ sau khi hoàn tất

```sh
python -m py_compile app/__init__.py app/data_views.py app/solver_views.py app/temporal_views.py app/dynamics_views.py app/precompute.py app/presentation.py app/presentation_views.py app/app.py run_all.py
python run_all.py --seed "$(cat data/seed.txt)" --stage m5
# Windows PowerShell: python run_all.py --seed (Get-Content data/seed.txt -Raw).Trim() --stage m5
python -m pytest app/tests -q
cd app && python -m streamlit run app.py
```

---

## Gợi ý Live-Change khi quay video bảo vệ (~30 phút, 2 gợi ý / thành viên)

1. **Patch 1 — `2551931 Dinh Hoang Quang Vinh` (`app/data_views.py`, `app/presentation.py`, `app/presentation_views.py`)**
   - Trong `staff_workload_rows` (`app/data_views.py`), thêm cột `max_week_load = max(by_week[i, k] for k in range(len(starts)))` hoặc bộ lọc theo buổi (`M`, `A`, `N`) trong `weekly_assignment_rows`, rồi chạy `python -m pytest app/tests/test_m5_data_views.py -q`.
   - Trong `overview(inst)` (`app/presentation_views.py`), đổi 3 cột metric thành 4 cột để thêm `"Tỉ lệ ca/giám thị"` = `f"{sum(inst.demand)/len(inst.staff_ids):.2f}"` và mở lại trang Tổng quan kiểm chứng trực tiếp.

2. **Patch 2 — `2551896 Nguyen Quoc Hung` (`app/solver_views.py`, `app/presentation_views.py`)**
   - Trong `solve_schedule_in_app` (`app/solver_views.py`), đổi `weight_scale` (ví dụ `(2.0, 1.0, 1.0)` để tăng trọng số phạt cơ sở) khi giải lát cắt `week1` hoặc `toy` và đối chiếu sự thay đổi `location` vs `l1` trong bảng `compare_schedule_metrics`.
   - Trong `plan_panel` (`app/presentation_views.py`), bổ sung metric thứ 4 `"Chênh lệch tải (max - min)"` = `result["spread"]` cạnh `Tải đỉnh`, `Độ lệch tải L1` và `Vi phạm H1–H3`.

3. **Patch 3 — `2551919 Dang Nguyen Thien Phuc` (`app/temporal_views.py`, `app/presentation_views.py`, `app/app.py`)**
   - Trong `word_lab` (`app/presentation_views.py`), thêm chuỗi mẫu mới vào dict `examples` (ví dụ `"MNN": "Vi phạm R2 · hai ca tối liên tiếp"` hoặc `"MM-MM-N": "Hợp lệ R1–R3"`) và chạy trace từng ngày trên tab **Thử chuỗi ngày**.
   - Trong `evaluate_temporal_validity` (`app/temporal_views.py`) và `temporal_panel` (`app/presentation_views.py`), hiển thị thêm trạng thái `R4_ok` (`|#M - #A| <= 3`) trên bảng giám thị để minh họa ranh giới regular (R1–R3) vs bounded counter (R4).

4. **Patch 4 — `2551913 Vo Nguyen Vi Nguyen` (`app/dynamics_views.py`, `app/presentation_views.py`, `app/precompute.py`)**
   - Trong `dynamics_panel` (`app/presentation_views.py`), nâng cận trên slider `"Mức tăng fatigue ban đầu"` (`10.0 -> 20.0`) hoặc số tuần mặc định (`12 -> 24`) để minh họa `F tại tuần 0` thay đổi trong khi `Điểm cân bằng F*` giữ nguyên vì `|a| < 1`.
   - Trong `run_m5` (`app/precompute.py`), bổ sung trường `equal_load_spread` vào `payload["m4_stability"]` (hoặc `payload`), chạy `python run_all.py --seed "$(cat data/seed.txt)" --stage m5` hai lần để kiểm chứng JSON đầu ra giống hệt từng byte.

5. **Patch 5 — `2551922 Chu Ngoc Phuc Thanh` (`app/app.py`, `app/precompute.py`, `app/tests/test_m5_app_integration.py`)**
   - Trong `main()` (`app/app.py`), hiển thị thêm tổng số giám thị và số ca thi của `inst` đang chọn ngay trong popover **Tùy chọn dữ liệu**, rồi chạy `python -m pytest app/tests/test_m5_app_integration.py -q`.
   - Trong `app/tests/test_m5_app_integration.py`, bổ sung assertion `AppTest` kiểm tra cả khi chọn lịch `M2 Optimal` ở route `m3` (`24/73` đạt DFA) so với `M2 + R1xR2xR3` (`73/73` đạt DFA).

---

## Kiểm chứng thực tế (Validation Log)

- **Kiểm tra nền base & chữ ký file:** Đã tái dựng bản checkout sạch khớp blob SHA-1 của commit gốc `79b7743756a6722f99ab9f129c27125f5539081f` (`DECISIONS.md`: `090d24f`, `README.md`: `d4471d8`, `app/README.md`: `dae1c06`, `run_all.py`: `87628ae`). Mọi file trong `patch_m5/` dùng LF (`\n`, `0` CRLF) và khớp `SHA256SUMS` & `series`.
- **Kiểm thử tuần tự từng patch trên checkout sạch:**
  - Sau Patch 1 (`0001`): `py_compile`, import `app.data_views` / `app.presentation` / `app.presentation_views`, và `pytest app/tests -q` -> **3 passed**.
  - Sau Patch 2 (`0002`): `py_compile`, import `app.solver_views` / `app.presentation_views`, và `pytest app/tests -q` -> **6 passed**.
  - Sau Patch 3 (`0003`): `py_compile`, import `app.temporal_views` / `app.presentation_views` / `app.app`, và `pytest app/tests -q` -> **9 passed**.
  - Sau Patch 4 (`0004`): `py_compile`, import `app.dynamics_views` / `app.presentation_views` / `app.precompute`, và `pytest app/tests -q` -> **12 passed**.
  - Sau Patch 5 (`0005`): `py_compile` + import toàn bộ module; chạy `python run_all.py --seed 1358677812 --stage m5` hai lần liên tiếp cho stdout và file `app/m5_bundle.json` giống nhau từng byte (`140.219` bytes), `0` thay đổi trên `m1_logic/`, `m2_ilp/`, `m3_automata/`, `m4_dynamics/`, `data/`, `tools/`; sau đó `pytest app/tests -q` -> **22 passed**.
- **Đối chiếu từng byte & hoàn tác (reverse-apply):** Toàn bộ 15 file `.py` (`app/` và `run_all.py`) khớp từng byte với workspace gốc; `app/presentation.css` và `app/.streamlit/config.toml` khớp sau khi chuẩn hóa LF. Đảo ngược `0005 -> 0001` bằng `git apply -R` khôi phục nguyên trạng cây base (`git diff` rỗng và `git status --porcelain` sạch).
