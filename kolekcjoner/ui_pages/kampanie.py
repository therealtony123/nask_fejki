"""Kampanie — grupy powiązanych materiałów, z przesłankami po ludzku."""
import streamlit as st

from kolekcjoner import ui
from kolekcjoner.report import campaign_report_md

ui.hero(compact=True)
st.subheader("Kampanie — na jakie grupy złożyły się materiały")

features = st.session_state.features
clusters = st.session_state.clusters
links = st.session_state.links

if not features:
    ui.no_data_hint()
    st.stop()

ui.guide_box(
    ["<b>Krok 1:</b> przejrzyj karty kampanii z góry na dół — na każdej widać, "
     "dlaczego materiały są razem.",
     "<b>Krok 2:</b> rozwiń „Dlaczego te materiały są razem?”, żeby zobaczyć "
     "szczegóły każdego powiązania.",
     "<b>Krok 3:</b> gdy skończysz, kliknij „Zobacz te kampanie na mapie” pod kartami."])

m = st.columns(4)
m[0].metric("MATERIAŁY", len(features))
m[1].metric("KAMPANIE", len(clusters))
m[2].metric("POWIĄZANIA", len(links))
m[3].metric("TWARDE DOWODY", sum(1 for l in links if l.strong_signals))

st.markdown(
    """Każda karta to jedna **kampania** — grupa materiałów powiązanych np.
podobnym tekstem, zbliżonymi grafikami albo tą samą infrastrukturą.
Pod kartą znajdziesz **przesłanki powiązania** wyjaśnione prostym językiem.""")
st.markdown(f'Aplikacja znalazła **{len(clusters)} kampanii** w '
            f'**{len(features)} materiałach** (przy tym progu podobieństwa).')
st.caption("Wskazówka: przesuń suwak „próg podobieństwa” w panelu po lewej, "
           "aby grupy były większe (suwak niżej) albo ostrożniejsze (suwak wyżej).")

cols = st.columns(3)
for i, c in enumerate(sorted(clusters, key=lambda x: -len(x.members))):
    col = cols[i % 3]
    size = len(c.members)
    with col:
        is_camp = size > 1
        cls = "kf-card campaign" if is_camp else "kf-card solo"
        badge_cls = "kf-badge camp" if is_camp else "kf-badge inc"
        badge = f"KAMPANIA · {size} materiały" if is_camp else "POJEDYNCZY MATERIAŁ"
        if size > 4:
            badge = f"KAMPANIA · {size} materiałów"
        chips = " ".join(f'<span class="kf-chip">{mm}</span>' for mm in c.members)
        st.markdown(
            f'<div class="{cls}">'
            f'<div class="kf-card-top"><span class="kf-id">{c.cluster_id}</span>'
            f'<span class="{badge_cls}">{badge}</span></div>'
            f'<div class="kf-members">{chips}</div></div>',
            unsafe_allow_html=True)
        # Takedown Pack — raport dowodowy kampanii (CERT-ready)
        try:
            md = campaign_report_md(c, st.session_state.materials,
                                    features, links)
            st.download_button(
                "📄 Takedown pack", data=md,
                file_name=f"{c.cluster_id}_takedown.md",
                mime="text/markdown", key=f"td_{c.cluster_id}",
                use_container_width=True)
        except Exception as e:                    # noqa: BLE001
            st.caption(f"(takedown pack niedostępny: {e})")
        if c.links:
            with st.expander(f"Dlaczego te materiały są razem? "
                             f"({len(c.links)} powiązań)"):
                for l in sorted(c.links, key=lambda x: -x.score)[:8]:
                    st.markdown(f"**{l.a} ↔ {l.b}** — podobieństwo "
                                f"**{ui.pct(l.score)}**")
                    st.markdown(ui.bar_html(l.score) +
                                f'<div class="kf-bar-cap">pewność porównania: '
                                f'{ui.confidence_label(l.confidence)} '
                                f'({ui.pct(l.confidence)} danych dostępnych)</div>',
                                unsafe_allow_html=True)
                    if l.strong_signals:
                        for s in l.strong_signals:
                            st.markdown(f"⚡ **{ui.friendly_strong(s)}**")
                    for e in sorted(l.reasons, key=lambda x: -x.score):
                        st.markdown(f"• {ui.friendly_reason(e)}")
                    st.markdown("---")

st.page_link("kolekcjoner/ui_pages/mapa.py",
             label="🕸️ Zobacz te kampanie na mapie powiązań ▸", icon="🕸️")
st.caption("Kolory na mapie odpowiadają kartom powyżej — łatwo rozpoznać, "
           "co jest czym.")
