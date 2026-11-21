#!/usr/bin/env python3
"""KOLEKCJONER FEJKÓW — demonstrator (HackNation 2026, wyzwanie NASK).

Uruchomienie:  streamlit run app.py
Pełny proces: materiały -> ekstrakcja cech -> podobieństwa -> klastry/kampanie
-> graf zależności z przesłankami -> analiza nowego materiału.
"""
import json
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from kolekcjoner import (  # noqa: E402
    Cluster, Features, Link, Material, SimilarityConfig,
    assign_new_material, build_clusters, extract_features,
    from_jsonl, from_records, from_text, from_url,
)

ROOT = Path(__file__).resolve().parent

st.set_page_config(page_title="Kolekcjoner fejków", page_icon="🕵️", layout="wide")
st.title("🕵️ Kolekcjoner fejków — korelacja podejrzanych reklam w kampanie")


# ------------------------------------------------------------- stan

def default_state():
    st.session_state.materials = None      # list[Material]
    st.session_state.features = None       # list[Features]
    st.session_state.cfg = SimilarityConfig()


if "materials" not in st.session_state:
    default_state()


def load_materials(records):
    mats = from_records(records)
    st.session_state.materials = mats
    st.session_state.features = [extract_features(m) for m in mats]


def ensure_dataset():
    if st.session_state.materials is None and (ROOT / "data" / "demo_materials.jsonl").exists():
        mats = from_jsonl(ROOT / "data" / "demo_materials.jsonl")
        st.session_state.materials = mats
        st.session_state.features = [extract_features(m) for m in mats]


def add_material(m: Material):
    if st.session_state.materials is None:
        st.session_state.materials = []
        st.session_state.features = []
    st.session_state.materials.append(m)
    st.session_state.features.append(extract_features(m))


# ------------------------------------------------------------- sidebar

with st.sidebar:
    st.header("⚙️ Parametry analizy")
    ensure_dataset()
    cfg = SimilarityConfig(
        threshold=st.slider("Próg podobieństwa (krawędź grafu)", 0.1, 0.9, 0.45, 0.05),
        weights={
            "text": st.slider("Waga: treść/narracja", 0.0, 1.0, 0.35, 0.05),
            "image": st.slider("Waga: materiał wizualny", 0.0, 1.0, 0.20, 0.05),
            "domain": st.slider("Waga: domena", 0.0, 1.0, 0.15, 0.05),
            "infra": st.slider("Waga: infrastruktura", 0.0, 1.0, 0.10, 0.05),
            "persona": st.slider("Waga: wizerunki osób", 0.0, 1.0, 0.20, 0.05),
        },
    )

    st.divider()
    st.subheader("📥 Materiały")
    if st.session_state.materials:
        st.caption(f"{len(st.session_state.materials)} materiałów w zbiorze")

    st.markdown("**Dodaj pojedynczy materiał:**")
    in_url = st.text_input("Adres URL (reklama / strona)", key="new_url")
    in_text = st.text_area("Lub treść reklamy (tekst)", key="new_text")
    up_img = st.file_uploader("Lub zrzut ekranu / kreatyw", type=["png", "jpg", "jpeg"],
                              key="new_img")
    if st.button("➕ Dodaj materiał", use_container_width=True):
        mid = f"M{len(st.session_state.materials or []) + 1:03d}"
        if in_url:
            with st.spinner("Pobieram treść + metadane (RDAP/DNS)..."):
                add_material(from_url(in_url, mid, fetch=True))
        elif in_text or up_img:
            from kolekcjoner.ingest import from_screenshot
            ip = None
            if up_img:
                ip = str(ROOT / "data" / "ads" / f"upload_{mid}.png")
                ip.parent.mkdir(parents=True, exist_ok=True)
                ip.write_bytes(up_img.getvalue())
            add_material(from_screenshot(ip, mid, text=in_text or None))
        else:
            st.warning("Podaj URL, tekst lub plik obrazu.")
        st.rerun()

    st.divider()
    up_json = st.file_uploader("Import zbioru (JSON Lines / CSV)", type=["jsonl", "json"],
                               key="bulk")
    if up_json and st.button("wczytaj zbiór z pliku"):
        try:
            records = [json.loads(l) for l in up_json.getvalue().decode().splitlines() if l.strip()]
            load_materials(records)
            st.rerun()
        except Exception as e:
            st.error(f"Błąd importu: {e}")
    if st.button("🔄 Reset do zbioru demo", use_container_width=True):
        default_state()
        st.rerun()

# ------------------------------------------------------------- obliczenia

if not st.session_state.materials:
    st.info("Brak materiałów — dodaj materiał w panelu bocznym lub uruchom generator "
            "`python3 scripts/make_demo.py` i wczytaj zbiór demo.")
    st.stop()

features = st.session_state.features
with st.spinner("Buduję podobieństwa i klastry..."):
    clusters, links = build_clusters(features, cfg)

tabs = st.tabs(["🗺️ Kampanie", "🕸️ Graf zależności", "🧬 Cechy materiałów",
                "🔍 Nowy materiał", "📘 Metodyka"])

# ------------------------------------------------------------- kampanie

with tabs[0]:
    st.subheader(f"Wykryte kampanie: {len(clusters)} (materiałów: {len(features)}, powiązań: {len(links)})")
    c_cols = st.columns(3)
    for i, c in enumerate(sorted(clusters, key=lambda x: -len(x.members))):
        col = c_cols[i % 3]
        size = len(c.members)
        with col:
            kind = "🚩 kampania" if size > 1 else "⚫ pojedynczy incydent"
            st.markdown(f"**{c.cluster_id}** — {kind}, {size} mat.")
            st.markdown("`" + "  ".join(c.members) + "`")
            if c.links:
                with st.expander(f"Przesłanki powiązań ({len(c.links)})"):
                    for l in sorted(c.links, key=lambda x: -x.score)[:8]:
                        strong = " ｜ ".join(l.strong_signals) or ""
                        st.markdown(
                            f"**{l.a} ↔ {l.b}** — wynik `{l.score}` "
                            f"(ufność `{l.confidence}`)"
                            + (f" ⚡ *{strong}*" if strong else ""))
                        for e in l.reasons:
                            st.markdown(f"&nbsp;&nbsp;&nbsp;• [{e.kind}] {e.description}: "
                                        f"**{e.score}** (waga {e.weight_in_sum})")
    st.download_button(
        "⬇️ Pobierz wynik analizy (JSON)",
        data=json.dumps({
            "clusters": [{"id": c.cluster_id, "members": c.members} for c in clusters],
            "links": [{"a": l.a, "b": l.b, "score": l.score,
                       "confidence": l.confidence,
                       "strong": l.strong_signals,
                       "reasons": [e.description for e in l.reasons]} for l in links],
        }, ensure_ascii=False, indent=2),
        file_name="kolekcjoner_wynik.json", mime="application/json")

# ------------------------------------------------------------- graf

with tabs[1]:
    st.subheader("Graf zależności (krawędzie = wykryte powiązania)")
    edges = []
    for l in links:
        color = "red" if l.strong_signals else "steelblue"
        label = f"{l.score:.2f}"
        edges.append(f'  "{l.a}" -> "{l.b}" [label="{label}", color="{color}", '
                     f'fontcolor="{color}"];')
    dot = ("digraph kampanie {\n  rankdir=LR;\n  node [shape=box, style=rounded, "
           "fontsize=11];\n  edge [fontsize=9];\n" + "\n".join(edges) + "\n}\n")
    st.graphviz_chart(dot)
    st.caption("Czerwone krawędzie = twarde sygnały (ta sama domena rejestrowa, "
               "near-duplikat obrazu, duplikat tekstu). Granatowe = podobieństwo ważone.")

# ------------------------------------------------------------- cechy

with tabs[2]:
    st.subheader("Zestaw wyekstrahowanych cech")
    rows = []
    for m, f in zip(st.session_state.materials, features):
        rows.append(dict(
            id=f.id, źródło=m.source, URL=m.url,
            domena=f.registrable_domain or "—",
            słowa_kluczowe=", ".join(sorted(f.keywords)) or "—",
            osoby=", ".join(sorted(f.personas)) or "—",
            kwoty=", ".join(sorted(f.money_patterns))[:40] or "—",
            dHash=hex(f.dhash) if f.dhash is not None else "brak obrazu",
            przekierowania=", ".join(sorted(f.redirect_domains)) or "—",
            NS=", ".join(sorted(f.ns_set))[:40] or "—",
            IP=f.ip or "—",
            modaliwości=",".join(sorted(f.available_modalities)),
        ))
    st.dataframe(rows, use_container_width=True)
    st.caption("Braki danych (martwa domena, brak zrzutu) nie dyskwalifikują materiału — "
               "porównanie liczy się po dostępnych modaliowościach.")

# ------------------------------------------------------------- nowy materiał

with tabs[3]:
    st.subheader("Czy nowy materiał należy do znanej kampanii?")
    n_url = st.text_input("URL nowego materiału", key="cmp_url")
    n_text = st.text_area("Treść nowego materiału", key="cmp_text")
    n_img = st.file_uploader("Zrzut nowego materiału", type=["png", "jpg", "jpeg"],
                             key="cmp_img")
    if st.button("🔍 Przypisz materiał", use_container_width=True):
        if not (n_url or n_text or n_img):
            st.warning("Podaj URL, treść lub zrzut.")
        else:
            tmp = None
            if n_img:
                tmp = ROOT / "data" / "ads" / "cmp_tmp.png"
                tmp.write_bytes(n_img.getvalue())
            mat = Material(id="NOWY", source="check", url=n_url or None,
                           text=n_text or None, image_path=str(tmp) if tmp else None)
            if n_url:
                with st.spinner("Pobieram treść i metadane..."):
                    mat = from_url(n_url, "NOWY", fetch=True)
                mat.text = mat.text or n_text or None
            nf = extract_features(mat)
            best_cid, best, top = assign_new_material(features, clusters, nf, cfg)
            if best_cid:
                st.success(f"✅ Przypisano do kampanii **{best_cid}** "
                          f"(najbliższy materiał: {best.b}, wynik {best.score}, "
                          f"ufność {best.confidence})")
                if best.strong_signals:
                    st.markdown("⚡ Twarde sygnały: " + " ｜ ".join(best.strong_signals))
                st.markdown("**Przesłanki:**")
                for e in sorted(best.reasons, key=lambda x: -x.score):
                    st.markdown(f"• [{e.kind}] {e.description}: **{e.score}** "
                                f"(waga {e.weight_in_sum})")
            else:
                st.error("🆕 Brak powiązań powyżej progu — materiał reprezentuje "
                         "prawdopodobnie NOWĄ kampanię.")
            st.markdown("---")
            st.markdown("**Top podobne materiały (niezależnie od progu):**")
            for l in top:
                st.markdown(f"- `{l.b}` — wynik {l.score} (ufność {l.confidence})"
                            + (" ⚡ " + " ｜ ".join(l.strong_signals) if l.strong_signals else ""))

# ------------------------------------------------------------- metodyka

with tabs[4]:
    st.subheader("Metodyka (pełny opis w README.md)")
    st.markdown(
        """
1. **Ingest** — materiał może być URL-em, tekstem, zrzutem ekranu, rekordem JSON.
   Dla URL-i: pobranie treści + łańcuch przekierowań (HTTP), DNS (IP),
   **RDAP** (publiczne metadane rejestru: NS, rejestrator, data rejestracji).
   Strona martwa / brak sieci ⇒ materiał niekompletny, ale analizowalny.
2. **Cechy** — tekst: n-gramy słowne (3), leksykon narracji scam, baza referencyjna
   wizerunków osób, wzorce kwot; obraz: **dHash 64-bit**; infrastruktura: domena
   rejestrowa, tokeny subdomen, TLD, domeny przekierowań, NS, MX, IP.
3. **Podobieństwo** — ważona kompozycja modaliwości (tekst/obraz/domena/infra/osoby);
   wagi renormalizowane po dostępnych danych, `confidence` = dostępna część wagi.
4. **Twarde sygnały** — identyczna domena rejestrowa, near-duplikat obrazu
   (Hamming ≤ 6), duplikat tekstu (Jaccard ≥ 0.8) — wiążą niezależnie od progu.
5. **Grupowanie** — graf krawędzi powyżej progu + **union-find** ⇒ komponenty
   spójności = kampanie. Każda krawędź nosi listę przesłanek (dla audytora).
6. **Nowy materiał** — porównanie ze wszystkimi przypadkami; przypisanie do klastru,
   gdy najlepsza krawędź przekroczy próg / da twardy sygnał; inaczej ⇒ nowa kampania.
        """
    )
