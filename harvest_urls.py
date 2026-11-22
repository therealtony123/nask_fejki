#!/usr/bin/env python3
"""Pomocnik 2: zbieranie podejrzanych stron z OTWARTYCH źródeł (bez kluczy API)
i przekazywanie ich do identyfikacji przez pipeline KOLEKCJONERA FEJKÓW.

Źródła:
  - OpenPhish (publiczny feed phishingowych URL-i): https://openphish.com/feed.txt
  - AA419 (baza fałszywych banków/platform inwestycyjnych): https://db.aa419.org/fakebankslist.php

Każda strona zapisywana jako incydent (data/do_udostępnienia/harvest_<seq>/):
page.html + meta.json + pobrane obrazy (do cech wizualnych i twarzy).

Użycie:
  python harvest_urls.py --max 50 --run-pipeline
  python harvest_urls.py --source aa419 --pages 5 --max 60 --run-pipeline
"""
import argparse
import html as html_mod
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

sys.path.insert(0, str(Path(__file__).parent))

PROJ = Path(__file__).parent
DEFAULT_DATA = PROJ / "data"
DEFAULT_DB = PROJ / "kfk.sqlite"

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
IMG_CT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
          "image/gif": ".gif"}


def incident_dir(data_root: Path) -> Path:
    d = data_root / "do_udostępnienia"
    d.mkdir(parents=True, exist_ok=True)
    return d


def gather_candidates(source: str, pages: int) -> list:
    """Lista unikalnych URL-i kandydatów z otwartych źródeł."""
    cands = set()
    if source in ("openphish", "both"):
        try:
            r = requests.get("https://openphish.com/feed.txt", timeout=30)
            for line in r.text.splitlines():
                line = line.strip()
                if line.startswith("http"):
                    cands.add(("openphish", line))
        except Exception as e:
            print(f"[!] OpenPhish niedostępny: {e}")
    if source in ("aa419", "both"):
        for page in range(1, pages + 1):
            try:
                r = requests.get("https://db.aa419.org/fakebankslist.php",
                                 params={"page": page}, timeout=30)
                for m in re.findall(r"https?://[^\s\"'<>]+", r.text):
                    cands.add(("aa419", m.rstrip(".,;)")))
            except Exception as e:
                print(f"[!] AA419 strona {page} niedostępna: {e}")
            time.sleep(0.5)
    return sorted(cands, key=lambda x: x[1])


def fetch_page(src: str, url: str) -> dict:
    """Pobiera stronę: finalny HTML + przekierowania + obrazy. Zwraca metadane."""
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": UA},
                         allow_redirects=True, verify=True)
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}
    if r.status_code != 200 or not r.text or len(r.text) < 200:
        return {"ok": False, "error": f"status {r.status_code} / pusto"}
    redirects = [[h.status_code, h.url] for h in r.history]
    # obrazy
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "lxml")
        img_urls = []
        for im in soup.find_all("img", src=True)[:15]:
            img_urls.append(urljoin(r.url, im["src"]))
    except Exception:
        img_urls = []
    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", r.text, re.S | re.I)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()[:200]
    return {"ok": True, "url": url, "final": r.url, "html": r.text,
            "redirects": redirects, "img_urls": img_urls, "title": title,
            "ct": r.headers.get("content-type", "")}


def save_incident(meta: dict, html_text: str, data_root: Path, seq: int):
    base = incident_dir(data_root)
    folder = base / f"harvest_{seq:04d}"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "page.html").write_text(html_text, encoding="utf-8", errors="replace")
    (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    # pobranie obrazów (cechy wizualne + twarze)
    for i, img_url in enumerate(meta.get("img_urls", [])[:12]):
        try:
            ir = requests.get(img_url, timeout=8, headers={"User-Agent": UA}, verify=True)
            ext = IMG_CT.get(ir.headers.get("content-type", "").split(";")[0].strip())
            if ir.status_code == 200 and ext:
                (folder / f"img_{i:02d}{ext}").write_bytes(ir.content)
        except Exception:
            continue


def main():
    ap = argparse.ArgumentParser(description="Harvester: otwarte źródła -> KOLEKCJONER FEJKÓW")
    ap.add_argument("--source", choices=["openphish", "aa419", "both"], default="both")
    ap.add_argument("--pages", type=int, default=3, help="Strony listy AA419")
    ap.add_argument("--max", type=int, default=50, help="Maks. unikalnych domen do pobrania")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--data", default=str(DEFAULT_DATA))
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--threshold", type=float, default=0.25)
    ap.add_argument("--join", type=float, default=0.30)
    ap.add_argument("--run-pipeline", action="store_true")
    args = ap.parse_args()

    data_root = Path(args.data)
    db = Path(args.db)

    # 1. kandydaci
    cands = gather_candidates(args.source, args.pages)
    # jedna domena rejestrowalna raz
    seen_dom = set()
    unique = []
    for src, url in cands:
        host = urlparse(url).hostname or ""
        parts = host.split(".")
        reg = ".".join(parts[-2:]) if len(parts) >= 2 else host
        if reg and reg not in seen_dom:
            seen_dom.add(reg)
            unique.append((src, url))
    unique = unique[: args.max]
    print(f"[1/4] Kandydaci: {len(unique)} unikalnych domen "
          f"(źródła: {args.source}, z {len(cands)} surowych wpisów)")

    # 2. pobieranie równoległe
    results = []
    ok_meta = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(fetch_page, src, url): (src, url) for src, url in unique}
        for fut in as_completed(futs):
            src, url = futs[fut]
            res = fut.result()
            if res.get("ok"):
                res["source"] = src
                ok_meta.append(res)
            else:
                results.append((url, res.get("error")))
    ok_meta.sort(key=lambda m: m["url"])
    print(f"[2/4] Pobrano {len(ok_meta)}/{len(unique)} stron "
          f"w {time.time() - t0:.0f}s (niedostępnych: {len(results)})")
    for u, e in results[:8]:
        print(f"      ✗ {u[:60]} — {e}")

    # 3. zapis jako incydenty
    seq = 1
    base = incident_dir(data_root)
    existing = {d.name for d in base.iterdir() if d.is_dir() and d.name.startswith("harvest_")}
    while f"harvest_{seq:04d}" in existing:
        seq += 1
    new_ids = []
    for meta in ok_meta:
        fid = f"harvest_{seq:04d}"
        meta_out = {"source": meta["source"], "url": meta["url"], "final_url": meta["final"],
                    "redirects": meta["redirects"], "title": meta["title"],
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "img_urls": meta["img_urls"]}
        save_incident(meta_out, meta["html"], data_root, seq)
        new_ids.append(fid)
        print(f"      + {fid} | {meta['final'][:70]}")
        seq += 1
    print(f"[3/4] Zapisano {len(new_ids)} incydentów")

    if not new_ids:
        return

    # 4. pipeline + identyfikacja
    if args.run_pipeline:
        from kfk import Store, Tfidf, pair_similarity, scan, extract_incident
        from pipeline import run
        # zbiór bazowy (przed zebraniem): bez harvest_* i ad_*
        originals = []
        if db.is_file() and db.stat().st_size > 0:
            try:
                originals = [x for x in Store(db).load_incidents()
                             if not x["id"].startswith(("harvest_", "ad_"))]
            except Exception:
                originals = []
        print(f"[4/4] Uruchamiam pipeline (zbiór bazowy: {len(originals)} incydentów)…")
        run(str(data_root), str(db), args.threshold, verbose=False)
        # cechy nowych incydentów
        inc_map = {i["id"]: i for i in scan(data_root)}
        new_feats = [extract_incident(inc_map[i]) for i in new_ids if i in inc_map]
        clusters = Store(db).load_clusters()
        tfidf = Tfidf()
        tfidf.fit([x["text"].get("body_norm", "") for x in originals])
        print("\n=== IDENTYFIKACJA POZYSKANYCH STRON ===")
        n_assigned = n_new = 0
        for nf in new_feats:
            best = None
            for s in originals:
                sim = pair_similarity(nf, s, tfidf)
                if best is None or sim["score"] > best["score"]:
                    best = {"id": s["id"], "title": s["text"].get("title", ""), **sim}
            t = (nf["text"].get("title") or nf["path"])[:60]
            if best and best["score"] >= args.join:
                n_assigned += 1
                cl = next((c["cluster_id"] for c in clusters
                           if best["id"] in c["members"]), "?")
                print(f"  {nf['id']} ({t}):")
                print(f"    🚨 PRZYPISANO DO KAMPANII {cl} — incydent {best['id']}, "
                      f"score={best['score']:.3f}")
                for ev in best["evidence"][:2]:
                    print(f"        • {ev}")
            else:
                n_new += 1
                sc = f"{best['score']:.3f}" if best else "—"
                print(f"  {nf['id']} ({t}): 🔶 NOWY WZORZEC (najlepsze {sc})")
        print(f"\nPodsumowanie: {n_assigned} przypisanych do znanych kampanii, "
              f"{n_new} nowych wzorców.")
    else:
        print("[4/4] Pominięto identyfikację (dodaj --run-pipeline).")


if __name__ == "__main__":
    main()
