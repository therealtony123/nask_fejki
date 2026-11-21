"""Szukaj powiązanych — aktywne wyszukiwanie materiałów podejrzanych
w publicznie dostępnych źródłach i porównanie ich ze znanymi kampaniami."""
import streamlit as st

from kolekcjoner import ui
from kolekcjoner import assign_new_material
from kolekcjoner import szukacz

ui.hero(compact=True)
st.subheader("Szukaj powiązanych materiałów w internecie")

features = st.session_state.features
clusters = st.session_state.clusters
cfg = st.session_state.cfg
materials = st.session_state.materials

if not features:
    ui.no_data_hint()
    st.stop()

ui.guide_box(
    ["<b>Krok 1:</b> wybierz punkt startowy — materiał z analizy (użyjemy jego "
     "słów kluczowych i osób) albo własne frazy.",
     "<b>Krok 2:</b> kliknij <b>🛰️ Szukaj w internecie</b> i poczekaj chwilę "
     "(pobieramy i porównujemy strony — poszczególne niedostępne po prostu pomijamy).",
     "<b>Krok 3:</b> przejrzyj znalezione materiały z werdyktem: pasuje do "
     "kampanii (z procentami i przesłankami) czy to coś nowego.",
     "<b>Krok 4:</b> dodaj wybrane pozycje do zbioru jednym kliknięciem."])

st.markdown(
    """To funkcja „aktywnego polowania”: aplikacja **sama wychodzi do publicznie
dostępnych źródeł**, szuka stron o podobnej tematyce i porównuje je z Twoimi
kampaniami — żeby wykryć kolejne odsłony tej samej akcji oszustów,
zanim ktoś je zgłosi. Źródła są publiczne i **nie wymagają żadnych kluczy
API**.""")

# ------------------------------------------------- punkt startowy
tryb = st.radio(
    "Punkt startowy:",
    ["Materiał z mojej analizy (użyjemy jego słów i osób)",
     "Własne frazy wyszukiwania"],
    horizontal=True)

query_key = "szukaj_query"
if tryb.startswith("Materiał"):
    ids = [f.id for f in features]
    mid = st.selectbox("Wybierz materiał:", ids,
                       help="Wyszukamy w internecie strony o podobnym "
                            "doborze słów, kwotach i występujących osobach.")
    f = next(x for x in features if x.id == mid)
    q = szukacz.query_for_features(f)
    q = st.text_input("Frazy wyszukiwania (możesz doprecyzować):", value=q,
                      key=query_key)
else:
    q = st.text_input("Frazy wyszukiwania:", key=query_key + "2",
                      help="Np. „gwarantowany zysk kryptowaluty Elon Musk”.")

limit = 12  # bierzemy wszystko, co zwróci wyszukiwarka (bez widżetu/limitu)

if st.button("🛰️ Szukaj w internecie", type="primary"):
    if not q.strip():
        st.warning("Podaj frazy wyszukiwania.")
        st.stop()
    with st.spinner(f"Szukam w publicznych źródłach: „{q}”..."):
        try:
            urls = szukacz.web_search(q, max_results=limit)
        except Exception as e:
            st.error(f"Wyszukiwarka niedostępna ({type(e).__name__}). "
                     "Sprawdź połączenie z internetem i spróbuj ponownie.")
            st.stop()
    if not urls:
        st.info("Wyszukiwarka nie znalazła nic na te frazy. Spróbuj innych "
                "słów kluczowych (np. samych fraz z narracji reklamy).")
        st.stop()
    st.success(f"Znaleziono {len(urls)} kandydatów — pobieram i porównuję "
               "z Twoimi kampaniami...")
    znalezione = []
    for i, url in enumerate(urls[:limit], 1):
        mid = f"W{i:03d}"
        try:
            mat, nf = szukacz.fetch_candidate(url, mid)
        except Exception:
            st.caption(f"↳ pomijam (strona niedostępna): {url}")
            continue
        best_cid, best, top = assign_new_material(features, clusters, nf, cfg)
        if best_cid:
            st.markdown(
                f'<div class="kf-verdict"><h4>🔗 {url}</h4>'
                f'<div class="why">Strona znaleziona w publicznym źródle — '
                f'<b>pasuje do kampanii {best_cid}</b> '
                f'(podobieństwo <b>{ui.pct(best.score)}</b>)'
                + ui.bar_html(best.score)
                + "".join(f"<div>⚡ {ui.friendly_strong(s)}</div>"
                          for s in best.strong_signals)
                + "".join(f"<div>• {ui.friendly_reason(e)}</div>"
                          for e in sorted(best.reasons,
                                          key=lambda x: -x.score)[:3])
                + "</div></div>", unsafe_allow_html=True)
        elif top and top[0].score >= cfg.threshold * 0.5:
            st.markdown(
                f'<div class="kf-verdict new"><h4>🆕 {url}</h4>'
                f'<div class="why">Podobieństwo <b>{ui.pct(top[0].score)}</b> do '
                f'{top[0].b} — poniżej progu, więc to raczej <b>nowa '
                'kampania</b>, ale warto uwzględnić w analizie.</div></div>',
                unsafe_allow_html=True)
        else:
            st.markdown(
                f'<div class="kf-verdict new"><h4>— {url}</h4>'
                '<div class="why">Brak powiązań z Twoimi kampaniami.</div>'
                '</div>', unsafe_allow_html=True)
        znalezione.append((mat, nf, best_cid, best, top))
    st.session_state["znalezione"] = znalezione
    if not znalezione:
        st.info("Żadna ze znalezionych stron nie dała się pobrać. "
                "To normalne przy krótko żyjących domenach — spróbuj "
                "innych fraz.")

# ------------------------------------------------- dodawanie wyników
if st.session_state.get("znalezione"):
    st.divider()
    ile = len(st.session_state["znalezione"])
    if st.button(f"➕ Dodaj wszystkie znalezione ({ile}) do zbioru"):
        for mat, nf, *_ in st.session_state.pop("znalezione"):
            mat.id = f"M{len(st.session_state.materials) + 1:03d}"
            ui.add_material(mat)
        st.toast("Dodano! Zobacz je w Kampaniach i na Mapie.")
        st.rerun()
    if st.button("🗑️ Odrzuć wyniki"):
        st.session_state.pop("znalezione")
        st.rerun()
    st.caption("Dodane materiały wracają do kompletu narzędzia: biorą udział "
               "w grupowaniu, pojawiają się na mapie i w raporcie.")

st.caption("Źródła wyszukiwania są publiczne (wyszukiwarka DuckDuckGo) i nie "
           "wymagają kluczy API. Dodatkowe źródła (Meta Ad Library, OpenPhish, "
           "AA419) obsługuje moduł `kolekcjoner-fejkow`; frazy wyszukiwania "
           "można tam podać dokładnie tak samo jak powyżej.")
