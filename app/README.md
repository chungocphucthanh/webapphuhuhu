# M5 — Integration & Streamlit Web Application

`app/app.py` integrates all four CO2011 modules into a single-page Streamlit decision-support dashboard:

1. **Dataset selection & upload** (`app/data_views.py`): choose the full Faculty dataset (73 staff, 83 sessions, 27 calendar days), 1-week or 2-week real-data slices, the M1 seeded SAT/UNSAT slice, the brief's toy instance, or upload a custom dataset/schedule CSV validated through M1 and M4's strict readers.
2. **Module 1 — Logic & SAT check** (`app/solver_views.py`): report CNF assignment/auxiliary variable and clause counts, run `Minisat22` satisfiability or minimal assumption-based UNSAT core extraction, and inspect the Logic-to-0/1-Linear bridge.
3. **Module 2 — ILP schedule & fairness** (`app/data_views.py`, `app/solver_views.py`): filter the session-by-session weekly assignment table by week and campus, export CSV plans, compare Baseline vs solved schedules (`max_load`, `L1`, `LOC`, `FAT`, `TRV`), diagnose infeasible shortages via elastic slacks, and solve subsets/uploads live with configurable CBC time limits.
4. **Module 3 — Automaton temporal validity** (`app/temporal_views.py`): display the prominent **Schedule valid (DFA-accepted)** flag, per-rule violation counts (`R1`, `R2`, `R3`, plus informational `R4`), product/minimization state counts (`259 -> 15`), and per-invigilator 27-day strings over `{M, A, N, -}` with first-violation day traces.
5. **Module 4 — Vector fatigue dynamics (Direction B)** (`app/dynamics_views.py`): plot fairness curves (fatigue spread `max - min` and variance over time), within-term block-end peak fatigue against the 95% soft threshold `H`, and long-run trajectories converging to `F*` with interactive perturbation testing.

## Run

From the repository root with Python 3.12 and `requirements.txt` installed:

```sh
# Optional offline precomputation of the full-dataset bundle (also run by stage 'all')
python run_all.py --seed "$(cat data/seed.txt)" --stage m5

# Launch the Streamlit dashboard (works both with and without precomputation)
streamlit run app/app.py

# Run Module 5 unit and headless UI tests
python -m pytest app/tests -q
```
