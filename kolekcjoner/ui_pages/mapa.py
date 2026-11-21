"""Mapa powiązań — animowany graf (ruchome kulki) w neonowej zieleni."""
import streamlit as st

from kolekcjoner import ui

ui.hero(compact=True)
st.subheader("Mapa powiązań — jak materiały łączą się w sieci")

features = st.session_state.features
clusters = st.session_state.clusters
links = st.session_state.links
materials = st.session_state.materials

if not features:
    ui.no_data_hint()
    st.stop()

ui.guide_box(
    ["<b>Krok 1:</b> kliknij <b>▶ Odtwórz animację</b> — kuleczki same ułożą się w grupy.",
     "<b>Krok 2:</b> przeciągnij myszką, żeby przesunąć mapę; kółkiem przybliż grupę.",
     "<b>Krok 3:</b> najedź kursorem na kulkę albo nitkę, żeby zobaczyć szczegóły.",
     "Nie da się tej mapy zepsuć — eksperymentuj śmiało."])

st.markdown(
    """To ta sama analiza, co w **Kampaniach**, tylko narysowana jako mapa.
Każda **kulka** to jeden materiał, **nitki** między kulkami to wykryte
powiązania. Kolory kulek odpowiadają kartom kampanii.""")

st.markdown(
    """
<div class="kf-legend">
  <span><span class="sw" style="background:#00ff9c"></span>kulka w odcieniu neonu = materiał należący do kampanii (każda grupa ma swój odcień)</span>
  <span><span class="sw" style="background:#2e5c47"></span>ciemna kulka = materiał bez powiązań</span>
  <span><span class="ln" style="background:#00ff9c"></span>jasna nić = twardy dowód (ta sama domena / niemal identyczny obraz / kopia tekstu)</span>
  <span><span class="ln" style="background:repeating-linear-gradient(90deg,#0aa868 0 4px,transparent 4px 7px)"></span>ciemna przerywana = podobieństwo ważone (imię nić, tym pewniejsze pokrewieństwo)</span>
</div>
    """, unsafe_allow_html=True)

# filtr kampanii + odtworzenie animacji
c1, c2 = st.columns([2, 1])
opcje = ["Wszystkie kampanie"] + [c.cluster_id for c in clusters]
wyb = c1.selectbox("Pokaż:", opcje,
                   help="Możesz wyświetlić tylko wybraną kampanię, żeby przyjrzeć "
                        "się jej z bliska.")
if c2.button("▶ Odtwórz animację", use_container_width=True):
    st.rerun()

only = None if wyb == opcje[0] else wyb
if only:
    st.caption(f"Pokazuję tylko kampanię **{only}**. Wróć opcją „Wszystkie "
               "kampanie”, żeby zobaczyć całość.")

ok = ui.show_graph(clusters, links, materials, features, only_cluster=only)
if not ok:
    # fallback: statyczny graphviz z tymi samymi kolorami
    edges = []
    for l in links:
        if only and not ({l.a, l.b} <= {m for c in clusters
                                        if c.cluster_id == only for m in c.members}):
            continue
        color = "#00ff9c" if l.strong_signals else "#0aa868"
        edges.append(f'  "{l.a}" -> "{l.b}" [label="{l.score:.2f}", '
                     f'color="{color}", fontcolor="{color}"];')
    dot = ("digraph kampanie {\n  rankdir=LR;\n  bgcolor=\"#0b101a\";\n"
           "  node [shape=box, style=\"rounded,filled\", fillcolor=\"#0d1420\", "
           "color=\"#00ff9c\", fontcolor=\"#c9ffe0\", fontsize=11];\n"
           "  edge [fontsize=9];\n" + "\n".join(edges) + "\n}\n")
    st.graphviz_chart(dot)

st.caption("Mapa jest interaktywna: najedź na kulkę (materiał) albo nitkę "
          "(powiązanie), żeby zobaczyć szczegóły — łącznie z twardymi dowodami "
          "i zgodnością poszczególnych cech. Mapę przesuwasz myszką, "
          "a przybliżasz kółkiem.")
