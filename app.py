#!/usr/bin/env python3
"""KOLEKCJONER FEJKÓW — demonstrator (HackNation 2026, wyzwanie NASK).

Uruchomienie:  streamlit run app.py
Pełny proces: materiały -> ekstrakcja cech -> podobieństwa -> klastry/kampanie
-> graf zależności z przesłankami -> analiza nowego materiału.
"""
import json
import random
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

# ------------------------------------------------------------- skin (dark-ops)

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

/* binarne tło 0101… — pod treścią, delikatnie przezroczyste */
.kf-matrix {
  position: fixed; inset: 0; z-index: -1;
  overflow: hidden; pointer-events: none; user-select: none;
  color: rgba(0, 255, 156, .06);
  font-size: 12px; line-height: 2.6rem; letter-spacing: .3em;
  white-space: pre-wrap; word-break: break-all;
  padding: 4px 12px;
  text-shadow: 0 0 8px rgba(0, 255, 156, .12);
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


def inject_theme():
    st.markdown(_KF_CSS, unsafe_allow_html=True)


def features_table_html(rows):
    """Tabela cech jako HTML (fallback, gdy pandas nie działa)."""
    if not rows:
        return "<p class='kf-sub'>brak danych</p>"
    cols = list(rows[0].keys())
    head = "".join(f"<th>{c}</th>" for c in cols)
    body = "".join(
        "<tr>" + "".join(f"<td>{r[c]}</td>" for c in cols) + "</tr>" for r in rows)
    return (f'<div class="kf-table-wrap"><table class="kf-table">'
            f'<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>')


inject_theme()

# binarne tło 0101… (deterministyczny wzór, generowany raz na sesję)
if "kf_binary_bg" not in st.session_state:
    rng = random.Random(0x1010)
    lines = []
    for _ in range(48):
        width = rng.randint(70, 115)
        lines.append("".join(
            rng.choice(("0", "1", " ", " ")) for _ in range(width)))
    st.session_state.kf_binary_bg = "\n".join(lines)
st.markdown(f'<div class="kf-matrix" aria-hidden="true">{st.session_state.kf_binary_bg}</div>',
            unsafe_allow_html=True)

st.markdown(
    """
<div class="kf-head">
  <div class="kf-term">
    <span class="kf-dot r"></span><span class="kf-dot y"></span><span class="kf-dot g"></span>
    &nbsp;kolekcjoner@fejki:~$ ./scan --correlate --campaigns<span class="kf-live"> ●</span>
  </div>
  <div class="kf-h1">KOLEKCJONER <span class="acc">FEJKÓW</span><span class="kf-cursor">█</span></div>
  <p class="kf-sub">korelacja podejrzanych reklam w kampanie
    <span class="tag">HackNation 2026</span><span class="tag">NASK</span>
    <span class="tag">offline / lokalnie</span>
  </p>
</div>
    """,
    unsafe_allow_html=True,
)


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
    st.markdown(
        '<div class="kf-side-head">'
        '<span class="kf-side-kicker">// config</span>'
        '<div class="kf-side-title">PARAMETRY ANALIZY</div>'
        '</div>', unsafe_allow_html=True)
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

    st.markdown('<div class="kf-side-sep"></div>', unsafe_allow_html=True)
    _count = (f"{len(st.session_state.materials)} materiałów w zbiorze"
              if st.session_state.materials else "zbiór pusty")
    st.markdown(
        '<div class="kf-side-head">'
        '<span class="kf-side-kicker">// input</span>'
        '<div class="kf-side-title sm">MATERIAŁY</div>'
        f'<div class="kf-side-count">{_count}</div>'
        '</div>', unsafe_allow_html=True)

    st.markdown('<div class="kf-lbl">▸ dodaj pojedynczy materiał</div>',
                unsafe_allow_html=True)
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

    st.markdown('<div class="kf-side-sep"></div>', unsafe_allow_html=True)
    st.markdown('<div class="kf-lbl">▸ import zbioru (JSON Lines / CSV)</div>',
                unsafe_allow_html=True)
    up_json = st.file_uploader("Plik zbioru", type=["jsonl", "json"],
                               key="bulk")
    if up_json and st.button("wczytaj zbiór z pliku", use_container_width=True):
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

# pasek metryk
_m = st.columns(4)
_hard = sum(1 for l in links if l.strong_signals)
_m[0].metric("MATERIAŁY", len(features))
_m[1].metric("KAMPANIE", len(clusters))
_m[2].metric("POWIĄZANIA", len(links))
_m[3].metric("TWARDE SYGNAŁY", _hard)

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
            is_camp = size > 1
            cls = "kf-card campaign" if is_camp else "kf-card solo"
            badge_cls = "kf-badge camp" if is_camp else "kf-badge inc"
            badge = "KAMPANIA · {} mat.".format(size) if is_camp else "POJEDYNCZY INCYDENT"
            chips = " ".join(f'<span class="kf-chip">{m}</span>' for m in c.members)
            st.markdown(
                f'<div class="{cls}">'
                f'<div class="kf-card-top"><span class="kf-id">{c.cluster_id}</span>'
                f'<span class="{badge_cls}">{badge}</span></div>'
                f'<div class="kf-members">{chips}</div></div>',
                unsafe_allow_html=True)
            if c.links:
                with st.expander(f"⚡ Przesłanki powiązań ({len(c.links)})"):
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
    try:
        st.dataframe(rows, width="stretch")
    except Exception:
        st.markdown(features_table_html(rows), unsafe_allow_html=True)
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
