"""Metodyka i wyniki: podsumowanie metody + eksport STIX/IoC."""
import streamlit as st

from kfk.skin import guide_box, head_box
from ui_common import render_export

head_box("METODYKA I WYNIKI", "// kolekcjoner fejków / raport")
guide_box([
    "Poniżej skrót metodyki; pełny opis w README.md repozytorium.",
    "Eksport: pakiet STIX 2.1 i watchlista IoC — gotowe do MISP/OpenCTI.",
])

st.markdown("""
**1. Cechy (pięć widoków):** tekst/OCR • wizja (pHash/dHash, kolory) •
infrastruktura (domeny, trackery GA/Pixel/GTM, przekierowania z HAR) •
wzorce nazw domen (TLD, entropia) • wizerunki osób (YuNet + SFace vs baza 14 osób).

**2. Podobieństwo:** ważona suma widoków; wagi normalizowane do cech dostępnych
w obu materiałach (odporność na niekompletne dane). Każda krawędź ma jawne
przesłanki — „dlaczego połączono".

**3. Kampanie:** graf incydentów → Louvain (community detection) → stabilne
identyfikatory kampanii. Nowy materiał: przypisanie do kampanii (głosowanie
ważone) albo nowy wzorzec.

**4. Odporność:** brakujące dane pomijane; duplikaty wyłapywane hashami
percepcyjnymi; przesłanki PRZECIW pokazują, czemu materiały pozostały rozdzielone.
""")

st.markdown("---")
graph = st.session_state.get("graph")
db = st.session_state.get("db")
if graph:
    m1, m2, m3 = st.columns(3)
    m1.metric("Incydenty", len(graph["nodes"]))
    m2.metric("Krawędzie", len(graph["edges"]))
    m3.metric("Kampanie", len(graph["clusters"]))
render_export(db or "kfk.sqlite")
