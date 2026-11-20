"""Shared presentation components and session-local memoization for Module 5."""

from collections.abc import Callable, Mapping
from html import escape
from pathlib import Path
from typing import TypeVar

import pandas as pd
import streamlit as st

T = TypeVar("T")

PRESETS = {
    "full": "Toàn bộ dữ liệu khoa",
    "week1": "Dữ liệu thực · 1 tuần",
    "week2": "Dữ liệu thực · 2 tuần",
    "m1_slice": "Lát cắt SAT / UNSAT",
    "toy": "Ví dụ nhỏ trong đề bài",
    "upload": "Tải dữ liệu CSV riêng",
}

SCHEDULES = {
    "Baseline": "Lịch gốc",
    "M2 Optimal": "Lịch tối ưu M2",
    "M2 + R1xR2xR3": "Lịch M2 + DFA",
    "M4 Fatigue-Aware": "Lịch M2 + ngưỡng fatigue",
    "Uploaded Schedule": "Lịch CSV tải lên",
    "Solved Plan": "Lịch vừa giải bằng CBC",
    "Equal-load reference": "Tham chiếu tải đều",
}


def apply_style() -> None:
    css = Path(__file__).with_name("presentation.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def hero(track: str, title: str, description: str) -> None:
    st.markdown(
        '<div class="iap-hero">'
        f'<p class="iap-track">{escape(track)}</p>'
        f'<h1>{escape(title)}</h1><p>{escape(description)}</p></div>',
        unsafe_allow_html=True,
    )


def badge(kind: str, label: str) -> str:
    style = {"Hàm / lớp": "code", "Thuật toán / cấu trúc": "algorithm", "Big-O": "bound"}[kind]
    return f'<code class="iap-badge iap-{style}">{escape(label)}</code>'


def technical(symbols: tuple[str, ...], algorithms: tuple[str, ...], bounds: tuple[str, ...], note: str) -> None:
    with st.expander("Góc kỹ thuật"):
        for kind, values in (("Hàm / lớp", symbols), ("Thuật toán / cấu trúc", algorithms), ("Big-O", bounds)):
            pills = " ".join(badge(kind, value) for value in values)
            st.markdown(f'<div class="iap-badges"><b>{kind}</b>{pills}</div>', unsafe_allow_html=True)
        st.write(note)


def spreadsheet_text(value):
    """Keep uploaded identifiers literal in Streamlit's built-in CSV export."""
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) and value != "-":
        return "'" + value
    return value


def table(rows: list[dict], columns: Mapping[str, str]) -> None:
    if not rows:
        st.info("Không có dòng nào khớp với lựa chọn hiện tại.")
        return
    frame = pd.DataFrame(rows, columns=list(columns)).rename(columns=columns)
    for field in {"session", "session_id", "staff_id", "staff", "invigilators"} & columns.keys():
        label = columns[field]
        frame[label] = frame[label].map(spreadsheet_text)
    st.dataframe(frame, hide_index=True, use_container_width=True)


def memo(slot: str, key: object, build: Callable[[], T]) -> T:
    """Keep the most recent result per operation, private to this browser session."""
    cache = st.session_state.setdefault("iap_results", {})
    if slot not in cache or cache[slot][0] != key:
        cache[slot] = (key, build())
    return cache[slot][1]


def schedule_label(value: str) -> str:
    return SCHEDULES.get(value, value)


def named_rows(rows: list[dict], field: str = "schedule") -> list[dict]:
    return [{**row, field: schedule_label(row[field])} for row in rows]
