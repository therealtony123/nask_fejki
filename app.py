"""KOLEKCJONER FEJKÓW — demonstrator (Streamlit).

Uruchomienie:
  streamlit run app.py
"""
import json
import sys
import time
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from kfk import (Store, Tfidf, assign_new_incident, extract_from_url_text,
                 extract_incident, pair_similarity, scan)
from kfk.similarity import negative_evidence

HOME = Path.home()
PROJ = Path(__file__).parent
DEFAULT_DATA = PROJ / "data"
DEFAULT_DB = PROJ / "kfk.sqlite"

st.set_page_config(page_title="Kolekcjoner Fejków — FOLLOW THE FAKE", layout="wide")


@st.cache_resource
def get_store(db):
    return Store(db)


def run_pipeline(data, db, threshold, progress=True):
    from kfk import build_edges, cluster_graph
    incidents = scan(data)
    if not incidents:
        st.error("Brak incydentów w katalogu (oczekuję .../do_udostępnienia/<id>/).")
        return None
    feats = []
    bar = st.progress(0.0, text="Wyodrębnianie cech…") if progress else None
    for i, inc in enumerate(incidents, 1):
        feats.append(extract_incident(inc))
        if bar:
            bar.progress(i / (len(incidents) + 1), text=f"Cechy: {inc['id']}")
    tfidf = Tfidf()
    tfidf.fit([f["text"].get("body_norm", "") or f["text"].get("title_norm", "") for f in feats])
    edges = build_edges(feats, tfidf, threshold)
    clusters = cluster_graph([f["id"] for f in feats], edges, threshold)
    store = get_store(db)
    store.save_incidents(feats)
    store.save_edges(edges)
    store.save_clusters(clusters)
    graph = {
        "nodes": [{"id": f["id"], "title": f["text"]["title"][:80],
                   "cluster": next((c["cluster_id"] for c in clusters if f["id"] in c["members"]), None)}
                  for f in feats],
        "edges": [{"a": e["a"], "b": e["b"], "score": e["score"], "hard": e["hard"],
                   "evidence": e["evidence"]} for e in edges],
        "clusters": clusters,
    }
    Path(db).with_suffix(".graph.json").write_text(
        json.dumps(graph, ensure_ascii=False, indent=1), encoding="utf-8")
    if bar:
        bar.progress(1.0, text="Gotowe")
    return graph, tfidf


def render_graph(graph):
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
        from collections import Counter
        deg = Counter()
        for e in graph["edges"]:
            deg[e["a"]] += 1
            deg[e["b"]] += 1
        max_deg = max(deg.values()) or 1
        for n in graph["nodes"]:
            size = 12 + 16 * (deg.get(n["id"], 0) / max_deg)
            net.add_node(
                n["id"], label=n["id"], shape="dot", size=size, borderWidth=1.5,
                color={"background": colors.get(n["id"], "#555555"),
                       "border": "#ffffff",
                       "highlight": {"background": colors.get(n["id"], "#555555"),
                                     "border": "#ffd34b"}},
                font={"size": 14, "color": "#fafafa", "face": "monospace"},
                title=(f"{n['id']}: {n['title']}<br>"
                       f"kampania: {n.get('cluster', '—')}<br>"
                       f"pierwsza aktywność: {n.get('first_seen', '—')}"))
        for e in graph["edges"]:
            ev = "<br>".join(e["evidence"][:4])
            net.add_edge(e["a"], e["b"], value=round(e["score"] * 10, 1),
                         title=(f"{e['a']} ↔ {e['b']} — score={e['score']:.3f}"
                                f"{' [TWARDE]' if e['hard'] else ''}<br>{ev}"),
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
        # legenda klastrów (tylko kampanie wieloelementowe)
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


st.title("🕵️ KOLEKCJONER FEJKÓW — FOLLOW THE FAKE")
st.caption("Z pojedynczych podejrzanych reklam wydobywamy wspólne ślady i łączymy je w kampanie oszustw.")

with st.sidebar:
    st.header("Konfiguracja")
    data_dir = st.text_input("Katalog danych", str(DEFAULT_DATA))
    db_path = st.text_input("Baza SQLite", str(DEFAULT_DB))
    threshold = st.slider("Próg krawędzi (podobieństwo)", 0.05, 0.95, 0.25, 0.05)
    join_thr = st.slider("Próg przypisania do kampanii", 0.05, 0.95, 0.30, 0.05)
    if st.button("▶ Uruchom analizę", type="primary", use_container_width=True):
        t0 = time.time()
        res = run_pipeline(data_dir, db_path, threshold)
        if res:
            st.session_state["graph"], st.session_state["tfidf"] = res
            st.session_state["db"] = db_path
            st.success(f"Analiza zakończona w {time.time() - t0:.1f}s — "
                       f"{len(res[0]['nodes'])} incydentów, {len(res[0]['edges'])} krawędzi, "
                       f"{len(res[0]['clusters'])} kampanii.")
    if st.button("Wczytaj ostatnie wyniki z bazy"):
        g = Path(db_path).with_suffix(".graph.json")
        if g.is_file():
            st.session_state["graph"] = json.loads(g.read_text(encoding="utf-8"))
            st.session_state["db"] = db_path
            st.info("Wczytano zapisane wyniki.")

if "graph" not in st.session_state:
    g = Path(str(db_path)).with_suffix(".graph.json")
    if g.is_file():
        st.session_state["graph"] = json.loads(g.read_text(encoding="utf-8"))
        st.session_state["db"] = str(db_path)

if "graph" in st.session_state:
    graph = st.session_state["graph"]
    store = get_store(st.session_state["db"])

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Incydenty", len(graph["nodes"]))
    m2.metric("Powiązania (krawędzie)", len(graph["edges"]))
    m3.metric("Kampanie", len(graph["clusters"]))
    m4.metric("Twarde powiązania", sum(1 for e in graph["edges"] if e["hard"]))

    tab_prz, tab_kamp, tab_graf, tab_inc, tab_nowy, tab_eks, tab_meta = st.tabs(
        ["Przegląd kampanii", "Kampanie", "Graf zależności", "Incydenty", "Nowy materiał",
         "Eksport (STIX/IoC)", "Biblioteka reklam (bonus)"])

    with tab_prz:
        inc_feats = store.load_incidents()
        for c in graph["clusters"]:
            with st.expander(f"{c['cluster_id']} — {len(c['members'])} materiałów | "
                             f"{c['label'][:110]}", expanded=True):
                st.write(f"**Członkowie:** {', '.join(c['members'])}")
                st.write(f"**Uzasadnienie:** {c['summary']}")
                st.write(f"Krawędzi w kampanii: {c['n_edges']}, twarde: {c['hard_links']}, "
                         f"średnie podobieństwo: {c['mean_score']}")
                if c.get("first_seen"):
                    st.write(f"Pierwsza aktywność: {c['first_seen']} | ostatnia: {c.get('last_seen')}")
                pats = {}
                for f in inc_feats:
                    if f["id"] in c["members"]:
                        for d in f["infra"].get("domain_patterns", []):
                            pats.setdefault(d["pattern"], set()).add(d["domain"])
                if pats:
                    st.write("**Wzorce nazw domen:**")
                    for p, doms in sorted(pats.items()):
                        st.write(f"• `{p}` → {', '.join(sorted(doms))}")
                names_by_inc = {}
                for f in inc_feats:
                    if f["id"] in c["members"]:
                        names_by_inc[f["id"]] = set(f.get("faces", {}).get("known_names") or [])
                vals = list(names_by_inc.values())
                if vals:
                    shared_names = set.intersection(*vals) if len(vals) > 1 else vals[0]
                    if shared_names:
                        st.write(f"**Wizerunki osób:** {', '.join(sorted(shared_names))}")

    with tab_kamp:
        sel = st.selectbox("Kampania", [c["cluster_id"] for c in graph["clusters"]])
        c = next(x for x in graph["clusters"] if x["cluster_id"] == sel)
        st.subheader(f"{sel}: {', '.join(c['members'])}")
        edges_in = [e for e in graph["edges"]
                    if e["a"] in c["members"] and e["b"] in c["members"]]
        for e in edges_in:
            with st.expander(f"{e['a']} ↔ {e['b']} — score {e['score']:.3f}"
                             f"{' ⚡TWARDE' if e['hard'] else ''}"):
                for ev in e["evidence"]:
                    st.write(f"• {ev}")
        st.markdown("---")
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

    with tab_graf:
        st.caption("Kolor węzła = kampania; grubość krawędzi = podobieństwo; czerwone krawędzie = twarde przesłanki (kliknij krawędź/węzeł, aby zobaczyć dowody).")
        render_graph(graph)

    with tab_inc:
        incs = get_store(st.session_state["db"]).load_incidents()
        sel_inc = st.selectbox("Incydent", [f["id"] for f in incs])
        f = next(x for x in incs if x["id"] == sel_inc)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**ID:** {f['id']}  ")
            st.markdown(f"**Tytuł:** {f['text'].get('title') or '(brak)'}")
            st.markdown(f"**Plików:** {f['n_files']}, **obrazów:** {len(f['images'])}")
            st.markdown(f"**Domeny:** {', '.join(f['infra']['registrable']) or '(brak)'}")
            st.markdown(f"**Trackery:** {', '.join(f['infra']['tracker_ids']) or '(brak)'}")
            faces = f.get("faces", {})
            if faces.get("persons"):
                st.markdown("**Wizerunki osób:** " + ", ".join(
                    f"{p['name']} (dopasowanie {p['score']})" for p in faces["persons"]))
            if f["text"].get("ocr"):
                st.markdown(f"**OCR (zrzut ekranu):** _{f['text']['ocr'][:400]}_")
        with c2:
            st.markdown("**Tekst strony (fragment):**")
            st.text(f["text"].get("body", "")[:600] or "(brak)")
        st.caption(f"Ścieżka: {f['path']}")

    with tab_nowy:
        st.write("Wklej adres URL podejrzanej strony lub reklamy — narzędzie porówna ją "
                 "ze znanym zbiorem i wskaże kampanię lub nowy wzorzec.")
        url = st.text_input("URL", placeholder="https://przyklad-zlosliwa-domena.xyz")
        if st.button("🔎 Zbadaj materiał", type="primary"):
            if not url:
                st.warning("Podaj URL.")
            else:
                import requests
                try:
                    with st.spinner("Pobieranie i analiza…"):
                        r = requests.get(url, timeout=20, headers={
                            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                                          "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"})
                        redirects = [[str(h.status_code), h.url] for h in r.history]
                        nf = extract_from_url_text(url, r.text, redirects)
                        stored = store.load_incidents()
                        if not stored:
                            st.error("Najpierw uruchom analizę zbioru.")
                        else:
                            tfidf = Tfidf()
                            tfidf.fit([x["text"].get("body_norm", "") for x in stored])
                            matches = []
                            for s in stored:
                                sim = pair_similarity(nf, s, tfidf)
                                if sim["score"] > 0:
                                    matches.append({"b": s["id"], "title": s["text"]["title"],
                                                    **sim})
                            matches.sort(key=lambda m: -m["score"])
                            verdict = assign_new_incident(nf, stored, matches, join_thr)
                            st.subheader(verdict["verdict"])
                            st.write(verdict["explanation"])
                            if matches and matches[0]["score"] < join_thr:
                                bs = next((x for x in stored if x["id"] == matches[0]["b"]), None)
                                if bs:
                                    neg = negative_evidence(nf, bs, tfidf)
                                    if neg:
                                        st.markdown("**Przesłanki PRZECIW przypisaniu:**")
                                        for e in neg:
                                            st.write(f"• {e}")
                            for m in matches[:5]:
                                with st.expander(f"{m['b']} ({m['title'][:60]}) — "
                                                 f"score {m['score']:.3f}"):
                                    for ev in m["evidence"]:
                                        st.write(f"• {ev}")
                except Exception as e:
                    st.error(f"Nie udało się pobrać/zbadać materiału: {e}")

    with tab_meta:
        st.write("**Bonus:** automatyczne wyszukiwanie podejrzanych reklam w bibliotece "
                 "Meta Ad Library wg słów kluczowych i porównanie ich z wykrytymi kampaniami. "
                 "Wymaga tokena Graph API (opcjonalny — bez niego używamy zapisanej próbki, "
                 "plik `samples/meta_ads_sample.json`).")
        token = st.text_input("Token Meta Ad Library (Graph API)", type="password")
        terms = st.text_input("Słowa kluczowe", "zarabiaj z domu inwestycja")
        if st.button("🔎 Szukaj w bibliotece reklam"):
            from kfk.adlibrary import search_ads, load_sample, compare_ads
            stored = store.load_incidents()
            tfidf = Tfidf()
            tfidf.fit([x["text"].get("body_norm", "") for x in stored])
            ads = None
            if token:
                try:
                    with st.spinner("Pobieranie reklam z Meta Ad Library…"):
                        ads = search_ads(token, terms)
                except Exception as e:
                    st.error(f"Błąd API: {e}")
                    st.info("Próbuję zapisaną próbkę…")
            if ads is None:
                ads = load_sample()
                if ads:
                    st.info("Użyto zapisanej przykładowej odpowiedzi API (demo offline).")
            if not ads:
                st.warning("Brak danych. Podaj token lub umieść plik samples/meta_ads_sample.json.")
            else:
                st.success(f"Pobrano {len(ads.get('data', []))} reklam — porównuję z kampaniami…")
                rows = compare_ads(ads, stored, tfidf)
                for row in rows:
                    b = row["best"]
                    verd = ("🚨 POWIĄZANA Z KAMPANIĄ" if b and b["score"] >= join_thr
                            else "nowy wzorzec")
                    with st.expander(f"[{row['page']}] {row['text'][:90]}… — {verd}"):
                        st.write(f"**Strona reklamodawcy:** {row['page']} | start: {row['start']}")
                        st.write(f"**Najlepsze dopasowanie:** incydent {b['id']} "
                                 f"({b['title'][:60]}) — score {b['score']:.3f}")
                        for ev in b["evidence"][:4]:
                            st.write(f"• {ev}")
                        if row["snapshot"]:
                            st.write(f"[Zrzut reklamy w bibliotece Meta]({row['snapshot']})")

    with tab_eks:
        st.write("Artefakty zrozumiałe dla CSIRT/NASK: pakiet **STIX 2.1** (kampanie, "
                 "incydenty, wskaźniki domen, relacje z przesłankami i poziomem ufności) "
                 "oraz **watchlista IoC**.")
        stix_f = Path(st.session_state["db"]).with_suffix(".stix.json")
        ioc_f = Path(st.session_state["db"]).with_suffix(".ioc.csv")
        c1, c2 = st.columns(2)
        with c1:
            if stix_f.is_file():
                data = stix_f.read_text(encoding="utf-8")
                st.download_button("⬇ Pobierz STIX 2.1 (.json)", data,
                                   file_name="kolekcjoner-fejkow.stix.json",
                                   mime="application/json")
                bundle = json.loads(data)
                from collections import Counter
                counts = Counter(o["type"] for o in bundle["objects"])
                st.write("Obiekty w pakiecie:", dict(counts))
            else:
                st.info("Uruchom analizę, aby wygenerować pakiet STIX.")
        with c2:
            if ioc_f.is_file():
                st.download_button("⬇ Pobierz watchlistę IoC (.csv)",
                                   ioc_f.read_text(encoding="utf-8"),
                                   file_name="ioc_watchlist.csv", mime="text/csv")
                try:
                    import pandas as pd
                    df = pd.read_csv(ioc_f)
                    st.dataframe(df, height=300)
                except Exception:
                    st.text(ioc_f.read_text(encoding="utf-8")[:2000])
            else:
                st.info("Uruchom analizę, aby wygenerować watchlistę IoC.")

else:
    st.info("Ustaw katalog danych w panelu bocznym i kliknij **▶ Uruchom analizę** "
            "(lub wczytaj ostatnie wyniki).")