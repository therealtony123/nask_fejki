#!/usr/bin/env python3
"""Smoke test end-to-end rdzenia pipeline: ingest -> cechy -> krawędzie -> klastry -> nowy materiał.

Uruchomienie (z katalogu repo):  .venv/bin/python tests/smoke.py
Sukces = exit 0 + "SMOKE OK" na stdout.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from kfk import (  # noqa: E402
    scan,
    extract_incident,
    Tfidf,
    build_edges,
    cluster_graph,
    assign_new_incident,
    extract_from_url_text,
)

FIXTURES = REPO_ROOT / "tests" / "fixtures"
TITLE_AB = "Rewolucyjny lek na stawy — zamów teraz"
TRACKER_AB = "G-ABCDEF1234"
TITLE_C = "Tanie kredyty online"
TRACKER_C = "G-ZZZZZZZZZZ"
EDGE_THRESHOLD = 0.25
JOIN_THRESHOLD = 0.30
NEW_ID = "NEW"


def new_material(title, tracker, body):
    """Cechy „nowego materiału" zbudowane z syntetycznego HTML (jak w demo pipeline)."""
    html = (
        "<!DOCTYPE html><html lang=\"pl\"><head><meta charset=\"utf-8\">"
        "<title>{title}</title>"
        "<script async src=\"https://www.googletagmanager.com/gtag/js?id={tracker}\"></script>"
        "<script>window.dataLayer=window.dataLayer||[];"
        "function gtag(){{dataLayer.push(arguments);}}"
        "gtag('js', new Date());gtag('config', '{tracker}');</script>"
        "</head><body><h1>{title}</h1><p>{body}</p></body></html>"
    ).format(title=title, tracker=tracker, body=body)
    return extract_from_url_text("https://przyklad.example/nowy-material", html, [])


def main():
    # 1. ingest — skan fixtury
    incidents = scan(FIXTURES)
    assert len(incidents) == 3, f"oczekiwano 3 incydentów, jest {len(incidents)}: {[i['id'] for i in incidents]}"
    by_id = {inc["id"]: inc for inc in incidents}
    assert set(by_id) == {"a", "b", "c"}, f"nieoczekiwane id incydentów: {sorted(by_id)}"
    for inc in incidents:
        assert len(inc["html"]) == 1 and inc["n_files"] == 1, f"zła struktura incydentu {inc['id']}"

    # 2. cechy
    feats = {i: extract_incident(by_id[i]) for i in ("a", "b", "c")}
    fa, fb, fc = feats["a"], feats["b"], feats["c"]
    assert fa["text"]["title"] == TITLE_AB
    assert fb["text"]["title"] == TITLE_AB
    assert fc["text"]["title"] == TITLE_C
    for name, f in (("a", fa), ("b", fb), ("c", fc)):
        assert len(f["text"]["body_norm"]) >= 200, f"body_norm incydentu {name} za krótkie ({len(f['text']['body_norm'])} znaków)"
    assert TRACKER_AB in fa["infra"]["tracker_ids"], fa["infra"]["tracker_ids"]
    assert TRACKER_AB in fb["infra"]["tracker_ids"], fb["infra"]["tracker_ids"]
    assert TRACKER_C in fc["infra"]["tracker_ids"], fc["infra"]["tracker_ids"]

    # 3. krawędzie
    tfidf = Tfidf()
    tfidf.fit([f["text"].get("body_norm", "") for f in feats.values()])
    edges = build_edges([fa, fb, fc], tfidf, EDGE_THRESHOLD)
    by_pair = {frozenset((e["a"], e["b"])): e for e in edges}
    assert frozenset(("a", "b")) in by_pair, f"brak krawędzi a-b; krawędzie: {[(e['a'], e['b'], e['score']) for e in edges]}"
    ab = by_pair[frozenset(("a", "b"))]
    assert ab["hard"] is True, f"krawędź a-b nie jest twarda: {ab}"
    assert ab["score"] >= EDGE_THRESHOLD, f"krawędź a-b poniżej progu: {ab['score']}"
    assert frozenset(("a", "c")) not in by_pair, f"nieoczekiwana krawędź a-c: {by_pair.get(frozenset(('a', 'c')))}"
    assert frozenset(("b", "c")) not in by_pair, f"nieoczekiwana krawędź b-c: {by_pair.get(frozenset(('b', 'c')))}"

    # 4. klastry
    clusters = cluster_graph([f["id"] for f in (fa, fb, fc)], edges, EDGE_THRESHOLD)
    assert len(clusters) == 2, f"oczekiwano 2 klastrów, jest {len(clusters)}: {[(c['cluster_id'], c['members']) for c in clusters]}"
    cluster_of = {}
    for c in clusters:
        for m in c["members"]:
            cluster_of[m] = c["cluster_id"]
    assert cluster_of["a"] == cluster_of["b"], f"a i b w różnych klastrach: {cluster_of}"
    assert cluster_of["c"] != cluster_of["a"], f"c w tym samym klastrze co a: {cluster_of}"
    cl_c = next(c for c in clusters if c["cluster_id"] == cluster_of["c"])
    assert cl_c["members"] == ["c"], f"klaster c nie jest singletonem: {cl_c['members']}"

    # 5. nowy materiał — przypisanie do znanej kampanii
    new1 = new_material(
        TITLE_AB, TRACKER_AB,
        "Rewolucyjna metoda leczenia stawów opracowana przez zespół polskich naukowców przynosi ulgę "
        "już po kilku dniach. Naturalny preparat regeneruje chrząstkę stawową, likwiduje stan zapalny "
        "oraz ból kolan, bioder i kręgosłupa bez operacji i bez skutków ubocznych. Kuracja oparta na "
        "kolagenie morskim, glukozaminie i kwasie hialuronowym przywraca pełną sprawność ruchową w "
        "zaledwie trzy tygodnie. Tysiące zadowolonych pacjentów potwierdza spektakularne efekty. Zamów "
        "jeszcze dziś ze specjalnym rabatem pięćdziesiąt procent dla pierwszych stu klientów.",
    )
    edges_to_new1 = [e for e in build_edges([new1, fa, fb, fc], tfidf, 0.0) if e["a"] == NEW_ID]
    res1 = assign_new_incident(new1, [fa, fb, fc], edges_to_new1, JOIN_THRESHOLD)
    assert res1["verdict"].startswith("PRZYPISANO"), f"verdict 1: {res1['verdict']!r}"

    # 6. nowy materiał — zupełnie obcy
    new2 = new_material(
        "Zarabiaj na kryptowalutach bez ryzyka", "G-OTHERZZ9999",
        "Kupuj i sprzedawaj kryptowaluty w kilka sekund dzięki naszej autorskiej platformie handlowej. "
        "Sztuczna inteligencja analizuje rynek dwadzieścia cztery godziny na dobę i generuje zyski nawet "
        "podczas snu. Dołącz do tysięcy inwestorów, którzy pomnożyli swój kapitał w ciągu miesiąca. "
        "Wypłacaj środki na kartę natychmiast, bez prowizji i bez ukrytych opłat. Zarejestruj darmowe "
        "konto i odbierz bonus startowy o wartości dwustu złotych już teraz.",
    )
    edges_to_new2 = [e for e in build_edges([new2, fa, fb, fc], tfidf, 0.0) if e["a"] == NEW_ID]
    res2 = assign_new_incident(new2, [fa, fb, fc], edges_to_new2, JOIN_THRESHOLD)
    assert res2["verdict"].startswith("NOWA"), f"verdict 2: {res2['verdict']!r}"

    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
