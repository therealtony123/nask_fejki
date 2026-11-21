#!/usr/bin/env python3
"""Smoke test end-to-end rdzenia (bez GUI): ingest -> cechy -> klastry -> nowy materiał.

Uruchomienie: python3 tests/smoke.py   (z katalogu głównego projektu)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from kolekcjoner import (  # noqa: E402
    SimilarityConfig, assign_new_material, build_clusters, extract_features,
    from_jsonl,
)
from kolekcjoner.model import Material  # noqa: E402

EXPECTED = {
    frozenset({"a1", "a2", "a3", "a4", "a5"}),
    frozenset({"b1", "b2", "b3"}),
    frozenset({"c1", "c2", "c3"}),
    frozenset({"d1"}),
    frozenset({"d2"}),
}


def main() -> int:
    demo = ROOT / "data" / "demo_materials.jsonl"
    if not demo.exists():
        print("Brak zbioru demo — generuję (scripts/make_demo.py)...")
        import subprocess
        subprocess.run([sys.executable, str(ROOT / "scripts" / "make_demo.py")], check=True)

    mats = from_jsonl(demo)
    feats = [extract_features(m) for m in mats]
    assert len(feats) == 13, f"oczekiwano 13 materiałów, jest {len(feats)}"
    print(f"[ok] ingest + ekstrakcja cech: {len(feats)} materiałów")

    cfg = SimilarityConfig()
    clusters, links = build_clusters(feats, cfg)
    got = {frozenset(c.members) for c in clusters}
    assert got == EXPECTED, f"klastry niezgodne z oczekiwaniami:\n {got}\n != \n {EXPECTED}"
    print(f"[ok] klastrowanie: {len(clusters)} klastrów, {len(links)} powiązań "
          "(kampanie A/B/C + 2 samotne incydenty)")

    assert any(l.strong_signals for l in links), "brak twardych sygnałów w wynikach"
    assert all(l.reasons or l.strong_signals for l in links), "krawędź bez przesłanek"
    print("[ok] interpretowalność: każda krawędź ma przesłanki/twarde sygnały")

    # nowy wariant kampanii B -> powinien trafić do klastra B
    nf = extract_features(Material(
        id="NOWY", source="check", url="https://nowy-okafor-2025.xyz/lp",
        text="DIETA OKAFOR 2025: tabletki keto odchudzanie detoks cukrzyca",
        image_path=str(ROOT / "data" / "ads" / "ad_b1.png"),
        ns=["ns1.dns-simple.cc"], ip="185.77.9.99",
    ))
    cid, best, _ = assign_new_material(feats, clusters, nf, cfg)
    b_cluster = [c for c in clusters if "b1" in c.members][0]
    assert cid == b_cluster.cluster_id, f"wariant B trafił do {cid}, a nie {b_cluster.cluster_id}"
    print(f"[ok] nowy materiał (wariant B) przypisany do kampanii {cid}")

    # obcy materiał -> nowa kampania
    nf2 = extract_features(Material(
        id="NOWY2", source="check",
        text="Windykacja komornik sprawy sądowe Teraz"))
    cid2, _, _ = assign_new_material(feats, clusters, nf2, cfg)
    assert cid2 is None, f"obcy materiał błędnie przypisany do {cid2}"
    print("[ok] obcy materiał poprawnie uznany za nową kampanię")

    print("\nWSZYSTKIE TESTY PRZESZŁY ✔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
