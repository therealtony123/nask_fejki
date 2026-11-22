"""Sprawdź nowy materiał: URL vs zbiór + bonus: biblioteka reklam."""
import streamlit as st

from kfk import Tfidf, assign_new_incident, extract_from_url_text, pair_similarity
from kfk.similarity import negative_evidence
from kfk.skin import guide_box, head_box
from ui_common import get_store

head_box("SPRAWDŹ NOWY MATERIAŁ", "// kolekcjoner fejków / identyfikacja")
guide_box([
    "Wklej URL podejrzanej strony lub reklamy — narzędzie porówna go ze zbiorem",
    "i wskaże kampanię (przypisanie) lub nowy wzorzec działania, z przesłankami ZA/PRZECIW.",
    "Poniżej bonus: wyszukiwanie reklam w Meta Ad Library (token opcjonalny, próbka offline).",
])

graph = st.session_state.get("graph")
db = st.session_state.get("db")
join_thr = st.session_state.get("join_thr", 0.30)
if not graph:
    st.info("Brak wyników — uruchom analizę na stronie Start (panel boczny).")
    st.stop()
store = get_store(db)
stored = [x for x in store.load_incidents()
          if not x["id"].startswith(("ad_", "harvest_"))]

url = st.text_input("URL materiału", placeholder="https://przyklad-zlosliwa-domena.xyz")
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
                tfidf = Tfidf()
                tfidf.fit([x["text"].get("body_norm", "") for x in stored])
                matches = []
                for s in stored:
                    sim = pair_similarity(nf, s, tfidf)
                    if sim["score"] > 0:
                        matches.append({"b": s["id"], "title": s["text"]["title"], **sim})
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
                    with st.expander(f"{m['b']} ({m['title'][:60]}) — score {m['score']:.3f}"):
                        for ev in m["evidence"]:
                            st.write(f"• {ev}")
        except Exception as e:
            st.error(f"Nie udało się pobrać/zbadać materiału: {e}")

st.markdown("---")
st.markdown("### 🛰️ Biblioteka reklam (bonus)")
token = st.text_input("Token Meta Ad Library (Graph API)", type="password")
terms = st.text_input("Słowa kluczowe", "zarabiaj z domu inwestycja")
if st.button("🔎 Szukaj w bibliotece reklam"):
    from kfk.adlibrary import search_ads, load_sample, compare_ads
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
            st.info("Użyto zapisanej syntetycznej próbki API (demo offline).")
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
