"""Wspólna logika widoków UI — wszystkie strony korzystają z tych funkcji."""
import json
import time
from collections import Counter
from pathlib import Path

import streamlit as st

from kfk import (Store, Tfidf, assign_new_incident, extract_from_url_text,
                 extract_incident, pair_similarity, scan)
from kfk.similarity import negative_evidence
from kfk.features import top_images
from kfk.skin import guide_box, head_box

PROJ = Path(__file__).parent
DEFAULT_DATA = PROJ / "data"
DEFAULT_DB = PROJ / "kfk.sqlite"


@st.cache_resource
def get_store(db):
    return Store(db)


def load_graph(db: str):
    g = Path(db).with_suffix(".graph.json")
    if g.is_file():
        return json.loads(g.read_text(encoding="utf-8"))
    return None


def run_analysis(data, db, threshold):
    from kfk import build_edges, cluster_graph
    from kfk.stix import incident_timespan
    incidents = scan(data)
    if not incidents:
        st.error("Brak incydentów w katalogu (oczekuję .../do_udostępnienia/<id>/).")
        return None
    feats = []
    bar = st.progress(0.0, text="Wyodrębnianie cech…")
    for i, inc in enumerate(incidents, 1):
        feats.append(extract_incident(inc))
        bar.progress(i / (len(incidents) + 1), text=f"Cechy: {inc['id']}")
    tfidf = Tfidf()
    tfidf.fit([f["text"].get("body_norm", "") or f["text"].get("title_norm", "")
               for f in feats])
    edges = build_edges(feats, tfidf, threshold)
    clusters = cluster_graph([f["id"] for f in feats], edges, threshold)
    spans = {f["id"]: incident_timespan(f["path"]) for f in feats}
    for c in clusters:
        first = min((spans[m][0] for m in c["members"] if spans[m][0]), default=None)
        last = max((spans[m][1] for m in c["members"] if spans[m][1]), default=None)
        c["first_seen"], c["last_seen"] = first, last
    store = get_store(db)
    store.save_incidents(feats)
    store.save_edges(edges)
    store.save_clusters(clusters)
    graph = {
        "nodes": [{"id": f["id"], "title": f["text"]["title"][:80],
                   "first_seen": spans[f["id"]][0], "last_seen": spans[f["id"]][1],
                   "cluster": next((c["cluster_id"] for c in clusters
                                    if f["id"] in c["members"]), None),
                   "domains": f["infra"]["registrable"],
                   "faces": [p["name"] for p in f.get("faces", {}).get("persons", [])],
                    "trackers": f["infra"]["tracker_ids"],
                    "n_images": len(f["images"]), "n_files": f.get("n_files", 0),
                    "img": top_images(f, 2)}
                   for f in feats],
        "edges": [{"a": e["a"], "b": e["b"], "score": e["score"], "hard": e["hard"],
                   "evidence": e["evidence"]} for e in edges],
        "clusters": clusters,
    }
    Path(db).with_suffix(".graph.json").write_text(
        json.dumps(graph, ensure_ascii=False, indent=1), encoding="utf-8")
    bar.progress(1.0, text="Gotowe")
    return graph


def _rgba(hex_color: str, alpha: float) -> str:
    """"#00ff9c" -> "rgba(0,255,156,0.5)" — do glow/shadow w pyvis."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(x * 2 for x in h)
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{alpha})"


def _tt_card(inner: str, min_w: int = 280) -> str:
    return (f"<div style='min-width:{min_w}px;max-width:440px;background:#060a10;"
            f"border:1px solid rgba(0,255,156,0.45);border-radius:8px;padding:10px 12px;"
            f"box-shadow:0 0 14px rgba(0,255,156,0.22);"
            f"font:12.5px/1.6 Consolas,monospace;color:#cdd7e0'>{inner}</div>")


def preview_images(f: dict, max_n: int = 6) -> list:
    """Najlepsze obrazy do podglądu incydentu (zrzuty > obrazy główne > największe)."""
    return [Path(p) for p in top_images(f, max_n)]


def title_map(graph) -> dict:
    out = {}
    for n in graph["nodes"]:
        t = (n.get("title") or "").strip()
        if not t or t == n["id"] or t.startswith("/"):
            doms = n.get("domains") or []
            t = doms[0] if doms else "(bez tytułu)"
        out[n["id"]] = t[:60]
    return out


def _tt_node(n: dict, deg_n: int) -> str:
    rows = []
    for label, val, maxlen in (("DOMENY", n.get("domains"), 8),
                               ("WIZERUNKI", n.get("faces"), 6),
                               ("TRACKERY", n.get("trackers"), 6)):
        if val:
            rows.append(f"<div style='margin-top:6px'><b style='color:#8b98a5'>"
                        f"{label}</b><br>{', '.join(v for v in val[:maxlen]) or '—'}</div>")
    inner = (
        f"<div style='font-size:15px;font-weight:bold;color:#00ff9c'>{n['id']} · "
        f"KAMPANIA {n.get('cluster') or '—'}</div>"
        f"<div style='margin:5px 0 2px;color:#e6edf3'>{n['title']}</div>"
        + "".join(rows) +
        f"<div style='margin-top:8px;color:#5b7bd5'>powiązań: {deg_n} · pliki: "
        f"{n.get('n_files', '—')} · obrazy: {n.get('n_images', '—')} · "
        f"od: {(n.get('first_seen') or '—')[:10]}</div>")
    return _tt_card(inner)


def _tt_short(n: dict, deg_n: int) -> str:
    """Kompaktowy podgląd przy najechaniu — pełne szczegóły po kliknięciu."""
    t = (n.get("title") or "").strip()[:58]
    return _tt_card(
        f"<div style='font-size:13px;font-weight:bold;color:#00ff9c'>{n['id']} · "
        f"KAMPANIA {n.get('cluster') or '—'}</div>"
        f"<div style='margin-top:3px;color:#9aa7b4'>{t or '—'}</div>"
        f"<div style='margin-top:4px;color:#5b7bd5;font-size:11px'>"
        f"powiązań: {deg_n} · kliknij — pełne szczegóły</div>", 240)


def _card_image(text: str, width: int = 560) -> str:
    """Renderuje kartę tekstową do PNG (data-URI) — popup jako węzeł-obraz w grafie."""
    import base64
    import io
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return ""
    font = None
    for fp in ("/usr/share/fonts/TTF/DejaVuSans.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
               "/usr/share/fonts/dejavu/DejaVuSans.ttf"):
        if Path(fp).is_file():
            try:
                font = ImageFont.truetype(fp, 17)
                break
            except Exception:
                continue
    if font is None:
        try:
            font = ImageFont.load_default()
        except Exception:
            return ""
    pad, lh = 16, 26
    maxw = width - 2 * pad
    lines = []
    for raw in text.split("\n"):
        if not raw:
            lines.append("")
            continue
        cur = ""
        for ch in raw:
            if font.getlength(cur + ch) <= maxw:
                cur += ch
            else:
                lines.append(cur)
                cur = ch
        lines.append(cur)
    if len(lines) > 30:
        lines = lines[:29] + ["…"]
    h = pad * 2 + lh * len(lines)
    img = Image.new("RGB", (width, max(h, 40)), (4, 8, 14))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([1, 1, width - 2, img.height - 2], radius=10,
                        outline=(0, 255, 156), width=2)
    d.rounded_rectangle([1, 1, 5, img.height - 2], radius=2, fill=(0, 229, 255))
    y = pad
    for i, ln in enumerate(lines):
        if i == 0:
            color = (0, 255, 156)
        elif ln.startswith("graf v"):
            color = (62, 107, 85)
        else:
            color = (205, 215, 224)
        d.text((pad, y), ln, font=font, fill=color)
        y += lh
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _filter_graph(graph):
    """Panel filtrów nad grafem. Zwraca (graf po filtrach, pokazuj_pojedyncze)."""
    nodes = graph.get("nodes", [])
    edges = list(graph.get("edges", []))
    clusters = list(graph.get("clusters", []))
    with st.container(border=True):
        st.markdown('<div class="kf-fbar-title">// <b>FILTRY</b> MAPY POWIĄZAŃ</div>',
                    unsafe_allow_html=True)
        fc1, fc2, fc3, fc4 = st.columns([1.25, 1.75, 2.95, 1.15])
        with fc1:
            only_hard = st.toggle("tylko TWARDE", value=False,
                                  help="Zostaw wyłącznie krawędzie z twardymi "
                                       "przesłankami (identyczne domeny/wizerunki, "
                                       "hashe…).")
        with fc2:
            min_pct = st.slider("min. podobieństwo", 0, 100, 0, 5,
                                help="Zostaw na mapie tylko te powiązania, w których "
                                     "materiały są do siebie podobne co najmniej "
                                     "w takim stopniu (0% = wszystko, 100% = "
                                     "praktycznie bliźniaki).")
            min_score = min_pct / 100
        with fc3:
            query = st.text_input(
                "szukaj", value="",
                placeholder="🔍 fraza: id / tytuł / domena / wizerunek…",
                label_visibility="collapsed",
                help="Pokaż wyłącznie materiały pasujące do frazy (id, tytuł, domena, "
                     "wizerunek, tracker).")
        with fc4:
            show_single = st.toggle("pojedyncze", value=False,
                                    help="Pokaż też materiały bez powiązań.")
        sel = None
        cids = [c["cluster_id"] for c in clusters]
        if cids:
            sel = st.pills("kampanie", cids, selection_mode="multi",
                           help="Bez wyboru = wszystkie kampanie.")
        # --- filtracja ---
        fedges = [e for e in edges
                  if e["score"] >= min_score and (not only_hard or e.get("hard"))]
        cluster_of = {n["id"]: n.get("cluster") for n in nodes}
        if sel:
            s = set(sel)
            fedges = [e for e in fedges
                      if cluster_of.get(e["a"]) in s and cluster_of.get(e["b"]) in s]
        if query.strip():
            q = query.strip().lower()

            def _hit(n):
                hay = " ".join(filter(None, [
                    n.get("id") or "", n.get("title") or "",
                    " ".join(n.get("domains") or []),
                    " ".join(n.get("faces") or []),
                    " ".join(n.get("trackers") or [])])).lower()
                return q in hay
            keep = {n["id"] for n in nodes if _hit(n)}
            fedges = [e for e in fedges if e["a"] in keep and e["b"] in keep]
            fnodes = [n for n in nodes if n["id"] in keep]
            show_single = True  # pasujący pojedynczy materiał musi być widoczny
        else:
            fnodes = list(nodes)
        if sel:
            s = set(sel)
            fnodes = [n for n in fnodes if cluster_of.get(n["id"]) in s]
        ids = {n["id"] for n in fnodes}
        fclusters = [c for c in clusters if any(m in ids for m in c["members"])]
        active = bool(only_hard or min_score > 0 or query.strip() or sel)
        st.markdown(
            "<div class='kf-fstat'>PO FILTRACH: "
            f"<b>{len(fedges)}</b>/{len(edges)} powiązań · "
            f"<b>{len(fnodes)}</b>/{len(nodes)} materiałów · "
            f"<b>{len(fclusters)}</b>/{len(clusters)} kampanii "
            + ("<span class='off'>● FILTRY AKTYWNE</span>" if active
               else "<span class='on'>● PEŁNY ZBIÓR</span>")
            + "</div>", unsafe_allow_html=True)
    return {"nodes": fnodes, "edges": fedges, "clusters": fclusters}, show_single


def render_graph(graph, mode: str = "hub"):
    """Graf kampanii.

    mode='hub' (domyślny): kampania = hub + szprychy do materiałów — gęste kliki
    bez spaghetti, połączenia cały czas widoczne.
    mode='full': wszystkie krawędzie materiał–materiał.
    """
    graph, show_single = _filter_graph(graph)
    if not graph["nodes"] or (not graph["edges"] and not show_single):
        st.info("Filtry wykluczyły wszystkie materiały — osłab kryteria "
                "(fraza, próg, wybrane kampanie) albo odśwież wynik analizy.")
        return
    try:
        from pyvis.network import Network
        net = Network(height="680px", width="100%", bgcolor="#04070c",
                      font_color="#c9ffe9", directed=False, cdn_resources="in_line")
        # paleta neonowa (dark-ops): każda kampania świeci własnym kolorem
        palette = ["#00ff9c", "#00e5ff", "#ff2bd6", "#ffb400", "#a855f7",
                   "#ff5f1f", "#00ffc8", "#ff2079", "#c8ff00", "#38bdf8"]
        colors = {}
        for i, c in enumerate(graph["clusters"]):
            for m in c["members"]:
                colors[m] = palette[i % len(palette)]
        deg = Counter()
        for e in graph["edges"]:
            deg[e["a"]] += 1
            deg[e["b"]] += 1
        max_deg = max(deg.values(), default=0) or 1
        dtxt = {}   # teksty szczegółów węzłów (popup = węzeł w świecie grafu)
        etxt = {}   # teksty szczegółów krawędzi

        def _tt_node_text(n: dict, deg_n: int) -> str:
            lines = [f"{n['id']} · KAMPANIA {n.get('cluster') or '—'}",
                     (n.get("title") or "").strip()[:80]]
            for lbl, key in (("DOMENY", "domains"), ("WIZERUNKI", "faces"),
                             ("TRACKERY", "trackers")):
                if n.get(key):
                    lines.append(f"{lbl}: {', '.join(str(v) for v in n[key][:8])}")
            lines.append(f"powiązań: {deg_n} · pliki: {n.get('n_files', '—')} · "
                         f"obrazy: {n.get('n_images', '—')} · "
                         f"od: {(n.get('first_seen') or '—')[:10]}")
            return "\n".join(lines)

        hidden = 0
        n_vis = 0
        e_cnt = 0
        for n in graph["nodes"]:
            if deg.get(n["id"], 0) == 0 and not show_single:
                hidden += 1  # pojedyncze, niepołączone materiały — ukrywamy
                continue
            size = 12 + 16 * (deg.get(n["id"], 0) / max_deg)
            col = colors.get(n["id"], "#00e5ff")
            net.add_node(
                n["id"], label=n["id"], shape="dot", size=size, borderWidth=2.5,
                color={"background": "#04070c",
                       "border": col,
                       "highlight": {"background": "#0a1420", "border": "#ffffff"},
                       "hover": {"background": "#0a1420", "border": "#ffffff"}},
                shadow={"enabled": True, "color": _rgba(col, 0.55),
                        "size": 14, "x": 0, "y": 0},
                font={"size": 15, "color": col, "face": "Consolas,monospace"},
                title=_tt_short(n, deg.get(n["id"], 0)))
            n_vis += 1
            dtxt[n["id"]] = _tt_node_text(n, deg.get(n["id"], 0))
        if mode == "hub":
            for c in graph["clusters"]:
                members = [m for m in c["members"] if deg.get(m, 0) > 0]
                if len(members) < 2:
                    continue
                col = colors.get(members[0], "#00e5ff")
                hub_text = (
                    f"{c['cluster_id']} — KAMPANIA · {len(members)} materiałów\n"
                    f"{c['label'][:160]}\n"
                    f"CZŁONKOWIE: {', '.join(members[:12])}\n"
                    f"średnie podobieństwo {c['mean_score']} · twarde: {c['hard_links']}")
                hub_short = _tt_card(
                    f"<div style='font-size:14px;font-weight:bold;color:{col}'>"
                    f"{c['cluster_id']} — KAMPANIA · {len(members)} materiałów</div>"
                    f"<div style='margin-top:3px;color:#9aa7b4'>{c['label'][:70] or '—'}</div>"
                    f"<div style='margin-top:4px;color:#5b7bd5;font-size:11px'>"
                    f"kliknij — pełne szczegóły</div>", 260)
                net.add_node(
                    c["cluster_id"], label=c["cluster_id"], shape="diamond",
                    size=24 + 6 * len(members), borderWidth=2.5,
                    mass=2 + 2 * len(members),
                    color={"background": "#04070c", "border": col,
                           "highlight": {"background": "#0a1420", "border": "#ffffff"},
                           "hover": {"background": "#0a1420", "border": "#ffffff"}},
                    shadow={"enabled": True, "color": _rgba(col, 0.6),
                            "size": 16, "x": 0, "y": 0},
                    font={"size": 17, "color": col, "face": "Consolas,monospace"},
                    title=hub_short)
                n_vis += 1
                dtxt[c["cluster_id"]] = hub_text
                for m in members:
                    best = None
                    for e in graph["edges"]:
                        if (m in (e["a"], e["b"]) and e["a"] in c["members"]
                                and e["b"] in c["members"]):
                            if best is None or e["score"] > best["score"]:
                                best = e
                    spoke = {"enabled": True, "type": "curvedCW", "roundness": 0.16}
                    if best is None:
                        net.add_edge(c["cluster_id"], m, width=1.5, color=col,
                                     dashes=True, smooth=spoke,
                                     shadow={"enabled": True, "color": _rgba(col, 0.35),
                                             "size": 8, "x": 0, "y": 0},
                                     title=f"{m} — kampania {c['cluster_id']}")
                        e_cnt += 1
                        continue
                    other = best["b"] if best["a"] == m else best["a"]
                    edge_text = (
                        f"{m} ↔ {other} · score {best['score']:.3f}"
                        f"{' · TWARDE' if best['hard'] else ''}\n"
                        + "\n".join(f"• {x}" for x in best["evidence"][:4]))
                    net.add_edge(
                        c["cluster_id"], m, value=round(best["score"] * 10, 1),
                        width=1.5 + 4.5 * best["score"],
                        dashes=(not best["hard"]),
                        color=col,
                        shadow={"enabled": True, "color": _rgba(col, 0.5),
                                "size": 10, "x": 0, "y": 0},
                        smooth=spoke,
                        title=_tt_card(
                            f"<div style='font-size:12px;font-weight:bold;color:{col}'>"
                            f"{m} ↔ {other} · score {best['score']:.3f}"
                            f"{' · TWARDE' if best['hard'] else ''}</div>"
                            f"<div style='margin-top:3px;color:#9aa7b4;font-size:11px'>"
                            f"kliknij — przesłanki</div>", 230))
                    e_cnt += 1
                    etxt[f"{c['cluster_id']}|{m}"] = edge_text
        else:
            for e in graph["edges"]:
                if deg.get(e["a"], 0) == 0 or deg.get(e["b"], 0) == 0:
                    continue
                ev = "".join(f"<div style='margin-top:4px'>• {x}</div>"
                             for x in e["evidence"][:4])
                edge_text = (
                    f"{e['a']} ↔ {e['b']} · score {e['score']:.3f}"
                    f"{' · TWARDE' if e['hard'] else ''}\n"
                    + "\n".join(f"• {x}" for x in e["evidence"][:4]))
                net.add_edge(e["a"], e["b"], value=round(e["score"] * 10, 1),
                             title=_tt_card(
                                 f"<div style='font-size:12px;font-weight:bold;"
                                 f"color:{'#00ff9c' if e['hard'] else '#00e5ff'}"
                                 f"'>{e['a']} ↔ {e['b']} · score {e['score']:.3f}"
                                 f"{' · TWARDE' if e['hard'] else ''}</div>"
                                 f"<div style='margin-top:3px;color:#9aa7b4;font-size:11px'>"
                                 f"kliknij — przesłanki</div>", 230),
                             dashes=(not e["hard"]),
                             color=("#00ff9c" if e["hard"] else "#00e5ff"),
                             shadow={"enabled": True,
                                     "color": _rgba("#00ff9c" if e["hard"] else "#00e5ff", 0.45),
                                     "size": 10, "x": 0, "y": 0},
                             width=1.5 + 4.5 * e["score"])
                e_cnt += 1
                etxt[f"{e['a']}|{e['b']}"] = edge_text
        net.set_options(
            """{"physics": {"barnesHut": {"gravitationalConstant": -9000,
                                           "springLength": 90,
                                           "damping": 0.08,
                                           "avoidOverlap": 0.6},
                             "minVelocity": 0.75,
                             "solver": "barnesHut",
                             "stabilization": {"enabled": true, "iterations": 300,
                                               "updateInterval": 20}},
                "interaction": {"hover": true, "tooltipDelay": 150,
                                "keyboard": true, "zoomSpeed": 0.6},
                "nodes": {"shadow": {"enabled": true},
                          "font": {"face": "Consolas, monospace"}},
                "edges": {"selectionWidth": 2}}""")
        # karty popupów jako obrazy PNG (węzeł-obraz zawsze renderuje treść)
        import json as _json
        import subprocess as _sp
        try:
            _ver = _sp.run(["git", "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, cwd=PROJ,
                           timeout=5).stdout.strip()
        except Exception:
            _ver = "?"
        _foot = f"\n\ngraf v{_ver} · kliknij ponownie, aby zamknąć"
        dimg = {k: _card_image(t + _foot) for k, t in dtxt.items()}
        eimg = {k: _card_image(t + _foot) for k, t in etxt.items()}
        js = """<script>
(function () {
  var D = %s, E = %s, POPN = 0, open = {};
  function showPopup(img, cx, cy, key) {
    if (open[key]) {
      network.body.data.nodes.remove(open[key]);
      delete open[key];
      return;
    }
    var id = "__kf_popup_" + (POPN++);
    network.body.data.nodes.add({
      id: id,
      x: cx, y: cy,
      fixed: { x: true, y: true },
      shape: "image",
      image: img,
      size: 175,
      mass: 6,
      borderWidth: 0,
      color: { background: "rgba(0,0,0,0)", border: "rgba(0,0,0,0)" }
    });
    open[key] = id;
  }
  function closeAll() {
    Object.keys(open).forEach(function (k) {
      if (network.body.data.nodes.get(open[k])) network.body.data.nodes.remove(open[k]);
    });
    open = {};
  }
  // przeciąganie kart: podczas ciągnięcia zdejmujemy kotwicę, po upuszczeniu wraca
  network.on("dragStart", function (p) {
    (p.nodes || []).forEach(function (nid) {
      if (nid.indexOf("__kf_popup_") === 0) {
        network.body.data.nodes.update({ id: nid, fixed: { x: false, y: false } });
      }
    });
  });
  network.on("dragEnd", function (p) {
    (p.nodes || []).forEach(function (nid) {
      if (nid.indexOf("__kf_popup_") === 0) {
        network.body.data.nodes.update({ id: nid, fixed: { x: true, y: true } });
      }
    });
  });
  network.on("click", function (p) {
    if (p.nodes.length) {
      var nid = p.nodes[0];
      if (nid.indexOf("__kf_popup_") === 0) {
        network.body.data.nodes.remove(nid);
        Object.keys(open).forEach(function (k) { if (open[k] === nid) delete open[k]; });
        return;
      }
      var pos = network.getPosition(nid);
      if (D[nid]) showPopup(D[nid], pos.x + 340, pos.y - 90, "n:" + nid);
      return;
    }
    if (p.edges.length) {
      var ed = network.body.data.edges.get(p.edges[0]);
      if (ed) {
        var k1 = ed.from + "|" + ed.to, k2 = ed.to + "|" + ed.from;
        var t = E[k1] || E[k2];
        if (t) {
          var a = network.getPosition(ed.from), b = network.getPosition(ed.to);
          showPopup(t, (a.x + b.x) / 2 + 340, (a.y + b.y) / 2 - 60, "e:" + k1);
        }
      }
      return;
    }
    closeAll();
  });
})();
</script>""" % (_json.dumps(dimg, ensure_ascii=False),
        _json.dumps(eimg, ensure_ascii=False))
        net.write_html("/tmp/kfk_graph.html")
        html = Path("/tmp/kfk_graph.html").read_text(encoding="utf-8")
        # skin dark-ops: siatka + mgiełka neonowa w tle, skanliny CRT, HUD w rogach
        hud = (
            "<div class='kf-vig'></div>"
            "<div class='kf-hud'>&#9673; KFK // MAPA POWIĄZAŃ <b>&#9646;</b><br>"
            f"<span class='dim'>SCAN:CAMPAIGN_GRAPH &middot; TRYB:"
            f"{'HUB' if mode == 'hub' else 'FULL'}</span></div>"
            f"<div class='kf-hud2'>WĘZŁY:{n_vis} &middot; KRAWĘDZIE:{e_cnt}</div>")
        css = """<style>
body { background: #04070c !important; }
.card { background: transparent !important; border: none !important;
        box-shadow: none !important; }
#mynetwork {
  background-color: #04070c !important;
  border: 1px solid rgba(0,255,156,0.25) !important;
  background-image:
    radial-gradient(ellipse 70% 60% at 50% 45%, rgba(0,255,156,0.055), transparent 70%),
    linear-gradient(rgba(0,255,156,0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0,255,156,0.045) 1px, transparent 1px),
    radial-gradient(rgba(0,229,255,0.12) 1px, transparent 1.6px);
  background-size: auto, 44px 44px, 44px 44px, 22px 22px;
}
.kf-vig { position: absolute; inset: 0; z-index: 4; pointer-events: none;
  background: repeating-linear-gradient(0deg, rgba(0,0,0,0.13) 0 1px, transparent 1px 3px),
              radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.45) 100%); }
.kf-hud { position: absolute; top: 8px; left: 10px; z-index: 5; pointer-events: none;
  font: 11px/1.6 Consolas,monospace; color: #00ff9c; letter-spacing: 1.5px;
  text-shadow: 0 0 8px rgba(0,255,156,0.65); }
.kf-hud .dim { color: #3f6a58; text-shadow: none; }
.kf-hud2 { position: absolute; bottom: 8px; right: 12px; z-index: 5; pointer-events: none;
  font: 10px Consolas,monospace; color: #2e6b52; letter-spacing: 1.5px; }
@keyframes kfblink { 50% { opacity: 0; } }
.kf-hud b { animation: kfblink 1.1s steps(1) infinite; font-weight: normal; }
.vis-tooltip { background: #060a10 !important; color: #cdd7e0 !important;
  border: 1px solid rgba(0,255,156,0.45) !important; border-radius: 8px !important;
  box-shadow: 0 0 16px rgba(0,255,156,0.25) !important;
  font: 12.5px/1.6 Consolas,monospace !important; padding: 2px !important; }
</style>"""
        html = html.replace('<div id="mynetwork" class="card-body"></div>',
                            f'<div id="mynetwork" class="card-body">{hud}</div>')
        html = html.replace("</body>", css + js + "</body>")
        st.components.v1.html(html, height=640, scrolling=True)
        if mode == "hub":
            st.caption("Romby = kampanie (hub), kółka = materiały. "
                       "Linia ciągła = twardy dowód, przerywana = podobieństwo. "
                       "Najedź — skrót; **kliknij węzeł/szprychę** — karta w świecie "
                       "grafu (można otworzyć kilka naraz, przeciągać je i zamykać "
                       "kliknięciem; klik w puste zamyka wszystkie).")
        if hidden:
            st.caption(f"Ukryto {hidden} pojedynczych materiałów bez powiązań "
                       "(pełna lista na stronie Incydenty).")
        big = [c for c in graph["clusters"] if len(c["members"]) > 1]
        if big:
            cols = st.columns(min(3, len(big)))
            for i, c in enumerate(big):
                with cols[i % len(cols)]:
                    st.markdown(
                        f"<span style='color:{colors[c['members'][0]]}'>●</span> "
                        f"**{c['cluster_id']}**: {', '.join(c['members'][:8])}",
                        unsafe_allow_html=True)
    except Exception as e:
        st.warning(f"Widok grafu niedostępny (pyvis): {e}")


def render_campaigns(graph, store):
    inc_feats = store.load_incidents()
    titles = title_map(graph)
    by_id = {f["id"]: f for f in inc_feats}
    clusters = graph["clusters"]
    big = sorted((c for c in clusters if len(c["members"]) >= 3),
                 key=lambda c: -len(c["members"]))
    pairs = sorted((c for c in clusters if len(c["members"]) == 2),
                   key=lambda c: c["cluster_id"])
    n_single = sum(1 for c in clusters if len(c["members"]) == 1)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Kampanie ≥3 materiały", len(big))
    m2.metric("Pary wariantów", len(pairs))
    m3.metric("Materiały pojedyncze", n_single)
    m4.metric("Kampanie łącznie", len(clusters))
    if big:
        st.markdown("### Główne kampanie")
        for c in big:
            members_preview = c["members"][:4]
            thumbs = []
            for m in members_preview[:3]:
                f = by_id.get(m)
                if f:
                    prev = preview_images(f, 1)
                    if prev:
                        thumbs.append((m, prev[0]))
            with st.container(border=True):
                if thumbs:
                    left, right = st.columns([2.6, 3.4])
                    with left:
                        tcols = st.columns(len(thumbs))
                        for i, (m, p) in enumerate(thumbs):
                            with tcols[i]:
                                try:
                                    st.image(str(p), width=200)
                                except Exception:
                                    pass
                                st.caption(m)
                else:
                    right = st.container()
                with right:
                    st.markdown(f"### {c['cluster_id']} — {len(c['members'])} materiałów")
                    uniq = []
                    for t in [titles.get(m, m) for m in members_preview]:
                        if t not in uniq:
                            uniq.append(t)
                    st.markdown(f"*{' · '.join(t[:46] for t in uniq[:3])}*")
                    st.write(f"**Motyw:** {c['label'][:160] or '—'}")
                    st.write(f"Twarde powiązania: **{c['hard_links']}** · "
                             f"średnie podobieństwo: **{c['mean_score']}**")
                    with st.expander("Wszystkie materiały"):
                        for m in c["members"]:
                            f = by_id.get(m)
                            col1, col2 = st.columns([1, 4])
                            with col1:
                                prev = preview_images(f, 1) if f else []
                                if prev:
                                    try:
                                        st.image(str(prev[0]), width=160)
                                    except Exception:
                                        st.markdown("`(brak obrazu)`")
                                else:
                                    st.markdown("`(brak podglądu)`")
                            with col2:
                                st.write(f"**{m}** · {titles.get(m, m)}")
                                if f:
                                    d = f["infra"].get("registrable") or []
                                    if d:
                                        st.caption("domeny: " + ", ".join(d[:5]))
    if pairs:
        with st.expander(f"Pary wariantów ({len(pairs)}) — materiały niemal identyczne",
                         expanded=False):
            for c in pairs:
                st.write(f"• **{c['cluster_id']}**: "
                         f"{' / '.join(titles.get(m, m) for m in c['members'])}")
    if not big and not pairs:
        st.info("Brak powiązanych materiałów w zbiorze.")


def render_pair_analyzer(graph, store):
    st.markdown("### 🔍 Dlaczego materiały NIE zostały połączone?")
    all_ids = [n["id"] for n in graph["nodes"]]
    col_a, col_b = st.columns(2)
    with col_a:
        sel_a = st.selectbox("Materiał A", all_ids, key="pa")
    with col_b:
        sel_b = st.selectbox("Materiał B", list(reversed(all_ids)), key="pb")
    if sel_a and sel_b and sel_a != sel_b:
        inc_feats = store.load_incidents()
        fa = next(x for x in inc_feats if x["id"] == sel_a)
        fb = next(x for x in inc_feats if x["id"] == sel_b)
        tfidf = Tfidf()
        tfidf.fit([x["text"].get("body_norm", "") for x in inc_feats])
        r = pair_similarity(fa, fb, tfidf)
        neg = negative_evidence(fa, fb, tfidf)
        edge_pairs = {(e["a"], e["b"]) for e in graph["edges"]} | {(e["b"], e["a"]) for e in graph["edges"]}
        linked = (sel_a, sel_b) in edge_pairs
        st.write(f"Podobieństwo ważone: **{r['score']:.3f}** → "
                 f"{'✅ POŁĄCZONE' if linked else '❌ nie połączone (poniżej progu)'}")
        if r["evidence"]:
            st.markdown("**Przesłanki ZA:**")
            for e in r["evidence"]:
                st.write(f"• {e}")
        if neg:
            st.markdown("**Przesłanki PRZECIW:**")
            for e in neg:
                st.write(f"• {e}")
        if not r["evidence"] and not neg:
            st.info("Brak porównywalnych danych po obu stronach (materiały niekompletne).")


def render_incidents(graph, store):
    incs = store.load_incidents()
    sel_inc = st.selectbox("Incydent", [f["id"] for f in incs])
    f = next(x for x in incs if x["id"] == sel_inc)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**ID:** {f['id']}")
        st.markdown(f"**Tytuł:** {f['text'].get('title') or '(brak)'}")
        st.markdown(f"**Plików:** {f['n_files']}, **obrazów:** {len(f['images'])}")
        st.markdown(f"**Domeny:** {', '.join(f['infra']['registrable']) or '(brak)'}")
        st.markdown(f"**Trackery:** {', '.join(f['infra']['tracker_ids']) or '(brak)'}")
        for r in f["infra"].get("rdap") or []:
            if r.get("error"):
                st.caption(f"RDAP {r['domain']}: {r['error']}")
                continue
            st.markdown(f"**RDAP {r['domain']}:** rejestrator: {r.get('registrar') or '—'} · "
                        f"NS: {', '.join(r.get('ns') or []) or '—'} · "
                        f"od {(r.get('created') or '?')[:10]} do {(r.get('expires') or '?')[:10]}")
        faces = f.get("faces", {})
        if faces.get("persons"):
            st.markdown("**Wizerunki osób:** " + ", ".join(
                f"{p['name']} ({p['score']})" for p in faces["persons"]))
        if f["text"].get("ocr"):
            st.markdown(f"**OCR:** _{f['text']['ocr'][:400]}_")
    with c2:
        st.markdown("**Tekst strony (fragment):**")
        st.text(f["text"].get("body", "")[:600] or "(brak)")
    prev = preview_images(f, 6)
    if prev:
        st.markdown("**Podgląd materiału:**")
        cols = st.columns(min(3, len(prev)))
        for i, p in enumerate(prev):
            with cols[i % len(cols)]:
                try:
                    st.image(str(p), width=260)
                    st.caption(p.name[:48])
                except Exception:
                    pass
    elif f["text"].get("body"):
        st.info(f"Brak obrazów — materiał tylko tekstowy: _{f['text']['body'][:220]}_")
    st.caption(f"Ścieżka: {f['path']}")


def render_export(db):
    stix_f = Path(db).with_suffix(".stix.json")
    ioc_f = Path(db).with_suffix(".ioc.csv")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**STIX 2.1** — kampanie, incydenty, wskaźniki domen, relacje "
                    "z przesłankami i poziomem ufności.")
        if stix_f.is_file():
            st.download_button("⬇ Pobierz STIX 2.1 (.json)", stix_f.read_text(encoding="utf-8"),
                               file_name="kolekcjoner-fejkow.stix.json",
                               mime="application/json")
        else:
            st.info("Uruchom analizę, aby wygenerować pakiet STIX.")
    with c2:
        st.markdown("**Watchlista IoC** — domeny, trackery, favicony, hashe wideo "
                    "z przypisaniem kampanii.")
        if ioc_f.is_file():
            st.download_button("⬇ Pobierz IoC (.csv)", ioc_f.read_text(encoding="utf-8"),
                               file_name="ioc_watchlist.csv", mime="text/csv")
            try:
                import pandas as pd
                st.dataframe(pd.read_csv(ioc_f), height=300)
            except Exception:
                st.text(ioc_f.read_text(encoding="utf-8")[:2000])
        else:
            st.info("Uruchom analizę, aby wygenerować watchlistę IoC.")
