"""Design tokens and the one stylesheet of the Module 5 app."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from streamlit import config

INK, INK2, MUTED, LINE = "#0E1726", "#44516A", "#5E6C84", "#D5DBE4"
BLUE, ORANGE, AQUA, BAD = "#2A78D6", "#EB6834", "#1BAF7A", "#C0362C"
SERIES = (BLUE, ORANGE, AQUA)  # fixed order, never cycled
CSS_PATH = Path(__file__).with_name("theme.css")
THEME = {"theme.base": "light", "theme.primaryColor": INK, "theme.backgroundColor": "#FFFFFF",
         "theme.secondaryBackgroundColor": "#F5F7FA", "theme.textColor": INK}


def force_light_theme() -> None:
    # `streamlit run app/app.py` from the repo root never reads app/.streamlit/config.toml,
    # so on a dark-mode OS the widgets would come out dark on our white page.
    changed = [key for key, value in THEME.items() if config.get_option(key) != value]
    for key in changed:
        config.set_option(key, THEME[key])
    if changed:
        st.rerun()  # the theme travels in the next run's NewSession message


@st.cache_data(show_spinner=False)
def _css(mtime: int) -> str:
    return CSS_PATH.read_text(encoding="utf-8")


def inject_css() -> None:
    st.markdown(f"<style>{_css(CSS_PATH.stat().st_mtime_ns)}</style>", unsafe_allow_html=True)


def vn(value: float, digits: int = 2) -> str:
    """Vietnamese number format: comma decimals, period thousands."""
    text = f"{value:,.{digits}f}"
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
