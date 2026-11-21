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
    return (f"<div style='min-width:{min_w}px;max-width:440px;background:#0c1220;"
            f"border:1px solid #223047;border-radius:6px;padding:10px 12px;"
            f"font:12.5px/1.6 Consolas,monospace;color:#cdd7e0'>{inner}</div>")


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


def render_graph(graph, mode: str = "hub"):
    """Graf kampanii.

    mode='hub' (domyślny): kampania = hub + szprychy do materiałów — gęste kliki
    bez spaghetti, połączenia cały czas widoczne.
    mode='full': wszystkie krawędzie materiał–materiał.
    """
    try:
        from pyvis.network import Network
        net = Network(height="600px", width="100%", bgcolor="#0e1117",
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
                title=_tt_node(n, deg.get(n["id"], 0)))
        if mode == "hub":
            for c in graph["clusters"]:
                members = [m for m in c["members"] if deg.get(m, 0) > 0]
                if len(members) < 2:
                    continue
                col = colors.get(members[0], "#4bb3ff")
                hub_title = _tt_card(
                    f"<div style='font-size:16px;font-weight:bold;color:{col}'>"
                    f"{c['cluster_id']} — KAMPANIA · {len(members)} materiałów</div>"
                    f"<div style='margin:5px 0;color:#e6edf3'>{c['label'][:160]}</div>"
                    f"<div style='margin-top:6px'><b style='color:#8b98a5'>CZŁONKOWIE</b><br>"
                    f"{', '.join(members[:12])}</div>"
                    f"<div style='margin-top:8px;color:#5b7bd5'>średnie podobieństwo "
                    f"{c['mean_score']} · twarde powiązania: {c['hard_links']}</div>")
                net.add_node(
                    c["cluster_id"], label=c["cluster_id"], shape="box",
                    size=22 + 6 * len(members), borderWidth=2, mass=2 + 2 * len(members),
                    color={"background": "#0c1220", "border": col,
                           "highlight": {"background": "#122033", "border": "#ffd34b"}},
                    font={"size": 18, "color": col, "face": "monospace"},
                    title=hub_title)
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
                    net.add_edge(
                        c["cluster_id"], m, value=round(best["score"] * 10, 1),
                        width=1 + 4 * best["score"],
                        color="#ff6b6b" if best["hard"] else "#5b7bd5",
                        title=_tt_card(
                            f"<div style='font-size:13px;font-weight:bold;"
                            f"color:{'#ff6b6b' if best['hard'] else '#5b7bd5'}'>"
                            f"{m} ↔ {other} · score {best['score']:.3f}"
                            f"{' · TWARDE' if best['hard'] else ''}</div>{ev}"))
        else:
            for e in graph["edges"]:
                if deg.get(e["a"], 0) == 0 or deg.get(e["b"], 0) == 0:
                    continue
                ev = "<br>".join(e["evidence"][:4])
                net.add_edge(e["a"], e["b"], value=round(e["score"] * 10, 1),
                             title=_tt_card(
                                 f"<div style='font-size:13px;font-weight:bold;"
                                 f"color:{'#ff6b6b' if e['hard'] else '#5b7bd5'}'>"
                                 f"{e['a']} ↔ {e['b']} · score {e['score']:.3f}"
                                 f"{' · TWARDE' if e['hard'] else ''}</div>"
                                 + "".join(f"<div style='margin-top:4px'>• {x}</div>"
                                           for x in e["evidence"][:4])),
                             color="#ff6b6b" if e["hard"] else "#5b7bd5",
                             width=1 + 4 * e["score"])
        net.set_options(
            """{"physics": {"barnesHut": {"gravitationalConstant": -3000,
                                           "springLength": 140,
                                           "damping": 0.09}},
                "nodes": {"shadow": {"enabled": true, "size": 6,
                                     "color": "rgba(255,255,255,0.25)"}}}""")
        net.write_html("/tmp/kfk_graph.html")
        st.components.v1.html(Path("/tmp/kfk_graph.html").read_text(encoding="utf-8"),
                              height=640, scrolling=True)
        if mode == "hub":
            st.caption("Kwadraty = kampanie (hub). Szprychy łączą kampanię z jej "
                       "materiałami — najedź na szprychę, aby zobaczyć najsilniejsze "
                       "przesłanki. Przełącznikiem wrócisz do pełnego grafu krawędzi.")
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
        try:
            import pandas as pd
            df = pd.DataFrame([{
                "Kampania": c["cluster_id"],
                "Materiały": len(c["members"]),
                "Twarde": c["hard_links"],
                "Śr. podob.": c["mean_score"],
                "Motyw": c["label"][:70],
            } for c in big])
            st.dataframe(df, hide_index=True, width="stretch")
        except Exception:
            for c in big:
                st.write(f"• **{c['cluster_id']}** ({len(c['members'])}): {c['label'][:80]}")
        for c in big:
            with st.expander(f"{c['cluster_id']} — szczegóły", expanded=False):
                st.write(f"**Członkowie:** {', '.join(c['members'])}")
                st.write(f"**Przesłanki:** {c['summary']}")
                pats = {}
                for f in inc_feats:
                    if f["id"] in c["members"]:
                        for d in f["infra"].get("domain_patterns", []):
                            pats.setdefault(d["pattern"], set()).add(d["domain"])
                if pats:
                    st.write("**Wzorce nazw domen:**")
                    for p, doms in sorted(pats.items()):
                        st.write(f"• `{p}` → {', '.join(sorted(doms))}")
                names = [set(f.get("faces", {}).get("known_names") or [])
                         for f in inc_feats if f["id"] in c["members"]]
                shared = set.intersection(*names) if len(names) > 1 else (names[0] if names else set())
                if shared:
                    st.write(f"**Wizerunki osób:** {', '.join(sorted(shared))}")
    if pairs:
        with st.expander(f"Pary wariantów ({len(pairs)}) — materiały niemal identyczne",
                         expanded=False):
            for c in pairs:
                st.write(f"• **{c['cluster_id']}**: {', '.join(c['members'])} — {c['label'][:80]}")
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
