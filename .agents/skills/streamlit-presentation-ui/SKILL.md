---
name: streamlit-presentation-ui
description: Use when designing or editing the CO2011 Module 5 Streamlit presentation, including roster demos, navigation, and technical callouts.
---

# Streamlit Presentation UI

- Preserve the `streamlit run app/app.py` entry point and existing solver adapters. Keep changes under `app/`; do not change Modules 1–4 or the input dataset.
- Lead each view with a question the presenter can answer by running a preset. Use Vietnamese for UI copy; keep code identifiers and established technical terms intact.
- Label saved artifacts separately from live runs. Label an unavailable result as unavailable, never as a failed solver check. Distinguish M2 hard feasibility from M3 temporal acceptance and M4 modeled fatigue from measured fatigue.
- Put the input, key output, and next action first. Put source symbols, structures, and bounded complexity claims in a labeled technical callout. State which variables and algorithm each bound describes.
- Prefer native Streamlit controls, visible labels, and keyboard focus. Use CSS for visual hierarchy and contrast, and escape any values interpolated into HTML. Keep fonts/assets offline and check desktop and narrow layouts.
