"""Sprawdź nowy materiał — pasuje do znanej kampanii czy to nowa?"""
from pathlib import Path

import streamlit as st

from kolekcjoner import ui
from kolekcjoner import Material, assign_new_material, extract_features, from_url

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
