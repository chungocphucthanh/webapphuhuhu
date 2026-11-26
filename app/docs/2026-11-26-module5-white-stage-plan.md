# Module 5 "Sân khấu nền trắng" Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Module 5 Streamlit UI as six one-screen pages (Tổng quan, Module 1–4, Module 5) where each module page presents its theory ideas with a figure and lets the presenter practise live.

**Architecture:** `app/app.py` injects one stylesheet, draws a narrow sidebar rail (one `st.radio`) and dispatches to one view file per page. Module pages declare their ideas as data (`Idea` records) and are drawn by one shared `stage` renderer: idea tabs, headline, figure + three points, a bordered "Thử ngay" dock, the "Góc kỹ thuật" badges and Ý trước / Ý tiếp. All Modules 1–4 calls go through the existing adapters (`data_views`, `solver_views`, `temporal_views`, `dynamics_views`, `precompute`, `experiments`) behind cached wrappers in `app/services.py`.

**Tech Stack:** Python 3.12, Streamlit 1.36.0 (pinned), Altair 5 (ships with Streamlit) for data charts, inline SVG/HTML for diagrams, pytest + `streamlit.testing.v1.AppTest`.

**Spec:** the approved canvas, page "Bản thiết kế · B nền trắng": `C:\Users\Admin\OpenArtifact\webapphuhuhu\co2011-iap-thiet-ke-lai-web-app\project\` (`TongQuan`, `M1-Logic`, `M2-ILP`, `M3-Automata`, `M4-Dynamics`, `M5-TichHop` `.dc.html`; copy, tokens and layout are read from these files). Brief: Module 5 section and rubric (M1 check, M2 plan, M3 flag, M4 trajectory in one page).

## Global Constraints

- Only files under `app/` change. Never edit `m1_logic/`, `m2_ilp/`, `m3_automata/`, `m4_dynamics/`, `data/`, `tools/`. Run Python with `PYTHONDONTWRITEBYTECODE=1`.
- Entry point stays `streamlit run app/app.py` from the repository root; no setting may depend on `app/.streamlit/config.toml` being loaded.
- Streamlit 1.36.0 API only: no `st.fragment`, `st.pills`, `st.segmented_control`, `st-key-*` CSS classes, or deprecated `st.experimental_*` / `st.cache`.
- Every page fits one 1440×900 window without page scroll.
- UI copy in Vietnamese (comma decimals, period thousands, old-style tone marks: hóa, thỏa); technical terms, function/class names and Big-O stay as in code.
- Tokens: ink `#0E1726`, secondary `#44516A`, muted `#5E6C84`, hairline `#E4E8EE` / `#D5DBE4`, panel `#F5F7FA`, accent `#F5B83D` (text on it `#1A1203`), accent tint `#FFF3D6` / `#7A4A00`, chart blue `#2A78D6`, orange `#EB6834`, aqua `#1BAF7A`, good `#0B6B2A` on `#E8F6EC`, bad `#A12A2A` on `#FCEBEA`, bad mark `#C0362C`.
- Badges come only from the shared helper, three kinds: `fn` (bg `#0F2A52`, text `#E6EEFB`, border `#2B4C82`, monospace), `ds` (bg `#EEEBFF`, text `#4530B3`, border `#B9B0F2`), `bigo` (bg `#FFF1E0`, text `#9A4A00`, border `#F2C48E`, monospace, labelled `Time:` / `Space:`).
- Fonts offline: headline `'Space Grotesk'` only if bundled under `app/static/fonts/`, else `'Segoe UI Variable Display', 'Segoe UI', system-ui`; body `'Segoe UI', system-ui, sans-serif`; mono `'Cascadia Mono', Consolas, monospace`. No external font, script or image.
- Every value interpolated into HTML goes through `html.escape`. Heavy calls sit behind `st.cache_data` or `st.session_state` and run inside `st.spinner`. Exceptions from Modules 1–4 surface as Vietnamese `st.error` / `st.warning`, never a traceback.
- Old UI files (`presentation.py`, `presentation.css`, `presentation_views.py`, `theory_content.py`) are not deleted without the owner's confirmation; they just stop being imported.

## Review Focus

1. Window shorter than 900 px: the page may scroll, but nothing overlaps or is clipped.
2. Uploaded CSV that is malformed or too large: Vietnamese `st.error`, the rest of the page still renders (test in Task 7).
3. Typed DFA string with lowercase or foreign characters, or empty: it is normalised to `M A N -`, at most 60 symbols, empty string shows a neutral message (test in Task 5).
4. CBC time limit hit or infeasible slice: status text says so and no schedule table is shown as if valid (test in Task 4).
5. Missing or stale `app/m5_bundle.json`: pages fall back to live artifacts and say which source is used (test in Task 7).

## File Structure

| File | Responsibility |
| --- | --- |
| `app/app.py` | page config, CSS injection, rail navigation, route dispatch, top-level error boundary |
| `app/ui/theme.py`, `app/ui/theme.css` | tokens, stylesheet text, `inject_css()` |
| `app/ui/parts.py` | escaped HTML helpers: `badge`, `callout`, `headline`, `points`, `verdict`, `kpi`, `strip`, `hbars`, `marker` |
| `app/ui/charts.py` | Altair config and `line_chart`, `column_chart`, `scatter_chart` with fixed heights |
| `app/ui/stage.py` | `Idea`, `Module`, `render_module(module)` |
| `app/services.py` | cached wrappers over the adapters |
| `app/views/overview.py`, `m1_logic.py`, `m2_ilp.py`, `m3_automata.py`, `m4_dynamics.py`, `m5_integration.py` | one page each: `IDEAS`, figure functions, `lab()`, `render()` |
| `app/tests/test_m5_ui.py` | AppTest over every route and interaction; replaces the AppTest parts of the two old UI test files |

## Tasks

### Task 1: Theme, parts and shell

**Files:** create `app/ui/__init__.py`, `theme.py`, `theme.css`, `parts.py`; rewrite `app/app.py`; create `app/views/__init__.py`, `app/views/overview.py` (placeholder body until Task 2 is not allowed: Task 1 ships the real overview headline and cards); test `app/tests/test_m5_ui.py`.

**Interfaces (produced):**
- `theme.inject_css() -> None`
- `parts.badge(kind: Literal["fn","ds","bigo"], text: str) -> str`; `parts.callout(fn: list[str], ds: list[str], bigo: list[str], note: str = "") -> None`
- `parts.headline(pre: str, hot: str, post: str, sub: str) -> None`; `parts.points(items: list[tuple[str, str]]) -> None`
- `parts.verdict(kind: Literal["good","bad","warn"], title: str, detail: str) -> None`; `parts.kpi(label: str, value: str, note: str = "") -> str`
- `parts.strip(word: str, tags: dict[int, str]) -> None`; `parts.hbars(rows: list[tuple[str, float, str]], good_note: str = "") -> None`; `parts.marker(name: str) -> None`
- `app.ROUTES: dict[str, tuple[str, str]]` = `overview, m1, m2, m3, m4, m5` → (number, short label); session key `route`; presenters `PRESENTERS = {"m1": "Vinh", "m2": "Hùng", "m3": "Phúc", "m4": "Nguyên", "m5": "Thành"}`.

- [ ] Test `test_every_route_renders_without_exception`: for each key in `ROUTES`, `AppTest.from_file(app.py, default_timeout=120)`, set `session_state["route"]`, `run()`, assert `not at.exception` and no `st.error`.
- [ ] Test `test_badge_kinds_are_distinct_and_escaped`: `badge("fn", "<b>")` contains `&lt;b&gt;` and class `iap-badge-fn`; the three kinds give three different class names; an unknown kind raises `ValueError`.
- [ ] Implement, run `pytest app/tests/test_m5_ui.py -q`, screenshot the overview at 1440×900.

### Task 2: Stage renderer and charts

**Files:** create `app/ui/stage.py`, `app/ui/charts.py`, `app/services.py`.

**Interfaces (produced):**
- `@dataclass(frozen=True) class Idea: title: str; pre: str; hot: str; post: str; sub: str; points: tuple[tuple[str, str], ...]; figure: Callable[[], None]`
- `@dataclass(frozen=True) class Module: key: str; label: str; ideas: tuple[Idea, ...]; start: int; lab_title: str; lab: Callable[[], None]; fn: tuple[str, ...]; ds: tuple[str, ...]; bigo: tuple[str, ...]; note: str`
- `stage.render_module(module: Module) -> None`; idea index lives in `st.session_state[f"idea_{module.key}"]`.
- `charts.line_chart(rows: list[dict], x: str, y: str, series: str | None, *, height: int, x_title: str, y_title: str, rules: list[tuple[float, str]] = ()) -> None`; `charts.column_chart(rows, x, y, series=None, *, height, x_title, y_title, log=False) -> None`; `charts.scatter_chart(rows, x, y, *, height, x_title, y_title, line: tuple[float, float] | None = None) -> None`. Series colours in fixed order blue, orange, aqua; never more than three series.
- `services`: `full() -> tuple[Instance, dict[str, frozenset], str]`, `m1_case(name: Literal["toy_sat","toy_unsat","slice_sat","slice_unsat"]) -> tuple[dict, dict]` (input data, `run_m1_check` result), `solve_slice(preset: Literal["toy","week1","week2"], enforce: bool, seconds: int) -> dict`, `temporal(schedule: str) -> dict`, `temporal_table() -> list[dict]`, `dynamics() -> dict`, `metrics_table() -> list[dict]`.

- [ ] Test `test_idea_navigation_changes_headline_but_keeps_lab_state` (on `m3`): click Ý tiếp, the headline text changes, the DFA text input keeps its value.
- [ ] Implement and run the tests.

### Tasks 3–6: Module pages (one task per module)

Each task creates `app/views/<module>.py` with `MODULE: Module` and `render()`, draws every figure of the module (no placeholder), wires the lab to the real adapters, and adds one AppTest per module to `test_m5_ui.py`.

- **Task 3, M1 (4 ideas):** figures: predicate table of H1–H3 with a real session; clause count of pairwise encoding against `CardEnc.equals` sequential counter as n grows (computed, cached); CNF → Minisat22 → SAT/UNSAT pipeline; Logic/CNF/linear bridge table from `CONVERSION_ROWS`. Lab: four scenarios, grid, verdict, core, CNF against linear row counts. Test: `slice_unsat` shows `UNSAT` and a core of 6; `toy_sat` shows `SAT`.
- **Task 4, M2 (5 ideas):** figures: availability grid (2.593 of 6.059 pairs); load histogram baseline against M2; six constraint cards with λ and K from the instance; baseline against M2 metric bars; LP-relaxation counterexample (4/3 against 2) and dropped-H2 double booking from `experiments`. Lab: Toy 3×4, Tuần 1, 2 tuần, checkbox R1–R3, CBC button with spinner, table + KPIs + status. Test: week-1 solve gives max load 1 and 0 violations; an infeasible or timed-out result shows a warning and no table.
- **Task 5, M3 (5 ideas):** figures: roster strips of real staff; R1 DFA; reachable against minimal state counts from `counts_table`; layered day × state graph for R1 with one accepted path; R4 counter chain plus pumping illustration. Lab: text input + five presets, strip, verdict, per-rule result, rejected counts per schedule. Tests: `MMM` rejected by R1 at day 3; `mm-x` normalised to `MM-`; empty input shows the neutral message.
- **Task 6, M4 (5 ideas):** figures: the brief's example 0, 2, 3,6 … towards 10; lag-one scatter with the OLS line (219 points); three regimes a = 0,27 / 1 / 1,05; spread over weeks for baseline, M2, equal load; peak fatigue per block against H for the schedules. Lab: slider for `a` + three presets, decay chart, verdict, two metrics. Test: `a = 1.05` shows "Phân kỳ"; `a = 0.27` shows "Ổn định tiệm cận".

### Task 7: Module 5 page and overview data panel

**Files:** `app/views/m5_integration.py`, `app/views/overview.py`.

- Headline exactly "Kết luận của 4 mô hình" (hot phrase "4 mô hình").
- Controls: dataset (Dữ liệu khoa, Tải CSV lên), week, schedule (Lịch gốc, M2 Optimal, M2 + DFA, M4 fatigue-aware), "Chạy tất cả". Four tiles on the selected schedule: M1 SAT check, M2 weekly assignment table with KPIs, M3 "Lịch hợp lệ" flag with per-rule counts, M4 variance-over-weeks and peak-fatigue charts.
- Tests: switching to "Lịch gốc" shows "Lịch chưa hợp lệ" and 41/73; "M2 + DFA" shows "Lịch hợp lệ" and 73/73; a malformed upload shows an `st.error` and no exception; with `bundle_path` pointing to a missing file the source label says live artifacts.

### Task 8: Verification gate and handoff

- [ ] `python -m py_compile` on every `app/**/*.py`; `pytest app/tests -q`.
- [ ] Run the app headless, screenshot all six routes at 1440×900, fix overflow.
- [ ] `git status`, `git diff --name-only`: only `app/` paths.
- [ ] Update `app/README.md`; ask the owner before deleting the four old UI files; commit and push only after their go-ahead.
