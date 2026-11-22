"""Skórka 'dark-ops' (wspólna warstwa UI): wstrzykiwanie CSS + pomocniki HTML."""
from pathlib import Path

import streamlit as st

CSS_PATH = Path(__file__).parent / "skin.css"


def inject_theme():
    """Wstrzykuje motyw dark-ops (monospace, neon #00ff9c, scanlines)."""
    css = CSS_PATH.read_text(encoding="utf-8")
    st.markdown(css, unsafe_allow_html=True)


def head_box(title: str, kicker: str = "// moduł"):
    """Nagłówek strony w stylu terminala."""
    st.markdown(
        '<div class="kf-head">'
        f'<span class="kf-side-kicker">{kicker}</span>'
        f'<div class="kf-head-title">{title}</div>'
        '</div>', unsafe_allow_html=True)


def guide_box(lines):
    """Panel przewodni 'co kliknąć'."""
    html = "".join(f"<div>{l}</div>" for l in lines)
    st.markdown(f'<div class="kf-guide">{html}</div>', unsafe_allow_html=True)
