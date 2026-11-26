"""Altair charts with one fixed look: thin marks, hairline grid, at most three series."""

from __future__ import annotations

from html import escape
from math import ceil, floor, log10

import altair as alt
import streamlit as st

from .theme import BAD, INK, INK2, LINE, MUTED, SERIES

AXIS = dict(labelColor=MUTED, titleColor=INK2, gridColor=LINE, domainColor="#9AA5B5", tickColor="#9AA5B5",
            labelFontSize=11, titleFontSize=12, titleFontWeight="normal")
# Vietnamese number labels: 1.000 and 0,5 (swap the separators d3 prints).
VN = "replace(replace(replace(format(datum.value, ','), regexp(',', 'g'), '_'), '.', ','), regexp('_', 'g'), '.')"
# SVG stays sharp when the page is zoomed to fit the window; the export menu is noise on a slide.
EMBED = {"embedOptions": {"renderer": "svg", "actions": False}}


def _show(chart, height: int, rows=None) -> None:
    chart = (chart.properties(height=height, background="transparent", usermeta=EMBED,
                              padding={"left": 2, "right": 8, "top": 6, "bottom": 2})
             .configure_axis(**AXIS).configure_view(strokeWidth=0)
             .configure_legend(orient="top", title=None, labelColor=INK, labelFontSize=12, symbolStrokeWidth=3))
    st.altair_chart(chart, use_container_width=True, theme=None)
    if rows:  # the same numbers as a table: colour is never the only way to read a chart
        with st.popover("Số liệu"):
            header = "".join(f"<th>{escape(str(k))}</th>" for k in rows[0])
            body = "".join("<tr>" + "".join(f"<td>{escape(str(v))}</td>" for v in row.values()) + "</tr>" for row in rows)
            # st.dataframe loops React updates inside a popover on Streamlit 1.36, st.table adds a noise index
            st.markdown(f'<div class="dvt"><table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>',
                        unsafe_allow_html=True)


def _color(rows, series):
    if series is None:
        return alt.value(SERIES[0])
    names = list(dict.fromkeys(row[series] for row in rows))
    if len(names) > len(SERIES):
        raise ValueError("At most three series per chart")
    return alt.Color(f"{series}:N", scale=alt.Scale(domain=names, range=list(SERIES[:len(names)])))


def _steps(rows, x) -> alt.Axis:
    """Whole-number x values (weeks, blocks) get exactly one tick each."""
    values = sorted({row[x] for row in rows})
    if len(values) <= 13 and all(float(v).is_integer() for v in values):
        return alt.Axis(values=values, labelExpr=VN)  # no format="d": it caps the tick count and drops every other value
    return alt.Axis(labelExpr=VN)


def line_chart(rows, x, y, series=None, *, height, x_title, y_title, rules=(), log=False) -> None:
    """rules: (y value, label) drawn as a labelled threshold line."""
    scale = alt.Scale(type="log") if log else alt.Undefined
    base = alt.Chart(alt.Data(values=rows))
    tip = [f"{x}:Q", alt.Tooltip(f"{y}:Q", format=".3f")] + ([f"{series}:N"] if series else [])
    layers = [base.mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=28)).encode(
        x=alt.X(f"{x}:Q", title=x_title, axis=_steps(rows, x)),
        y=alt.Y(f"{y}:Q", title=y_title, scale=scale, axis=alt.Axis(labelExpr=VN)), color=_color(rows, series), tooltip=tip)]
    for value, label in rules:
        rule = alt.Chart(alt.Data(values=[{"v": value, "t": label}]))
        layers += [rule.mark_rule(color=BAD, strokeDash=[5, 4]).encode(y="v:Q"),
                   rule.mark_text(align="left", dx=4, dy=-7, color="#A12A2A", fontSize=11, fontWeight=600)
                   .encode(x=alt.value(0), y="v:Q", text="t:N")]
    _show(alt.layer(*layers), height, rows)


def column_chart(rows, x, y, series=None, *, height, x_title, y_title, log=False, sort=None, ticks=None) -> None:
    """ticks: the x labels to print when there are too many columns to label each one."""
    scale, y_axis = alt.Undefined, alt.Axis(labelExpr=VN)
    if log:  # one gridline per power of ten, bars start at the lowest one
        values = [row[y] for row in rows]
        decades = [10 ** k for k in range(floor(log10(min(values))), ceil(log10(max(values))) + 1)]
        scale, y_axis = alt.Scale(type="log", domain=[decades[0], decades[-1]]), alt.Axis(values=decades, labelExpr=VN)
    x_axis = alt.Axis(labelAngle=0, values=ticks) if ticks else alt.Axis(labelAngle=0)
    encode = dict(x=alt.X(f"{x}:O", title=x_title, sort=sort, axis=x_axis),
                  y=alt.Y(f"{y}:Q", title=y_title, scale=scale, axis=y_axis), color=_color(rows, series),
                  tooltip=[f"{x}:O", f"{y}:Q"] + ([f"{series}:N"] if series else []))
    if series is not None:
        encode["xOffset"] = alt.XOffset(f"{series}:N", sort=list(dict.fromkeys(row[series] for row in rows)))
    chart = alt.Chart(alt.Data(values=rows)).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(**encode)
    _show(chart, height, rows)


def scatter_chart(rows, x, y, *, height, x_title, y_title, line=None) -> None:
    """line: (intercept, slope) of a fitted line drawn over the points."""
    base = alt.Chart(alt.Data(values=rows))
    layers = [base.mark_circle(size=26, opacity=0.45, color=SERIES[0]).encode(
        x=alt.X(f"{x}:Q", title=x_title, axis=_steps(rows, x)),
        y=alt.Y(f"{y}:Q", title=y_title, axis=alt.Axis(labelExpr=VN)), tooltip=[f"{x}:Q", f"{y}:Q"])]
    if line is not None:
        top = max(row[x] for row in rows)
        ends = [{"x": 0, "y": line[0]}, {"x": top, "y": line[0] + line[1] * top}]
        layers.append(alt.Chart(alt.Data(values=ends)).mark_line(color=SERIES[1], strokeWidth=2).encode(x="x:Q", y="y:Q"))
    _show(alt.layer(*layers), height, rows)


def cell_chart(rows, x, y, *, height, x_title, y_title) -> None:
    chart = alt.Chart(alt.Data(values=rows)).mark_rect(color=SERIES[0]).encode(
        x=alt.X(f"{x}:O", title=x_title, axis=alt.Axis(labels=False, ticks=False)),
        y=alt.Y(f"{y}:O", title=y_title, axis=alt.Axis(labels=False, ticks=False)))
    _show(chart, height)
