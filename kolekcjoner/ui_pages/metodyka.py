"""Metodyka i wyniki — jak to działa + raport do pobrania."""
import json

import streamlit as st

from kolekcjoner import ui

ui.hero(compact=True)
st.subheader("Metodyka i wyniki — jak to działa pod maską")

features = st.session_state.features
clusters = st.session_state.clusters
links = st.session_state.links
materials = st.session_state.materials

if not features:
    ui.no_data_hint()
    st.stop()

ui.guide_box(
    ["<b>Krok 1:</b> przejrzyj „Metoda krok po kroku” — 6 krótkich punktów.",
     "<b>Krok 2 (dla odważnych):</b> rozwiń „Co robią suwaki” i zróbcie eksperyment "
     "z progiem w panelu po lewej.",
     "<b>Krok 3:</b> kliknij <b>⬇️ Pobierz raport</b> — wynik zabierzesz ze sobą."])

st.markdown(
    """Nie dzieje się tu żadna magia. Aplikacja porównuje **pięć rodzajów
sygnałów**: treść, obrazy, domeny, infrastrukturę i osoby występujące w
materiałach. Wszystkie wyniki można wyjaśnić — do każdego powiązania
odnotowujemy **przesłanki**, czyli konkretne powody, dla których dwa materiały
uznaliśmy za spokrewnione.""")

st.markdown("#### Jak to narzędzie odpowiada na wyzwanie")
st.markdown(
    """Narzędzie **automatycznie pozyskuje informacje** z podejrzanych reklam i
powiązanych stron (treść, obrazy, metadane domen i infrastruktury),
**identyfikuje wspólne cechy** (tekst, wizerunki, odcisk obrazu, domeny,
przekierowania, serwery) i **wykrywa zależności między incydentami**
(podobieństwo ważone + twarde dowody → kampanie). W skrócie:""")

_krok, _cechy, _zal = st.columns(3)
_krok.markdown(
    '<div class="kf-step"><span class="num">1</span>'
    '<span class="t">POZYSKUJEMY</span>'
    '<div class="d">Z adresu URL pobieramy treść i łańcuch przekierowań, '
    'z DNS i rejestru (RDAP) — serwery i datę rejestracji domeny; '
    'z obrazu — cyfrowy odcisk; z tekstu — słowa i frazy. '
    'Brakujące dane nie dyskwalifikują materiału.</div></div>',
    unsafe_allow_html=True)
_cechy.markdown(
    '<div class="kf-step"><span class="num">2</span>'
    '<span class="t">IDENTYFIKUJEMY CECHY</span>'
    '<div class="d">Każdy materiał zamieniamy na wspólny, porównywalny '
    'zestaw cech w pięciu kategoriach: treść, obraz, domena, '
    'infrastruktura i występujące osoby.</div></div>',
    unsafe_allow_html=True)
_zal.markdown(
    '<div class="kf-step"><span class="num">3</span>'
    '<span class="t">WYKRYWAMY ZALEŻNOŚCI</span>'
    '<div class="d">Porównujemy pary materiałów (podobieństwo ważone, 0–100%), '
    'przesłanki zapisujemy, a grupy trzymające się razem '
    'ogłaszamy kampaniami.</div></div>',
    unsafe_allow_html=True)

st.markdown("#### Metoda krok po kroku")
st.markdown(
    """1. **Przyjęcie materiału** — materiałem może być adres URL (pobieramy treść
   i metadane domeny z DNS i rejestru RDAP), tekst, zrzut ekranu, log komunikacji
   albo zwykła wskazówka. Martwa strona czy brak sieci **nie dyskwalifikuje**
   materiału: porównujemy po tym, co dostępne.
2. **Wydobycie cech** — z tekstów: kluczowe słowa, charakterystyczne frazy,
   styl narracji oszustw, kwoty, występujące osoby (z małej bazy referencyjnej);
   z obrazów: cyfrowy odcisk (dHash); z infrastruktury: domena, subdomeny,
   przekierowania, serwery DNS, IP.
3. **Porównanie parami** — każdą parę materiałów porównujemy w pięciu
   kategoriach i liczymy **podobieństwo ważone** (0–100%). Wagi renormalizujemy,
   gdy czegoś brakuje — dzięki temu niekompletne dane nie psują wyniku; jako
   „pewność porównania” podajemy, jakiej części danych udało się użyć.
4. **Twarde dowody** — czasem dowód jest rozstrzygający bez liczenia: ta sama
   domena, obrazy różniące się pojedynczymi pikselami (odległość Hamminga ≤ 6),
   tekst będący niemal kopią (zgodność ≥ 80%). Takie pary łączymy zawsze.
5. **Kampanie** — materiały to kulki, powiązania to nici; grupy, które się
   trzymają razem, nazywamy **kampaniami**. Każda nić ma zapisane przesłanki —
   dlatego wynik da się audytować.
6. **Nowy materiał** — świeży materiał porównujemy ze całym zbiorem; trafia do
   kampanii, gdy przekroczy próg lub da twardy dowód. W przeciwnym razie
   oznaczamy go jako **nową kampanię** (celowo nie łączymy „na siłę”).""")

with st.expander("🎛️ Co robią suwaki w panelu po lewej? (dla odważnych)"):
    st.markdown(
        """- **Próg podobieństwa** — jak bardzo podobne muszą być dwa materiały,
  żebyśmy je połączyli. Niżej = większe (ale bardziej spontaniczne) grupy;
  wyżej = mniejsze, ale pewniejsze.
- **Waga: treść/narracja** — jak mocno liczy się podobny dobór słów.
- **Waga: obraz** — czy podobne grafiki mają łączyć materiały.
- **Waga: domena** — czy adres strony jest ważnym sygnałem.
- **Waga: infrastruktura** — czy ten sam serwer/dostawca ma znaczenie.
- **Waga: osoby** — czy te same osoby (np. celebryci) wiążą materiały.

Twarde dowody działają **niezależnie od suwaków** — to zabezpieczenie,
że oczywiste duplikaty nie rozejdą się po szufladach.""")

with st.expander("🔬 Dane dla dociekliwych — pełna tabela wyekstrahowanych cech"):
    rows = []
    for m, f in zip(materials, features):
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
    try:
        st.dataframe(rows, width="stretch")
    except Exception:
        st.markdown(ui.features_table_html(rows), unsafe_allow_html=True)
    st.caption("Braki danych (martwa domena, brak zrzutu) nie dyskwalifikują "
               "materiału — porównanie liczy się po dostępnych kategoriach.")

st.divider()
st.markdown("#### Raport do pobrania")
st.markdown("Pobierz wynik analizy: kampanie, powiązania i przesłanki w jednym "
            "pliku JSON. Pasuje jako materiał dowodowy do prezentacji lub "
            "dalszej analizy.")
st.download_button(
    "⬇️ Pobierz raport z wynikami (JSON)",
    data=json.dumps({
        "kampanie": [{"id": c.cluster_id, "materiały": c.members} for c in clusters],
        "powiązania": [{
            "a": l.a, "b": l.b, "podobieństwo": l.score,
            "pewność_porównania": l.confidence,
            "twarde_dowody": l.strong_signals,
            "przesłanki": [
                {"kategoria": e.kind, "opis": e.description,
                 "zgodność": e.score, "udział_w_wyniku": e.weight_in_sum}
                for e in l.reasons],
        } for l in links],
    }, ensure_ascii=False, indent=2),
    file_name="kolekcjoner_raport.json", mime="application/json",
    use_container_width=True)

st.caption("Pełny opis metodyki: README.md w repozytorium. Demonstator działa "
           "offline, bez kluczy API i usług zewnętrznych (poza publicznymi "
           "DNS/RDAP używanymi przy pobieraniu materiałów z URL).")
