# Module 5 — Streamlit presentation

Use Python 3.12 with the root requirements installed. Start Streamlit from `app/` so it loads the presentation theme:

```sh
cd app
python -m streamlit run app.py
cd ..
python -m pytest app/tests -q
```

`streamlit run app/app.py` from the repository root remains supported; it uses the caller's Streamlit theme settings.

The light theme combines UI UX Pro Max's educational-dashboard palette with
Open Design's Airtable/Dashboard references. Qiaomu's craft pass replaced the
generic gradient with a timetable motif, moved the demo action above the
architecture explanation, and paired rounded surfaces with a visible focus ring.
All styling assets are local; no external typeface or script is needed.

## Live walkthrough

Use **Bắt đầu trình chiếu**, then switch sections from the top bar or use
**Phần trước** and **Phần tiếp**. Changing sections returns to the top; changing
data or schedule keeps the controls in place. Live solving updates the selected
schedule when it returns a feasible plan. Source provenance lives in **Tùy chọn dữ liệu**.
Implementation details stay out of the projected UI:

| Module | Implementation reference |
| --- | --- |
| M1 | `encode_invigilator_assignment`, `solve_instance`, `extract_minimal_core`, and `clause_to_linear`. CNF encoding is linear in the emitted literals; the deletion-based minimizer makes at most quadratic SAT calls in the initial core size. |
| M2 | `create_variables`, `build_model`, `solve`, and `check_schedule`. The sparse assignment variables use storage proportional to the available staff/session pairs. CBC's search tree can grow exponentially. |
| M3 | `DFA.run`, `DFA.accepts`, `product`, `minimize`, and `add_regular_constraint`. With the fixed alphabet, a DFA run is linear in days and uses constant extra memory; a trace stores a state per day. |
| M4 | `WeeklyWorkload`, `calibrate`, `simulate`, and `fixed_point`. Retaining the full trajectory takes time and storage proportional to staff times simulation steps. |

1. **Tổng quan kiến trúc:** show the shared dataset and follow the inputs and outputs through M1–M4.
2. **Logic và SAT:** select one session to see the people assigned in the SAT witness. Use **Thử UNSAT** to show the exact sessions and people in the inclusion-minimal conflict, then **Thử SAT** to return to a feasible example. The second tab contains the Logic-to-0/1 bridge.
3. **Tối ưu lịch ILP:** compare the peak-load and fairness cards before opening the table. Filter by week and campus, select a single session to show the assigned staff, or switch to the workload chart. The CSV export is a presentation report, not a dense M2 schedule file.
4. **Quy tắc thời gian DFA:** read R1–R3 and their counts above the roster table. Filter the roster by one rule, or switch to the word lab to demonstrate when a sequence first violates a rule.
5. **Fatigue và công bằng:** adjust the initial perturbation, then switch between the individual trajectory, team fairness, model and historical load. Open the chart's data popover on demand.
6. **Demo đầu-cuối:** switch between SAT, the weekly assignment table, DFA acceptance and fatigue using four tabs on one page. Switch between the baseline and the precomputed M2+DFA schedule to distinguish hard-rule feasibility from temporal validity.

## Data and solver limits

- The full Faculty dataset uses the checked-in `app/m5_bundle.json` when it matches the seed and dataset. Refresh it outside the live demo with `python -m app.precompute`. A missing bundle can make the first full load slower; the app identifies the fallback source.
- For live solves use one- or two-week slices or the toy instance. CBC's limit applies to each solver call, not the whole workflow. The app distinguishes infeasibility from a run that produced no schedule. Solver results stay in the session and are not reused after a change in data or solver settings.
- Upload anonymized dataset CSV files with the same columns as `data/input.csv` (up to 512 KiB, 2,000 records, 150 staff, 150 sessions and 120 calendar days). More restrictive model-size limits apply to overlapping sessions and live DFA solves. The optional full-dataset schedule upload accepts up to 2 MiB and uses `invigilator_id,session_id,assigned` with one row per pair and flags `0` or `1`, as in `m2_ilp/schedule.csv`. Run the presentation on localhost; the app does not authenticate remote users.

## Implementation and AI use

`app.py` owns the shared inputs and navigation. `presentation.py`, `presentation.css`, and `presentation_views.py` render the views and technical callouts. The existing data, solver, DFA and dynamics adapters call Modules 1–4; those modules and the original dataset are unchanged.

AI assistance was used to redesign the Streamlit presentation and write interaction checks. Project-local guidance lives in [`streamlit-presentation-ui`](../.agents/skills/streamlit-presentation-ui/SKILL.md) and [`module5-verification`](../.agents/skills/module5-verification/SKILL.md). The team should review the changes and be able to explain the underlying models before presenting.
