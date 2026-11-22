"""Mapa powiązań: interaktywny graf kampanii."""
import streamlit as st

from kfk.skin import guide_box, head_box
from ui_common import render_graph

head_box("MAPA POWIĄZAŃ", "// kolekcjoner fejków / graf")
guide_box([
    "Kampania = kwadratowy hub; szprychy łączą go z materiałami (grubość = siła powiązania, "
    "czerwony = twarde przesłanki).",
    "Najedź na węzeł/szprychę — karta pokaże tytuł, domeny, wizerunki, trackery i dowody.",
    "Graf się rusza — klastry rozchodzą się same. Przeciągnij węzły, jeśli chcesz ułożyć je po swojemu.",
])

graph = st.session_state.get("graph")
if not graph:
    st.info("Brak wyników — uruchom analizę na stronie Start (panel boczny).")
    st.stop()
full_edges = st.toggle("Pełny graf krawędzi (materiał–materiał)",
                       value=False,
                       help="Domyślnie: kampanie jako huby ze szprychami — czytelny "
                            "widok bez spaghetti. Włącz, aby zobaczyć każdą krawędź "
                            "między materiałami.")
render_graph(graph, mode="full" if full_edges else "hub")
