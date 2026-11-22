"""Wizerunki osób w materiałach: detekcja twarzy (YuNet) + embeddingi (SFace)
+ identyfikacja względem bazy referencyjnej (publiczne portrety z Wikipedii).

Baza referencyjna: kfk/faces_ref/ (manifest.json + zdjęcia) — kilkanaście osób
najczęściej podszywanych w fałszywych reklamach (politycy, dziennikarze,
sportowcy, światowi miliarderzy).

Bezpieczna degradacja: gdy brak modeli (kfk/models/*.onnx) lub OpenCV — funkcje
zwracają puste wyniki, pipeline działa dalej (cecha po prostu nieobecna).
"""
import json
from pathlib import Path

import numpy as np

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

MODEL_DIR = Path(__file__).parent / "models"
REF_DIR = Path(__file__).parent / "faces_ref"
YUNET = MODEL_DIR / "face_detection_yunet_2023mar.onnx"
SFACE = MODEL_DIR / "face_recognition_sface_2021dec.onnx"
EMB_CACHE = REF_DIR / "embeddings.json"

NAME_MATCH_THR = 0.45   # cos(SFace) dla identyfikacji z bazą referencyjną
EMB_MATCH_THR = 0.55    # cos dla "ta sama (nieznana) twarz" między materiałami
MAX_UNKNOWN_EMBS = 12   # ile embeddingów niezidentyfikowanych twarzy zapisujemy
MIN_FACE = 24           # minimalny rozmiar twarzy w px

_detector = None
_recognizer = None
_ref = None


def available() -> bool:
    return HAS_CV2 and YUNET.exists() and SFACE.exists()


def _models():
    global _detector, _recognizer
    if not available():
        return None, None
    if _detector is None:
        try:
            _detector = cv2.FaceDetectorYN.create(str(YUNET), "", (320, 320), 0.6, 0.3, 5000)
            _recognizer = cv2.FaceRecognizerSF.create(str(SFACE), "")
        except Exception:
            return None, None
    return _detector, _recognizer


def _imread(path: Path):
    """Odczyt obrazu odporny na polskie znaki w ścieżce (np. «...» w nazwach)."""
    try:
        buf = np.fromfile(str(path), dtype=np.uint8)
        return cv2.imdecode(buf, cv2.IMREAD_COLOR)
    except Exception:
        return None


def detect_faces(img_bgr, min_conf=0.6) -> list:
    """Twarze na obrazie: [{box, conf, emb}] (emb — 128-wymiarowy wektor SFace)."""
    det, rec = _models()
    if det is None or img_bgr is None or img_bgr.size == 0:
        return []
    h, w = img_bgr.shape[:2]
    if w < 32 or h < 32:
        return []
    # YuNet ma limit rozmiaru wejścia — duże obrazy skalujemy w dół
    scale = 1.0
    work = img_bgr
    if max(w, h) > 2000:
        scale = 2000 / max(w, h)
        work = cv2.resize(work, (int(w * scale), int(h * scale)))
        h, w = work.shape[:2]
    det.setInputSize((w, h))
    try:
        _, faces = det.detect(work)
    except Exception:
        return []
    out = []
    if faces is not None:
        for f in faces:
            x, y, fw, fh = [int(v) for v in f[:4]]
            conf = float(f[-1])
            if conf < min_conf or fw < MIN_FACE or fh < MIN_FACE:
                continue
            x0, y0 = max(0, x), max(0, y)
            x1, y1 = min(w, x + fw), min(h, y + fh)
            crop = work[y0:y1, x0:x1]
            if crop.size == 0:
                continue
            try:
                emb = rec.feature(crop)
            except Exception:
                continue
            if scale != 1.0:
                x0, y0, x1, y1 = [int(v / scale) for v in (x0, y0, x1, y1)]
            out.append({"box": [x0, y0, x1 - x0, y1 - y0],
                        "conf": round(conf, 3),
                        "emb": emb.flatten().tolist()})
    return out


def _load_manifest() -> list:
    p = REF_DIR / "manifest.json"
    if not p.is_file():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


def load_reference(rebuild=False) -> list:
    """Baza referencyjna: [{slug, name, emb}]. Embeddingi cache'owane w pliku."""
    global _ref
    if _ref is not None:
        return _ref
    manifest = _load_manifest()
    if not manifest or not available():
        _ref = []
        return _ref
    cached = {}
    if EMB_CACHE.is_file() and not rebuild:
        try:
            cached = {e["slug"]: e.get("emb") for e in json.loads(EMB_CACHE.read_text(encoding="utf-8"))}
        except Exception:
            cached = {}
    ref = []
    for m in manifest:
        slug = m.get("slug", "")
        photo = REF_DIR / m.get("photo", "")
        if not slug or not photo.is_file():
            continue
        emb = cached.get(slug)
        if emb is None:
            img = _imread(photo)
            if img is None:
                continue
            faces = detect_faces(img, min_conf=0.4)
            if not faces:
                continue
            emb = max(faces, key=lambda f: f["conf"])["emb"]
        ref.append({"slug": slug, "name": m.get("name", slug), "emb": emb})
    _ref = ref
    if ref:
        try:
            EMB_CACHE.write_text(json.dumps(
                [{"slug": r["slug"], "emb": r["emb"]} for r in ref], ensure_ascii=False),
                encoding="utf-8")
        except Exception:
            pass
    return _ref


def _cos(a, b) -> float:
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(a @ b / (na * nb))


def identify(emb, ref=None):
    """Najlepsze dopasowanie z bazy powyżej progu: (name, score) lub None."""
    ref = load_reference() if ref is None else ref
    best, best_s = None, 0.0
    for r in ref:
        s = _cos(emb, r["emb"])
        if s > best_s:
            best, best_s = r["name"], s
    if best and best_s >= NAME_MATCH_THR:
        return best, round(best_s, 3)
    return None


def extract_incident_faces(image_paths: list, ref=None) -> dict:
    """Wizerunki osób w materiałach incydentu.

    Zwraca:
      persons:      [{name, score, path, box}] — zidentyfikowane osoby z bazy,
      known_names:  unikalne nazwy osób (np. ["Monika Olejnik"]),
      unknown_embs: embeddingi niezidentyfikowanych twarzy (do porównań
                    "ta sama twarz" między materiałami).
    """
    if not available():
        return {"persons": [], "known_names": [], "unknown_embs": []}
    ref = load_reference() if ref is None else ref
    persons, unknown = [], []
    for ip in image_paths:
        img = _imread(Path(ip))
        if img is None:
            continue
        for f in detect_faces(img):
            ident = identify(f["emb"], ref)
            if ident:
                persons.append({"name": ident[0], "score": ident[1],
                                "path": str(Path(ip).name), "box": f["box"]})
            elif len(unknown) < MAX_UNKNOWN_EMBS:
                unknown.append(f["emb"])
    # dedup osób (ta sama osoba na wielu obrazach incydentu)
    best_person = {}
    for p in persons:
        cur = best_person.get(p["name"])
        if cur is None or p["score"] > cur["score"]:
            best_person[p["name"]] = p
    persons = sorted(best_person.values(), key=lambda p: -p["score"])
    return {"persons": persons,
            "known_names": sorted(best_person.keys()),
            "unknown_embs": unknown}


def face_similarity(fa: dict, fb: dict):
    """Podobieństwo wizerunków między dwoma materiałami.

    Zwraca (score 0..1, evidence list): wspólne osoby z bazy (1.0) lub ta sama
    niezidentyfikowana twarz po embeddingach (0.8)."""
    a, b = fa.get("faces") or {}, fb.get("faces") or {}
    shared = set(a.get("known_names") or []) & set(b.get("known_names") or [])
    if shared:
        return 1.0, [f"ta sama osoba w obu materiałach: {', '.join(sorted(shared))}"]
    ea, eb = a.get("unknown_embs") or [], b.get("unknown_embs") or []
    matched = 0
    best_s = 0.0
    for x in ea:
        for y in eb:
            s = _cos(x, y)
            if s > best_s:
                best_s = s
            if s >= EMB_MATCH_THR:
                matched += 1
    if matched:
        return 0.8, [f"{matched} pasujących niezidentyfikowanych twarzy "
                     f"(najlepsze podobieństwo {best_s:.2f})"]
    return 0.0, []
