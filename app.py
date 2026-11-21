#!/usr/bin/env python3
"""KOLEKCJONER FEJKÓW — demonstrator (HackNation 2026, wyzwanie NASK).

Powłoka UI: skórka, nawigacja podstronami i panel parametrów analizy.
Pełny proces: materiały → ekstrakcja cech → podobieństwa → kampanie
→ mapa powiązań → analiza nowego materiału → raport.

Uruchomienie:  streamlit run app.py
"""
import streamlit as st

from kolekcjoner import ui
from kolekcjoner import SimilarityConfig

st.set_page_config(page_title="Kolekcjoner fejków", page_icon="🕵️", layout="wide")

if "materials" not in st.session_state:
    ui.default_state()

ui.inject_theme()

# ------------------------------------------------------------- nawigacja

pages = [
    st.Page("kolekcjoner/ui_pages/start.py",
            title="Start — kreator", icon="🏠", default=True),
    st.Page("kolekcjoner/ui_pages/kampanie.py",
            title="Kampanie", icon="🗂️"),
    st.Page("kolekcjoner/ui_pages/mapa.py",
            title="Mapa powiązań", icon="🕸️"),
    st.Page("kolekcjoner/ui_pages/nowy.py",
            title="Sprawdź nowy materiał", icon="🔍"),
    st.Page("kolekcjoner/ui_pages/szukaj.py",
            title="Szukaj powiązanych", icon="🛰️"),
    st.Page("kolekcjoner/ui_pages/metodyka.py",
            title="Metodyka i wyniki", icon="📘"),
]
pg = st.navigation(pages)

# ------------------------------------------------------------- sidebar

ui.ensure_dataset()

with st.sidebar:
    st.markdown(
        '<div class="kf-side-head">'
        '<span class="kf-side-kicker">// config</span>'
        '<div class="kf-side-title">PARAMETRY ANALIZY</div>'
        '</div>', unsafe_allow_html=True)
    cfg = SimilarityConfig(
        threshold=st.slider(
            "Próg podobieństwa", 0.1, 0.9, 0.45, 0.05, format="%.2f",
            help=("Im NIŻEJ suwak, tym łatwiej materiały lądują w jednej grupie "
                  "(ale rośnie ryzyko przypadkowych par). Przesuń w PRAWO, "
                  "jeśli widzisz grupy, które Twoim zdaniem nie powinny być razem.")),
        weights={
            "text": st.slider(
                "Waga: treść/narracja", 0.0, 1.0, 0.35, 0.05,
                help="Jak mocno liczy się podobny dobór słów i sposób opowiadania historii."),
            "image": st.slider(
                "Waga: obraz", 0.0, 1.0, 0.20, 0.05,
                help="Materiały z podobnymi grafikami łatwiej trafią do jednej grupy."),
            "domain": st.slider(
                "Waga: domena", 0.0, 1.0, 0.15, 0.05,
                help="Czy materiały łączy adres internetowy, z którego pochodzą."),
            "infra": st.slider(
                "Waga: infrastruktura", 0.0, 1.0, 0.10, 0.05,
                help="Czy materiały siedzą na tym samym serwerze lub u tego samego dostawcy."),
            "persona": st.slider(
                "Waga: osoby", 0.0, 1.0, 0.20, 0.05,
                help="Czy w materiałach występują te same osoby (np. znane postaci)."),
        },
    )

    st.markdown('<div class="kf-side-sep"></div>', unsafe_allow_html=True)
    n_mat = len(st.session_state.materials or [])
    st.markdown(
        '<div class="kf-side-head">'
        '<span class="kf-side-kicker">// input</span>'
        '<div class="kf-side-title sm">MATERIAŁY</div>'
        f'<div class="kf-side-count">{n_mat} materiałów w zbiorze</div>'
        '</div>', unsafe_allow_html=True)
    st.caption("Własne materiały i pliki wczytasz na stronie „Start”.")
    if st.button("🔄 Reset do zbioru demo", use_container_width=True):
        ui.default_state()
        st.rerun()

# ------------------------------------------------------------- obliczenia

st.session_state.cfg = cfg
with st.spinner("Buduję podobieństwa i kampanie..." if st.session_state.materials
                else None):
    st.session_state.clusters, st.session_state.links = ui.compute(cfg)

pg.run()
