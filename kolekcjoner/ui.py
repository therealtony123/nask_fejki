#!/usr/bin/env python3
"""Kolekcjoner fejków — wspólna warstwa UI (skórka, stan sesji, pomocniki, graf).

Importowane przez app.py (powłoka) i strony kolekcjoner/ui_pages/*.py.
Błędy są celowo łagodne: demonstrator ma działać nawet na niepełnych danych.
"""
import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kolekcjoner import (  # noqa: E402
    Features, Link, Material, SimilarityConfig,
    assign_new_material, build_clusters, extract_features,
    from_jsonl, from_records, from_screenshot, from_url,
)

DEMO_PATH = ROOT / "data" / "demo_materials.jsonl"

_KF_CSS = """
<style>
/* ===== KOLEKCJONER FEJKÓW // dark-ops skin — wszystko lokalnie ===== */

@keyframes kf-blink { 0%, 49% { opacity: 1; } 50%, 100% { opacity: 0; } }
@keyframes kf-pulse { 0%, 100% { opacity: 1; } 50% { opacity: .25; } }

html, body, .stApp, .stApp [class*="css"],
button, input, textarea, select, label, summary {
  font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Roboto Mono',
               'Ubuntu Mono', 'Liberation Mono', monospace !important;
}

.stApp {
  background:
    radial-gradient(1100px 520px at 88% -10%, rgba(0, 255, 156, .06), transparent 60%),
    radial-gradient(900px 460px at -8% 112%, rgba(0, 217, 255, .05), transparent 60%),
    #0a0e14 !important;
  color: #c9d1d9;
}

/* delikatne scanlines na całym ekranie */
.stApp::after {
  content: "";
  position: fixed; inset: 0; z-index: 99999; pointer-events: none;
  background: repeating-linear-gradient(0deg,
              rgba(0, 0, 0, .14) 0px, rgba(0, 0, 0, .14) 1px,
              transparent 1px, transparent 3px);
  opacity: .5;
}

::selection { background: rgba(0, 255, 156, .25); }
* { scrollbar-color: #1c2634 #0a0e14; scrollbar-width: thin; }
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: #0a0e14; }
::-webkit-scrollbar-thumb { background: #1c2634; border-radius: 6px; border: 2px solid #0a0e14; }
::-webkit-scrollbar-thumb:hover { background: #00ff9c66; }

/* ---------- header ---------- */
.kf-head {
  position: relative; overflow: hidden;
  border: 1px solid #1c2634; border-radius: 10px;
  padding: 16px 22px 14px; margin-bottom: 1.1rem;
  background: linear-gradient(180deg, rgba(0,255,156,.05), rgba(0,217,255,.02) 55%, transparent), #0c1220;
  box-shadow: inset 0 1px 0 rgba(255,255,255,.03), 0 0 34px rgba(0,255,156,.05);
}
.kf-head::before {
  content: ""; position: absolute; top: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, #00ff9c, #00d9ff 45%, transparent 80%);
  box-shadow: 0 0 12px rgba(0,255,156,.7);
}
.kf-term { color: #4d5c6e; font-size: .72rem; letter-spacing: .1em; }
.kf-dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; }
.kf-dot.r { background: #ff5f57; } .kf-dot.y { background: #febc2e; } .kf-dot.g { background: #28c840; }
.kf-h1 {
  margin: .45rem 0 .15rem; font-size: 1.95rem; font-weight: 800;
  letter-spacing: .07em; color: #e6edf3; line-height: 1.15;
}
.kf-h1 .acc { color: #00ff9c; text-shadow: 0 0 16px rgba(0,255,156,.55); }
.kf-cursor { color: #00ff9c; animation: kf-blink 1.1s step-end infinite; }
.kf-sub { color: #7d8ca1; font-size: .78rem; margin: 0; }
.kf-sub .tag {
  border: 1px solid #243042; border-radius: 4px; padding: 1px 7px;
  color: #8ad8ff; background: #0a0f18; margin-left: 6px;
}
.kf-live { color: #ff5f57; animation: kf-pulse 1.6s ease-in-out infinite; }

/* ---------- typografia sekcji ---------- */
h2, h3, .stApp h2, .stApp h3 {
  color: #e6edf3 !important;
  letter-spacing: .04em;
  border-left: 3px solid #00ff9c;
  padding-left: 10px;
  text-shadow: 0 0 10px rgba(0,255,156,.15);
}
.small-font, .stApp p, .stApp li { font-size: .9rem; }
code { background: #0a0f18 !important; border: 1px solid #1c2634; border-radius: 4px; padding: 1px 6px; }
blockquote { border-left: 3px solid #00d9ff; }

/* ---------- sidebar ---------- */
section[data-testid="stSidebar"] {
  background: #0b111c !important;
  border-right: 1px solid #16202e;
  box-shadow: -12px 0 34px rgba(0,0,0,.45);
}
section[data-testid="stSidebar"] .block-container { padding-top: .55rem; }
section[data-testid="stSidebar"] hr { border-color: #1c2634; }
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: .3rem; }

/* nagłówki sekcji w sidebarze */
.kf-side-head { margin: 0 0 .9rem; }
.kf-side-kicker { display: block; color: #4d5c6e; font-size: .58rem;
                  letter-spacing: .26em; margin-bottom: 3px; }
.kf-side-title {
  color: #00ff9c; font-size: 1.02rem; font-weight: 800; letter-spacing: .09em;
  text-shadow: 0 0 14px rgba(0, 255, 156, .4);
  border-bottom: 1px solid #1c2634; padding-bottom: 9px;
}
.kf-side-title.sm { color: #8ad8ff; font-size: .92rem;
                   text-shadow: 0 0 12px rgba(0, 217, 255, .3); }
.kf-side-count { color: #7d8ca1; font-size: .68rem; margin-top: 7px; }
.kf-side-sep { height: 1px; margin: 1.35rem 0 .6rem;
               background: linear-gradient(90deg, #1c2634, transparent); }
.kf-lbl { color: #c9d1d9; font-size: .76rem; letter-spacing: .06em;
          margin: .55rem 0 .45rem; }
.kf-lbl b { color: #00ff9c; }

/* odstępy widgetów w sidebarze */
section[data-testid="stSidebar"] [data-testid="stSlider"] { margin: .3rem 0 1.35rem; }
section[data-testid="stSidebar"] [data-testid="stSlider"] label { font-size: .72rem; }
section[data-testid="stSidebar"] [data-testid="stTextInput"],
section[data-testid="stSidebar"] [data-testid="stTextArea"] { margin: .3rem 0 1.05rem; }
section[data-testid="stSidebar"] [data-testid="stFileUploader"] { margin: .3rem 0 1.2rem; }
section[data-testid="stSidebar"] div[data-testid="stWidgetLabel"] p { font-size: .72rem; }
section[data-testid="stSidebar"] [data-testid="stButton"] { margin: .15rem 0 .45rem; }

/* ---------- metryki ---------- */
[data-testid="stMetric"] {
  background: linear-gradient(180deg, #0d1420, #0b101a) !important;
  border: 1px solid #1c2634; border-radius: 8px;
  padding: 10px 14px 12px !important;
  box-shadow: inset 0 0 26px rgba(0,255,156,.03);
}
[data-testid="stMetricLabel"] {
  color: #6b7a8f !important; text-transform: uppercase;
  letter-spacing: .14em; font-size: .6rem !important;
}
[data-testid="stMetricValue"] {
  color: #00ff9c !important; font-size: 1.55rem !important;
  text-shadow: 0 0 14px rgba(0,255,156,.4);
}
[data-testid="stMetricDelta"] { font-size: .7rem !important; }

/* ---------- karty kampanii / chipy ---------- */
.kf-card { border: 1px solid #1c2634; border-radius: 8px; padding: 10px 12px 11px;
           margin-bottom: .75rem; background: #0d1420; }
.kf-card.campaign { border-color: rgba(255, 86, 86, .45);
                    box-shadow: 0 0 18px rgba(255, 86, 86, .07) inset; }
.kf-card.solo { opacity: .85; }
.kf-card-top { display: flex; align-items: baseline; justify-content: space-between; }
.kf-id { color: #e6edf3; font-weight: 700; letter-spacing: .06em; }
.kf-badge { font-size: .62rem; letter-spacing: .12em; padding: 2px 8px; border-radius: 4px; }
.kf-badge.camp { color: #ff6b6b; border: 1px solid rgba(255,86,86,.5); background: rgba(255,86,86,.08); }
.kf-badge.inc { color: #8ad8ff; border: 1px solid #243042; background: #0a0f18; }
.kf-members { margin-top: 6px; }
.kf-chip { display: inline-block; padding: 1px 8px; margin: 3px 4px 0 0;
           border: 1px solid #243042; border-radius: 4px; background: #0a0f18;
           color: #8ad8ff; font-size: .72rem; }

/* ---------- tabela cech (fallback bez pandas) ---------- */
.kf-table-wrap { overflow-x: auto; border: 1px solid #1c2634; border-radius: 8px;
                 background: #0b101a; box-shadow: inset 0 0 30px rgba(0,0,0,.35); }
table.kf-table { border-collapse: collapse; width: 100%; font-size: .72rem; min-width: 1050px; }
.kf-table th { background: #0d1420; color: #00ff9c; text-transform: uppercase;
               letter-spacing: .1em; font-size: .58rem; font-weight: 700;
               padding: 8px 10px; border-bottom: 1px solid #1c2634;
               text-align: left; white-space: nowrap; position: sticky; top: 0; }
.kf-table td { padding: 7px 10px; border-bottom: 1px solid #141c28;
               color: #c9d1d9; white-space: nowrap; }
.kf-table tbody tr:hover td { background: rgba(0, 255, 156, .04);
                              box-shadow: inset 2px 0 0 #00ff9c; }
.kf-table tbody tr:last-child td { border-bottom: none; }

/* ---------- przyciski ---------- */
div[data-testid="stButton"] > button,
.stButton > button {
  border: 1px solid rgba(0, 255, 156, .35) !important;
  color: #00ff9c !important;
  background: rgba(0, 255, 156, .05) !important;
  border-radius: 6px !important;
  letter-spacing: .08em; text-transform: uppercase;
  font-size: .78rem !important;
  transition: all .18s ease-in-out;
}
div[data-testid="stButton"] > button:hover,
.stButton > button:hover {
  background: rgba(0, 255, 156, .14) !important;
  box-shadow: 0 0 16px rgba(0, 255, 156, .35);
  border-color: #00ff9c !important;
}
div[data-testid="stDownloadButton"] > button,
.stDownloadButton > button {
  border: 1px solid #00ff9c !important;
  color: #0a0e14 !important;
  background: #00ff9c !important;
  border-radius: 6px !important;
  letter-spacing: .08em; text-transform: uppercase;
  font-size: .78rem !important; font-weight: 700;
  box-shadow: 0 0 22px rgba(0, 255, 156, .45) !important;
}
div[data-testid="stDownloadButton"] > button:hover { box-shadow: 0 0 34px rgba(0, 255, 156, .8) !important; }

/* ---------- inputy ---------- */
div[data-baseweb="input"] > input,
div[data-baseweb="textarea"] textarea {
  background: #0c1118 !important;
  color: #e6edf3 !important;
  border: 1px solid #1c2634 !important;
  border-radius: 6px !important;
  caret-color: #00ff9c !important;
  font-size: .82rem !important;
}
div[data-baseweb="input"]:focus-within,
div[data-baseweb="textarea"]:focus-within,
div[data-baseweb="input"]:hover,
div[data-baseweb="textarea"]:hover {
  border-color: rgba(0, 255, 156, .55) !important;
  box-shadow: 0 0 12px rgba(0, 255, 156, .18) !important;
}
.stApp label, .stApp .st-ci { color: #7d8ca1 !important; font-size: .78rem !important; }
[data-testid="stFileUploaderDropzone"] {
  background: #0a0f18 !important; border: 1px dashed #1c2634 !important;
  border-radius: 8px !important; color: #6b7a8f !important;
}
[data-testid="stFileUploaderDropzone"]:hover {
  border-color: rgba(0, 255, 156, .45) !important;
  box-shadow: inset 0 0 20px rgba(0, 255, 156, .05);
}

/* ---------- taby ---------- */
div[data-testid="stTabs"] div[data-baseweb="tab-list"] { gap: 6px; }
div[data-testid="stTabs"] button[data-baseweb="tab"] {
  background: #0b101a !important; border-radius: 6px 6px 0 0 !important;
  border: 1px solid #1c2634 !important; border-bottom: 2px solid #1c2634 !important;
  color: #7d8ca1 !important; letter-spacing: .05em;
  transition: all .18s ease-in-out;
}
div[data-testid="stTabs"] button[data-baseweb="tab"]:hover {
  color: #00ff9c !important; box-shadow: 0 0 14px rgba(0,255,156,.15);
  border-color: #24405a !important;
}
div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] {
  color: #00ff9c !important; background: rgba(0, 255, 156, .06) !important;
  border-bottom: 2px solid #00ff9c !important;
  text-shadow: 0 0 10px rgba(0,255,156,.5);
}
div[data-testid="stTabs"] hr { border-color: #1c2634; }

/* ---------- expander / alerty / tabele / graf ---------- */
[data-testid="stExpander"], details[data-testid="stExpander"] {
  border: 1px solid #1c2634 !important; border-radius: 8px !important;
  background: #0c121d !important;
}
[data-testid="stExpander"] summary, details[data-testid="stExpander"] summary {
  color: #00ff9c !important; font-size: .78rem !important; letter-spacing: .05em;
}
[data-testid="stExpander"] summary:hover { text-shadow: 0 0 10px rgba(0,255,156,.7); }

[data-testid="stAlert"], [data-baseweb="notification"] {
  border-radius: 6px !important;
  border: 1px solid #1c2634 !important;
  background: #0c121d !important;
  backdrop-filter: blur(2px);
}
[data-baseweb="notification"] span, [data-baseweb="notification"] svg { color: #00ff9c !important; fill: #00ff9c !important; }
div[role="alert"] { font-size: .85rem !important; color: #c9d1d9 !important; }

[data-testid="stDataFrame"], [data-testid="stTable"] {
  border: 1px solid #1c2634 !important; border-radius: 8px !important;
  box-shadow: inset 0 0 30px rgba(0,0,0,.35);
}
[data-testid="stGraphVizChart"] {
  border: 1px solid #1c2634; border-radius: 8px; padding: 10px;
  background: #0b101a;
}
[data-testid="stGraphVizChart"] svg { border-radius: 6px; }

.stApp hr, hr { border-color: #1c2634 !important; }
[data-testid="stSpinner"] span { color: #00ff9c !important; }
caption, .caption, p.small-font { color: #6b7a8f !important; font-size: .74rem !important; }
a { color: #00d9ff !important; text-decoration: none; }
a:hover { text-shadow: 0 0 8px rgba(0, 217, 255, .6); }
</style>
"""

_EXTRA_CSS = """
<style>
/* ===== nowe komponenty UI (kreator / termometr / legenda / werdykt) ===== */

/* kroki kreatora (Start) */
.kf-steps { display: flex; gap: 10px; flex-wrap: wrap; margin: 1rem 0; }
.kf-step {
  flex: 1 1 170px; min-width: 150px;
  border: 1px solid #1c2634; border-radius: 8px;
  padding: 12px 14px; background: #0d1420;
}
.kf-step .num {
  display: inline-block; width: 22px; height: 22px; line-height: 22px; text-align: center;
  border-radius: 50%; background: rgba(0,255,156,.12); color: #00ff9c;
  border: 1px solid rgba(0,255,156,.4); font-size: .72rem; font-weight: 700; margin-right: 8px;
}
.kf-step .t { color: #e6edf3; font-size: .82rem; font-weight: 700; letter-spacing: .04em; }
.kf-step .d { color: #7d8ca1; font-size: .7rem; margin-top: 6px; line-height: 1.45; }

/* termometr podobieństwa */
.kf-bar { height: 8px; border-radius: 4px; background: #0a0f18;
          border: 1px solid #1c2634; overflow: hidden; margin: 6px 0 2px; }
.kf-bar > span { display: block; height: 100%; border-radius: 4px;
  background: linear-gradient(90deg, #0aa868, #00ff9c);
  box-shadow: 0 0 10px rgba(0,255,156,.5); }
.kf-bar.mid > span { background: linear-gradient(90deg, #b8860b, #ffd34b); box-shadow: none; }
.kf-bar.low > span { background: linear-gradient(90deg, #5c2e2e, #ff6b6b); box-shadow: none; }
.kf-bar-cap { color: #6b7a8f; font-size: .64rem; letter-spacing: .05em; }

/* legenda mapy */
.kf-legend { display: flex; gap: 14px; flex-wrap: wrap; align-items: center;
  border: 1px solid #1c2634; border-radius: 8px; padding: 10px 14px;
  background: #0c121d; margin: .6rem 0 1rem; font-size: .72rem; color: #9aa7ba; }
.kf-legend .sw { display: inline-block; width: 12px; height: 12px;
  border-radius: 50%; margin-right: 6px; vertical-align: -1px; }
.kf-legend .ln { display: inline-block; width: 22px; height: 2px;
  margin-right: 6px; vertical-align: 3px; }

/* werdykt (wynik sprawdzenia nowego materiału) */
.kf-verdict {
  border: 1px solid rgba(0,255,156,.45); border-radius: 10px; padding: 16px 18px;
  background: linear-gradient(180deg, rgba(0,255,156,.06), transparent), #0c1420;
  box-shadow: 0 0 24px rgba(0,255,156,.08); margin: .8rem 0;
}
.kf-verdict.new { border-color: rgba(0,217,255,.45);
  background: linear-gradient(180deg, rgba(0,217,255,.06), transparent), #0c1420;
  box-shadow: 0 0 24px rgba(0,217,255,.08); }
.kf-verdict h4 { margin: 0 0 6px; color: #00ff9c; font-size: 1rem; letter-spacing: .04em; }
.kf-verdict.new h4 { color: #8ad8ff; }
.kf-verdict .why { color: #c9d1d9; font-size: .82rem; line-height: 1.6; }

/* panel "co kliknąć" */
.kf-guide { border-left: 2px solid #00ff9c; padding: 2px 0 2px 12px; margin: .4rem 0 1rem;
            color: #9aa7ba; font-size: .74rem; line-height: 1.6; }
.kf-guide b { color: #00ff9c; }
</style>
"""


# ------------------------------------------------------------- skórka

def inject_theme():
    st.markdown(_KF_CSS + _EXTRA_CSS, unsafe_allow_html=True)


def hero(compact: bool = False):
    """Nagłówek terminalowy: pełny na stronie Start, szczątkowy na podstronach."""
    if compact:
        st.markdown(
            '<div class="kf-term" style="margin-bottom:.2rem">'
            '<span class="kf-dot g"></span>kolekcjoner@fejki:~$&nbsp;./scan'
            '<span class="kf-live"> ●</span></div>', unsafe_allow_html=True)
        return
    st.markdown(
        """
<div class="kf-head">
  <div class="kf-term">
    <span class="kf-dot r"></span><span class="kf-dot y"></span><span class="kf-dot g"></span>
    &nbsp;kolekcjoner@fejki:~$ ./scan --correlate --campaigns<span class="kf-live"> ●</span>
  </div>
  <div class="kf-h1">KOLEKCJONER <span class="acc">FEJKÓW</span><span class="kf-cursor">█</span></div>
  <p class="kf-sub">z pojedynczych podejrzanych reklam wydobywamy wspólne ślady
    i łączymy je w kampanie oszustw
    <span class="tag">HackNation 2026</span><span class="tag">NASK · FOLLOW THE FAKE</span>
    <span class="tag">offline / lokalnie</span>
  </p>
</div>
        """, unsafe_allow_html=True)


# ------------------------------------------------------------- stan sesji

def default_state():
    st.session_state.materials = None
    st.session_state.features = None


def load_materials(records):
    mats = from_records(records)
    st.session_state.materials = mats
    st.session_state.features = [extract_features(m) for m in mats]


def ensure_dataset():
    if st.session_state.get("materials", None) is None and DEMO_PATH.exists():
        mats = from_jsonl(DEMO_PATH)
        st.session_state.materials = mats
        st.session_state.features = [extract_features(m) for m in mats]


def add_material(m: Material):
    if st.session_state.materials is None:
        st.session_state.materials = []
        st.session_state.features = []
    st.session_state.materials.append(m)
    st.session_state.features.append(extract_features(m))


def compute(cfg):
    """(clusters, links) dla aktualnego zbioru materiałów i parametrów."""
    feats = st.session_state.features or []
    return build_clusters(feats, cfg) if feats else ([], [])


# ------------------------------------------------------------- język laika

_FMT_KIND = {
    "text": "podobna treść i narracja (dobór słów)",
    "image": "podobne obrazy / grafiki",
    "domain": "ten sam adres internetowy (domena)",
    "infra": "ta sama infrastruktura (serwery, przekierowania, DNS)",
    "persona": "te same osoby występują w materiałach",
}

_FMT_STRONG = [
    ("ta sama domena rejestrowa: ", "TWARDY DOWÓD: ta sama domena — "),
    ("near-duplikat obrazu (dHash, odległość Hamminga=",
     "TWARDY DOWÓD: obrazy niemal identyczne (różnica "),
    ("duplikat/wariant tekstu (Jaccard n-gramów=",
     "TWARDY DOWÓD: tekst to niemal kopia (zgodność "),
]


def pct(x) -> str:
    try:
        return f"{round(float(x) * 100)}%"
    except Exception:
        return "—"


def confidence_label(c: float) -> str:
    if c >= 0.8:
        return "wysoki"
    if c >= 0.5:
        return "średni"
    return "niski"


def bar_html(value: float, cls: str = "") -> str:
    v = min(100.0, max(0.0, float(value) * 100))
    return (f'<div class="kf-bar {cls}"><span style="width:{v:.0f}%"></span></div>')


def friendly_reason(e) -> str:
    return f"{_FMT_KIND.get(e.kind, e.kind)} — zgodność {pct(e.score)}"


def friendly_strong(sig: str) -> str:
    s = sig
    for old, new in _FMT_STRONG:
        s = s.replace(old, new)
    if s.endswith("="):
        s += "?"
    return s


# ------------------------------------------------------------- graf (pyvis)

def graph_html(clusters, links, materials, features, only_cluster=None) -> str:
    """Animowany graf powiązań w neonowej zieleni; zwraca gotowy HTML."""
    from pyvis.network import Network

    net = Network(height="600px", width="100%", bgcolor="#0b101a",
                  font_color="#c9ffe0", directed=False, cdn_resources="in_line")
    palette = ["#00ff9c", "#61ffb0", "#00e582", "#39d98a", "#0fd9a3",
               "#00c77c", "#0aa868", "#7dfff2", "#0a8f66", "#1fd9c9"]
    cmap = {}
    for i, c in enumerate(sorted(clusters, key=lambda x: -len(x.members))):
        for m in c.members:
            cmap[m] = palette[i % len(palette)]
    keep = None
    if only_cluster:
        keep = {m for c in clusters if c.cluster_id == only_cluster for m in c.members}
    for m, f in zip(materials, features):
        if keep is not None and f.id not in keep:
            continue
        tip = (f"<b>{f.id}</b><br>źródło: {m.source}"
               + (f"<br>domena: {f.registrable_domain}" if f.registrable_domain else "")
               + (f"<br>słowa kluczowe: {', '.join(sorted(f.keywords)[:6])}"
                  if f.keywords else ""))
        net.add_node(f.id, label=f.id, color=cmap.get(f.id, "#2e5c47"),
                     title=tip, shape="dot", borderWidth=1,
                     font={"color": "#c9ffe0", "size": 12})
    for l in links:
        if keep is not None and not ({l.a, l.b} <= keep):
            continue
        strong = bool(l.strong_signals)
        edge_col = ({"color": "#00ff9c", "highlight": "#7dfff2"} if strong
                    else {"color": "#0aa868", "highlight": "#00ff9c"})
        tip = (f"podobieństwo: <b>{pct(l.score)}</b> "
               f"(pewność porównania: {confidence_label(l.confidence)})"
               + (f"<br>⚡ <b>{' | '.join(l.strong_signals)}</b>" if strong else "")
               + "".join(f"<br>• {friendly_reason(e)}"
                         for e in sorted(l.reasons, key=lambda x: -x.score)[:4]))
        net.add_edge(l.a, l.b, value=round(l.score * 10, 1), title=tip,
                     color=edge_col, width=2 if strong else 1,
                     dashes=False if strong else True)
    options = json.dumps({
        "physics": {"barnesHut": {"gravitationalConstant": -4000,
                                  "springLength": 120}},
        "nodes": {"shadow": {"enabled": True, "size": 8,
                             "color": "rgba(0,255,156,0.35)"}}})
    json.loads(options)  # walidacja: pyvis wymaga poprawnego JSON
    net.set_options(options)
    out = "/tmp/kolekcjoner_graf.html"
    net.write_html(out)
    return Path(out).read_text(encoding="utf-8")


def show_graph(clusters, links, materials, features, only_cluster=None):
    """Rysuje graf; gdy pyvis niedostępne — zwraca False (caller pokazuje fallback)."""
    try:
        html = graph_html(clusters, links, materials, features, only_cluster)
        st.components.v1.html(html, height=640, scrolling=True)
        return True
    except Exception as e:
        st.caption(f"Mapa interaktywna niedostępna ({type(e).__name__}) — "
                   "pokazuję wersję statyczną.")
        return False


# ------------------------------------------------------------- drobne pomocniki

def features_table_html(rows):
    """Tabela cech jako HTML (zamiennnik gdy pandas niedostępny)."""
    if not rows:
        return "<p class='kf-sub'>brak danych</p>"
    cols = list(rows[0].keys())
    head = "".join(f"<th>{c}</th>" for c in cols)
    body = "".join(
        "<tr>" + "".join(f"<td>{r[c]}</td>" for c in cols) + "</tr>" for r in rows)
    return ('<div class="kf-table-wrap"><table class="kf-table">'
            f'<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>')


def guide_box(lines):
    """Panel 'co kliknąć' — krótka lista przewodnia nad treścią strony."""
    html = "".join(f"<div>{l}</div>" for l in lines)
    st.markdown(f'<div class="kf-guide">{html}</div>', unsafe_allow_html=True)


def no_data_hint():
    """Gdy strona wymaga danych, a zbiór jest pusty."""
    st.info("Brak materiałów w zbiorze. Wróć na stronę Start i wczytaj "
            "przykładowy zbiór albo własny plik — to zajmie 5 sekund.")
    st.page_link("kolekcjoner/ui_pages/start.py", label="◀ Wróć na Start", icon="🏠")
