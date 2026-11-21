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
    edges = graph["edges"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Materiały", len(graph["nodes"]))
    m2.metric("Powiązania", len(edges))
    m3.metric("Kampanie", len(graph["clusters"]))
    m4.metric("Twarde powiązania", sum(1 for e in edges if e["hard"]))
    big = sorted((c for c in graph["clusters"] if len(c["members"]) >= 3),
                 key=lambda c: -len(c["members"]))
    if big:
        st.markdown("**Największe kampanie:**")
        for c in big[:6]:
            st.write(f"• **{c['cluster_id']}** — {len(c['members'])} materiałów · {c['label'][:70]}")
        st.caption("Pełny przegląd i szczegóły: strona **Kampanie**.")
    else:
        st.info("Brak kampanii wieloelementowych — uruchom analizę.")
else:
    st.info("Brak wyników. Uruchom analizę w panelu bocznym (▶ Uruchom analizę) "
            "albo wczytaj zapisane wyniki.")
