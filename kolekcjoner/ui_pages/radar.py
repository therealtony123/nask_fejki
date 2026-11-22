"""Autopilot — radar nowych odsłon kampanii (strona demonstratora).

Okresowo i automatycznie skanuje publiczne źródła reklam i oszustw,
porównuje znalezione materiały z wykrytymi kampaniami i alarmuje
o ich nowych odsłonach — bez kluczy API (token Meta Ad Library
opcjonalny).
"""
import time

import streamlit as st

from kolekcjoner import ui
from kolekcjoner.radar import Radar, DEFAULT_PROFILES

ui.hero(compact=True)
st.subheader("📡 Autopilot — radar nowych odsłon kampanii")

st.markdown(
    """Ten radar **sam, w tle i cyklicznie** przeszukuje publicznie dostępne
źródła podejrzanych reklam (DuckDuckGo, feed OpenPhish, bazę fałszywych
banków AA419, a opcjonalnie oficjalną Bibliotekę Reklam Meta), pobiera
znalezione strony standardowym pipeline i porównuje je z Twoimi
kampaniami. Gdy pojawi się **nowa odsłona znanej kampanii** — dostajesz
alarm z dowodami. Frazy wyszukiwania buduje też **automatycznie z cech
Twoich kampanii**, więc radar szuka ich nowych wariantów.""")


# ----------------------------------------------------------------- silnik

@st.cache_resource
def get_radar() -> Radar:
    return Radar()


radar = get_radar()
radar.update_baseline(st.session_state.features,
                      st.session_state.clusters,
                      st.session_state.cfg,
                      st.session_state.materials)

# ----------------------------------------------------------------- panel sterowania

with st.container(border=True):
    left, mid, right = st.columns([2, 2, 2])
    with left:
        interval = st.slider("⏱️ Odstęp między skanami (sek)", 10, 300,
                              value=radar.interval, step=10, key="radar_interval")
    with mid:
        max_scan = st.slider("📦 Kandydaci na skan", 1, 12,
                             value=radar.max_per_scan, key="radar_max")
    with right:
        st.caption("Źródła publiczne (bez kluczy API):")
        src_ddg = st.checkbox("duckduckgo",
                              value=radar.sources["duckduckgo"], key="cb_ddg")
        src_phish = st.checkbox("openphish",
                                value=radar.sources["openphish"], key="cb_phish")
        src_aa = st.checkbox("aa419", value=radar.sources["aa419"], key="cb_aa")
        src_meta = st.checkbox("Meta Ad Library (token)",
                               value=radar.sources["meta"], key="cb_meta")

    # zapisz konfigurację do silnika (od razu dla wątku w tle)
    radar.interval = interval
    radar.max_per_scan = max_scan
    radar.sources = {"duckduckgo": src_ddg, "openphish": src_phish,
                     "aa419": src_aa, "meta": src_meta}

    with st.expander("🔎 Frazy wyszukiwania (plus automatyczne z kampanii)"):
        prof = st.text_area(
            "Po jednej frazie w linii:",
            value="\n".join(radar.profiles),
            height=120, key="radar_profiles")
        if prof.strip() and prof.splitlines() != radar.profiles:
            radar.profiles = [l.strip() for l in prof.splitlines() if l.strip()]
        auto = radar.auto_queries()
        if auto:
            st.caption("Frazy wygenerowane AUTOMATYCZNIE z profili Twoich "
                        "kampanii (słowa kluczowe + wizerunki):")
            for q in auto:
                st.markdown(f'<span class="kf-chip">🤖 {q}</span>',
                            unsafe_allow_html=True)

    token = st.text_input(
        "Token Meta Ad Library (opcjonalny, https://developers.facebook.com/)",
        type="password", value=radar.fb_token or "", key="radar_token")
    radar.fb_token = token.strip() or None
    if radar.fb_token:
        st.caption("✅ token przyjęty — radar odpyta też oficjalną "
                   "Bibliotekę Reklam Meta (DSA: wszystkie reklamy w PL/EU).")

    colA, colB, colC = st.columns(3)
    started = colA.button("🟢 START", type="primary", use_container_width=True)
    stopped = colB.button("🔴 STOP", use_container_width=True)
    once = colC.button("⚡ Skanuj teraz (raz)", use_container_width=True)
    if started:
        radar.start()
    if stopped:
        radar.stop()
    if once:
        with st.spinner("Skanuję publiczne źródła..."):
            radar.scan_once()

# ----------------------------------------------------------------- status

s = radar.stats()
stat_cols = st.columns(5)
stat_cols[0].metric("SKANY", s["scans"])
stat_cols[1].metric("KANDYDACI", s["candidates"])
stat_cols[2].metric("PORÓWNANI", s["processed"])
stat_cols[3].metric("ALERTY WARIANTÓW", s["variants"])
stat_cols[4].metric("NOWE WZORCE", s["new_patterns"])

if radar.running:
    st.markdown('<div class="kf-side-count">🟢 autopilot działa — strona '
                'sama się odświeża</div>', unsafe_allow_html=True)
else:
    st.caption("⚪ autopilot zatrzymany")

# ----------------------------------------------------------------- alerty

if radar.alerts:
    st.markdown("### 🚨 Alarmy — nowe odsłony znanych kampanii")
    for a in reversed(radar.alerts[-8:]):
        ts = time.strftime("%H:%M:%S", time.localtime(a["ts"]))
        strong = " · ".join(a["strong"]) if a["strong"] else "brak twardych sygnałów"
        st.error(f"**{a['cluster_id']}** — nowy wariant z {a['source']} "
                 f"({ts})\n\n`{a['url'][:80]}`\n\n"
                 f"podobieństwo **{a['score']:.0%}** · ⚡ {strong}")

# ----------------------------------------------------------------- znaleziska

st.markdown("### 🛰 Znaleziska")
finds = list(reversed(radar.finds))
if not finds:
    st.info("Radar jeszcze nic nie znalazł. Kliknij **⚡ Skanuj teraz** "
            "albo **🟢 START**, aby wystartować cykliczne skanowanie.")
else:
    added = 0
    for i, f in enumerate(finds[:20]):
        verdict = (f"🚨 wariant kampanii **{f.cluster_id}** "
                   f"(podobieństwo {f.score:.0%})"
                   if f.status == "variant" else
                   f"🆕 nowy wzorzec (najbliżej: {f.score:.0%})")
        icon = "🚨" if f.status == "variant" else "🆕"
        box = st.container(border=True)
        with box:
            head, btn = st.columns([4, 1])
            head.markdown(f"**{icon} `{f.url[:90]}`**")
            head.markdown(
                f"źródło: **{f.source}** · fraza: „{f.query[:50]}” · "
                f"domena: `{f.domain or '—'}` · wynik: {verdict}")
            key = f"add_{f.ts}_{i}"
            if btn.button("➕ Dodaj", key=key, use_container_width=True):
                f.material.id = (f"M{len(st.session_state.materials) + 1:03d}")
                ui.add_material(f.material)
                added += 1
                st.toast(f"Dodano {f.material.id} do zbioru")
                st.rerun()
            if f.strong_signals or f.reasons:
                with st.expander("Dowody powiązania"):
                    for sig in f.strong_signals:
                        st.markdown(f"⚡ **{ui.friendly_strong(sig)}**")
                    for e in sorted(f.reasons, key=lambda x: -x.score):
                        st.markdown(f"• {ui.friendly_reason(e)}")
                    st.caption(f"pewność porównania: "
                               f"{ui.confidence_label(f.confidence)}")

# ----------------------------------------------------------------- wykres aktywności

# ----------------------------------------------------------------- wykres aktywności

def _activity_svg(scans) -> str:
    """Mini-wykres aktywności radara jako czysty SVG (bez pandas/altair —
    odporny na dowolne środowisko uruchomieniowe)."""
    if not scans:
        return ""
    max_v = max(max(r.candidates, r.processed, 1) for r in scans)
    n = len(scans)
    bw, gap, h = max(8, min(28, 900 // max(n, 1))), 4, 110
    w = n * (bw + gap)
    bars = []
    for i, r in enumerate(scans):
        x = i * (bw + gap)
        for vi, (val, color) in enumerate([
                (r.variants, "#ff5d5d"), (r.processed, "#7ee0ff"),
                (r.candidates, "#00ff9c")]):
            bh = round(h * val / max_v)
            if bh < 2 and val:
                bh = 2
            y = h - bh
            bars.append(f'<rect x="{x + vi * (bw / 3):.0f}" y="{y:.0f}" '
                        f'width="{bw / 3 - 1:.0f}" height="{bh:.0f}" '
                        f'fill="{color}" rx="1"/>')
        label = time.strftime("%H:%M", time.localtime(r.ts))
        if n <= 12 or i % max(1, n // 10) == 0:
            bars.append(f'<text x="{x + bw / 2:.0f}" y="{h + 14}" fill="#8b98a5" '
                        f'font-size="9" text-anchor="middle" '
                        f'font-family="monospace">{label}</text>')
    legend = "".join(
        f'<circle cx="{30 + i * 110}" cy="16" r="5" fill="{c}"/>' +
        f'<text x="{40 + i * 110}" y="20" fill="#8b98a5" font-size="11" '
        f'font-family="monospace">{t}</text>'
        for i, (t, c) in enumerate([("kandydaci", "#00ff9c"),
                                    ("porównania", "#7ee0ff"),
                                    ("warianty", "#ff5d5d")]))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" '
            f'viewBox="0 0 {max(w, 360)} {h + 30}" '
            f'style="max-height:150px;background:transparent">'
            f'{legend}'
            + "".join(bars) + f'</svg>')


if radar.scans:
    st.markdown("### 📈 Aktywność radara przez czas")
    st.markdown(_activity_svg(radar.scans), unsafe_allow_html=True)
    with st.expander("🧾 Dziennik robota radara"):
        for line in list(reversed(radar.log))[:40]:
            st.caption(line)

# ----------------------------------------------------------------- auto-odświeżanie

if radar.running:
    time.sleep(4)
    st.rerun()
