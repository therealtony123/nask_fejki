"""Incydenty: eksploracja pojedynczych materiałów i ich cech."""
import streamlit as st

from kfk.skin import guide_box, head_box
from ui_common import get_store, render_incidents

head_box("INCYDENTY — EKSPLORATOR", "// kolekcjoner fejków / materiały")
guide_box([
    "Wybierz materiał i zobacz wyodrębnione cechy: tekst, domeny, trackery, wizerunki.",
    "To dokładnie te cechy, na których opiera się porównywanie materiałów.",
])

graph = st.session_state.get("graph")
db = st.session_state.get("db")
if not graph:
    st.info("Brak wyników — uruchom analizę na stronie Start (panel boczny).")
    st.stop()
render_incidents(graph, get_store(db))
