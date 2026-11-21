"""Kampanie: przegląd klastrów + analizator par (dlaczego NIE połączono)."""
import streamlit as st

from kfk.skin import guide_box, head_box
from ui_common import get_store, render_campaigns, render_pair_analyzer

head_box("KAMPANIE OSZUSTW", "// kolekcjoner fejków / klastry")
guide_box([
    "Każda karta to jedna kampania: kto w niej jest i jakie przesłanki ją zbudowały.",
    "Na dole — analizator dowolnej pary: przesłanki ZA i PRZECIW połączeniu.",
])

graph = st.session_state.get("graph")
db = st.session_state.get("db")
if not graph:
    st.info("Brak wyników — uruchom analizę na stronie Start (panel boczny).")
    st.stop()
store = get_store(db)
render_campaigns(graph, store)
st.markdown("---")
render_pair_analyzer(graph, store)
