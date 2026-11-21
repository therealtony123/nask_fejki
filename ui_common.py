"""Wspólna logika widoków UI — wszystkie strony korzystają z tych funkcji."""
import json
import time
from collections import Counter
from pathlib import Path

import streamlit as st

from kfk import (Store, Tfidf, assign_new_incident, extract_from_url_text,
                 extract_incident, pair_similarity, scan)
from kfk.similarity import negative_evidence
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
                   "n_images": len(f["images"]), "n_files": f.get("n_files", 0)}
                  for f in feats],
        "edges": [{"a": e["a"], "b": e["b"], "score": e["score"], "hard": e["hard"],
                   "evidence": e["evidence"]} for e in edges],
        "clusters": clusters,
    }
    Path(db).with_suffix(".graph.json").write_text(
        json.dumps(graph, ensure_ascii=False, indent=1), encoding="utf-8")
    bar.progress(1.0, text="Gotowe")
    return graph


def _tt_card(inner: str, min_w: int = 280) -> str:
    return (f"<div style='min-width:{min_w}px;max-width:440px;background:#000000;"
            f"border:1px solid #2b2b2b;border-radius:6px;padding:10px 12px;"
            f"font:12.5px/1.6 Consolas,monospace;color:#cdd7e0'>{inner}</div>")


def preview_images(f: dict, max_n: int = 6) -> list:
    """Najlepsze obrazy do podglądu incydentu (zrzuty > obrazy główne > największe)."""
    base = Path(f["path"])
    scored = []
    for im in f.get("images", []):
        p = base / im["path"]
        if not p.is_file():
            continue
        name = p.name.lower()
        score = 0
        if "zrzut" in name or "screen" in name:
            score += 100
        if im.get("top"):
            score += 50
        if name.startswith(("img_00", "01-hero", "hero", "og-")):
            score += 40
        try:
            score += min(p.stat().st_size // 100_000, 20)
        except OSError:
            pass
        scored.append((score, p))
    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored[:max_n]]


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


def render_graph(graph, mode: str = "hub"):
    """Graf kampanii.

    mode='hub' (domyślny): kampania = hub + szprychy do materiałów — gęste kliki
    bez spaghetti, połączenia cały czas widoczne.
    mode='full': wszystkie krawędzie materiał–materiał.
    """
    try:
        from pyvis.network import Network
        net = Network(height="600px", width="100%", bgcolor="#000000",
                      font_color="#fafafa", directed=False, cdn_resources="in_line")
        palette = ["#ff4b4b", "#4bb3ff", "#ffd34b", "#4bff8c", "#c44bff", "#ff9d4b",
                   "#4bffd3", "#ff4bd3", "#8cff4b", "#4b8cff"]
        colors = {}
        for i, c in enumerate(graph["clusters"]):
            for m in c["members"]:
                colors[m] = palette[i % len(palette)]
        deg = Counter()
        for e in graph["edges"]:
            deg[e["a"]] += 1
            deg[e["b"]] += 1
        max_deg = max(deg.values()) or 1
        detail = {}   # pełne szczegóły węzłów (panel po kliknięciu)
        edetail = {}  # pełne szczegóły krawędzi (panel po kliknięciu)
        hidden = 0
        for n in graph["nodes"]:
            if deg.get(n["id"], 0) == 0:
                hidden += 1  # pojedyncze, niepołączone materiały — ukrywamy
                continue
            size = 12 + 16 * (deg.get(n["id"], 0) / max_deg)
            net.add_node(
                n["id"], label=n["id"], shape="dot", size=size, borderWidth=2,
                color={"background": colors.get(n["id"], "#555555"),
                       "border": "#ffffff",
                       "highlight": {"background": colors.get(n["id"], "#555555"),
                                     "border": "#ffd34b"}},
                font={"size": 15, "color": "#fafafa", "face": "monospace"},
                title=_tt_short(n, deg.get(n["id"], 0)))
            detail[n["id"]] = _tt_node(n, deg.get(n["id"], 0))
        if mode == "hub":
            for c in graph["clusters"]:
                members = [m for m in c["members"] if deg.get(m, 0) > 0]
                if len(members) < 2:
                    continue
                col = colors.get(members[0], "#4bb3ff")
                hub_full = _tt_card(
                    f"<div style='font-size:16px;font-weight:bold;color:{col}'>"
                    f"{c['cluster_id']} — KAMPANIA · {len(members)} materiałów</div>"
                    f"<div style='margin:5px 0;color:#e6edf3'>{c['label'][:160]}</div>"
                    f"<div style='margin-top:6px'><b style='color:#8b98a5'>CZŁONKOWIE</b><br>"
                    f"{', '.join(members[:12])}</div>"
                    f"<div style='margin-top:8px;color:#5b7bd5'>średnie podobieństwo "
                    f"{c['mean_score']} · twarde powiązania: {c['hard_links']}</div>")
                hub_short = _tt_card(
                    f"<div style='font-size:14px;font-weight:bold;color:{col}'>"
                    f"{c['cluster_id']} — KAMPANIA · {len(members)} materiałów</div>"
                    f"<div style='margin-top:3px;color:#9aa7b4'>{c['label'][:70] or '—'}</div>"
                    f"<div style='margin-top:4px;color:#5b7bd5;font-size:11px'>"
                    f"kliknij — pełne szczegóły</div>", 260)
                net.add_node(
                    c["cluster_id"], label=c["cluster_id"], shape="box",
                    size=22 + 6 * len(members), borderWidth=2, mass=2 + 2 * len(members),
                    color={"background": "#000000", "border": col,
                           "highlight": {"background": "#111111", "border": "#ffd34b"}},
                    font={"size": 18, "color": col, "face": "monospace"},
                    title=hub_short)
                detail[c["cluster_id"]] = hub_full
                for m in members:
                    best = None
                    for e in graph["edges"]:
                        if (m in (e["a"], e["b"]) and e["a"] in c["members"]
                                and e["b"] in c["members"]):
                            if best is None or e["score"] > best["score"]:
                                best = e
                    if best is None:
                        net.add_edge(c["cluster_id"], m, width=2, color="#33415c",
                                     title=f"{m} — kampania {c['cluster_id']}")
                        continue
                    other = best["b"] if best["a"] == m else best["a"]
                    ev = "".join(f"<div style='margin-top:4px'>• {x}</div>"
                                 for x in best["evidence"][:4])
                    edge_full = _tt_card(
                        f"<div style='font-size:13px;font-weight:bold;"
                        f"color:{'#ff6b6b' if best['hard'] else '#5b7bd5'}'>"
                        f"{m} ↔ {other} · score {best['score']:.3f}"
                        f"{' · TWARDE' if best['hard'] else ''}</div>{ev}")
                    net.add_edge(
                        c["cluster_id"], m, value=round(best["score"] * 10, 1),
                        width=1 + 4 * best["score"],
                        color="#ff6b6b" if best["hard"] else "#5b7bd5",
                        title=_tt_card(
                            f"<div style='font-size:12px;font-weight:bold;"
                            f"color:{'#ff6b6b' if best['hard'] else '#5b7bd5'}'>"
                            f"{m} ↔ {other} · score {best['score']:.3f}"
                            f"{' · TWARDE' if best['hard'] else ''}</div>"
                            f"<div style='margin-top:3px;color:#9aa7b4;font-size:11px'>"
                            f"kliknij — przesłanki</div>", 230))
                    edetail[f"{c['cluster_id']}|{m}"] = edge_full
        else:
            for e in graph["edges"]:
                if deg.get(e["a"], 0) == 0 or deg.get(e["b"], 0) == 0:
                    continue
                ev = "".join(f"<div style='margin-top:4px'>• {x}</div>"
                             for x in e["evidence"][:4])
                edge_full = _tt_card(
                    f"<div style='font-size:13px;font-weight:bold;"
                    f"color:{'#ff6b6b' if e['hard'] else '#5b7bd5'}'>"
                    f"{e['a']} ↔ {e['b']} · score {e['score']:.3f}"
                    f"{' · TWARDE' if e['hard'] else ''}</div>{ev}")
                net.add_edge(e["a"], e["b"], value=round(e["score"] * 10, 1),
                             title=_tt_card(
                                 f"<div style='font-size:12px;font-weight:bold;"
                                 f"color:{'#ff6b6b' if e['hard'] else '#5b7bd5'}'>"
                                 f"{e['a']} ↔ {e['b']} · score {e['score']:.3f}"
                                 f"{' · TWARDE' if e['hard'] else ''}</div>"
                                 f"<div style='margin-top:3px;color:#9aa7b4;font-size:11px'>"
                                 f"kliknij — przesłanki</div>", 230),
                             color="#ff6b6b" if e["hard"] else "#5b7bd5",
                             width=1 + 4 * e["score"])
                edetail[f"{e['a']}|{e['b']}"] = edge_full
        net.set_options(
            """{"physics": {"barnesHut": {"gravitationalConstant": -3000,
                                           "springLength": 140,
                                           "damping": 0.09}},
                "nodes": {"shadow": {"enabled": true, "size": 6,
                                     "color": "rgba(255,255,255,0.25)"}}}""")
        net.write_html("/tmp/kfk_graph.html")
        # panel szczegółów po kliknięciu (zwijany) + czarna skórka
        import json as _json
        _panel_css = ("position:fixed;top:70px;right:16px;z-index:9999;"
                      "max-width:400px;max-height:72vh;overflow:auto;"
                      "background:#000000;border:1px solid #00ff9c;border-radius:8px;"
                      "padding:12px 14px;display:none;"
                      "font:12.5px/1.6 Consolas,monospace;color:#cdd7e0;"
                      "box-shadow:0 0 24px rgba(0,255,156,.25)")
        js = """<div id="kf-panel" style="%s"></div>
<script>
(function () {
  var D = %s, E = %s, panel = document.getElementById("kf-panel"), last = null;
  function show(html, key) {
    if (last === key) { panel.style.display = "none"; last = null; return; }
    panel.innerHTML = html +
      "<div style='margin-top:10px;text-align:right;color:#00ff9c;cursor:pointer' " +
      "onclick='window.kfClose()'>✕ zamknij</div>";
    panel.style.display = "block"; last = key;
  }
  window.kfClose = function () { panel.style.display = "none"; last = null; };
  network.on("click", function (p) {
    if (p.nodes.length) { show(D[p.nodes[0]] || "", "n:" + p.nodes[0]); }
    else if (p.edges.length && p.nodes.length === 2) {
      var k1 = p.nodes[0] + "|" + p.nodes[1], k2 = p.nodes[1] + "|" + p.nodes[0];
      show(E[k1] || E[k2] || "", "e:" + k1);
    } else { panel.style.display = "none"; last = null; }
  });
})();
</script>""" % (_panel_css, _json.dumps(detail, ensure_ascii=False),
        _json.dumps(edetail, ensure_ascii=False))
        html = Path("/tmp/kfk_graph.html").read_text(encoding="utf-8")
        html = html.replace("</body>", js + "</body>")
        st.components.v1.html(html, height=640, scrolling=True)
        if mode == "hub":
            st.caption("Kwadraty = kampanie (hub), kółka = materiały. Najedź — skrót; "
                       "**kliknij węzeł lub szprychę** — zwijany panel z pełnymi "
                       "szczegółami (✕ zamyka).")
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
