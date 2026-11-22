#!/usr/bin/env python3
"""KOLEKCJONER FEJKÓW — demonstrator (HackNation 2026, wyzwanie NASK PIB).

Powłoka UI: skórka dark-ops, nawigacja podstronami i panel parametrów analizy.
Pełny proces: materiały → cechy → podobieństwa → kampanie → mapa powiązań
→ analiza nowego materiału → eksport STIX/IoC.

Uruchomienie:  streamlit run app.py
"""
import sys
import time
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from kfk.skin import inject_theme
from ui_common import (DEFAULT_DATA, DEFAULT_DB, load_graph, run_analysis)

st.set_page_config(page_title="Kolekcjoner fejków", page_icon="🕵️", layout="wide")

# automatyczne wczytanie świeżych wyników (graf.json z nowszym mtime)
_gf = Path(str(DEFAULT_DB)).with_suffix(".graph.json")
if _gf.is_file():
    _mt = _gf.stat().st_mtime
    if st.session_state.get("graph_mtime") != _mt:
        st.session_state["graph"] = load_graph(str(DEFAULT_DB))
        st.session_state["graph_mtime"] = _mt
        st.session_state["db"] = str(DEFAULT_DB)
elif "graph" not in st.session_state:
    st.session_state["graph"] = None

inject_theme()

# ------------------------------------------------------------- nawigacja

pages = [
    st.Page("ui_pages/start.py", title="Start — kreator", icon="🏠", default=True),
    st.Page("ui_pages/kampanie.py", title="Kampanie", icon="🗂️"),
    st.Page("ui_pages/mapa.py", title="Mapa powiązań", icon="🕸️"),
    st.Page("ui_pages/incydenty.py", title="Incydenty", icon="📁"),
    st.Page("ui_pages/nowy.py", title="Sprawdź nowy materiał", icon="🔍"),
    st.Page("ui_pages/metodyka.py", title="Metodyka i wyniki", icon="📘"),
]
pg = st.navigation(pages)

# ------------------------------------------------------------- sidebar

with st.sidebar:
    try:
        import subprocess
        _ver = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True,
            text=True, cwd=Path(__file__).parent, timeout=5).stdout.strip()
    except Exception:
        _ver = "?"
    st.markdown(
        f'<div style="font-family:Consolas,monospace;color:#00ff9c;'
        f'border:1px solid #00ff9c;border-radius:6px;padding:6px 10px;'
        f'margin-bottom:10px;background:#000">wersja: {_ver}</div>',
        unsafe_allow_html=True)
    st.markdown(
        '<div class="kf-side-head">'
        '<span class="kf-side-kicker">// config</span>'
        '<div class="kf-side-title">PARAMETRY ANALIZY</div>'
        '</div>', unsafe_allow_html=True)
    data_dir = st.text_input("Katalog danych", str(DEFAULT_DATA))
    db_path = st.text_input("Baza SQLite", str(DEFAULT_DB))
    threshold = st.slider(
        "Próg krawędzi (podobieństwo)", 0.05, 0.95, 0.25, 0.05,
        help="Im NIŻEJ suwak, tym łatwiej materiały lądują w jednej kampanii "
             "(ale rośnie ryzyko przypadkowych par).")
    join_thr = st.slider(
        "Próg przypisania do kampanii", 0.05, 0.95, 0.30, 0.05,
        help="Próg, od którego nowy materiał uznajemy za wariant znanej kampanii.")
    st.session_state["join_thr"] = join_thr
    st.markdown('<div class="kf-side-sep"></div>', unsafe_allow_html=True)

    if st.button("▶ Uruchom analizę", type="primary", use_container_width=True):
        t0 = time.time()
        g = run_analysis(data_dir, db_path, threshold)
        if g:
            st.session_state["graph"] = g
            st.session_state["db"] = db_path
            st.success(f"Analiza w {time.time() - t0:.1f}s — {len(g['nodes'])} incydentów, "
                       f"{len(g['edges'])} krawędzi, {len(g['clusters'])} kampanii.")
    if st.button("🔄 Wczytaj zapisane wyniki", use_container_width=True):
        g = load_graph(db_path)
        if g:
            st.session_state["graph"] = g
            st.session_state["db"] = db_path
            st.info(f"Wczytano: {len(g['nodes'])} incydentów, {len(g['clusters'])} kampanii.")
        else:
            st.warning("Brak zapisanych wyników dla tej bazy.")

    n_inc = len(st.session_state["graph"]["nodes"]) if st.session_state["graph"] else 0
    st.markdown(
        '<div class="kf-side-head">'
        '<span class="kf-side-kicker">// input</span>'
        '<div class="kf-side-title sm">MATERIAŁY</div>'
        f'<div class="kf-side-count">{n_inc} materiałów w zbiorze</div>'
        '</div>', unsafe_allow_html=True)
    st.caption("Zbiór organizatora: katalog data/ (struktura do_udostępnienia/<id>/). "
               "Własne materiały zbierają: fb_collector.py (Meta Ad Library) "
               "i harvest_urls.py (OpenPhish, AA419).")

pg.run()
