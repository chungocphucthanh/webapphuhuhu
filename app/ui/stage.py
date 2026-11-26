"""One layout for every module page: idea tabs, headline, figure + points, lab dock, badges."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Callable

import streamlit as st

from . import parts


@dataclass(frozen=True)
class Idea:
    title: str
    pre: str
    hot: str
    post: str
    sub: str
    points: tuple
    figure: Callable[[], None]


@dataclass(frozen=True)
class Module:
    key: str
    label: str
    presenter: str
    ideas: tuple
    start: int
    lab: Callable[[], None]
    fn: tuple = ()
    ds: tuple = ()
    bigo: tuple = ()
    note: str = ""


def presenter_chip(name: str) -> None:
    parts.html(f'<div class="iap-chip"><b aria-hidden="true">{escape(name[:1])}</b>'
               f"<span><small>Trình bày</small>{escape(name)}</span></div>")


def _step(key: str, delta: int, count: int) -> None:
    st.session_state[key] = min(count - 1, max(0, st.session_state[key] + delta))


def render_module(module: Module) -> None:
    key, count = f"idea_{module.key}", len(module.ideas)
    st.session_state.setdefault(key, module.start)
    left, middle, right = st.columns((1.8, 7.9, 1.3))
    with left:
        parts.text("eyebrow", module.label)
    with middle:
        st.radio("Các ý của module", range(count), key=key, horizontal=True, label_visibility="collapsed",
                 format_func=lambda i: f"**{i + 1}** {module.ideas[i].title}")
    with right:
        presenter_chip(module.presenter)
    idea = module.ideas[st.session_state[key]]
    parts.headline(idea.pre, idea.hot, idea.post, idea.sub)
    figure, text = st.columns((1.55, 1))
    with figure:
        parts.marker("figure")
        idea.figure()
    with text:
        parts.points(idea.points)
    with st.container():
        parts.marker("dock")
        module.lab()
    badges, previous, following = st.columns((7, 1, 1))
    with badges:
        parts.callout(module.fn, module.ds, module.bigo, module.note)
    previous.button("Ý trước", key=f"prev_{module.key}", on_click=_step, args=(key, -1, count),
                    use_container_width=True, disabled=st.session_state[key] == 0)
    following.button("Ý tiếp", key=f"next_{module.key}", on_click=_step, args=(key, 1, count),
                     use_container_width=True, disabled=st.session_state[key] == count - 1)
