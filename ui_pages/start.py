"""Start — kreator: status zbioru, metryki, co dalej."""
import io
import zipfile
from datetime import datetime
from pathlib import Path

import streamlit as st

from kfk.skin import guide_box, head_box
from ui_common import DEFAULT_DATA

head_box("START — KREATOR ANALIZY", "// kolekcjoner fejków / start")
guide_box([
    "1. Zbiór ładuje się sam (dane w katalogu data/ — struktura do_udostępnienia/<id>/).",
    "2. W panelu bocznym możesz ustawić progi i kliknąć ▶ Uruchom analizę.",
    "3. Wyniki zobaczysz na stronach: Kampanie • Mapa powiązań • Incydenty.",
    "4. Nowy materiał sprawdzisz na stronie „Sprawdź nowy materiał”.",
])

# ------------------------------------------------------------- upload materiałów
# typy plików rozpoznawane przez zbiór (kfk.features.scan): html/har/json,
# obrazy png/jpg/webp/gif/bmp, wideo mp4/webm/mov + zip jako paczka
UPLOAD_TYPES = ["html", "har", "json", "png", "jpg", "jpeg", "webp", "gif",
                "bmp", "mp4", "webm", "mov", "zip"]


def new_incident_id(base: Path) -> str:
    """Bezpieczny id incydentu: upload_YYYYMMDD_HHMMSS, przy kolizji z przyrostkiem _n."""
    stamp = datetime.now().strftime("upload_%Y%m%d_%H%M%S")
    inc_id, n = stamp, 1
    while (base / inc_id).exists():
        inc_id = f"{stamp}_{n}"
        n += 1
    return inc_id


def save_uploaded(file_name: str, data: bytes, target_dir: Path) -> list:
    """Zapisuje wgrany plik do target_dir (katalog powstaje w razie potrzeby).

    Plik .zip jest rozpakowywany bezpiecznie: każda ścieżka w archiwum musi
    pozostać wewnątrz target_dir (ochrona przed Zip Slip), a zawartość członków
    jest zapisywana wprost — wpisy-symlinki z ZIP nie są tworzone. Zwraca listę
    zapisanych ścieżek względem target_dir; przy niebezpiecznej ścieżce lub
    pustych danych podnosi ValueError.
    """
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    root = target_dir.resolve()
    if not data:
        raise ValueError("pusty plik — nic do zapisania")
    safe_name = Path(file_name).name
    if not safe_name or safe_name in (".", ".."):
        raise ValueError(f"nieprawidłowa nazwa pliku: {file_name!r}")
    if safe_name.lower().endswith(".zip"):
        saved = []
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for member in zf.infolist():
                if member.is_dir():
                    continue
                target = (target_dir / member.filename).resolve()
                if target == root or not target.is_relative_to(root):
                    raise ValueError(
                        f"Zip Slip — ścieżka poza katalogiem: {member.filename!r}")
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(target, "wb") as dst:
                    dst.write(src.read())
                saved.append(str(target.relative_to(root)))
        return saved
    target = (target_dir / safe_name).resolve()
    if target == root or not target.is_relative_to(root):
        raise ValueError(f"ścieżka poza katalogiem: {file_name!r}")
    target.write_bytes(data)
    return [str(target.relative_to(root))]


st.markdown(
    '<div class="kf-side-head">'
    '<span class="kf-side-kicker">// upload</span>'
    '<div class="kf-side-title">DODAJ MATERIAŁ DO ZBIORU</div>'
    '</div>', unsafe_allow_html=True)

uploaded = st.file_uploader(
    "Wrzuć materiały podejrzanego incydentu (HTML, HAR, zrzuty PNG/JPG, mp4, zip)",
    type=UPLOAD_TYPES, accept_multiple_files=True, key="start_upload",
    help="Pliki z jednego zgłoszenia utworzą wspólny incydent "
         "data/do_udostępnienia/<id>/; archiwum ZIP zostanie bezpiecznie rozpakowane.")

done_ids = set(st.session_state.get("start_upload_done", ()))
fresh = [u for u in uploaded if u.file_id not in done_ids]

if fresh and st.button("📥 Dodaj do zbioru", type="primary"):
    base = DEFAULT_DATA / "do_udostępnienia"
    target = base / new_incident_id(base)
    saved, errors = [], []
    for up in fresh:
        try:
            saved += save_uploaded(up.name, up.getvalue(), target)
        except (ValueError, zipfile.BadZipFile, OSError) as exc:
            errors.append(f"{up.name}: {exc}")
    if errors:
        st.error("Nie udało się zapisać części plików: " + "; ".join(errors))
    if not saved:
        if not errors:
            st.warning("Nic nie zapisano — archiwum ZIP nie zawiera plików?")
        try:
            target.rmdir()  # sprząta pusty katalog po całkowicie nieudanym zapisie
        except OSError:
            pass
    else:
        st.session_state["start_upload_done"] = sorted(done_ids | {u.file_id for u in fresh})
        st.success(
            f"Incydent **{target.name}** zapisany do zbioru "
            f"(`data/do_udostępnienia/{target.name}/`) — {len(saved)} plików:\n\n"
            + "\n".join(f"• `{p}`" for p in saved)
            + "\n\nKliknij ▶ **Uruchom analizę** w panelu bocznym.")
elif uploaded and not fresh:
    st.caption("Wybrane pliki są już w zbiorze — dodaj nowe albo usuń je z listy powyżej.")

graph = st.session_state.get("graph")
if graph:
    edges = graph["edges"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Materiały", len(graph["nodes"]))
    m2.metric("Powiązania", len(edges))
    m3.metric("Kampanie", len(graph["clusters"]))
    m4.metric("Twarde powiązania", sum(1 for e in edges if e["hard"]))
    big = sorted((c for c in graph["clusters"] if len(c["members"]) >= 3),
                 key=lambda c: -len(c["members"]))
    if big:
        titles = {n["id"]: (n.get("title") or n["id"])[:55] for n in graph["nodes"]}
        st.markdown("**Największe kampanie:**")
        for c in big[:6]:
            ex = " / ".join(titles.get(m, m) for m in c["members"][:2])
            st.write(f"• **{c['cluster_id']}** — {len(c['members'])} materiałów · {ex}")
        st.caption("Pełny przegląd z podglądami materiałów: strona **Kampanie**.")
    else:
        st.info("Brak kampanii wieloelementowych — uruchom analizę.")
else:
    st.info("Brak wyników. Uruchom analizę w panelu bocznym (▶ Uruchom analizę) "
            "albo wczytaj zapisane wyniki.")
