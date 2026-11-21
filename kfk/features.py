"""Pozyskiwanie i wyodrębnianie cech incydentów (tekst, wizja, infrastruktura, struktura)."""
import hashlib
import json
import math
import re
import subprocess
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

try:
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
VID_EXT = {".mp4", ".webm", ".mov"}
TITLE_MAX = 200
BODY_MAX = 60_000

_OCR_LANGS = None


def _ocr_langs():
    global _OCR_LANGS
    if _OCR_LANGS is None:
        try:
            out = subprocess.run(
                ["tesseract", "--list-langs"], capture_output=True, text=True, timeout=10
            ).stdout
            langs = set(out.split())
        except Exception:
            langs = set()
        _OCR_LANGS = langs
    return _OCR_LANGS


def norm_text(s: str) -> str:
    """Normalizacja tekstu: małe litery, tylko litery/cyfry (z polskimi znakami)."""
    return re.sub(r"[^a-z0-9ąćęłńóśźż]+", " ", s.lower()).strip()


def _md5_file(p: Path, chunk=1 << 20):
    h = hashlib.md5()
    with open(p, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def dominant_colors(p: Path, k: int = 5):
    """Top-k dominujących kolorów (3 bity/kanał)."""
    try:
        img = Image.open(p).convert("RGB").resize((24, 24))
    except Exception:
        return []
    arr = np.asarray(img, dtype=np.uint8) // 32
    keys = (arr[:, :, 0].astype(int) << 6) | (arr[:, :, 1].astype(int) << 3) | arr[:, :, 2]
    cnt = Counter(keys.ravel())
    out = []
    for key, c in cnt.most_common(k):
        r = (key >> 6) * 32 + 16
        g = ((key >> 3) & 7) * 32 + 16
        b = (key & 7) * 32 + 16
        out.append((f"#{r:02x}{g:02x}{b:02x}", round(c / 576.0, 3)))
    return out


def phash(p: Path):
    """Perceptual hash (DCT, 64 bity) — odporny na skalowanie/kompresję."""
    try:
        img = Image.open(p).convert("L").resize((32, 32))
    except Exception:
        return None
    arr = np.asarray(img, dtype=np.float64)
    try:
        from scipy.fftpack import dct
    except ImportError:
        return None
    d = dct(dct(arr, axis=0, norm="ortho"), axis=1, norm="ortho")
    low = d[:8, :8]
    med = np.median(low)
    bits = (low > med).ravel()
    return _bits_to_hex(bits)


def dhash(p: Path):
    """Difference hash (64 bity) — bardzo odporny na drobne zmiany."""
    try:
        img = Image.open(p).convert("L").resize((9, 8))
    except Exception:
        return None
    arr = np.asarray(img, dtype=np.int16)
    bits = (arr[:, 1:] > arr[:, :-1]).ravel()
    return _bits_to_hex(bits)


def _bits_to_hex(bits):
    val = 0
    for i, b in enumerate(bits):
        if b:
            val |= 1 << i
    return f"{val:016x}"


def hamming(h1: str, h2: str):
    """Odległość Hamminga dwóch hex-hashy."""
    if not h1 or not h2:
        return None
    a, b = int(h1, 16), int(h2, 16)
    return bin(a ^ b).count("1")


_TRACKER_RE = re.compile(
    r"\b(?:G-[A-Z0-9]{8,14}|UA-\d{6,12}-\d{1,4}|AW-\d{6,12}|GTM-[A-Z0-9]{4,10}|DC-\d{6,10})\b"
)
_PIXEL_RE = re.compile(r"fbq\(\s*['\"]init['\"]\s*,\s*['\"](\d{10,20})['\"]")
_PIXEL_URL_RE = re.compile(r"[?&]id=(\d{10,20})")
_TRACKER_SERVICES = [
    ("google-analytics", r"(google-analytics\.com|googletagmanager\.com|doubleclick\.net)"),
    ("facebook-pixel", r"(facebook\.com/tr|facebook\.net|fbevents\.js)"),
    ("hotjar", r"hotjar\.com"),
    ("clarity", r"clarity\.ms"),
    ("tiktok-pixel", r"analytics\.tiktok\.com"),
]


def scan(root) -> list:
    """Skanuje katalog ze zbiorem (do_udostępnienia/<id>/*) i zwraca listę incydentów."""
    base = Path(root)
    if (base / "do_udostępnienia").is_dir():
        base = base / "do_udostępnienia"
    incidents = []
    for d in sorted(base.iterdir(),
                    key=lambda p: (0, int(p.name)) if p.name.isdigit() else (1, p.name)):
        if not d.is_dir():
            continue
        files = [p for p in d.rglob("*") if p.is_file()]
        incidents.append({
            "id": d.name,
            "path": str(d),
            "html": [p for p in files if p.suffix.lower() == ".html" and "_files" not in str(p)],
            "har": [p for p in files if p.suffix.lower() == ".har"],
            "images": [p for p in files if p.suffix.lower() in IMG_EXT],
            "videos": [p for p in files if p.suffix.lower() in VID_EXT],
            "json": [p for p in files if p.suffix.lower() == ".json"],
            "n_files": len(files),
        })
    return incidents


def parse_html(p: Path) -> dict:
    """Wyciąga cechy tekstowe, strukturalne i infra z zapisanego HTML."""
    out = {
        "title": "", "title_norm": "", "body": "", "meta_desc": "", "meta_kw": "",
        "links": [], "imgs": [], "scripts": [], "css_classes": [], "tracker_ids": [],
        "favicon_md5": None,
    }
    try:
        html = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for m in _TRACKER_RE.finditer(html):
        out["tracker_ids"].append(m.group(0))
    for m in _PIXEL_RE.finditer(html):
        out["tracker_ids"].append("FB_" + m.group(1))
    for m in _PIXEL_URL_RE.finditer(html):
        if "fbevents" in html[max(0, m.start() - 200): m.start()].lower():
            out["tracker_ids"].append("FB_" + m.group(1))
    if not HAS_BS4:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
        if m:
            out["title"] = re.sub(r"\s+", " ", m.group(1)).strip()
        out["body"] = re.sub(r"<[^>]+>", " ", html)
        out["title_norm"] = norm_text(out["title"])
        return out
    soup = BeautifulSoup(html, "lxml")
    if soup.title and soup.title.string:
        out["title"] = re.sub(r"\s+", " ", soup.title.string).strip()
    for meta in soup.find_all("meta"):
        name = (meta.get("name") or "").lower()
        if name == "description":
            out["meta_desc"] = (meta.get("content") or "")[:2000]
        elif name == "keywords":
            out["meta_kw"] = (meta.get("content") or "")[:2000]
    body = soup.get_text("\n", strip=True)
    out["body"] = body[:BODY_MAX]
    out["title_norm"] = norm_text(out["title"])
    for a in soup.find_all("a", href=True):
        out["links"].append(a["href"])
    for im in soup.find_all("img", src=True):
        out["imgs"].append(im["src"])
    for s in soup.find_all("script", src=True):
        out["scripts"].append(s["src"])
    classes = Counter()
    for el in soup.find_all(class_=True):
        for c in el["class"]:
            classes[c] += 1
    out["css_classes"] = [c for c, _ in classes.most_common(300)]
    for lnk in soup.find_all("link", rel=True):
        rels = " ".join(lnk.get("rel", []))
        if "icon" in rels and lnk.get("href"):
            local = p.parent / Path(lnk["href"]).name
            if local.is_file():
                out["favicon_md5"] = _md5_file(local)
            else:
                out["favicon_md5"] = hashlib.md5(lnk["href"].encode()).hexdigest()
            break
    return out


def parse_har(p: Path) -> dict:
    """Wyciąga domeny, przekierowania i trackery z archiwum HAR."""
    out = {"domains": [], "urls": [], "redirects": [], "tracker_services": set(), "tracker_ids": []}
    try:
        data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return out
    for e in data.get("log", {}).get("entries", []):
        req = e.get("request", {})
        res = e.get("response", {})
        url = req.get("url", "")
        m = re.match(r"https?://([^/]+)", url)
        if m:
            out["domains"].append(m.group(1))
        out["urls"].append(url)
        redir = res.get("redirectURL")
        if redir:
            out["redirects"].append([url, redir])
            m2 = re.match(r"https?://([^/]+)", redir)
            if m2:
                out["domains"].append(m2.group(1))
    for u in out["urls"]:
        low = u.lower()
        for svc, pat in _TRACKER_SERVICES:
            if re.search(pat, low):
                out["tracker_services"].add(svc)
        for m in _PIXEL_URL_RE.finditer(low):
            if "fbevents" in low or "facebook" in low:
                out["tracker_ids"].append("FB_" + m.group(1))
        for m in _TRACKER_RE.finditer(low):
            out["tracker_ids"].append(m.group(0))
    return out


def registrable(host: str) -> str:
    """Naiwna rejestrowalna domena (ostatnie 2 etykiety); patrz README — ograniczenie."""
    host = host.lower().split(":")[0]
    parts = [x for x in host.split(".") if x]
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


# platformy/CDN/ad-tech — ich wzorce nazw nie mówią nic o operatorze kampanii
KNOWN_PLATFORMS = {"facebook.com", "facebook.net", "google.com", "google.pl",
                   "googleapis.com", "gstatic.com", "doubleclick.net",
                   "googletagmanager.com", "jsdelivr.net", "cloudflare.com",
                   "unpkg.com", "jquery.com", "unsplash.com", "netlify.app",
                   "er-api.com", "b-cdn.net", "translate.google.com"}


def domain_patterns(registrable_domains):
    """Cechy wzorca nazw domen: TLD, segmentacja, słowopodobieństwo, entropia.

    Scam-domeny często powstają wg jednego schematu (np. słowo-słowo w nietypowym
    TLD albo losowe litery) — wzorzec nazewniczy jest dodatkowym, rzadko zmienianym
    śladem operatora kampanii.
    """
    from collections import Counter
    out = []
    for d in registrable_domains:
        if d in KNOWN_PLATFORMS:
            continue
        sld, _, tld = d.partition(".")
        if not tld:
            sld, tld = d, ""
        segs = [s for s in re.split(r"[-_]", sld) if s]
        ent = 0.0
        if sld:
            cnt = Counter(sld)
            n = len(sld)
            ent = -sum((c / n) * math.log2(c / n) for c in cnt.values())

        def wordlike(s):
            if not s or len(s) < 3:
                return False
            v = sum(1 for ch in s if ch in "aeiouy")
            ratio = v / len(s)
            return 0.2 <= ratio <= 0.6 and not re.search(r"[bcdfghjklmnpqrstvwxz]{4,}", s)

        classes = []
        if len(segs) >= 2:
            classes.append("multi-segment")
        if "-" in sld:
            classes.append("hyphen")
        classes.append("wordlike" if all(wordlike(s) for s in segs) else "nonwordlike")
        if ent >= 3.5:
            classes.append("high-entropy")
        elif ent <= 2.6:
            classes.append("low-entropy")
        pattern = f"{'|'.join(sorted(set(classes)))}|tld:{tld}"
        out.append({"domain": d, "sld": sld, "tld": tld,
                    "entropy": round(ent, 2), "classes": sorted(set(classes)),
                    "pattern": pattern})
    return out


def extract_incident(inc: dict) -> dict:
    """Łączy cechy wszystkich plików incydentu w jeden wektor cech."""
    feats = {
        "id": inc["id"],
        "path": inc["path"],
        "n_files": inc["n_files"],
        "text": {"title": "", "title_norm": "", "body": "", "meta_desc": "", "ocr": ""},
        "images": [],
        "videos": [],
        "infra": {"domains": [], "registrable": [], "tracker_ids": [], "tracker_services": set(),
                  "redirects": [], "urls": []},
        "structure": {"css_classes": [], "scripts": [], "favicon_md5": None},
    }
    titles, bodies, descs, kws = [], [], [], []
    for hp in inc["html"]:
        h = parse_html(hp)
        if h["title"]:
            titles.append(h["title"])
        if h["body"]:
            bodies.append(h["body"])
        if h["meta_desc"]:
            descs.append(h["meta_desc"])
        if h["meta_kw"]:
            kws.append(h["meta_kw"])
        feats["infra"]["tracker_ids"].extend(h["tracker_ids"])
        feats["structure"]["css_classes"].extend(h["css_classes"])
        feats["structure"]["scripts"].extend(h["scripts"])
        if h["favicon_md5"] and not feats["structure"]["favicon_md5"]:
            feats["structure"]["favicon_md5"] = h["favicon_md5"]
        for u in h["links"] + h["imgs"] + h["scripts"]:
            m = re.match(r"https?://([^/]+)", u)
            if m:
                feats["infra"]["domains"].append(m.group(1))
    for hp in inc["har"]:
        hr = parse_har(hp)
        feats["infra"]["domains"].extend(hr["domains"])
        feats["infra"]["urls"].extend(hr["urls"])
        feats["infra"]["redirects"].extend(hr["redirects"])
        feats["infra"]["tracker_services"].update(hr["tracker_services"])
        feats["infra"]["tracker_ids"].extend(hr["tracker_ids"])
    if titles:
        feats["text"]["title"] = titles[0][:TITLE_MAX]
        feats["text"]["title_norm"] = norm_text(titles[0])
        feats["text"]["alt_titles"] = titles[1:5]
    if descs:
        feats["text"]["meta_desc"] = descs[0][:2000]
    feats["text"]["body"] = "\n".join(bodies)[:BODY_MAX]
    feats["text"]["kw"] = kws
    # obrazy — hashe percepcyjne + kolory
    base = Path(inc["path"])
    for ip in inc["images"]:
        rel = str(ip.relative_to(base))
        feats["images"].append({
            "path": rel,
            "phash": phash(ip),
            "dhash": dhash(ip),
            "colors": dominant_colors(ip),
            "top": ip.parent == base,
        })
    # OCR na wybranych zrzutach ekranu (max 3)
    ocr_imgs = [i for i in inc["images"] if "zrzut" in i.name.lower() or "screen" in i.name.lower()
                or i.parent == base][:3]
    if HAS_OCR and ocr_imgs:
        langs = "pol+eng" if "pol" in _ocr_langs() else "eng"
        parts = []
        for ip in ocr_imgs:
            try:
                txt = pytesseract.image_to_string(Image.open(ip), lang=langs)
                parts.append(txt[:3000])
            except Exception:
                pass
        feats["text"]["ocr"] = "\n".join(parts)
    # wideo — md5 + metadata z .info.json (yt-dlp)
    for vp in inc["videos"]:
        feats["videos"].append({"path": str(vp.relative_to(base)), "md5": _md5_file(vp)})
    for jp in inc["json"]:
        try:
            jd = json.loads(jp.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        feats["videos"].append({
            "path": str(jp.relative_to(base)),
            "meta": {k: jd.get(k) for k in ("id", "title", "description", "duration",
                                            "uploader", "webpage_url") if k in jd},
        })
    # finalne porządki
    feats["infra"]["domains"] = sorted(set(d.lower() for d in feats["infra"]["domains"]))
    feats["infra"]["registrable"] = sorted({registrable(d) for d in feats["infra"]["domains"]})
    feats["infra"]["domain_patterns"] = domain_patterns(feats["infra"]["registrable"])
    feats["infra"]["tracker_ids"] = sorted(set(feats["infra"]["tracker_ids"]))
    feats["infra"]["tracker_services"] = sorted(feats["infra"]["tracker_services"])
    feats["structure"]["css_classes"] = sorted(set(feats["structure"]["css_classes"]))
    feats["structure"]["scripts"] = sorted(set(feats["structure"]["scripts"]))
    feats["text"]["body_norm"] = norm_text(feats["text"]["body"] + " " + feats["text"]["ocr"])
    return feats


def extract_from_url_text(url: str, html: str, redirects: list) -> dict:
    """Cechy materiału pobranego z URL (demo: nowy materiał vs zbiór)."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "page.html"
        p.write_text(html, encoding="utf-8", errors="replace")
        h = parse_html(p)
    feats = {
        "id": "NEW",
        "path": url,
        "n_files": 1,
        "text": {"title": h["title"], "title_norm": h["title_norm"],
                 "body": h["body"], "meta_desc": h["meta_desc"], "ocr": ""},
        "images": [],
        "videos": [],
        "infra": {"domains": [], "registrable": [], "tracker_ids": h["tracker_ids"],
                  "tracker_services": [], "redirects": list(redirects), "urls": [url]},
        "structure": {"css_classes": h["css_classes"], "scripts": h["scripts"],
                      "favicon_md5": h["favicon_md5"]},
    }
    doms = set()
    for u in [url] + [r[1] for r in redirects] + h["links"] + h["imgs"] + h["scripts"]:
        m = re.match(r"https?://([^/]+)", u)
        if m:
            doms.add(m.group(1).lower())
    feats["infra"]["domains"] = sorted(doms)
    feats["infra"]["registrable"] = sorted({registrable(d) for d in doms})
    feats["infra"]["domain_patterns"] = domain_patterns(feats["infra"]["registrable"])
    feats["text"]["body_norm"] = norm_text(h["body"])
    return feats