---
name: module5-verification
description: Use when validating, debugging, or preparing a handoff for the CO2011 Module 5 Streamlit app.
---

# Verify Module 5

- Compile all Python files under `app/`; run `python -m pytest app/tests -q` with the pinned Streamlit version where available. Test real adapters rather than replacing solver outputs with mock results.
- Verify every route in the running app. Cover SAT and UNSAT, a live ILP solve, a DFA rejection with its state trace, a fatigue perturbation, and a full pipeline with a consistent source for all results. Exercise valid and invalid CSV input without rendering raw exceptions.
- When a check fails, trace the source data, adapter result, and UI state before editing. Keep existing behavior and core solver contracts intact.
- Before committing, inspect `git status` and changed paths, including untracked, staged and branch changes. Only `app/` and explicitly approved skill files belong in this change. Preserve other work; report test and push failures instead of bypassing them.
