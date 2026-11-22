"""Kampanie i mapa: przegląd klastrów, analizator par + interaktywny graf powiązań."""
import streamlit as st

from kfk.skin import guide_box, head_box
from ui_common import (get_store, render_campaigns, render_graph,
                       render_pair_analyzer)

head_box("KAMPANIE I MAPA POWIĄZAŃ", "// kolekcjoner fejków / klastry + graf")
guide_box([
    "Każda karta to jedna kampania: kto w niej jest i jakie przesłanki ją zbudowały.",
    "Niżej — analizator dowolnej pary: przesłanki ZA i PRZECIW połączeniu.",
    "Na dole — mapa powiązań: kampania = kwadratowy hub, szprychy łączą go z materiałami "
    "(grubość = siła powiązania, czerwony = twarde przesłanki).",
    "Najedź na węzeł/szprychę — karta pokaże tytuł, domeny, wizerunki, trackery i dowody.",
])

graph = st.session_state.get("graph")
db = st.session_state.get("db")
if not graph:
    st.info("Brak wyników — uruchom analizę na stronie Start (panel boczny).")
else:
    store = get_store(db)
    render_campaigns(graph, store)
    st.markdown("---")
    render_pair_analyzer(graph, store)

    # --------------------------------------------------------- mapa powiązań

    st.markdown("---")
    st.markdown("### 🕸️ Mapa powiązań")
    full_edges = st.toggle("Pełny graf krawędzi (materiał–materiał)",
                           value=False,
                           help="Domyślnie: kampanie jako huby ze szprychami — czytelny "
                                "widok bez spaghetti. Włącz, aby zobaczyć każdą krawędź "
                                "między materiałami.")
    render_graph(graph, mode="full" if full_edges else "hub")
