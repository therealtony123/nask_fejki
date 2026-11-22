"""Wzbogacanie domen o publiczne metadane RDAP (rejestrator, NS, daty).

enrich_domains() odpytuje agregator https://rdap.org/domain/<domain>, który
przekierowuje do rejestru właściwego dla danej TLD. Jest to cecha ŁAGODNIE
OPCJONALNA: brak sieci, timeout, błąd HTTP lub nietypowy kształt JSON nigdy nie
wywalają pipeline'u — dla takiej domeny zwracamy {"domain": ..., "error": ...},
a funkcja nie rzuca wyjątku na zewnątrz.

Jak można by użyć tych danych szerzej (świadomie NIE zaimplementowane, żeby nie
rozrastać widoków — np. similarity.py):

- similarity.py / pair_similarity(): twarda przesłanka "wspólny rejestrator",
  gdy obie strony mają ten sam registrar spoza listy dużych hurtowników
  (GoDaddy, Namecheap, OVH, ...), oraz miękki sygnał, gdy zbiory NS się pokrywają;
- ui_common.render_graph(): krawędź/kolor węzła dla domen zarejestrowanych
  < 30 dni przed incydentem (cecha "young_domain") lub o wspólnym registrarze;
- kfk/stix.py: dates z RDAP jako "valid_from"/"valid_until" wskaźnika domeny,
  rejestrator jako dodatkowe pole description (dziś RDAP nie wchodzi do STIX).
"""
import time

import requests

_RDAP_BASE = "https://rdap.org/domain/"
_HEADERS = {"User-Agent": "kolekcjoner-fejkow/0.1 kontakt: nask-demo",
            "Accept": "application/rdap+json"}

# domain -> (monotonic, dict); sukcesy żyją dobę, błędy minutę (żeby dać sieci szansę).
_CACHE = {}
_CACHE_TTL_OK = 24 * 3600
_CACHE_TTL_ERR = 120


def _vcard_fn(entity: dict) -> str:
    """Nazwa z vcard (['vcard', [['fn', {}, 'text', 'Nazwa'], ...]])."""
    for card in (entity.get("vcardArray"), entity.get("vcard")):
        if not (isinstance(card, list) and card and card[0] == "vcard"):
            continue
        props = card[1] if len(card) > 1 else []
        for item in props:
            if (isinstance(item, list) and item and item[0] == "fn"
                    and isinstance(item[-1], str) and item[-1].strip()):
                return item[-1].strip()
    return ""


def _parse(payload: dict, domain: str) -> dict:
    """Wyciąga daty (events), rejestratora (entities role=registrar) i NS z JSON RDAP."""
    dates = {}
    for e in payload.get("events") or []:
        if not isinstance(e, dict):
            continue
        act = (e.get("eventAction") or "").lower()
        if act == "registration":
            dates["created"] = e.get("eventDate")
        elif act == "expiration":
            dates["expires"] = e.get("eventDate")
        elif act == "last changed":
            dates["updated"] = e.get("eventDate")
    registrar = ""
    for ent in payload.get("entities") or []:
        if isinstance(ent, dict) and "registrar" in (ent.get("roles") or []):
            registrar = _vcard_fn(ent)
            if registrar:
                break
    ns = []
    groups = [(payload.get("nameservers") or [])]
    groups.append([e for e in (payload.get("entities") or [])
                   if isinstance(e, dict) and e.get("objectClassName") == "nameserver"])
    for group in groups:
        for item in group:
            if isinstance(item, dict) and isinstance(item.get("ldhName"), str):
                ns.append(item["ldhName"])
    return {
        "domain": domain,
        "registrar": registrar,
        "ns": sorted({n for n in ns if n}),
        "created": dates.get("created"),
        "expires": dates.get("expires"),
        "updated": dates.get("updated"),
        "source": "rdap.org",
    }


def enrich_domains(registrable_domains: list[str], timeout: float = 6.0,
                   max_domains: int = 25) -> list[dict]:
    """Dla każdej domeny (max ``max_domains``) pobiera metadane RDAP.

    Zwraca listę słowników {"domain","registrar","ns","created","expires",
    "updated","source"} albo {"domain","error": ...}. Nigdy nie rzuca wyjątku.
    Wyniki są cachowane w pamięci procesu (moduł).
    """
    out = []
    now = time.monotonic()
    for raw in list(registrable_domains or [])[:max_domains]:
        domain = str(raw).lower().rstrip(".")
        if not domain:
            continue
        cached = _CACHE.get(domain)
        if cached and cached[0] > now:
            out.append(cached[1])
            continue
        result = None
        try:
            resp = requests.get(_RDAP_BASE + domain, headers=_HEADERS,
                                timeout=timeout)
            if resp.status_code != 200:
                result = {"domain": domain, "error": f"HTTP {resp.status_code}"}
            else:
                try:
                    result = _parse(resp.json(), domain)
                except ValueError:
                    result = {"domain": domain, "error": "invalid JSON"}
        except Exception as exc:  # noqa: BLE001 — łagodny fallback, nigdy nie rzucamy
            result = {"domain": domain,
                      "error": f"{type(exc).__name__}: {exc}"}
        ttl = _CACHE_TTL_OK if result and "error" not in result else _CACHE_TTL_ERR
        _CACHE[domain] = (time.monotonic() + ttl, result)
        out.append(result)
    return out
