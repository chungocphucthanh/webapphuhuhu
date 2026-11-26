"""Streamlit entry point for the CO2011 Module 5 presentation."""

from __future__ import annotations

import csv
import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
# Streamlit prepends app/; the package must win over the sibling app.py.
if sys.path[0] != str(ROOT_DIR):
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
from pulp import PulpSolverError

from app.ui.theme import force_light_theme, inject_css
from app.views import m1_logic, m2_ilp, m3_automata, m4_dynamics, m5_integration, overview

LOGGER = logging.getLogger(__name__)
# Widget choices that must survive a page change (Streamlit drops the state of widgets it did not draw).
KEEP = ("idea_m1", "idea_m2", "idea_m3", "idea_m4", "m1_case", "m2_slice", "m2_enforce", "m3_word", "m4_a",
        "m5_data", "m5_week", "m5_schedule")
ROUTES = {
    "overview": ("0", "Tổng quan", overview.render),
    "m1": ("1", "Logic", m1_logic.render),
    "m2": ("2", "ILP", m2_ilp.render),
    "m3": ("3", "Automata", m3_automata.render),
    "m4": ("4", "Dynamics", m4_dynamics.render),
    "m5": ("5", "Tích hợp", m5_integration.render),
}


def main() -> None:
    st.set_page_config(page_title="CO2011 · Xếp lịch coi thi", layout="wide", initial_sidebar_state="expanded")
    force_light_theme()
    inject_css()
    for key in KEEP:
        if key in st.session_state:
            st.session_state[key] = st.session_state[key]
    route = st.sidebar.radio("Điều hướng", list(ROUTES), key="route", label_visibility="collapsed",
                             format_func=lambda key: f"**{ROUTES[key][0]}** {ROUTES[key][1]}")
    try:
        ROUTES[route][2]()
    except (OSError, ValueError, RuntimeError, csv.Error, PulpSolverError):
        LOGGER.exception("Module 5 page %s failed", route)
        st.error("Trang này chưa chạy được. Kiểm tra data/seed.txt, dữ liệu và gói app/m5_bundle.json rồi tải lại trang.")


if __name__ == "__main__":
    main()
