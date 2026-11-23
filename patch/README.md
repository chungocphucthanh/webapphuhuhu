# M5 patch series

Base commit: `79b7743756a6722f99ab9f129c27125f5539081f`.

These five ordinary Git diff patches capture the Module 5 (`app/`) single-page
Streamlit dashboard, module adapters, integration tests, `run_all.py` stage
hook, and documentation in sequential commit order. Generated runtime outputs
(`*.json`, `*.csv`, `*.png`), `__pycache__/`, `.pytest_cache/`, and uncommitted
local working-tree edits are excluded.

Apply them to a clean checkout of the base commit. Keep this patch directory
outside the target checkout, or substitute its absolute path in the commands
below. These are `git apply` patches, not `git am` mail patches; commit
messages and exact `git add` paths are supplied below.

| Order | Patch | Files & LOC | Commit message |
| --- | --- | --- | --- |
| 1 | [0001-load-datasets-and-check-m1-logic.patch](0001-load-datasets-and-check-m1-logic.patch) | `app/__init__.py`, `app/data_context.py`, `app/m1_section.py`, `app/tests/test_m1_section.py` (`+252 / -0`) | `m5: load datasets and check m1 logic` |
| 2 | [0002-inspect-and-solve-m2-schedules.patch](0002-inspect-and-solve-m2-schedules.patch) | `app/m2_section.py`, `app/tests/test_m2_section.py` (`+249 / -0`) | `m5: inspect and solve m2 schedules` |
| 3 | [0003-verify-m3-automata-temporal-rules.patch](0003-verify-m3-automata-temporal-rules.patch) | `app/m3_section.py`, `app/tests/test_m3_section.py` (`+243 / -0`) | `m5: verify m3 automata temporal rules` |
| 4 | [0004-simulate-and-plot-m4-dynamics.patch](0004-simulate-and-plot-m4-dynamics.patch) | `app/m4_section.py`, `app/tests/test_m4_section.py` (`+250 / -0`) | `m5: simulate and plot m4 vector fatigue dynamics` |
| 5 | [0005-wire-streamlit-app-precompute-and-docs.patch](0005-wire-streamlit-app-precompute-and-docs.patch) | `app/precompute.py`, `app/app.py`, `app/tests/test_app_integration.py`, `run_all.py`, `app/README.md`, `README.md`, `DECISIONS.md` (`+250 / -2`) | `m5: wire streamlit dashboard precompute and docs` |

Apply and commit each patch in order (replace `/path/to/patched/m5` with the patch directory path):

```sh
git apply --check /path/to/patched/m5/0001-load-datasets-and-check-m1-logic.patch
git apply /path/to/patched/m5/0001-load-datasets-and-check-m1-logic.patch
git add -- app/__init__.py app/data_context.py app/m1_section.py app/tests/test_m1_section.py
git commit -m "m5: load datasets and check m1 logic"

git apply --check /path/to/patched/m5/0002-inspect-and-solve-m2-schedules.patch
git apply /path/to/patched/m5/0002-inspect-and-solve-m2-schedules.patch
git add -- app/m2_section.py app/tests/test_m2_section.py
git commit -m "m5: inspect and solve m2 schedules"

git apply --check /path/to/patched/m5/0003-verify-m3-automata-temporal-rules.patch
git apply /path/to/patched/m5/0003-verify-m3-automata-temporal-rules.patch
git add -- app/m3_section.py app/tests/test_m3_section.py
git commit -m "m5: verify m3 automata temporal rules"

git apply --check /path/to/patched/m5/0004-simulate-and-plot-m4-dynamics.patch
git apply /path/to/patched/m5/0004-simulate-and-plot-m4-dynamics.patch
git add -- app/m4_section.py app/tests/test_m4_section.py
git commit -m "m5: simulate and plot m4 vector fatigue dynamics"

git apply --check /path/to/patched/m5/0005-wire-streamlit-app-precompute-and-docs.patch
git apply /path/to/patched/m5/0005-wire-streamlit-app-precompute-and-docs.patch
git add -- app/precompute.py app/app.py app/tests/test_app_integration.py run_all.py app/README.md README.md DECISIONS.md
git commit -m "m5: wire streamlit dashboard precompute and docs"
```

## Verification commands

```sh
.venv/bin/python -m pytest app/tests -q
.venv/bin/python run_all.py --seed "$(cat data/seed.txt)" --stage m5
.venv/bin/python -m streamlit run app/app.py
```

## Live-change defense suggestions (2 per patch / member)

1. **Patch 1 (`data_context.py`, `m1_section.py`)**
   - Change `DEFAULT_SUBSET_DAYS` in `app/data_context.py` (e.g., `7 -> 10`) or enter an alternate seed in the sidebar to observe deterministic changes in `sessions_df`, `soft_weights`, and candidate availability `|A|`.
   - Toggle `Simulate single-session staff shortage (UNSAT core)` or pass an extra `(staff, session)` pair via `extra_busy` in `check_m1_feasibility` to flip SAT to UNSAT and inspect the minimal UNSAT core.
2. **Patch 2 (`m2_section.py`)**
   - Switch to `subset` mode with `Live bounded CBC solve` and adjust `time_limit` or `ModelConfig` soft weights in `_cached_m2_solve` to observe soft-penalty trade-offs (`LOC/FAT/TRV`) at fixed optimal `max_load`.
   - Upload a dense `invigilator_id,session_id,assigned` CSV with one flipped assignment bit to trigger immediate hard-rule or schema validation errors via `parse_uploaded_schedule`.
3. **Patch 3 (`m3_section.py`)**
   - Tighten `r1()` in `RULE_BUILDERS` (e.g., at most 1 consecutive working day) to watch the minimal product DFA state count, per-rule acceptance rates, and exact `day_step` violation pinpointing update live.
   - Select `subset` mode and enable `Re-solve slice with M3 DFA flow constraints (add_rules_to_m2)` to flip `Schedule valid (DFA-accepted)` from `No` to `Yes` (`100%` accepted).
4. **Patch 4 (`m4_section.py`)**
   - Adjust the `Initial impulse delta_f0` slider or `Perturbed invigilator` selector to verify geometric contraction `|delta_f0| * |a|^n` without shifting the equilibrium vector `F*`.
   - Change `fit_threshold` coverage in `app/m4_section.py` (e.g., `0.95 -> 0.85`) or switch `Trajectory regime` across `Baseline`, `M2`, `M4 fatigue-aware`, and `Equal-load reference` to inspect threshold excess and spread convergence.
5. **Patch 5 (`app.py`, `precompute.py`, `run_all.py`)**
   - Add a new KPI metric (e.g., `M3 Violation Count` or `M4 Threshold H`) to the top 5-column overview ribbon in `app/app.py` and re-run `AppTest` to verify single-page propagation.
   - Add an `equal_load_spread` field to `build_m5_summary` in `app/precompute.py` and run `python run_all.py --seed "$(cat data/seed.txt)" --stage m5` twice to verify byte-identical JSON output.

Validation: every patch was checked and applied in order to a clean temporary
checkout of `79b7743756a6722f99ab9f129c27125f5539081f`. `pytest app/tests -q`
passed after each individual commit (`4`, `8`, `13`, `27`, and `29` passed). All
17 touched files use LF line endings and match the build checkout byte-for-byte;
two consecutive `run_all.py --stage m5` runs produced identical bytes with zero
mutation of M1-M4 files. Reversing `0005` through `0001` restored the exact base
tree. No source files, index entries, branches, or commits were changed in the
working repository.
