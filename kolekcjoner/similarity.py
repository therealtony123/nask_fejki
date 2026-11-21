"""Podobieństwo par materiałów: ważona kompozycja modaliwości + twarde sygnały.

Metoda:
1. Dla każdej pary liczymy składowe podobieństwa per modaliwość:
   - text   : Jaccard na n-gramach słownych (3) + trafienia leksykonu scam
   - image  : 1 - hamming(dhash)/64
   - domain : identyczna domena rejestrowa, warianty subdomen, wspólny TLD
   - infra  : wspólne domeny przekierowań, NS, MX, IP
   - persona: wspólne wizerunki osób (baza referencyjna)
2. Brakujące dane NIE karzą pary: wynik ważony liczony jest tylko po dostępnych
   modaliwościach (wagi renormalizowane), a `confidence` = dostępna część wagi.
3. Twarde sygnały (strong signals) wiążą parę niezależnie od progu:
   - identyczna domena rejestrowa
   - near-duplikat obrazu (hamming <= 6)
   - duplikat tekstu (Jaccard n-gramow >= 0.8)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .extract import hamming
from .model import Evidence, Features, Link

DEFAULT_WEIGHTS = {
    "text": 0.35,
    "image": 0.20,
    "domain": 0.15,
    "infra": 0.10,
    "persona": 0.20,
}

STRONG_IMAGE_HAMMING = 6
STRONG_TEXT_JACCARD = 0.8


def jaccard(a: set, b: set) -> float:
    union = len(a | b)
    return len(a & b) / union if union else 0.0


@dataclass
class SimilarityConfig:
    weights: dict = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    threshold: float = 0.45  # próg decyzji dla krawędzi w grafie


def _text_sim(fa: Features, fb: Features) -> float:
    base = jaccard(fa.shingles, fb.shingles)
    kw = jaccard(fa.keywords, fb.keywords)
    return 0.75 * base + 0.25 * kw


def _image_sim(fa: Features, fb: Features) -> float:
    if fa.dhash is None or fb.dhash is None:
        return None
    return 1.0 - hamming(fa.dhash, fb.dhash) / 64.0


def _domain_sim(fa: Features, fb: Features) -> float:
    if fa.registrable_domain is None or fb.registrable_domain is None:
        return None
    if fa.registrable_domain == fb.registrable_domain:
        return 1.0
    sub = jaccard(fa.subdomain_tokens, fb.subdomain_tokens)
    tld = 1.0 if fa.tld == fb.tld else 0.0
    return 0.5 * sub + 0.5 * tld


def _infra_sim(fa: Features, fb: Features) -> float:
    parts = [
        jaccard(fa.redirect_domains, fb.redirect_domains),
        jaccard(fa.ns_set, fb.ns_set),
        jaccard(fa.mx_set, fb.mx_set),
        1.0 if (fa.ip and fb.ip and fa.ip == fb.ip) else 0.0,
    ]
    return sum(parts) / len(parts)


def _persona_sim(fa: Features, fb: Features) -> float:
    if not fa.personas and not fb.personas:
        return None
    inter = len(fa.personas & fb.personas)
    return min(1.0, inter / 2.0) if inter else 0.0


_SIM_FUNCS = {
    "text": _text_sim,
    "image": _image_sim,
    "domain": _domain_sim,
    "infra": _infra_sim,
    "persona": _persona_sim,
}

_DESCS = {
    "text": "Podobna treść / narracja (n-gramy słowne + słowa kluczowe)",
    "image": "Zbliżony materiał wizualny (dHash obrazu)",
    "domain": "Wspólna infrastruktura domenowa",
    "infra": "Wspólne metadane infrastruktury (przekierowania/NS/MX/IP)",
    "persona": "Te same wizerunki osób",
}


def compare(fa: Features, fb: Features, cfg: SimilarityConfig) -> Link:
    """Porównuje parę materiałów; zwraca krawędź z wynikiem, ufnością i przesłankami."""
    reasons: list[Evidence] = []
    strong: list[str] = []
    num = den = 0.0
    total_w = sum(cfg.weights.values()) or 1.0

    for kind, w in cfg.weights.items():
        if w <= 0:
            continue
        sim = _SIM_FUNCS[kind](fa, fb)
        if sim is None:      # modaliwość niedostępna dla pary -> pomijamy w ważeniu
            continue
        num += w * sim
        den += w
        if sim > 0:
            reasons.append(Evidence(kind=kind, description=_DESCS[kind],
                                    score=round(sim, 3), weight_in_sum=round(w / total_w, 3)))

    score = num / den if den else 0.0
    confidence = den / total_w

    # twarde sygnały
    if (fa.registrable_domain and fa.registrable_domain == fb.registrable_domain):
        strong.append(f"ta sama domena rejestrowa: {fa.registrable_domain}")
    if fa.dhash is not None and fb.dhash is not None:
        h = hamming(fa.dhash, fb.dhash)
        if h <= STRONG_IMAGE_HAMMING:
            strong.append(f"near-duplikat obrazu (dHash, odległość Hamminga={h})")
    tj = jaccard(fa.shingles, fb.shingles)
    if tj >= STRONG_TEXT_JACCARD:
        strong.append(f"duplikat/wariant tekstu (Jaccard n-gramów={tj:.2f})")

    return Link(a=fa.id, b=fb.id, score=round(score, 3),
                confidence=round(confidence, 3), reasons=reasons, strong_signals=strong)


def is_linked(link: Link, cfg: SimilarityConfig) -> bool:
    if link.strong_signals:
        return True
    return link.score >= cfg.threshold
