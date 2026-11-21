"""Sprawdź nowy materiał — pasuje do znanej kampanii czy to nowa?"""
from pathlib import Path

import streamlit as st

from kolekcjoner import ui
from kolekcjoner import Material, assign_new_material, extract_features, from_url
from kolekcjoner import szukacz

ROOT = Path(__file__).resolve().parents[2]

ui.hero(compact=True)
st.subheader("Sprawdź nowy materiał — pasuje do którejś kampanii?")

features = st.session_state.features
clusters = st.session_state.clusters
cfg = st.session_state.cfg

if not features:
    ui.no_data_hint()
    st.stop()

ui.guide_box(
    ["<b>Krok 1:</b> wypełnij DOWOLNE z pól poniżej (adres, tekst, obraz — wystarczy jedno).",
     "<b>Krok 2:</b> kliknij <b>🔍 Analizuj</b> i odczekaj kilka sekund.",
     "<b>Krok 3:</b> przeczytaj werdykt — powiemy po ludzku, dlaczego (nie) pasuje.",
     "<b>Krok 4 (opcjonalnie):</b> kliknij „Dodaj ten materiał do zbioru”, żeby "
     "zapisał się na mapie."])

st.markdown(
    """To najciekawszy moment demonstracji: wrzucasz materiał, którego aplikacja
jeszcze **nigdy nie widziała** — adres strony, tekst, zrzut ekranu, a nawet log
komunikacji (np. e-mail od oszusta) albo zwykłą wskazówkę. Aplikacja odpowie,
czy materiał wygląda jak część którejś **znanej kampanii**, czy reprezentuje
**nową kampanię**.""")

in_url = st.text_input(
    "1️⃣ Adres strony / reklamy (URL)", key="cmp_url",
    help="Pobieramy treść strony i publiczne metadane domeny (DNS, RDAP).")
in_text = st.text_area(
    "2️⃣ Treść materiału (tekst reklamy)", key="cmp_text",
    help="Wklej tekst reklamy lub treść strony.")
in_log = st.text_area(
    "3️⃣ Log komunikacji (opcjonalnie)", key="cmp_log",
    help="Wklej np. treść podejrzanego e-maila lub rozmowy z oszustem — "
         "porównamy styl wypowiedzi i użyte słowa.")
in_hint = st.text_input(
    "4️⃣ Wskazówka / nazwa produktu (opcjonalnie)", key="cmp_hint",
    help="Np. nazwa produktu lub fraza z reklamy — pomoże w wyszukaniu")
up_img = st.file_uploader(
    "5️⃣ Zrzut ekranu / obraz (opcjonalnie)",
    type=["png", "jpg", "jpeg"], key="cmp_img",
    help="Na obrazie szukamy m.in. podobieństwa graficznego z innymi materiałami.")

if st.button("🔍 Analizuj", type="primary"):
    if not (in_url or in_text or in_log or in_hint or up_img):
        st.warning("Wypełnij przynajmniej jedno pole — adres, tekst, wskazówkę "
                   "lub wgraj obraz.")
        st.stop()

    all_text = "\n\n".join(t for t in (in_text, in_log, in_hint) if t).strip() or None
    img_path = None
    if up_img is not None:
        img_path = str(ROOT / "data" / "ads" / "cmp_tmp.png")
        Path(img_path).parent.mkdir(parents=True, exist_ok=True)
        Path(img_path).write_bytes(up_img.getvalue())

    mat = Material(id="NOWY", source="check", url=in_url or None,
                   text=all_text, image_path=img_path)
    if in_url:
        with st.spinner("Pobieram treść strony i metadane domeny (DNS/RDAP)..."):
            try:
                mat = from_url(in_url, "NOWY", fetch=True)
                mat.text = mat.text or all_text
                if img_path:
                    mat.image_path = img_path
            except Exception:
                st.info("⚠️ Nie udało się pobrać strony (być może już nie działa). "
                        "Porównuję materiał na podstawie dostępnych danych — "
                        "to celowa cecha narzędzia: brakujące dane "
                        "nie dyskwalifikują materiału.")

    nf = extract_features(mat)
    best_cid, best, top = assign_new_material(features, clusters, nf, cfg)

    # --- werdykt ---
    if best_cid:
        why = "".join(f'<div>• {ui.friendly_reason(e)}</div>'
                      for e in sorted(best.reasons, key=lambda x: -x.score))
        strong = "".join(f'<div>⚡ {ui.friendly_strong(s)}</div>'
                         for s in best.strong_signals)
        st.markdown(
            f'<div class="kf-verdict"><h4>✅ Ten materiał pasuje do kampanii '
            f'{best_cid}</h4>'
            f'<div class="why">Podobieństwo do najbliższego materiału '
            f'({best.b}): <b>{ui.pct(best.score)}</b>'
            + ui.bar_html(best.score)
            + f'<div class="kf-bar-cap">pewność porównania: '
              f'{ui.confidence_label(best.confidence)} '
              f'({ui.pct(best.confidence)} danych dostępnych)</div></div>'
            + (f'<div class="why" style="margin-top:8px">{strong}</div>' if strong else "")
            + f'<div class="why" style="margin-top:8px">{why}</div></div>',
            unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="kf-verdict new"><h4>🆕 Brak powiązań — to prawdopodobnie '
            'NOWA kampania</h4>'
            '<div class="why">Żadna kampania z aktualnego zbioru nie przekroczyła '
            'progu podobieństwa ani nie dała twardego dowodu. To dobrze: '
            'narzędzie nie łączy materiałów „na siłę”.</div></div>',
            unsafe_allow_html=True)

    st.markdown("**Najbardziej podobne materiały** (niezależnie od progu):")
    for l in top[:6]:
        st.markdown(
            f"`{l.b}` — podobieństwo **{ui.pct(l.score)}**, "
            f"pewność porównania: {ui.confidence_label(l.confidence)} "
            + (" ⚡ " + " | ".join(ui.friendly_strong(s) for s in l.strong_signals)
               if l.strong_signals else ""), unsafe_allow_html=False)
        st.markdown(ui.bar_html(l.score, ui.confidence_class(l.confidence)),
                    unsafe_allow_html=True)

    st.session_state["_last_mat"] = mat

if st.session_state.get("_last_mat") is not None:
    if st.button("➕ Dodaj ten materiał do zbioru"):
        mat = st.session_state.pop("_last_mat")
        mat.id = f"M{len(st.session_state.materials) + 1:03d}"
        ui.add_material(mat)
        st.session_state.pop("_last_mat", None)
        st.toast("Dodano! Zobacz go w Kampaniach i na Mapie.")
        st.rerun()

# ============================================================= wiele materiałów

st.divider()
st.markdown("#### Masz wiele materiałów naraz? Wrzuć wszystko na raz")
st.caption("Każda **linia** to jeden materiał: adres URL, tekst reklamy, log "
           "komunikacji albo zwykła wskazówka (np. nazwa produktu). Obrazy "
           "wgraj z kolei poniżej — każdy plik liczony jest jako osobny "
           "materiał. Żadnych plików JSON.")

_line_hint = ("https://podejrzana-strona.example\n"
              "„Gwarantowany zysk 5000 zł dziennie z kryptowalut!” (tekst)\n"
              "email od „inwestora”: witaj, mam dla Ciebie okazję... (log)\n"
              "kurs lewandowski 5000 zł (wskazówka)")
bulk_txt = st.text_area(
    "Lista materiałów — każdy w osobnej linii:", key="bulk_urls",
    placeholder=_line_hint)
up_imgs = st.file_uploader(
    "Lub wgraj wiele obrazów / zrzutów ekranu (każdy plik = jeden materiał):",
    type=["png", "jpg", "jpeg"], accept_multiple_files=True, key="bulk_imgs")

if st.button("🚀 Analizuj wszystkie"):
    linie = [l.strip() for l in (bulk_txt or "").splitlines() if l.strip()]
    urls = [l for l in linie if l.lower().startswith("http")]
    teksty = [l for l in linie if not l.lower().startswith("http")]
    obrazy = list(up_imgs or [])
    if not (urls or teksty or obrazy):
        st.warning("Wklej przynajmniej jeden materiał (adres, tekst, wskazówkę) "
                   "albo wgraj obrazy.")
        st.stop()

    st.success(f"Analizuję {len(urls) + len(teksty) + len(obrazy)} materiałów "
               f"({len(urls)} URL-e, {len(teksty)} tekstów, {len(obrazy)} obrazów) —"
               " pobieram i porównuję z Twoimi kampaniami...")
    wyniki = []
    calkowito = len(urls) + len(teksty) + len(obrazy)
    progres = st.progress(0.0, text="Pobieram materiały...")
    nr = 0
    for url in urls:
        nr += 1
        try:
            mat, nf = szukacz.fetch_candidate(url, f"W{nr:03d}")
            best_cid, best, top = assign_new_material(features, clusters, nf, cfg)
            wyniki.append({"co": url, "mat": mat, "nf": nf,
                           "kampania": best_cid, "best": best, "top": top})
        except Exception:
            st.caption(f"↳ pomijam (strona niedostępna): {url}")
        progres.progress(nr / (calkowito + 1), text=f"Porównano {nr}/{calkowito}")
    for tekst in teksty:
        nr += 1
        mat = Material(id=f"W{nr:03d}", source="bulk-text", text=tekst)
        nf = extract_features(mat)
        best_cid, best, top = assign_new_material(features, clusters, nf, cfg)
        wyniki.append({"co": tekst[:60] + ("…" if len(tekst) > 60 else ""),
                       "mat": mat, "nf": nf,
                       "kampania": best_cid, "best": best, "top": top})
        progres.progress(nr / (calkowito + 1), text=f"Porównano {nr}/{calkowito}")
    for img in obrazy:
        nr += 1
        try:
            ip = str(ROOT / "data" / "ads" / f"bulk_{nr}.png")
            Path(ip).parent.mkdir(parents=True, exist_ok=True)
            Path(ip).write_bytes(img.getvalue())
            from kolekcjoner.ingest import from_screenshot
            mat = from_screenshot(ip, f"W{nr:03d}", text=None)
            nf = extract_features(mat)
            best_cid, best, top = assign_new_material(features, clusters, nf, cfg)
            wyniki.append({"co": f"🖼️ {img.name}", "mat": mat, "nf": nf,
                           "kampania": best_cid, "best": best, "top": top})
        except Exception:
            st.caption(f"↳ pomijam (obraz niedostępny): {img.name}")
        progres.progress(nr / (calkowito + 1), text=f"Porównano {nr}/{calkowito}")
    progres.empty()
    st.session_state["bulk_wyniki"] = wyniki
    if not wyniki:
        st.info("Żaden materiał nie dał się pobrać. To normalne przy krótko "
                "żyjących domenach — spróbuj innych adresów lub dodaj teksty.")

if st.session_state.get("bulk_wyniki"):
    wyniki = st.session_state["bulk_wyniki"]
    trafione = [w for w in wyniki if w["kampania"]]
    nowe = [w for w in wyniki if not w["kampania"]]

    if wyniki:
        podsumowanie = ", ".join(
            f"{k}: {sum(1 for w in trafione if w['kampania'] == k)} szt."
            for k in dict.fromkeys(w["kampania"] for w in trafione))
        st.markdown(
            f"""**Podsumowanie:** {len(trafione)} z {len(wyniki)} materiałów
pasuje do Twoich kampanii{(' — ' + podsumowanie) if podsumowanie else ''};
{'wszystkie pozostałe to prawdopodobnie **nowe kampanie**' if nowe
else 'żadnych nowych kampanii'}.""")
        for w in wyniki:
            if w["kampania"]:
                b = w["best"]
                strong = "".join(f"<div>⚡ {ui.friendly_strong(s)}</div>"
                                 for s in b.strong_signals)
                powody = "".join(f"<div>• {ui.friendly_reason(e)}</div>"
                                 for e in sorted(b.reasons,
                                                 key=lambda x: -x.score)[:3])
                st.markdown(
                    f'<div class="kf-verdict"><h4>🔗 {w["co"]}</h4>'
                    f'<div class="why">Pasuje do kampanii <b>{w["kampania"]}'
                    f'</b> (najbliższy materiał: {b.b}, podobieństwo '
                    f'<b>{ui.pct(b.score)}</b>)'
                    + ui.bar_html(b.score) + strong + powody
                    + "</div></div>", unsafe_allow_html=True)
            else:
                naj = (f"Najbliżej mu `{w['top'][0].b}` "
                       f"({ui.pct(w['top'][0].score)} — poniżej progu)."
                       if w["top"] else "Brak porównywalnych danych.")
                st.markdown(
                    f'<div class="kf-verdict new"><h4>🆕 {w["co"]}</h4>'
                    f'<div class="why">Nowa kampania — nie łączymy na siłę. '
                    f'{naj}</div></div>', unsafe_allow_html=True)

    kol1, kol2 = st.columns(2)
    if kol1.button(f"➕ Dodaj wszystkie ({len(wyniki)}) do zbioru"):
        for w in st.session_state.pop("bulk_wyniki"):
            w["mat"].id = f"M{len(st.session_state.materials) + 1:03d}"
            ui.add_material(w["mat"])
        st.toast(f"Dodano {len(wyniki)} materiałów! Zobacz je w Kampaniach "
                 "i na Mapie.")
        st.rerun()
    if kol2.button("🗑️ Odrzuć wyniki listy"):
        st.session_state.pop("bulk_wyniki")
        st.rerun()
