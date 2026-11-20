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

1. **Tổng quan kiến trúc:** show the shared dataset and follow the inputs and outputs through M1–M4.
2. **Logic và SAT:** select the toy example or the seeded slice, then switch between SAT and UNSAT. Compare the SAT witness with the inclusion-minimal UNSAT core and inspect the Logic-to-0/1-Linear bridge.
3. **Tối ưu lịch ILP:** select a schedule or solve a subset with CBC. Compare peak load, L1 deviation and soft penalties; filter the weekly table by campus and export the visible rows. The CSV export is a presentation report, not a dense M2 schedule file.
4. **Quy tắc thời gian DFA:** select a sample word or type your own over `M`, `A`, `N`, `-`. Inspect the first violating day and compare the submitted product with its minimized form. On a real schedule, select a staff member to inspect their daily trace.
5. **Fatigue và công bằng:** set the initial perturbation for one staff member. Compare their trajectory with the unchanged fixed point and inspect the fairness variance or spread over time. Fatigue is a workload proxy, not a measurement.
6. **Demo đầu-cuối:** inspect SAT, the weekly assignment table, DFA acceptance, and the fatigue and fairness charts on one screen. Switch between the baseline and the precomputed M2+DFA schedule to show why hard-rule feasibility alone is not enough.

## Data and solver limits

- The full Faculty dataset uses the checked-in `app/m5_bundle.json` when it matches the seed and dataset. Refresh it outside the live demo with `python -m app.precompute`. A missing bundle can make the first full load slower; the app identifies the fallback source.
- For live solves use one- or two-week slices or the toy instance. CBC's limit applies to each solver call, not the whole workflow. The app distinguishes infeasibility from a run that produced no schedule. Solver results stay in the session and are not reused after a change in data or solver settings.
- Upload anonymized dataset CSV files with the same columns as `data/input.csv` (up to 512 KiB, 2,000 records, 150 staff, 150 sessions and 120 calendar days). More restrictive model-size limits apply to overlapping sessions and live DFA solves. The optional full-dataset schedule upload accepts up to 2 MiB and uses `invigilator_id,session_id,assigned` with one row per pair and flags `0` or `1`, as in `m2_ilp/schedule.csv`. Run the presentation on localhost; the app does not authenticate remote users.

## Implementation and AI use

`app.py` owns the shared inputs and navigation. `presentation.py`, `presentation.css`, and `presentation_views.py` render the views and technical callouts. The existing data, solver, DFA and dynamics adapters call Modules 1–4; those modules and the original dataset are unchanged.

AI assistance was used to redesign the Streamlit presentation and write interaction checks. Project-local guidance lives in [`streamlit-presentation-ui`](../.agents/skills/streamlit-presentation-ui/SKILL.md) and [`module5-verification`](../.agents/skills/module5-verification/SKILL.md). The team should review the changes and be able to explain the underlying models before presenting.
