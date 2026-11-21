"""Mapa powiązań: interaktywny graf kampanii."""
import streamlit as st

from kfk.skin import guide_box, head_box
from ui_common import render_graph

head_box("MAPA POWIĄZAŃ", "// kolekcjoner fejków / graf")
guide_box([
    "Kolor węzła = kampania; rozmiar = liczba powiązań; czerwona krawędź = twarde przesłanki.",
    "Najedź na węzeł/krawędź, aby zobaczyć tytuł, kampanię i dowody.",
    "Graf się rusza — klastry rozchodzą się same. Przeciągnij węzły, jeśli chcesz ułożyć je po swojemu.",
])

graph = st.session_state.get("graph")
if not graph:
    st.info("Brak wyników — uruchom analizę na stronie Start (panel boczny).")
    st.stop()
render_graph(graph)
