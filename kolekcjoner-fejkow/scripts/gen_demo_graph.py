#!/usr/bin/env python3
"""Generator demo-grafu — identyczne kolory jak render_graph() w app.py."""
import json
from pathlib import Path
from pyvis.network import Network

net = Network(height="720px", width="100%", bgcolor="#0a0e14",
              font_color="#c9ffe0", directed=False, cdn_resources="in_line")

clusters = [
    (["M001", "M002", "M003", "M004"], "#00ff9c"),
    (["M005", "M006", "M007"], "#0fd9a3"),
    (["M008", "M009"], "#39d98a"),
]
title = {f"M00{i}": t for i, t in enumerate([
    "inwestycja w zloto", "zysk 5000 zl dziennie", "indywidualne konto VIP",
    "gwarantowany zwrot 300%", "kryptowaluta oil texas", "bot AI zarabia dla Ciebie",
    "Elon Musk poleca platforme", "pozyczka bez BIK 0%", "free iPhone 15",
    "przelew na adwokata", "romance scam — przelew na milosc"], start=1)}
solo = ["M0010", "M0011"]

for members, col in clusters:
    for m in members:
        net.add_node(m, label=f"{m}: {title[m][:28]}", color=col, shape="dot",
                     borderWidth=1, font={"color": "#c9ffe0", "size": 12}, title=title[m])
for m in solo:
    net.add_node(m, label=f"{m}: {title[m][:28]}", color="#2e5c47", shape="dot",
                 borderWidth=1, font={"color": "#6b8f7d", "size": 12}, title=title[m])

ev = ["ta sama domena rejestrowa", "near-duplikat obrazu (dHash)",
      "duplikat tekstu (Jaccard>=0.8)", "ta sama persona (Elon Musk)",
      "podobny leksykon narracji scam", "wspolna infrastruktura NS"]
edges = [("M001", "M002", .88, 1), ("M001", "M003", .61, 0),
         ("M002", "M004", .93, 1), ("M003", "M004", .47, 0),
         ("M005", "M006", .79, 1), ("M006", "M007", .52, 0),
         ("M005", "M007", .66, 0), ("M008", "M009", .71, 1),
         ("M001", "M005", .29, 0)]
for i, (a, b, s, hard) in enumerate(edges):
    edge_col = ({"color": "#00ff9c", "highlight": "#7dfff2"} if hard
                else {"color": "#0aa868", "highlight": "#00ff9c"})
    net.add_edge(a, b, value=round(s * 10, 1),
                 title=("score=%.3f%s<br>%s" % (s, " [TWARDE]" if hard else "",
                                                ev[i % len(ev)])),
                 color=edge_col, width=2 if hard else 1,
                 dashes=False if hard else True)

options = json.dumps({
    "physics": {"barnesHut": {"gravitationalConstant": -4000}},
    "nodes": {"shadow": {"enabled": True, "size": 8,
                         "color": "rgba(0,255,156,0.35)"}}})
json.loads(options)  # walidacja przed uzyciem
net.set_options(options)

out = Path(__file__).resolve().parent / "demo_graf_neon.html"
net.write_html(str(out))
print("OK:", out, "|", out.stat().st_size // 1024, "kB")
