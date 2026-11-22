#!/usr/bin/env python3
"""Pobiera prawdziwe reklamy z Meta Ad Library (ads_archive) dla zapytań scamowych
i zapisuje odpowiedź jako próbkę demo: samples/meta_ads_sample.json + data/meta_ads_sample.json.

Token: meta_token.txt w katalogu projektu lub env META_TOKEN.
Użycie:
  .venv/bin/python scripts/fetch_meta_ads.py              # domyślne zapytania
  META_TOKEN=... .venv/bin/python scripts/fetch_meta_ads.py --queries "zarabiaj z domu,inwestycja"
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kfk.adlibrary import search_ads

PROJ = Path(__file__).resolve().parent.parent
QUERIES = [
    "zarabiaj z domu",
    "inwestycja gwarantowany zysk",
    "szokujące doniesienia",
    "zanim usuną",
    "cudowny lek",
    "banki tego nie chcą",
]


def main():
    ap = argparse.ArgumentParser(description="Meta Ad Library -> próbka demo (realne reklamy)")
    ap.add_argument("--limit", type=int, default=50, help="Limit reklam na zapytanie")
    ap.add_argument("--queries", default=",".join(QUERIES),
                    help="Zapytania po przecinku")
    args = ap.parse_args()

    token = os.environ.get("META_TOKEN", "").strip()
    tf = PROJ / "meta_token.txt"
    if not token and tf.is_file():
        token = tf.read_text(encoding="utf-8").strip()
    if not token:
        raise SystemExit("Brak tokena (meta_token.txt lub META_TOKEN).")

    queries = [q.strip() for q in args.queries.split(",") if q.strip()]
    ads, seen = {}, set()
    for q in queries:
        try:
            resp = search_ads(token, q, limit=args.limit)
        except Exception as e:
            print(f"[!] '{q}': błąd ({type(e).__name__}) — pomijam")
            continue
        batch = resp.get("data", [])
        for ad in batch:
            aid = str(ad.get("id") or "")
            if aid and aid not in seen:
                seen.add(aid)
                ads[aid] = ad
        print(f"[ok] '{q}': +{len(batch)} reklam (unikalne łącznie: {len(ads)})")
        time.sleep(1.0)

    payload = {
        "data": list(ads.values()),
        "paging": {},
        "_source": ("Meta Ad Library API (ads_archive), zapytania: "
                    + ", ".join(queries) + "; pobrano lokalnie, do analizy kampanii."),
    }
    if not ads:
        raise SystemExit("Nie pobrano żadnych reklam — sprawdź token/uprawnienia aplikacji.")
    out = json.dumps(payload, ensure_ascii=False, indent=1)
    for dst in ("samples/meta_ads_sample.json", "data/meta_ads_sample.json"):
        p = PROJ / dst
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(out, encoding="utf-8")
        print(f"[zapis] {dst} ({len(payload['data'])} reklam)")


if __name__ == "__main__":
    main()
