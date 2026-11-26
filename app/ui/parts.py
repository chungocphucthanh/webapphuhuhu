"""Escaped HTML building blocks shared by every page."""

from __future__ import annotations

from html import escape

import streamlit as st

BADGE_KINDS = ("fn", "ds", "bigo")
VERDICT_ICON = {"good": "✓", "bad": "✕", "warn": "="}


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def marker(name: str) -> None:
    """Tag the enclosing block so theme.css can style it (dock, figure, tile)."""
    html(f'<span class="iap-mk iap-mk-{escape(name)}"></span>')


def badge(kind: str, text: str) -> str:
    if kind not in BADGE_KINDS:
        raise ValueError(f"Unknown badge kind: {kind}")
    return f'<span class="iap-badge-{kind}">{escape(text)}</span>'


def callout(fn=(), ds=(), bigo=(), note: str = "") -> None:
    """Góc kỹ thuật: original functions/classes, data structures/algorithms, Big-O."""
    items = [badge("fn", t) for t in fn] + [badge("ds", t) for t in ds] + [badge("bigo", t) for t in bigo]
    tail = f'<span class="iap-cap">{escape(note)}</span>' if note else ""
    html('<div class="iap-badges"><span class="iap-lab">Góc kỹ thuật</span>' + "".join(items) + tail + "</div>")


def headline(pre: str, hot: str, post: str, sub: str = "") -> None:
    body = f'<h1 class="iap-h1">{escape(pre)}<mark>{escape(hot)}</mark>{escape(post)}</h1>'
    html(body + (f'<div class="iap-sub">{escape(sub)}</div>' if sub else ""))


def points(items) -> None:
    rows = "".join(f"<div><b>{escape(h)}</b><span>{escape(t)}</span></div>" for h, t in items)
    html(f'<div class="iap-points">{rows}</div>')


def verdict(kind: str, title: str, detail: str = "") -> None:
    html(f'<div class="iap-verdict {kind}" role="status"><i aria-hidden="true">{VERDICT_ICON[kind]}</i>'
         f"<div><b>{escape(title)}</b><span>{escape(detail)}</span></div></div>")


def kpis(items) -> None:
    """items: (label, value, note)."""
    cells = "".join(f'<div class="iap-kpi"><small>{escape(l)}</small><b>{escape(v)}</b><em>{escape(n)}</em></div>'
                    for l, v, n in items)
    html(f'<div class="iap-kpis">{cells}</div>')


def flag(ok: bool, text: str) -> str:
    return f'<span class="{"iap-ok" if ok else "iap-no"}">{"✓" if ok else "✕"} {escape(text)}</span>'


def strip(word: str, tags: dict[int, str] | None = None) -> None:
    """One cell per day; tags maps a 1-based day to the rule violated there."""
    tags = tags or {}
    cells = "".join(
        f'<div><small>{d}</small><b class="{"R" if s == "-" else s}{" hit" if d in tags else ""}">{escape(s)}</b>'
        f"<em>{escape(tags.get(d, ''))}</em></div>" for d, s in enumerate(word, 1))
    html(f'<div class="iap-strip">{cells}</div>')


def hbars(rows, *, width: int = 120, alt: bool = False) -> None:
    """rows: (label, value, text). Bars share one scale; a zero value draws no bar."""
    top = max((v for _, v, _ in rows), default=0) or 1
    body = "".join(
        f"<div><span>{escape(label)}</span>"
        + (f'<i class="{"alt" if alt else ""}" style="width:{round(v / top * width)}px"></i>' if v > 0 else "")
        + f"<b>{escape(text)}</b></div>" for label, v, text in rows)
    html(f'<div class="iap-bars">{body}</div>')


def table(head, rows, classes=()) -> None:
    """rows of plain strings; classes gives a td class per column ('', 'num', 'mono')."""
    classes = list(classes) + [""] * (len(head) - len(classes))
    thead = "".join(f'<th class="{c}">{escape(h)}</th>' for h, c in zip(head, classes))
    tbody = "".join("<tr>" + "".join(f'<td class="{c}">{escape(str(v))}</td>' for v, c in zip(row, classes)) + "</tr>"
                    for row in rows)
    html(f'<table class="iap-table"><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table>')


def cards(items, *, tall: bool = False, columns: int | None = None) -> None:
    """items: (eyebrow, title, text, dark). columns fixes the grid; by default cards wrap to fit."""
    body = "".join(f'<div class="iap-card{" dark" if dark else ""}"><small>{escape(e)}</small><b>{escape(t)}</b>'
                   f"<span>{escape(x)}</span></div>" for e, t, x, dark in items)
    grid = f' style="grid-template-columns:repeat({int(columns)},minmax(0,1fr))"' if columns else ""
    html(f'<div class="iap-cards{" tall" if tall else ""}"{grid}>{body}</div>')


def roster(rows) -> None:
    """rows: (staff id, day string). One line per person, one cell per day, with a day-number header."""
    days = len(rows[0][1])
    head = "<span></span>" + "".join(f"<small>{d}</small>" for d in range(1, days + 1))
    body = "".join(f"<span>{escape(person)}</span>" + "".join(f'<b class="{"R" if s == "-" else s}">{escape(s)}</b>' for s in word)
                   for person, word in rows)
    html(f'<div class="iap-roster" style="grid-template-columns:52px repeat({days},minmax(0,1fr))">{head}{body}</div>')


def lines(items) -> None:
    """Monospace lines in one block (formulas, clauses, model rows)."""
    html('<div class="iap-lines">' + "".join(f"<span>{escape(item)}</span>" for item in items) + "</div>")


def flags(items) -> None:
    """items: (ok, text) drawn as a row of pass/fail pills."""
    html('<div class="iap-flags">' + "".join(flag(ok, label) for ok, label in items) + "</div>")


def text(kind: str, value: str) -> None:
    """kind: eyebrow, h2, cap, lab, mono, sub."""
    html(f'<div class="iap-{kind}">{escape(value)}</div>')
