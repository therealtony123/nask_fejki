"""Kampanie — grupy powiązanych materiałów, z przesłankami po ludzku."""
import html
from pathlib import Path

import streamlit as st

from kolekcjoner import ui

ui.hero(compact=True)
st.subheader("Kampanie — na jakie grupy złożyły się materiały")

features = st.session_state.features
clusters = st.session_state.clusters
links = st.session_state.links
materials = st.session_state.materials or []

if not features:
    ui.no_data_hint()
    st.stop()

ui.guide_box(
    ["<b>Krok 1:</b> przejrzyj karty kampanii z góry na dół — na każdej widać, "
     "dlaczego materiały są razem.",
     "<b>Krok 2:</b> rozwiń „Dlaczego te materiały są razem?”, żeby zobaczyć "
     "szczegóły każdego powiązania.",
     "<b>Krok 3:</b> kliknij „Podgląd materiałów” przy grupie, żeby zobaczyć jej "
     "treści i grafiki.",
     "<b>Krok 4:</b> gdy skończysz, kliknij „Zobacz te kampanie na mapie” pod kartami."])

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

material_by_id = {m.id: m for m in materials}


def render_preview(cluster):
    st.markdown(
        f'<div class="kf-preview-head">'
        f'<span class="kf-preview-cluster">{html.escape(cluster.cluster_id)}</span>'
        f'<span class="kf-preview-count">{len(cluster.members)} materiałów</span>'
        f'</div>',
        unsafe_allow_html=True)

    preview_cols = st.columns(2)
    for index, mid in enumerate(cluster.members):
        material = material_by_id.get(mid)
        with preview_cols[index % 2]:
            with st.container(border=True):
                st.markdown(
                    f'<div class="kf-preview-material">'
                    f'<span class="kf-preview-id">{html.escape(mid)}</span>'
                    f'<span class="kf-preview-source">'
                    f'{html.escape(material.source if material else "BRAK DANYCH")}'
                    f'</span></div>',
                    unsafe_allow_html=True)

                if material and material.image_path:
                    image_path = Path(material.image_path)
                    if not image_path.is_absolute():
                        image_path = ui.ROOT / image_path
                    if image_path.exists():
                        st.image(str(image_path), use_container_width=True)
                    else:
                        st.caption("Brak pliku grafiki.")
                else:
                    st.caption("Brak grafiki.")

                if material and material.text:
                    st.markdown("**Treść**")
                    st.write(material.text)
                else:
                    st.caption("Brak wyodrębnionej treści.")

                if material and material.url:
                    safe_url = html.escape(material.url, quote=True)
                    st.markdown(
                        f'<span class="kf-preview-meta-label">URL</span>'
                        f'<a class="kf-preview-url" href="{safe_url}" '
                        f'target="_blank" rel="noopener noreferrer">{safe_url}</a>',
                        unsafe_allow_html=True)

                if material:
                    metadata = []
                    if material.ip:
                        metadata.append(f"IP: `{html.escape(material.ip)}`")
                    if material.ns:
                        metadata.append(
                            "NS: " + ", ".join(f"`{html.escape(ns)}`"
                                               for ns in material.ns))
                    if material.mx:
                        metadata.append(
                            "MX: " + ", ".join(f"`{html.escape(mx)}`"
                                               for mx in material.mx))
                    if metadata:
                        st.markdown("  \n".join(metadata))

                if material and material.redirect_chain:
                    with st.expander("Przekierowania"):
                        for redirect in material.redirect_chain:
                            st.code(redirect)


if hasattr(st, "dialog"):
    @st.dialog("Podgląd materiałów w grupie", width="large")
    def preview_dialog():
        cluster_id = st.session_state.get("preview_cluster_id")
        cluster = next((c for c in clusters if c.cluster_id == cluster_id), None)
        if cluster:
            render_preview(cluster)

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
        if st.button("🔎 Podgląd materiałów",
                     key=f"preview_{c.cluster_id}",
                     use_container_width=True):
            if hasattr(st, "dialog"):
                st.session_state.preview_cluster_id = c.cluster_id
                preview_dialog()
            else:
                st.session_state.preview_cluster_id = c.cluster_id
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

if not hasattr(st, "dialog"):
    preview_cluster_id = st.session_state.get("preview_cluster_id")
    preview_cluster = next(
        (c for c in clusters if c.cluster_id == preview_cluster_id), None)
    if preview_cluster:
        st.divider()
        render_preview(preview_cluster)

st.page_link("kolekcjoner/ui_pages/mapa.py",
             label="🕸️ Zobacz te kampanie na mapie powiązań ▸", icon="🕸️")
st.caption("Kolory na mapie odpowiadają kartom powyżej — łatwo rozpoznać, "
           "co jest czym.")
