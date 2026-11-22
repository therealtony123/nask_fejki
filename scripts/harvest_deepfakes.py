#!/usr/bin/env python3
"""Harvester raportów o realnych kampaniach deepfake'owych (publiczne źródła, bez logowania).

Pobiera artykuły o prawdziwych oszustwach deepfake (sekurak.pl, niebezpiecznik.pl),
zapisuje każdy jako incydent data/do_udostępnienia/deepfake_<id>/
(page.html + meta.json z pochodzeniem + obraz główny, jeśli jest).

Użycie:
  .venv/bin/python scripts/harvest_deepfakes.py
  .venv/bin/python scripts/harvest_deepfakes.py --run-pipeline
"""
import argparse
import html
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

PROJ = Path(__file__).resolve().parent.parent
DATA = PROJ / "data"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# (id incydentu, URL, data publikacji wg źródła)
ARTICLES = [
    ("sekurak_nk_crypto_2026",
     "https://sekurak.pl/kolejne-masowe-kradzieze-kryptowalut-o-wartosci-ponad-400-milionow-dolarow-przez-koree-polnocna-tym-razem-wykorzystujaca-przejete-konta-falszywe-wideokonferencje-nagrania-prawdziwych-osob-i-deepfak/",
     "2026-11-18"),
    ("sekurak_ceo_129m_2026",
     "https://sekurak.pl/deepfakeami-podszywali-sie-pod-prezesow-prawnikow-ukradli-129-milionow/",
     "2026-11-16"),
    ("niebezpiecznik_vip_deepfake",
     "https://niebezpiecznik.pl/post/uwaga-na-deepfakei-z-vip-ami-np-andrzejem-duda-robertem-lewandowskim/",
     "2024-01-26"),
    ("niebezpiecznik_kwasniewski_deepfake",
     "https://niebezpiecznik.pl/post/przestepcy-uzyli-deepfakea-z-aleksandrem-kwasniewskim/",
     "2023-11-03"),
    ("niebezpiecznik_inwestycyjne",
     "https://niebezpiecznik.pl/post/oszustwa-inwestycyjne-to-nie-jeden-telefon-od-konsultanta/",
     "2024-01-26"),
]


def _fetch(url: str, timeout: float = 40.0):
    return requests.get(url, headers={"User-Agent": UA}, timeout=timeout)


def build_incident(inc_id: str, url: str, pub_date: str):
    inc_dir = DATA / "do_udostępnienia" / f"deepfake_{inc_id}"
    inc_dir.mkdir(parents=True, exist_ok=True)
    r = _fetch(url)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    title = ""
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        title = re.sub(r"\s+", " ", og["content"]).strip()[:200]
    if not title and soup.title and soup.title.string:
        title = re.sub(r"\s+", " ", soup.title.string).strip()
        title = re.sub(r"^[»«\s]+", "", title)
        title = re.sub(r"\s*--\s*\S+\.\S+\s*$", "", title)[:200]
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = re.sub(r"\s+", " ", h1.get_text(" ", strip=True)).strip()[:200]
    main = (soup.find("article")
            or soup.find("div", class_=re.compile("entry-content|post-content|content")))
    text = main.get_text("\n", strip=True) if main else soup.get_text("\n", strip=True)
    body = f"{title}\n\n{text[:40000]}"
    page_html = ("<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
                 f"<title>{html.escape(title)}</title></head><body>"
                 f"<h1>{html.escape(title)}</h1><pre>{html.escape(body)}</pre>"
                 "</body></html>")
    (inc_dir / "page.html").write_text(page_html, encoding="utf-8", errors="replace")
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        img_url = urljoin(url, og["content"])
        try:
            ir = requests.get(img_url, headers={"User-Agent": UA}, timeout=20)
            ext = ".png" if "png" in ir.headers.get("content-type", "") else ".jpg"
            if ir.status_code == 200 and len(ir.content) > 2000:
                (inc_dir / f"lead{ext}").write_bytes(ir.content)
        except Exception:
            pass
    meta = {
        "id": inc_id,
        "source_url": url,
        "source_date": pub_date,
        "collected_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "note": "Publiczny raport o realnej kampanii deepfake/oszustwa (źródło podane).",
    }
    (inc_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    print(f"[ok] deepfake_{inc_id}: {title[:80]}")


def main():
    ap = argparse.ArgumentParser(description="Harvester raportów o kampaniach deepfake")
    ap.add_argument("--run-pipeline", action="store_true",
                    help="Po pobraniu uruchom pipeline analizy")
    args = ap.parse_args()
    for inc_id, url, d in ARTICLES:
        try:
            build_incident(inc_id, url, d)
        except Exception as e:
            print(f"[!] {inc_id}: {type(e).__name__}: {e}")
        time.sleep(1.0)
    if args.run_pipeline:
        from pipeline import run
        run(str(DATA), str(PROJ / "kfk.sqlite"), 0.25)


if __name__ == "__main__":
    main()
