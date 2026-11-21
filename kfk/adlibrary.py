"""Bonus: wyszukiwanie podejrzanych reklam w Meta Ad Library API.

Wymaga tokena dostępu Graph API (opcjonalny). Bez tokena moduł potrafi wczytać
zapisaną przykładową odpowiedź (samples/meta_ads_sample.json) — demo działa offline.

Uzyskanie tokena (bezpłatnie):
1. Konto Meta + identyfikacja (Meta Business) — https://developers.facebook.com
2. Aplikacja Meta -> Graph API Explorer -> token z uprawnieniem ads_read,
   lub token systemowy aplikacji.
3. Dostęp do Ad Library API: https://www.facebook.com/ads/library/api
"""
import json
from pathlib import Path

import requests

from .features import norm_text

GRAPH_API = "https://graph.facebook.com/v27.0"
AD_FIELDS = ("ad_creative_bodies,ad_creation_time,ad_delivery_start_time,"
             "ad_snapshot_url,page_id,page_name,ad_creative_link_titles,"
             "ad_creative_link_descriptions,ad_creative_link_captions")


def search_ads(token: str, terms: str, countries=None, limit=30, after=None) -> dict:
    """Szuka reklam wg słów kluczowych w archiwum Meta (ads_archive)."""
    params = {
        "access_token": token,
        "search_terms": terms,
        "ad_type": "ALL",
        "ad_reached_countries": json.dumps(countries or ["PL"]),
        "fields": AD_FIELDS,
        "limit": limit,
    }
    if after:
        params["after"] = after
    r = requests.get(f"{GRAPH_API}/ads_archive", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def load_sample() -> dict:
    """Zapisana przykładowa odpowiedź API (demo offline, gdy brak tokena)."""
    for rel in ("samples/meta_ads_sample.json", "data/meta_ads_sample.json"):
        p = Path(__file__).parent.parent / rel
        if p.is_file():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
    return None


def ad_text(ad: dict) -> str:
    """Tekst reklamy do porównań: treści kreacji + tytuły/opisy linków + nazwa strony."""
    parts = list(ad.get("ad_creative_bodies") or [])
    for lst in ("ad_creative_link_titles", "ad_creative_link_descriptions",
                "ad_creative_link_captions"):
        parts.extend(ad.get(lst) or [])
    if ad.get("page_name"):
        parts.append(ad["page_name"])
    return "\n".join(x for x in parts if x)


def compare_ads(ads: dict, stored_feats: list, tfidf) -> list:
    """Porównuje pobrane reklamy ze znanymi kampaniami (te same widoki podobieństwa)."""
    from .similarity import pair_similarity
    results = []
    for ad in ads.get("data", []):
        text = ad_text(ad)
        title = (ad.get("ad_creative_link_titles") or [""])[0]
        fake = {
            "id": "AD", "path": "", "n_files": 1,
            "text": {"title": title, "title_norm": norm_text(title),
                     "body": text[:60000], "body_norm": norm_text(text),
                     "meta_desc": "", "ocr": ""},
            "images": [], "videos": [],
            "infra": {"domains": [], "registrable": [], "tracker_ids": [],
                      "tracker_services": [], "redirects": [], "urls": [],
                      "domain_patterns": []},
            "structure": {"css_classes": [], "scripts": [], "favicon_md5": None},
        }
        best = None
        for s in stored_feats:
            sim = pair_similarity(fake, s, tfidf)
            if best is None or sim["score"] > best["score"]:
                best = {"id": s["id"], "title": s["text"].get("title", ""), **sim}
        results.append({
            "ad_id": ad.get("id"),
            "page": ad.get("page_name") or "(brak)",
            "start": (ad.get("ad_delivery_start_time") or "")[:10],
            "text": text[:300],
            "snapshot": ad.get("ad_snapshot_url"),
            "best": best,
        })
    return results
