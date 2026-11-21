#!/usr/bin/env python3
"""KOLEKCJONER FEJKÓW — pipeline: ingest -> cechy -> podobieństwo -> kampanie.

Użycie:
  python pipeline.py [katalog_danych] [--db sciezka.sqlite] [--threshold 0.25]
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from kfk import (Tfidf, Store, build_edges, cluster_graph, extract_incident,
                 scan)
from kfk.stix import build_bundle, export_ioc, incident_timespan


def run(data_root, db_path, threshold=0.25, verbose=True):
    t0 = time.time()
    incidents = scan(data_root)
    if not incidents:
        raise SystemExit(f"Brak incydentów w {data_root} (szukam katalogu do_udostępnienia/)")
    if verbose:
        print(f"[1/4] Zeskanowano {len(incidents)} incydentów")
    feats = []
    for i, inc in enumerate(incidents, 1):
        f = extract_incident(inc)
        feats.append(f)
        if verbose:
            print(f"      [{i}/{len(incidents)}] {inc['id']}: "
                  f"{len(f['images'])} obrazów, {len(f['infra']['domains'])} domen, "
                  f"tytuł: {f['text']['title'][:60] or '(brak)'}")
    tfidf = Tfidf()
    texts = [f["text"].get("body_norm", "") or f["text"].get("title_norm", "")
             for f in feats]
    tfidf.fit(texts)
    if verbose:
        print(f"[2/4] TF-IDF: {len(tfidf.df)} n-gramów w słowniku")
    edges = build_edges(feats, tfidf, threshold)
    if verbose:
        print(f"[3/4] Krawędzie: {len(edges)} (próg {threshold})")
        for e in edges[:15]:
            print(f"      {e['a']} <-> {e['b']}  score={e['score']:.3f} "
                  f"{'[TWARDE]' if e['hard'] else ''}")
            for ev in e["evidence"][:3]:
                print(f"          • {ev}")
    clusters = cluster_graph([f["id"] for f in feats], edges, threshold)
    # oś czasu kampanii (mtime plików incydentu)
    spans = {f["id"]: incident_timespan(f["path"]) for f in feats}
    for c in clusters:
        first = min((spans[m][0] for m in c["members"] if spans[m][0]), default=None)
        last = max((spans[m][1] for m in c["members"] if spans[m][1]), default=None)
        c["first_seen"], c["last_seen"] = first, last
    if verbose:
        print(f"[4/4] Kampanie: {len(clusters)}")
        for c in clusters:
            print(f"      {c['cluster_id']}: {c['members']}  ({c['label'][:80]})")
    store = Store(db_path)
    store.save_incidents(feats)
    store.save_edges(edges)
    store.save_clusters(clusters)
    # eksport grafu dla UI
    graph = {
        "nodes": [{"id": f["id"], "title": f["text"]["title"][:80],
                   "first_seen": spans[f["id"]][0], "last_seen": spans[f["id"]][1],
                   "cluster": next((c["cluster_id"] for c in clusters if f["id"] in c["members"]), None),
                   "domains": f["infra"]["registrable"],
                   "faces": [p["name"] for p in f.get("faces", {}).get("persons", [])],
                   "trackers": f["infra"]["tracker_ids"],
                   "n_images": len(f["images"]), "n_files": f.get("n_files", 0)}
                  for f in feats],
        "edges": [{"a": e["a"], "b": e["b"], "score": e["score"], "hard": e["hard"],
                   "evidence": e["evidence"]} for e in edges],
        "clusters": clusters,
    }
    out = Path(db_path).with_suffix(".graph.json")
    out.write_text(json.dumps(graph, ensure_ascii=False, indent=1), encoding="utf-8")
    stix_path = Path(db_path).with_suffix(".stix.json")
    bundle = build_bundle(feats, clusters, edges)
    stix_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=1), encoding="utf-8")
    ioc_path = Path(db_path).with_suffix(".ioc.csv")
    n_ioc = export_ioc(feats, clusters, str(ioc_path))
    if verbose:
        print(f"\nGotowe w {time.time() - t0:.1f}s | baza: {db_path} | graf: {out}")
        print(f"STIX 2.1: {stix_path} ({len(bundle['objects'])} obiektów) | "
              f"IoC: {ioc_path} ({n_ioc} wpisów)")
    return {"incidents": len(feats), "edges": len(edges), "clusters": len(clusters),
            "db": str(db_path)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="KOLEKCJONER FEJKÓW — pipeline analizy")
    ap.add_argument("data", nargs="?", default=str(Path.home() / "kolekcjoner-fejkow" / "data"))
    ap.add_argument("--db", default=str(Path.home() / "kolekcjoner-fejkow" / "kfk.sqlite"))
    ap.add_argument("--threshold", type=float, default=0.25)
    args = ap.parse_args()
    run(args.data, args.db, args.threshold)