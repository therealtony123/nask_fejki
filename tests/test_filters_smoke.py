import json, sys, re
sys.path.insert(0, '.')
import streamlit as st
import ui_common

captured = []
st.components.v1.html = lambda html, **kw: captured.append(html)
graph = json.loads(open('kfk.graph.json', encoding='utf-8').read())

def nodes(html):
    return sorted(set(re.findall(r'"id": "(ad_[^"]+)"', html)))

def edges(html):
    return len(re.findall(r'\{[^{}]*"from": "ad_', html))

# T1: fraza "kajdankach" -> tylko ad_real_48 (K07)
del captured[:]
st.text_input = lambda *a, **k: "kajdankach"
ui_common.render_graph(graph, "hub")
print("T1 fraza kajdankach ->", nodes(captured[0]) if captured else "INFO (pusto)")

# T2: bez filtrów
del captured[:]
st.text_input = lambda *a, **k: ""
ui_common.render_graph(graph, "hub")
print("T2 bez filtrów      ->", nodes(captured[0]) if captured else "INFO")

# T3: tylko TWARDE — jedyna krawędź jest twarda, bez zmian
del captured[:]
st.toggle = lambda *a, **k: True
ui_common.render_graph(graph, "full")
print("T3 tylko TWARDE    ->", nodes(captured[0]) if captured else "INFO")

# T4: pigułki K02 — tylko para z Zamachu
del captured[:]
st.pills = lambda *a, **k: ["K02"]
ui_common.render_graph(graph, "full")
print("T4 kampania K02    ->", nodes(captured[0]) if captured else "INFO")

# T5: próg 0.995 — krawędź 0.992 znika
del captured[:]
st.pills = lambda *a, **k: None
st.slider = lambda *a, **k: 99
ui_common.render_graph(graph, "full")
print("T5 próg 0.995      ->", nodes(captured[0]) if captured else "INFO (bez krawędzi)")

# T6: toggle rozróżniane po etykiecie — tylko TWARDE, bez pojedynczych
del captured[:]
st.toggle = lambda label, *a, **k: label == "tylko TWARDE"
st.pills = lambda *a, **k: None
st.slider = lambda *a, **k: 0.0
st.text_input = lambda *a, **k: ""
ui_common.render_graph(graph, "full")
print("T6 toggle po label->", nodes(captured[0]) if captured else "INFO")
