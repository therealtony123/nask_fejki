"""Start — kreator: status zbioru, metryki, co dalej."""
import streamlit as st

from kfk.skin import guide_box, head_box

head_box("START — KREATOR ANALIZY", "// kolekcjoner fejków / start")
guide_box([
    "1. Zbiór ładuje się sam (dane w katalogu data/ — struktura do_udostępnienia/<id>/).",
    "2. W panelu bocznym możesz ustawić progi i kliknąć ▶ Uruchom analizę.",
    "3. Wyniki zobaczysz na stronach: Kampanie • Mapa powiązań • Incydenty.",
    "4. Nowy materiał sprawdzisz na stronie „Sprawdź nowy materiał”.",
])

graph = st.session_state.get("graph")
if graph:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Incydenty", len(graph["nodes"]))
    m2.metric("Powiązania (krawędzie)", len(graph["edges"]))
    m3.metric("Kampanie", len(graph["clusters"]))
    m4.metric("Twarde powiązania", sum(1 for e in graph["edges"] if e["hard"]))
    multi = [c for c in graph["clusters"] if len(c["members"]) > 1]
    st.markdown("**Kampanie wieloelementowe:**")
    for c in multi:
        st.write(f"• **{c['cluster_id']}**: {', '.join(c['members'])} — {c['label'][:90]}")
else:
    st.info("Brak wyników. Uruchom analizę w panelu bocznym (▶ Uruchom analizę) "
            "albo wczytaj zapisane wyniki.")
