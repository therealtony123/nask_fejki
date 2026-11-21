#!/usr/bin/env python3
"""Szukacz — aktywnie wyszukuje materiały powiązane z podejrzanymi linkami,
obrazami i tekstami w publicznie dostępnych źródłach (bez kluczy API).

Zgodnie z treścią zadania (funkcja punktowana): „mechanizm automatycznego
wyszzukiwania podejrzanych reklam w publicznie dostępnych źródłach,
według słów kluczowych, daty wystąpienia albo innych reguł”.

Źródła: DuckDuckGo (otwarty endpoint HTML) do wyszukania kandydatów,
potem standardowy pipeline Kolekcjonera: pobranie materiału (treść + DNS/RDAP),
wyekstrahowanie cech i porównanie ze znanymi kampaniami.
"""
import re
import urllib.parse

import requests

from kolekcjoner.ingest import from_url
from kolekcjoner import extract_features

UA = {"User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")}

_DDG = "https://html.duckduckgo.com/html/"


def web_search(query: str, max_results: int = 8):
    """Szuka stron w DuckDuckGo (publiczny endpoint HTML, bez kluczy API).

    Zwraca listę URL-i kandydatów.
    """
    r = requests.get(_DDG, params={"q": query}, headers=UA, timeout=25)
    r.raise_for_status()
    urls, seen = [], set()
    for href in re.findall(r'class="result__a"[^>]*href="([^"]+)"', r.text):
        m = re.search(r"uddg=([^&]+)", href)
        url = urllib.parse.unquote(m.group(1)) if m else href
        url = url.split("&rut=")[0]
        if not url.startswith("http") or url in seen:
            continue
        # odfiltruj same wyszukiwarki i Portale socialowe (nas nie interesują
        # jako "materiał", tylko realne strony/reklamy kampanii)
        dom = urllib.parse.urlparse(url).netloc
        if any(b in dom for b in ("duckduckgo.com", "google.", "facebook.com",
                                  "bing.com", "youtube.com", "wikipedia.org")):
            continue
        seen.add(url)
        urls.append(url)
        if len(urls) >= max_results:
            break
    return urls


def query_for_features(f):
    """Buduje frazy wyszukiwania z cech materiału (słowa kluczowe + osoby)."""
    parts = []
    if f.keywords:
        parts += sorted(f.keywords)[:6]
    if f.personas:
        parts += sorted(f.personas)[:2]
    if f.money_patterns:
        parts.append(sorted(f.money_patterns)[0])
    return " ".join(dict.fromkeys(parts)).strip()


def fetch_candidate(url: str, mid: str):
    """Pobiera kandydata przez standardowy pipeline (treść + DNS/RDAP).

    Zwraca (material, features) albo rzuca wyjątek (strona niedostępna —
    to normalne: Narzędzie ma działać mimo niepełnych danych, kandydat
    po prostu pomijamy).
    """
    m = from_url(url, mid, fetch=True)
    return m, extract_features(m)
