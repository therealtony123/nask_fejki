"""Podobieństwo ważone multi-widok z listą przesłanek (dowodów) dla każdej krawędzi."""
import difflib
import math
import re
from collections import Counter
from itertools import combinations

from .features import hamming

# wagi widoków (suma normalizowana do widoków dostępnych po obu stronach)
VIEW_WEIGHTS = {
    "title": 0.30,      # identyczny/prawie identyczny tytuł — silny sygnał tej samej kampanii
    "text": 0.15,       # podobieństwo treści (TF-IDF n-gramów znakowych)
    "images": 0.25,     # duplikaty i warianty graficzne (pHash/dHash)
    "infra": 0.20,      # wspólne domeny rejestrowalne
    "trackers": 0.30,   # te same identyfikatory analityki (GA/Pixel/GTM) — bardzo silny sygnał
    "structure": 0.10,  # wspólny szablon HTML (klasy CSS, skrypty, favicon)
    "domain_pattern": 0.08,  # wspólny wzorzec nazw domen (TLD + schemat nazewniczy)
}
EDGE_THRESHOLD = 0.25       # próg tworzenia krawędzi
PHASH_MAX_DIST = 12
DHASH_MAX_DIST = 8


class Tfidf:
    """Lekki TF-IDF na n-gramach znakowych (odporny na polską fleksję)."""

    def __init__(self, ngram_range=(2, 4), min_df=2):
        self.ngram_range = ngram_range
        self.min_df = min_df
        self.df = Counter()

    def _ngrams(self, s: str):
        s = re.sub(r"[^a-z0-9ąćęłńóśźż]+", "", s.lower())
        for n in range(self.ngram_range[0], self.ngram_range[1] + 1):
            for i in range(len(s) - n + 1):
                yield s[i:i + n]

    def fit(self, texts):
        self.df = Counter()
        for t in texts:
            if not t:
                continue
            for g in set(self._ngrams(t)):
                self.df[g] += 1
        self.df = Counter({g: c for g, c in self.df.items() if c >= self.min_df})

    def transform(self, text: str):
        if not text:
            return {}
        tf = Counter(self._ngrams(text))
        n = len(self.df)
        vec = {g: c * (1 + math.log((n + 1) / (self.df[g] + 1)))
               for g, c in tf.items() if g in self.df}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {g: v / norm for g, v in vec.items()}

    @staticmethod
    def cosine(v1: dict, v2: dict):
        if not v1 or not v2:
            return 0.0
        small, big = (v1, v2) if len(v1) <= len(v2) else (v2, v1)
        dot = sum(w * big.get(g, 0.0) for g, w in small.items())
        return dot


def _jac(a, b):
    if not a or not b:
        return None
    sa, sb = set(a), set(b)
    u = len(sa | sb)
    return len(sa & sb) / u if u else None


def view_scores(fa: dict, fb: dict, tfidf: Tfidf) -> tuple:
    """Liczy per-widok (wynik 0..1, przesłanki). Zwraca (views, hard_evidence)."""
    views = {}

    # 1. tytuł
    ta, tb = fa["text"].get("title_norm"), fb["text"].get("title_norm")
    if ta and tb:
        if ta == tb:
            views["title"] = (1.0, [f"identyczny tytuł: «{fa['text']['title'][:90]}»"])
        else:
            r = difflib.SequenceMatcher(None, ta, tb).ratio()
            if r >= 0.85:
                views["title"] = (0.9, [f"prawie identyczny tytuł (ratio {r:.2f})"])
            else:
                views["title"] = (0.0, [])
    # 2. tekst
    ba, bb = fa["text"].get("body_norm"), fb["text"].get("body_norm")
    if ba and bb:
        c = tfidf.cosine(tfidf.transform(ba), tfidf.transform(bb))
        if c > 0.10:
            views["text"] = (round(min(c * 1.5, 1.0), 3),
                             [f"podobieństwo treści: cos={c:.2f}"])
        else:
            views["text"] = (0.0, [])
    # 3. obrazy — duplikaty/warianty przez hashe percepcyjne
    ia, ib = fa["images"], fb["images"]
    if ia and ib:
        matched = []
        for x in ia:
            for y in ib:
                pd = hamming(x.get("phash"), y.get("phash"))
                dd = hamming(x.get("dhash"), y.get("dhash"))
                if pd is None and dd is None:
                    continue
                best = min([d for d in (pd, dd) if d is not None])
                if (pd is not None and pd <= PHASH_MAX_DIST) or (dd is not None and dd <= DHASH_MAX_DIST):
                    matched.append((x["path"], y["path"], best))
        if matched:
            score = min(1.0, len(matched) / min(len(ia), len(ib)))
            ev = [f"{len(matched)} pasujących obrazów, np. {m[0].split('/')[-1]} ≈ {m[1].split('/')[-1]} (odl. {m[2]})"
                  for m in matched[:3]]
            views["images"] = (round(score, 3), ev)
        else:
            views["images"] = (0.0, [])
    # 4. infrastruktura — wspólne domeny rejestrowalne
    da, db = fa["infra"]["registrable"], fb["infra"]["registrable"]
    j = _jac(da, db)
    if j is not None:
        if j > 0:
            shared = sorted(set(da) & set(db))
            views["infra"] = (round(j, 3), [f"wspólne domeny: {', '.join(shared[:8])}"])
        else:
            views["infra"] = (0.0, [])
    # 5. trackery — te same ID analityki
    ta_ids, tb_ids = set(fa["infra"]["tracker_ids"]), set(fb["infra"]["tracker_ids"])
    if ta_ids or tb_ids:
        shared = ta_ids & tb_ids
        if shared:
            views["trackers"] = (1.0, [f"te same trackery: {', '.join(sorted(shared)[:6])}"])
        else:
            views["trackers"] = (0.0, [])
    # 6. struktura — wspólne klasy CSS / skrypty
    ca, cb = fa["structure"]["css_classes"], fb["structure"]["css_classes"]
    jc = _jac(ca, cb)
    if jc is not None:
        if jc > 0:
            views["structure"] = (round(min(jc * 2, 1.0), 3),
                                  [f"wspólny szablon HTML (jaccard klas CSS: {jc:.2f})"])
        else:
            views["structure"] = (0.0, [])
    # 7. wzorce nazw domen — słaby sygnał, pomocny w połączeniu z innymi
    pa = [d["pattern"] for d in fa["infra"].get("domain_patterns", [])]
    pb = [d["pattern"] for d in fb["infra"].get("domain_patterns", [])]
    if pa and pb:
        shared = set(pa) & set(pb)
        if shared:
            ex_a = next(d for d in fa["infra"]["domain_patterns"] if d["pattern"] in shared)
            ex_b = next(d for d in fb["infra"]["domain_patterns"] if d["pattern"] in shared)
            views["domain_pattern"] = (
                0.5,
                [f"wspólny wzorzec nazw domen: {ex_a['domain']} ≈ {ex_b['domain']} "
                 f"({ex_a['tld']}, {','.join(ex_a['classes'])})"],
            )
        else:
            views["domain_pattern"] = (0.0, [])
    # twarde przesłanki
    hard = []
    if ta and tb and ta == tb:
        hard.append("ten sam tytuł")
    if fa["infra"]["tracker_ids"] and set(fa["infra"]["tracker_ids"]) & set(fb["infra"]["tracker_ids"]):
        hard.append("te same ID analityki")
    if "images" in views and views["images"][0] >= 0.5:
        hard.append("warianty graficzne")
    return views, hard


def negative_evidence(fa: dict, fb: dict, tfidf: Tfidf) -> list:
    """Przesłanki PRZECIWKO połączeniu — widoki z danymi po obu stronach, ale zerowym
    wynikiem. Pokazują analitykowi, dlaczego materiały pozostały rozdzielone
    (odporność na fałszywe połączenia)."""
    views, _ = view_scores(fa, fb, tfidf)
    neg = []
    if "title" in views and views["title"][0] == 0:
        neg.append(f"różne tytuły: «{(fa['text'].get('title') or '')[:60]}» vs "
                   f"«{(fb['text'].get('title') or '')[:60]}»")
    if "infra" in views and views["infra"][0] == 0:
        neg.append("brak wspólnych domen rejestrowalnych")
    if "trackers" in views and views["trackers"][0] == 0:
        neg.append("różne identyfikatory analityki (brak wspólnych GA/Pixel/GTM)")
    if "images" in views and views["images"][0] == 0:
        neg.append("brak pasujących wariantów graficznych (odległość hashów > próg)")
    if "structure" in views and views["structure"][0] == 0:
        neg.append("różne szablony HTML (rozłączne klasy CSS)")
    if "domain_pattern" in views and views["domain_pattern"][0] == 0:
        neg.append("różne wzorce nazw domen (inne TLD/schematy nazewnicze)")
    return neg


def pair_similarity(fa: dict, fb: dict, tfidf: Tfidf) -> dict:
    """Ważona suma widoków (wagi normalizowane do widoków dostępnych w obu materiałach)."""
    views, hard = view_scores(fa, fb, tfidf)
    if not views:
        return {"score": 0.0, "evidence": [], "per_view": {}, "hard": False}
    wsum = sum(VIEW_WEIGHTS[v] for v in views)
    score = sum(VIEW_WEIGHTS[v] * s for v, (s, _) in views.items()) / wsum if wsum else 0.0
    evidence = [e for _, ev in views.values() for e in ev]
    per_view = {v: {"score": s, "evidence": ev} for v, (s, ev) in views.items()}
    return {
        "score": round(score, 4),
        "evidence": evidence,
        "per_view": per_view,
        "hard": bool(hard),
        "hard_evidence": hard,
    }


def build_edges(feats: list, tfidf: Tfidf, threshold: float = EDGE_THRESHOLD):
    """Wszystkie pary incydentów -> krawędzie powyżej progu."""
    edges = []
    for fa, fb in combinations(feats, 2):
        r = pair_similarity(fa, fb, tfidf)
        if r["score"] >= threshold:
            edges.append({"a": fa["id"], "b": fb["id"], **r})
    edges.sort(key=lambda e: -e["score"])
    return edges