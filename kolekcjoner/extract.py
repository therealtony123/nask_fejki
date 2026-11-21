"""Ekstrakcja cech z materiałów: tekst, obraz (dHash), infrastruktura (domena/DNS/RDAP).

Wszystko tolerancyjne na brakujące dane: materiał bez obrazka / bez tekstu / bez DNS
po prostu dostaje pusty zestaw cech w danej modaliwości (wagi są renormalizowane
na etapie porównania).
"""
from __future__ import annotations

import re
import socket
import unicodedata
from typing import Optional
from urllib.parse import urlparse

import numpy as np
from PIL import Image

from .model import Features, Material

# ---------------------------------------------------------------- tekst

PL_STOPWORDS = {
    "i", "w", "na", "z", "do", "the", "a", "o", "że", "jak", "się", "jest",
    "to", "za", "od", "dla", "po", "przez", "oraz", "lub", "który", "często",
    "ją", "go", "twoje", "twojej", "mój", "nasz", "for", "with", "you",
    "your", "of", "in", "on", "and", "this", "that", "kliknij", "http",
    "https", "www", "com", "html",
}

# leksykon narracji oszukańczych (PL/EN) - konfigurowalny
SCAM_LEXICON = {
    "zysk", "zyski", "dochód", "dochodu", "inwestycja", "inwestuj", "inwestycji",
    "kryptowaluta", "kryptowaluty", "bitcoin", "btc", "giełda", "kapitał",
    "kredyt", "pożyczka", "emerytura", "renta", "wypłata", "wypłaty", "bonus",
    "kurs", "webinar", "szkolenie", "edukacja", "lekarz", "dieta", "suplement",
    "tabletki", "odchudzanie", "cukrzyca", "nadciśnienie", "keto", "detoks",
    "metoda", "system", "platforma", "portfel", "wycofanie", "wycofania",
    "sojusz", "alians", "profit", "passive", "income", "invest", "crypto",
    "guaranteed", "investment", "kursy",
}

# mała baza referencyjna osób najczęściej wykorzystywanych w fejkach (PL) - edytowalna
PERSONA_BASE = {
    "lewandowski", "lewandowska", "robert", "anna", "czubówna", "krystyna",
    "ibisz", "krzysztof", "okafor", "sofy", "bednarek", "natalia", "jestepremium",
}


def normalize(text: str) -> list[str]:
    text = unicodedata.normalize("NFKD", text).lower()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return [t for t in text.split() if t and t not in PL_STOPWORDS and len(t) > 2]


def shingles(tokens: list[str], n: int = 3) -> set[tuple[str, ...]]:
    if len(tokens) < n:
        return {tuple(tokens)} if tokens else set()
    return {tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)}


def find_keywords(tokens: list[str]) -> set[str]:
    return {t for t in tokens if t in SCAM_LEXICON}


def find_personas(text: str) -> set[str]:
    low = text.lower()
    return {p for p in PERSONA_BASE if re.search(rf"\b{re.escape(p)}\b", low)}


def find_money(text: str) -> set[str]:
    out = set()
    for m in re.finditer(r"\d[\d\s.,%]{2,12}(?:zł|zl|%|pln)", text.lower()):
        out.add(re.sub(r"\s+", "", m.group()))
    return out


# ---------------------------------------------------------------- obraz

def dhash(path: str, hash_size: int = 8) -> Optional[int]:
    """Difference hash 64-bit; czysty PIL+numpy, bez zależności od imagehash."""
    try:
        img = Image.open(path).convert("L").resize((hash_size + 1, hash_size))
        px = np.asarray(img, dtype=np.int16)
        diff = (px[:, 1:] > px[:, :-1]).reshape(-1)
        bits = np.packbits(diff)
        return int.from_bytes(bits.tobytes(), "big")
    except Exception:
        return None


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


# ---------------------------------------------------------------- domena / infra

PUBLIC_SUFFIX_2 = {
    "co.uk", "org.uk", "com.pl", "net.pl", "org.pl", "gov.pl", "edu.pl", "co.jp",
}


def registrable(domain: str) -> str:
    labels = domain.lower().strip(".").split(".")
    if len(labels) >= 3 and ".".join(labels[-2:]) in PUBLIC_SUFFIX_2:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:]) if len(labels) >= 2 else domain.lower()


def domain_from_url(url: str) -> Optional[str]:
    try:
        host = urlparse(url).hostname
        return host.lower() if host else None
    except Exception:
        return None


def resolve_ip(host: str) -> Optional[str]:
    try:
        return socket.gethostbyname(host)
    except Exception:
        return None


def rdap_lookup(domain: str, timeout: float = 5.0) -> dict:
    """Publiczne metadane rejestrowe domeny przez RDAP (best-effort, offline-safe).

    Źródła: https://rdap.org (przekierowuje do właściwego rejestru, m.in. NASK dla .pl).
    """
    import requests
    reg = registrable(domain)
    try:
        r = requests.get(
            f"https://rdap.org/domain/{reg}",
            headers={"Accept": "application/rdap+json",
                     "User-Agent": "kolekcjoner-fejkow/1.0"},
            timeout=timeout,
        )
        if r.status_code == 200:
            data = r.json()
            ns = sorted({(n.get("ldhName") or "").lower().rstrip(".")
                         for n in data.get("nameservers", []) or [] if n.get("ldhName")})
            return {
                "registrar": _registrar_name(data),
                "ns": ns,
                "created": next((e.get("eventDate") for e in data.get("events", [])
                                 if e.get("eventAction") == "registration"), None),
                "status": data.get("status", []),
            }
    except Exception:
        pass
    return {}


def _registrar_name(data: dict) -> Optional[str]:
    for ent in data.get("entities", []) or []:
        if "registrar" in [str(r).lower() for r in ent.get("roles", [])]:
            vcard = ent.get("vcardArray") or [None, []]
            for item in vcard[1]:
                if item[0] == "fn":
                    return item[3]
    return None


# ---------------------------------------------------------------- pełna ekstrakcja

def extract_features(m: Material) -> Features:
    f = Features(id=m.id)
    if m.text:
        toks = normalize(m.text)
        f.tokens = set(toks)
        f.shingles = shingles(toks)
        f.keywords = find_keywords(toks)
        f.personas = find_personas(m.text)
        f.money_patterns = find_money(m.text)
        f.available_modalities.add("text")
    if m.image_path:
        h = dhash(m.image_path)
        if h is not None:
            f.dhash = h
            f.available_modalities.add("image")
    host = domain_from_url(m.url) if m.url else None
    chain_hosts = [domain_from_url(u) for u in (m.redirect_chain or [])]
    chain_hosts = [h for h in chain_hosts if h]
    if host or chain_hosts:
        reg_host = registrable(host) if host else None
        f.registrable_domain = reg_host
        if host:
            reg_labels = registrable(host).split(".")
            f.subdomain_tokens = set(host.split(".")[:-len(reg_labels)])
            f.tld = host.split(".")[-1]
        f.redirect_domains = {registrable(h) for h in chain_hosts}
        f.ns_set = {n.lower().rstrip(".") for n in m.ns}
        f.mx_set = {x.lower().rstrip(".") for x in m.mx}
        f.ip = m.ip
        f.available_modalities.add("infra")
    return f
