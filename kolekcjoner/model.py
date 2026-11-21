"""Model danych: materiał wejściowy, cechy, powiązanie, klaster."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Material:
    """Pojedynczy incydent (reklama / strona / zrzut / zgłoszenie)."""
    id: str
    source: str = "manual"           # skąd pochodzi: url | screenshot | text | dataset | ...
    url: Optional[str] = None
    text: Optional[str] = None       # treść reklamy / landing page'a
    image_path: Optional[str] = None  # zrzut ekranu / kreatyw
    redirect_chain: list[str] = field(default_factory=list)  # łańcuch przekierowań
    ns: list[str] = field(default_factory=list)             # serwery NS (publiczne metadane DNS)
    mx: list[str] = field(default_factory=list)
    ip: Optional[str] = None
    raw: dict = field(default_factory=dict)                  # oryginalny rekord (np. JSON)


@dataclass
class Features:
    """Znormalizowany zestaw cech do porównań. Wszystkie pola opcjonalne = tolerancja na niepełne dane."""
    id: str
    # warstwa tekstowa / semantyczna
    tokens: set[str] = field(default_factory=set)
    shingles: set[tuple[str, ...]] = field(default_factory=set)  # n-gramy słowne
    keywords: set[str] = field(default_factory=set)              # słowa kluczowe (leksykon scam)
    personas: set[str] = field(default_factory=set)              # wizerunki osób (baza referencyjna)
    money_patterns: set[str] = field(default_factory=set)        # np. "5 000 zł", "300%"
    # warstwa wizualna
    dhash: Optional[int] = None
    # warstwa infrastruktury
    registrable_domain: Optional[str] = None
    subdomain_tokens: set[str] = field(default_factory=set)
    tld: Optional[str] = None
    redirect_domains: set[str] = field(default_factory=set)
    ns_set: set[str] = field(default_factory=set)
    mx_set: set[str] = field(default_factory=set)
    ip: Optional[str] = None
    # metadane
    available_modalities: set[str] = field(default_factory=set)  # "text" | "image" | "infra" ...


@dataclass
class Evidence:
    """Pojedyncza przesłanka powiązania (interpretowalność!)."""
    kind: str          # text | image | domain | infra | persona
    description: str   # opis po polsku
    score: float       # 0..1 podobieństwo tej cechy
    weight_in_sum: float

@dataclass
class Link:
    """Krawędź między dwoma materiałami z uzasadnieniem."""
    a: str
    b: str
    score: float            # wynik ważony (0..1)
    confidence: float        # jaka część wagi była dostępna (0..1)
    reasons: list[Evidence] = field(default_factory=list)
    strong_signals: list[str] = field(default_factory=list)  # twarde sygnały (np. ta sama domena)


@dataclass
class Cluster:
    """Kampania: grupa materiałów + wspólne cechy."""
    cluster_id: str
    members: list[str] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    label: str = ""
