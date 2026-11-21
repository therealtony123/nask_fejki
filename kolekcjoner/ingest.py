"""Ingest: zamiana różnych form wejścia (URL, tekst, zrzut, JSON/CSV, dataset demo)
na obiekty Material. Pobieranie z sieci jest best-effort — brak dostępu do sieci
lub martwa domena nie przerywa analizy (tolerancja na dane niekompletne)."""
from __future__ import annotations

import json
from pathlib import Path

from .extract import rdap_lookup, resolve_ip, domain_from_url
from .model import Material

FETCH_TIMEOUT = 6.0


def from_url(url: str, mid: str, fetch: bool = True) -> Material:
    """Adres URL reklamy/strony. Próbujemy pobrać treść; RDAP daje metadane rejestrowe."""
    import requests
    m = Material(id=mid, source="url", url=url, text=None)
    host = domain_from_url(url)
    if fetch:
        try:
            r = requests.get(url, timeout=FETCH_TIMEOUT,
                             headers={"User-Agent": "Mozilla/5.0 (kolekcjoner-fejkow)"},
                             allow_redirects=True)
            m.text = _html_to_text(r.text)
            m.redirect_chain = [h.get("url") for h in r.history] + [r.url]
            r.close()
        except Exception:
            pass  # strona niedostępna -> materiał niekompletny, OK
    if host:
        m.ip = resolve_ip(host)
        rd = rdap_lookup(host)
        m.ns = rd.get("ns", [])
        m.raw["rdap"] = rd
    return m


def from_text(text: str, mid: str) -> Material:
    return Material(id=mid, source="text", text=text)


def from_screenshot(image_path: str, mid: str, text: str | None = None,
                    url: str | None = None) -> Material:
    return Material(id=mid, source="screenshot", image_path=image_path,
                    text=text, url=url)


def _html_to_text(html: str) -> str:
    """Proste uchylenie tagów bez zależności od bs4."""
    import re
    html = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    import html as h
    return h.unescape(re.sub(r"\s+", " ", html)).strip()


def from_jsonl(path: str | Path) -> list[Material]:
    """Zbiór w formacie JSON Lines (pola jak w data/demo_materials.jsonl)."""
    out = []
    for i, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines()):
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        out.append(Material(
            id=rec.get("id", f"M{i:03d}"),
            source=rec.get("source", "dataset"),
            url=rec.get("url"),
            text=rec.get("text"),
            image_path=rec.get("image"),
            redirect_chain=rec.get("redirect_chain", []),
            ns=rec.get("ns", []),
            mx=rec.get("mx", []),
            ip=rec.get("ip"),
            raw=rec,
        ))
    return out


def from_records(records: list[dict]) -> list[Material]:
    """Rekordy z GUI / CSV (dict) -> Material."""
    out = []
    for i, rec in enumerate(records):
        out.append(Material(
            id=rec.get("id", f"M{i:03d}"),
            source=rec.get("source", "import"),
            url=rec.get("url"),
            text=rec.get("text"),
            image_path=rec.get("image") or rec.get("image_path"),
            redirect_chain=rec.get("redirect_chain", []),
            ns=rec.get("ns", []),
            mx=rec.get("mx", []),
            ip=rec.get("ip"),
            raw=rec,
        ))
    return out
