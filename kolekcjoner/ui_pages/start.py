"""Start — kreator demonstracji."""
import json

import streamlit as st

from kolekcjoner import ui

ui.hero()

st.subheader("Witaj! W 5 krokach przeprowadzisz całą analizę.")
st.markdown(
    """Ta aplikacja analizuje podejrzane reklamy i strony internetowe (zwane dalej
**materiałami**) i sama grupuje je w **kampanie** — zestawy materiałów, które
wyglądają na stworzone przez tę samą rękę. Porównuje przy tym to, co człowiek
zobaczy gołym okiem (tekst, obrazy, występujące osoby), ale też to, co widać
dopiero „pod spodem” (adresy stron, serwery, przekierowania).

Nie musisz nic umieć — po prostu przechodź przez kroki po kolei. :)
""")

features = st.session_state.features
clusters = st.session_state.clusters
links = st.session_state.links

if not features:
    st.info("Zbiór jest pusty. Kliknij poniżej, żeby wczytać przykładowy zbiór "
            "materiałów — albo wgraj własny plik nieco niżej.")
    if st.button("📥 Wczytaj przykładowy zbiór materiałów", type="primary",
                 use_container_width=False):
        ui.default_state()
        st.rerun()
    ui.no_data_hint()
    st.stop()

# --- stan zbioru ---
m = st.columns(4)
m[0].metric("MATERIAŁY", len(features))
m[1].metric("KAMPANIE", len(clusters))
m[2].metric("POWIĄZANIA", len(links))
m[3].metric("TWARDE DOWODY", sum(1 for l in links if l.strong_signals))

st.markdown(
    f"""
<div class="kf-guide">
  <div><b>Krok 1 — gotowy:</b> w zbiorze jest już {len(features)} materiałów
       (przykładowy zbiór wczytuje się sam przy starcie).</div>
  <div>Przejdź teraz po kolei przez kroki 2–6 — każdy to jedna pozycja w menu po lewej.</div>
</div>
    """, unsafe_allow_html=True)

steps = [
    ("1", "Start ✓", "Jesteś tutaj. Materiały wczytane."),
    ("2", "Kampanie", "Zobacz, na jakie grupy materiały się złożyły — i dlaczego."),
    ("3", "Mapa powiązań", "To samo, ale obrazowo: animowana mapa „kulek” i nici."),
    ("4", "Sprawdź nowy materiał", "Wrzuć świeży materiał i zobacz, do czego pasuje."),
    ("5", "Autopilot — radar", "Sam szuka nowych odsłon Twoich kampanii w sieci."),
    ("6", "Metodyka i wyniki", "Jak to działa + pobierz raport z wynikami."),
]
st.markdown(
    '<div class="kf-steps">' + "".join(
        f'<div class="kf-step {"done" if i == 0 else ""}">'
        f'<span class="num">{num}</span><span class="t">{t}</span>'
        f'<div class="d">{d}</div></div>'
        for i, (num, t, d) in enumerate(steps)) + '</div>',
    unsafe_allow_html=True)

c = st.columns(4)
c[0].page_link("kolekcjoner/ui_pages/kampanie.py",
               label="KROK 2 ▸ Kampanie", icon="🗂️")
c[1].page_link("kolekcjoner/ui_pages/mapa.py",
               label="KROK 3 ▸ Mapa powiązań", icon="🕸️")
c[2].page_link("kolekcjoner/ui_pages/nowy.py",
               label="KROK 4 ▸ Nowy materiał", icon="🔍")
c[3].page_link("kolekcjoner/ui_pages/metodyka.py",
               label="KROK 6 ▸ Pobierz wynik", icon="📘")

# --- własny zbiór ---
st.divider()
st.markdown('<div class="kf-lbl">▸ Masz własny plik z materiałami?</div>',
            unsafe_allow_html=True)
st.caption("Obsługujemy pliki JSON Lines (jeden rekord na linię) lub CSV "
           "przygotowane jak przykładowy zbiór demo.")
up = st.file_uploader("Wgraj plik zbioru (JSONL / JSON)", type=["jsonl", "json"],
                      key="bulk_start")
if up is not None:
    if st.button("✓ Wczytaj wgrany plik", use_container_width=False):
        try:
            records = [json.loads(l) for l in up.getvalue().decode().splitlines()
                       if l.strip()]
            ui.load_materials(records)
            st.toast(f"Wczytano {len(records)} materiałów.")
            st.rerun()
        except Exception as e:
            st.error(f"Nie udało się wczytać pliku: {e}. Sprawdź, czy to poprawny "
                     "JSON Lines (jeden materiał = jedna linia).")

st.caption("Dane materiałów udostępnionych na wyzwanie służą wyłącznie do "
           "realizacji zadania HackNation 2026 (NASK) i nie powinny być "
           "publicznie rozpowszechniane. Aplikacja działa w 100% lokalnie.")
