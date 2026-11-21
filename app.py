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
                      font_color="#fafafa", directed=False)
        palette = ["#ff4b4b", "#4bb3ff", "#ffd34b", "#4bff8c", "#c44bff", "#ff9d4b",
                   "#4bffd3", "#ff4bd3", "#8cff4b", "#4b8cff"]
        colors = {}
        for i, c in enumerate(graph["clusters"]):
            for m in c["members"]:
                colors[m] = palette[i % len(palette)]
        for n in graph["nodes"]:
            net.add_node(n["id"], label=f"{n['id']}: {n['title'][:35]}",
                         color=colors.get(n["id"], "#666666"), title=n["title"])
        for e in graph["edges"]:
            ev = "<br>".join(e["evidence"][:4])
            net.add_edge(e["a"], e["b"], value=round(e["score"] * 10, 1),
                         title=f"score={e['score']:.3f}{' [TWARDE]' if e['hard'] else ''}<br>{ev}",
                         color="#ff6b6b" if e["hard"] else "#6b8cff")
        net.set_options("""{"physics": {"barnesHut": {"gravitationalConstant": -4000}}}""")
        net.write_html("/tmp/kfk_graph.html")
        st.components.v1.html(Path("/tmp/kfk_graph.html").read_text(encoding="utf-8"),
                              height=640, scrolling=True)
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

    tab_prz, tab_kamp, tab_graf, tab_inc, tab_nowy = st.tabs(
        ["Przegląd kampanii", "Kampanie", "Graf zależności", "Incydenty", "Nowy materiał"])

    with tab_prz:
        for c in graph["clusters"]:
            with st.expander(f"{c['cluster_id']} — {len(c['members'])} materiałów | "
                             f"{c['label'][:110]}", expanded=True):
                st.write(f"**Członkowie:** {', '.join(c['members'])}")
                st.write(f"**Uzasadnienie:** {c['summary']}")
                st.write(f"Krawędzi w kampanii: {c['n_edges']}, twarde: {c['hard_links']}, "
                         f"średnie podobieństwo: {c['mean_score']}")

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
                            for m in matches[:5]:
                                with st.expander(f"{m['b']} ({m['title'][:60]}) — "
                                                 f"score {m['score']:.3f}"):
                                    for ev in m["evidence"]:
                                        st.write(f"• {ev}")
                except Exception as e:
                    st.error(f"Nie udało się pobrać/zbadać materiału: {e}")

else:
    st.info("Ustaw katalog danych w panelu bocznym i kliknij **▶ Uruchom analizę** "
            "(lub wczytaj ostatnie wyniki).")
