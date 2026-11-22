#!/usr/bin/env python3
"""Autopilot — radar nowych odsłon kampanii.

Okresowo i SAMODZIELNIE skanuje publicznie dostępne źródła podejrzanych
reklam / stron, buduje z nich materiały przez standardowy pipeline
Kolekcjonera i porównuje z wcześniej wykrytymi kampaniami.

Trafia jednocześnie w trzy funkcje wprost punktowane w zadaniu:
  1. „mechanizm automatycznego wyszukiwania podejrzanych reklam
      w publicznie dostępnych źródłach, według słów kluczowych…”
  2. „okresowe aktualizowanie informacji” (scheduler w tle),
  3. „identyfikowanie nowych materiałów powiązanych z wcześniej
      wykrytymi kampaniami” — frazy wyszukiwania są generowane
      AUTOMATYCZNIE z profili wykrytych kampanii.

Źródła (wszystkie publiczne, bez kluczy API):
  - DuckDuckGo (otwarty endpoint HTML) — frazy od użytkownika
    + frazy wyliczone z cech wykrytych kampanii,
  - OpenPhish — publiczny feed phishingowych URL-i,
  - AA419 — baza fałszywych banków / platform inwestycyjnych,
  - Meta Ad Library (oficjalne API, opcjonalnie, wymaga tokenu;
    w UE dzięki DSA widać wszystkie reklamy, nie tylko polityczne).

Silnik jest niezależny od Streamlita (można goauchać z CLI/wątku),
UI trzyma go jako singleton (st.cache_resource).
"""
from __future__ import annotations

import random
import re
import threading
import time
import urllib.parse
from dataclasses import dataclass, field

import requests

from .szukacz import UA, web_search, fetch_candidate
from .cluster import assign_new_material

# ------------------------------------------------------------------ stałe

DEFAULT_PROFILES = [
    "inwestycja gwarantowany zysk",
    "kredyt bez sprawdzania baz",
    "Elon Musk inwestycja opinie",
    "kurs tradingu jak zarobić",
    "prezent od znanej fundacji",
]

OPENPHISH_FEED = "https://openphish.com/feed.txt"
AA419_LIST = "https://db.aa419.org/fakebankslist.php"
META_AD_LIBRARY = "https://graph.facebook.com/v19.0/ads_archive"

MAX_FINDS_KEPT = 60          # okno pamięci radara (najnowsze)
MAX_LOG_KEPT = 200


# ------------------------------------------------------------------ dane

@dataclass
class RadarFind:
    """Pojedynczy kandydat znaleziony w publicznym źródle."""
    ts: float
    source: str                      # duckduckgo | openphish | aa419 | meta
    query: str                       # fraza / feed, którym trafiono
    url: str
    status: str                      # variant | new
    cluster_id: str | None           # do której kampanii przypisano
    score: float                     # najlepszy wynik podobieństwa
    confidence: float
    strong_signals: list
    reasons: list                    # przesłanki (Evidence)
    material: object                 # Material (do dodania do zbioru)
    features: object                 # Features
    domain: str = ""


@dataclass
class ScanRecord:
    """Podsumowanie jednego cyklu skanowania (do wykresu w UI)."""
    ts: float
    seconds: float
    queries: int
    candidates: int                  # po deduplikacji
    processed: int                   # pobrane i porównane
    variants: int                    # nowe odsłony znanych kampanii
    new_patterns: int                 # kandydaci bez dopasowania
    errors: int


# ------------------------------------------------------------------ silnik

class Radar:
    """Singletonowy skaner działający w tle procesu Streamlita."""

    def __init__(self):
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._scanning = False

        # konfiguracja (edytowalna z UI)
        self.running = False
        self.interval = 60                      # sekundy między skanami
        self.max_per_scan = 6
        self.profiles: list[str] = list(DEFAULT_PROFILES)
        self.sources = {"duckduckgo": True, "openphish": True,
                        "aa419": True, "meta": False}
        self.fb_token: str | None = None

        # pamięć radara
        self.finds: list[RadarFind] = []
        self.scans: list[ScanRecord] = []
        self.alerts: list[dict] = []
        self.log: list[str] = []
        self._seen_urls: set[str] = set()
        self._scan_no = 0

        # migawkowy obraz zbioru (UI podświeża przy każdym rerunie)
        self.features: list = []
        self.clusters: list = []
        self.materials: list = []
        self.cfg = None

    # ------------------------------------------------------------ pomocnicze

    def _say(self, msg: str):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        with self._lock:
            self.log.append(line)
            if len(self.log) > MAX_LOG_KEPT:
                del self.log[:len(self.log) - MAX_LOG_KEPT]

    def update_baseline(self, features, clusters, cfg, materials=None):
        """UI wywołuje przy każdym rerunie — radar porównuje z aktualnym zbiorem."""
        self.features = features or []
        self.clusters = clusters or []
        self.cfg = cfg
        self.materials = materials or []

    # ------------------------------------------------------------ start/stop

    def start(self):
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name="kolekcjoner-radar")
        self._thread.start()
        self._say("🟢 autopilot wystartował")

    def stop(self):
        self.running = False
        self._say("🔴 autopilot zatrzymany")

    def _loop(self):
        while self.running:
            try:
                self.scan_once()
            except Exception as e:              # noqa: BLE001 — radar ma trwać
                self._say(f"[!] błąd cyklu: {e}")
            # spanie w sekundowych krokach -> szybka reakcja na STOP
            for _ in range(max(5, int(self.interval))):
                if not self.running:
                    return
                time.sleep(1)

    # ------------------------------------------------------------ frazy

    def auto_queries(self) -> list[str]:
        """Frazy wygenerowane automatycznie z profili wykrytych kampanii.

        To serce „ Variant Radar”: zamiast szukać na ślepo, radar odpytuje
        publiczne źródła językiem WŁASNYCH kampanii (słowa kluczowe
        narracji + wizerunki osób), by wyłapać ich nowe odsłony.
        """
        out, seen = [], set()
        by_id = {f.id: f for f in (self.features or [])}
        for c in (self.clusters or []):
            if len(c.members) < 2:
                continue
            kws, personas = [], []
            for mid in c.members[:3]:
                f = by_id.get(mid)
                if not f:
                    continue
                kws += sorted(f.keywords)[:4]
                personas += sorted(f.personas)[:1]
            q = " ".join(dict.fromkeys(kws[:5] + personas[:1])).strip()
            if q and q not in seen:
                seen.add(q)
                out.append(q)
        return out[:4]

    def _all_queries(self) -> list[str]:
        manual = [q for q in self.profiles if q.strip()]
        auto = self.auto_queries()
        return list(dict.fromkeys(manual + auto))

    # ------------------------------------------------------------ źródła

    def _ddg_candidates(self, queries) -> list[tuple[str, str, str]]:
        out = []
        # rotacja: każdy skan bierze kolejne frazy (żeby nie odpytywać
        # wyłącznie pierwszej z listy)
        take = queries[1:] + queries[:1] if len(queries) > 1 else queries
        for q in take[:3]:
            try:
                urls = web_search(q, max_results=6)
                if not urls:
                    self._say(f"⋯ DuckDuckGo: brak wyników dla „{q[:40]}” "
                              "(ochrona anty-bot / fraza zbyt wąska)")
                out += [("duckduckgo", q, u) for u in urls]
            except Exception as e:              # noqa: BLE001
                self._say(f"[!] DuckDuckGo („{q[:40]}”): {e}")
        return out

    def _openphish_candidates(self) -> list[tuple[str, str, str]]:
        try:
            r = requests.get(OPENPHISH_FEED, timeout=20, headers=UA)
            urls = [l.strip() for l in r.text.splitlines()
                    if l.strip().startswith("http")][:40]
            rng = random.Random(int(time.time()))
            picks = rng.sample(urls, min(3, len(urls)))
            return [("openphish", "feed.txt", u) for u in picks]
        except Exception as e:                  # noqa: BLE001
            self._say(f"[!] OpenPhish: {e}")
            return []

    def _aa419_candidates(self) -> list[tuple[str, str, str]]:
        try:
            r = requests.get(AA419_LIST, timeout=20, headers=UA)
            urls = [m.rstrip(".,;)") for m in
                    re.findall(r"https?://[^\s\"'<>]+", r.text)]
            urls = [u for u in urls if "aa419.org" not in u][:40]
            rng = random.Random(int(time.time()) + 1)
            picks = rng.sample(urls, min(2, len(urls)))
            return [("aa419", "fakebanks", u) for u in picks]
        except Exception as e:                  # noqa: BLE001
            self._say(f"[!] AA419: {e}")
            return []

    def _meta_candidates(self) -> list[tuple[str, str, str]]:
        """Meta Ad Library (oficjalne API) — wymaga tokenu (UI)."""
        if not self.fb_token:
            return []
        out = []
        for q in self.profiles[:2]:
            if not q.strip():
                continue
            try:
                r = requests.get(META_AD_LIBRARY, params={
                    "search_terms": q,
                    "ad_reached_countries": "PL",
                    "fields": "ad_creative_link_urls,page_name",
                    "access_token": self.fb_token,
                }, timeout=20)
                data = r.json()
                if r.status_code != 200:
                    self._say(f"[!] Meta Ad Library: {data.get('error', {}).get('message', r.text)[:120]}")
                    continue
                for ad in data.get("data", []):
                    for u in (ad.get("ad_creative_link_urls") or []):
                        out.append(("meta", q, u))
            except Exception as e:              # noqa: BLE001
                self._say(f"[!] Meta Ad Library: {e}")
        return out

    def _candidates(self) -> list[tuple[str, str, str]]:
        queries = self._all_queries()
        pool: list[tuple[str, str, str]] = []
        if self.sources.get("duckduckgo"):
            pool += self._ddg_candidates(queries)
        if self.sources.get("openphish"):
            pool += self._openphish_candidates()
        if self.sources.get("aa419"):
            pool += self._aa419_candidates()
        if self.sources.get("meta"):
            pool += self._meta_candidates()

        # deduplikacja: nic, co już widziano lub co już jest w zbiorze
        known_urls = {getattr(m, "url", None) for m in (self.materials or [])}
        deduped, uniq = [], set()
        for src, q, u in pool:
            u = u.strip()
            if not u or u in self._seen_urls or u in known_urls or u in uniq:
                continue
            uniq.add(u)
            deduped.append((src, q, u))
        return deduped

    # ------------------------------------------------------------ skan

    def scan_once(self):
        """Jeden cykl: zbierz kandydatów, pobierz, porównaj, oceń."""
        with self._lock:
            if self._scanning:
                return
            self._scanning = True
        t0 = time.time()
        self._scan_no += 1
        rec = ScanRecord(ts=time.time(), seconds=0, queries=0, candidates=0,
                         processed=0, variants=0, new_patterns=0, errors=0)
        try:
            queries = self._all_queries()
            rec.queries = len(queries)
            cands = self._candidates()
            rec.candidates = len(cands)
            self._say(f"🛰  skan #{self._scan_no}: {len(cands)} kandydatów "
                      f"({', '.join(s for s in self.sources if self.sources.get(s))})")

            for src, q, url in cands[: self.max_per_scan]:
                self._seen_urls.add(url)
                try:
                    mid = f"SCAN{self._scan_no:03d}"
                    mat, feats = fetch_candidate(url, mid)
                except Exception as e:          # noqa: BLE001 — best effort
                    rec.errors += 1
                    self._say(f"[!] nieudane pobranie {url[:60]}: {e}")
                    continue

                if not (feats.available_modalities or mat.text):
                    rec.errors += 1
                    self._say(f"⋯ puste dane z {url[:60]} — pomijam "
                              "(tolerancja na dane niekompletne)")
                    continue

                best_cid, best, _top = assign_new_material(
                    self.features, self.clusters, feats, self.cfg)

                rec.processed += 1
                domain = (mat.url and
                          (urllib.parse.urlparse(mat.url).netloc or "")) or ""
                if best_cid:
                    status, cid = "variant", best_cid
                    rec.variants += 1
                    alert = {
                        "ts": time.time(), "cluster_id": cid, "source": src,
                        "query": q, "url": url, "score": best.score,
                        "strong": best.strong_signals[:3],
                    }
                    self.alerts.append(alert)
                    if len(self.alerts) > MAX_FINDS_KEPT:
                        del self.alerts[:len(self.alerts) - MAX_FINDS_KEPT]
                    self._say(f"🚨 NOWY WARIANT kampanii {cid}: {url[:60]} "
                              f"(podobieństwo {best.score:.0%})")
                else:
                    status, cid = "new", None
                    rec.new_patterns += 1
                    near = (f", najbliższe podobieństwo {_top[0].score:.0%}"
                            if _top else "")
                    self._say(f"🆕 nowy wzorzec (poza znanymi kampaniami): "
                              f"{url[:60]}{near}")

                find = RadarFind(
                    ts=time.time(), source=src, query=q, url=url,
                    status=status, cluster_id=cid,
                    score=(best.score if best else 0.0),
                    confidence=(best.confidence if best else 0.0),
                    strong_signals=(best.strong_signals if best else []),
                    reasons=(best.reasons if best else []),
                    material=mat, features=feats, domain=domain)
                self.finds.append(find)
                if len(self.finds) > MAX_FINDS_KEPT:
                    del self.finds[:len(self.finds) - MAX_FINDS_KEPT]
        finally:
            rec.seconds = round(time.time() - t0, 1)
            # każdy skan trafia do historii — metryka „SKANY” pokazuje,
            # że autopilot żyje, nawet gdy źródła milczą
            self.scans.append(rec)
            if len(self.scans) > MAX_LOG_KEPT:
                del self.scans[:len(self.scans) - MAX_LOG_KEPT]
            with self._lock:
                self._scanning = False
        return rec

    # ------------------------------------------------------------ podglądy

    def stats(self) -> dict:
        return {
            "scans": len(self.scans),
            "candidates": sum(s.candidates for s in self.scans),
            "processed": sum(s.processed for s in self.scans),
            "variants": sum(s.variants for s in self.scans),
            "new_patterns": sum(s.new_patterns for s in self.scans),
            "alerts": len(self.alerts),
        }
