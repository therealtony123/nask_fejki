#!/usr/bin/env python3
"""Build reference face photo DB for public figures commonly impersonated
in Polish fake ads. Downloads the pageimage 'original' thumbnail from
Wikipedia (pl first, en fallback), saves as <slug>.jpg, and writes manifest.json.
"""
import json
import os
import re
import sys
import time
from urllib.parse import unquote, urlparse

import requests
from PIL import Image

UA = {"User-Agent": "kfk-reference-builder/1.0 (demo; contact: nobody@example.invalid)"}

OUT_DIR = "/home/tymon/kolekcjoner-fejkow/kfk/faces_ref"
MANIFEST = os.path.join(OUT_DIR, "manifest.json")

PEOPLE = [
    ("donald_tusk", "Donald Tusk"),
    ("mateusz_morawiecki", "Mateusz Morawiecki"),
    ("andrzej_duda", "Andrzej Duda"),
    ("jaroslaw_kaczynski", "Jarosław Kaczyński"),
    ("szymon_holownia", "Szymon Hołownia"),
    ("monika_olejnik", "Monika Olejnik"),
    ("robert_lewandowski", "Robert Lewandowski"),
    ("kuba_wojewodzki", "Kuba Wojewódzki"),
    ("krzysztof_ibisz", "Krzysztof Ibisz"),
    ("elon_musk", "Elon Musk"),
    ("donald_trump", "Donald Trump"),
    ("jeff_bezos", "Jeff Bezos"),
    ("bill_gates", "Bill Gates"),
]


def api_get(url, params, timeout=30):
    r = requests.get(url, params=params, headers=UA, timeout=timeout)
    r.raise_for_status()
    return r.json()


def pageimage_original(lang, title):
    """Return (source_url, wiki_title) or (None, None)."""
    url = f"https://{lang}.wikipedia.org/w/api.php"
    data = api_get(url, {
        "action": "query",
        "prop": "pageimages",
        "piprop": "original",
        "format": "json",
        "titles": title,
        "redirects": "1",
    })
    pages = data.get("query", {}).get("pages", {})
    for pid, page in pages.items():
        if int(pid) < 0:
            continue
        orig = page.get("original")
        if orig and orig.get("source"):
            return orig["source"], page.get("title", title)
    return None, None


def file_title_from_url(src):
    """Extract 'File:...' title from a Wikimedia upload URL."""
    path = unquote(urlparse(src).path)
    m = re.search(r"/commons/(?:[0-9a-f]/){0,2}[0-9a-f]{2}/(.+)$", path)
    if not m:
        m = re.search(r"/([^/]+)$", path)
    name = m.group(1) if m else path.rsplit("/", 1)[-1]
    return "File:" + name


def commons_license(src):
    """Query Commons for license short name. Returns a string or None."""
    ftitle = file_title_from_url(src)
    try:
        data = api_get("https://commons.wikimedia.org/w/api.php", {
            "action": "query",
            "titles": ftitle,
            "prop": "imageinfo",
            "iiprop": "extmetadata",
            "format": "json",
        })
        pages = data.get("query", {}).get("pages", {})
        for pid, page in pages.items():
            if int(pid) < 0:
                continue
            md = page.get("imageinfo", [{}])[0].get("extmetadata", {})
            lic = md.get("LicenseShortName", {}).get("value")
            if lic:
                return lic
    except Exception:
        pass
    return None


def valid_jpeg(path):
    if not os.path.exists(path):
        return False, "missing"
    size = os.path.getsize(path)
    if size < 20 * 1024:
        return False, f"too small ({size} bytes)"
    try:
        im = Image.open(path)
        if im.format != "JPEG":
            return False, f"not JPEG ({im.format})"
        im.verify()
        return True, ""
    except Exception as e:
        return False, f"PIL error: {e}"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    manifest = []
    gaps = []
    for slug, name in PEOPLE:
        src = None
        wiki_title = None
        for lang in ("pl", "en"):
            try:
                src, wiki_title = pageimage_original(lang, name)
            except Exception as e:
                print(f"[{slug}] {lang} API error: {e}", file=sys.stderr)
            if src:
                break
        if not src:
            gaps.append({"slug": slug, "name": name, "reason": "no pageimage"})
            print(f"[{slug}] NO IMAGE")
            continue

        out_path = os.path.join(OUT_DIR, f"{slug}.jpg")
        try:
            r = requests.get(src, headers=UA, timeout=60)
            r.raise_for_status()
            with open(out_path, "wb") as f:
                f.write(r.content)
        except Exception as e:
            gaps.append({"slug": slug, "name": name, "reason": f"download error: {e}"})
            print(f"[{slug}] DOWNLOAD ERROR: {e}")
            continue

        ok, reason = valid_jpeg(out_path)
        if not ok:
            # Try converting non-JPEG (e.g. PNG) sources to JPEG.
            try:
                im = Image.open(out_path).convert("RGB")
                im.save(out_path, "JPEG", quality=95)
                ok, reason = valid_jpeg(out_path)
                if ok:
                    print(f"[{slug}] converted to JPEG")
            except Exception as e:
                reason = f"convert error: {e}"
        if not ok:
            gaps.append({"slug": slug, "name": name, "reason": reason})
            print(f"[{slug}] INVALID ({reason})")
            continue

        license_ = commons_license(src) or "CC (Wikimedia)"
        source_url = f"https://pl.wikipedia.org/wiki/{wiki_title.replace(' ', '_')}" if wiki_title else src
        entry = {
            "slug": slug,
            "name": name,
            "photo": f"{slug}.jpg",
            "source": source_url,
            "license": license_,
        }
        manifest.append(entry)
        print(f"[{slug}] OK ({os.path.getsize(out_path)} bytes, lic={license_})")
        time.sleep(0.3)

    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\nDONE: {len(manifest)}/{len(PEOPLE)} ok, {len(gaps)} gaps")
    if gaps:
        print("GAPS:", json.dumps(gaps, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
