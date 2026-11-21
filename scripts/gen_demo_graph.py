#!/usr/bin/env python3
"""Eksportuje REALNY graf kampanii (kfk.graph.json) do samodzielnego HTML.

Czytelne etykiety (ID + tooltip z tytułem i kampanią), rozmiar węzła wg stopnia,
grubość krawędzi wg podobieństwa, twarde krawędzie czerwone. Fizyka barnesHut
zostaje — graf dalej się rusza. Legenda klastrów wstrzykiwana do stopki HTML.

Użycie (po uruchomieniu pipeline):
  .venv/bin/python scripts/gen_demo_graph.py   # -> demo_graf.html
"""
import json
import re
from collections import Counter
from pathlib import Path

from pyvis.network import Network

PROJ = Path(__file__).resolve().parents[1]
GRAPH = PROJ / "kfk.graph.json"

if not GRAPH.is_file():
    raise SystemExit(f"Brak {GRAPH} — najpierw uruchom pipeline.py")

graph = json.loads(GRAPH.read_text(encoding="utf-8"))
net = Network(height="720px", width="100%", bgcolor="#000000",
              font_color="#fafafa", directed=False, cdn_resources="in_line")
palette = ["#ff4b4b", "#4bb3ff", "#ffd34b", "#4bff8c", "#c44bff", "#ff9d4b",
           "#4bffd3", "#ff4bd3", "#8cff4b", "#4b8cff"]
colors = {}
for i, c in enumerate(graph["clusters"]):
    for m in c["members"]:
        colors[m] = palette[i % len(palette)]


def _tt_card(inner: str, min_w: int = 280) -> str:
    return (f"<div style='min-width:{min_w}px;max-width:440px;background:#000000;"
            f"border:1px solid #2b2b2b;border-radius:6px;padding:10px 12px;"
            f"font:12.5px/1.6 Consolas,monospace;color:#cdd7e0'>{inner}</div>")

deg = Counter()
for e in graph["edges"]:
    deg[e["a"]] += 1
    deg[e["b"]] += 1
max_deg = max(deg.values()) or 1

for n in graph["nodes"]:
    if deg.get(n["id"], 0) == 0:
        continue  # pojedyncze, niepołączone materiały — ukrywamy
    size = 12 + 16 * (deg.get(n["id"], 0) / max_deg)
    net.add_node(
        n["id"], label=n["id"], shape="dot", size=size, borderWidth=2,
        color={"background": colors.get(n["id"], "#555555"), "border": "#ffffff",
               "highlight": {"background": colors.get(n["id"], "#555555"),
                             "border": "#ffd34b"}},
        font={"size": 15, "color": "#fafafa", "face": "monospace"},
        title=_tt_card(
            f"<div style='font-size:15px;font-weight:bold;color:#00ff9c'>{n['id']} · "
            f"KAMPANIA {n.get('cluster') or '—'}</div>"
            f"<div style='margin:5px 0 2px;color:#e6edf3'>{n['title']}</div>"
            + "".join(
                f"<div style='margin-top:6px'><b style='color:#8b98a5'>{lbl}</b><br>"
                f"{', '.join(v for v in (n.get(key) or [])[:8]) or '—'}</div>"
                for lbl, key in (("DOMENY", "domains"), ("WIZERUNKI", "faces"),
                                 ("TRACKERY", "trackers")))
            + f"<div style='margin-top:8px;color:#5b7bd5'>powiązań: {deg.get(n['id'], 0)} · "
              f"pliki: {n.get('n_files', '—')} · obrazy: {n.get('n_images', '—')} · "
              f"od: {(n.get('first_seen') or '—')[:10]}</div>"))

for e in graph["edges"]:
    if deg.get(e["a"], 0) == 0 or deg.get(e["b"], 0) == 0:
        continue
    ev = "<br>".join(e["evidence"][:4])
    net.add_edge(e["a"], e["b"], value=round(e["score"] * 10, 1),
                 title=(f"{e['a']} ↔ {e['b']} — score={e['score']:.3f}"
                        f"{' [TWARDE]' if e['hard'] else ''}<br>{ev}"),
                 color="#ff6b6b" if e["hard"] else "#5b7bd5",
                 width=1 + 4 * e["score"])

net.set_options(
    json.dumps({"physics": {"barnesHut": {"gravitationalConstant": -3000,
                                           "springLength": 140,
                                           "damping": 0.09}},
                "nodes": {"shadow": {"enabled": True, "size": 6,
                                     "color": "rgba(255,255,255,0.25)"}}}))

out = PROJ / "demo_graf.html"
net.write_html(str(out))

# legenda klastrów wieloelementowych
big = [c for c in graph["clusters"] if len(c["members"]) > 1]
items = []
for c in big:
    col = colors[c["members"][0]]
    members = ", ".join(c["members"][:8])
    label = re.sub(r"<[^>]+>", "", c["label"])[:70]
    items.append(
        f"<span style='color:{col}'>●</span> <b>{c['cluster_id']}</b> "
        f"({members}) — {label}")
legend = (
    "<div style='position:fixed;left:12px;bottom:12px;max-width:46vw;"
    "background:rgba(14,17,23,.88);border:1px solid #333;border-radius:8px;"
    "padding:10px 14px;color:#fafafa;font:12px/1.6 monospace;z-index:999'>"
    "<b>Kampanie:</b><br>" + "<br>".join(items) + "</div>")
html = out.read_text(encoding="utf-8")
html = html.replace("</body>", legend + "</body>")
out.write_text(html, encoding="utf-8")
print(f"OK: {out} ({out.stat().st_size // 1024} kB, "
      f"{len(graph['nodes'])} węzłów, {len(graph['edges'])} krawędzi)")
