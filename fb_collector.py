#!/usr/bin/env python3
"""Pomocnik: zbiera reklamy z Meta Ad Library i przekazuje je do identyfikacji.

Każda reklama jest zapisywana jako nowy incydent w zbiorze
(data/do_udostępnienia/ad_<ID>/{ad.html, ad.json}), po czym opcjonalnie
uruchamiany jest pipeline KOLEKCJONERA FEJKÓW, który porównuje je ze znanymi
kampaniami i raportuje: PRZYPISANO DO KAMPANII / NOWY WZORZEC.

Przykłady:
  # z tokenem (Graph API, uprawnienie ads_read):
  python fb_collector.py --token TWOJ_TOKEN --terms "zarabiaj z domu" --run-pipeline
  META_TOKEN=... python fb_collector.py --terms "inwestycja" --terms "suplement" --pages 3

  # tryb offline (demo bez tokena):
  python fb_collector.py --from-file samples/meta_ads_sample.json --run-pipeline
"""
import argparse
import getpass
import html
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from kfk.adlibrary import ad_text, search_ads
from kfk import Store

PROJ = Path(__file__).parent
DEFAULT_DATA = PROJ / "data"
DEFAULT_DB = PROJ / "kfk.sqlite"


def incident_dir(data_root: Path) -> Path:
    d = data_root / "do_udostępnienia"
    d.mkdir(parents=True, exist_ok=True)
    return d


def known_ad_ids(data_root: Path) -> set:
    """ID reklam już obecnych w zbiorze (deduplikacja)."""
    ids = set()
    base = incident_dir(data_root)
    for d in base.iterdir():
        if d.is_dir() and d.name.startswith("ad_"):
            try:
                j = json.loads((d / "ad.json").read_text(encoding="utf-8"))
                if j.get("id"):
                    ids.add(str(j["id"]))
            except Exception:
                pass
    return ids


def ad_to_html(ad: dict) -> str:
    """Buduje mini-stronę HTML z treścią reklamy — wejście dla ekstraktora cech."""
    title = (ad.get("ad_creative_link_titles") or [""])[0] or (ad.get("page_name") or "reklama")
    bodies = ad.get("ad_creative_bodies") or []
    descs = ad.get("ad_creative_link_descriptions") or []
    body_html = "\n".join(f"<p>{html.escape(b)}</p>" for b in bodies)
    desc_html = "\n".join(f"<p>{html.escape(d)}</p>" for d in descs)
    snap = ad.get("ad_snapshot_url") or ""
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape((bodies[0] if bodies else title)[:300])}">
<meta name="keywords" content="meta ad library, {html.escape(ad.get('page_name') or '')}">
</head><body>
<h1>{html.escape(title)}</h1>
{body_html}
{desc_html}
<p><b>Strona reklamodawcy:</b> {html.escape(ad.get('page_name') or '')}</p>
<p><b>ID reklamy:</b> {html.escape(str(ad.get('id') or ''))}</p>
<p><b>Publikacja od:</b> {html.escape((ad.get('ad_delivery_start_time') or '')[:10])}</p>
<a href="{html.escape(snap)}">Zobacz w bibliotece reklam Meta</a>
</body></html>
"""


def save_ad(ad: dict, data_root: Path) -> Path:
    base = incident_dir(data_root)
    folder = base / f"ad_{ad.get('id')}"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "ad.json").write_text(json.dumps(ad, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
    (folder / "ad.html").write_text(ad_to_html(ad), encoding="utf-8")
    return folder


def fetch_ads(token: str, terms: list, limit: int, pages: int, countries: list,
              verbose: bool) -> list:
    """Pobiera reklamy z paginacją (kursor 'after')."""
    all_ads = []
    after = None
    for page in range(1, pages + 1):
        try:
            resp = search_ads(token, " ".join(terms), countries, limit=limit, after=after)
        except Exception as e:
            print(f"[!] Błąd zapytania (strona {page}): {e}")
            break
        batch = resp.get("data", [])
        all_ads.extend(batch)
        if verbose:
            print(f"    strona {page}: +{len(batch)} reklam")
        after = (resp.get("paging") or {}).get("cursors", {}).get("after")
        if not after or len(batch) < limit:
            break
        time.sleep(1.0)  # uprzejmość dla API
    return all_ads


def report_identification(ads: list, originals: list, clusters: list,
                          join_threshold: float = 0.30):
    """Analiza nowych reklam względem zbioru SPRZED zebrania (jak w zakładce
    'Nowy materiał'): przypisanie do kampanii lub nowy wzorzec."""
    if not originals:
        print("Brak wcześniej przetworzonego zbioru — wszystkie reklamy to nowe wzorce.")
        return
    from kfk.adlibrary import compare_ads
    from kfk import Tfidf
    tfidf = Tfidf()
    tfidf.fit([x["text"].get("body_norm", "") for x in originals])
    rows = compare_ads({"data": ads}, originals, tfidf)
    print("\n=== IDENTYFIKACJA NOWYCH REKLAM ===")
    for row in rows:
        b = row["best"]
        title = row["text"][:70]
        if b and b["score"] >= join_threshold:
            cl = next((c["cluster_id"] for c in clusters if b["id"] in c["members"]), "?")
            print(f"  ad_{row['ad_id']} ({title}):")
            print(f"    🚨 PRZYPISANO DO KAMPANII {cl} — najbliższy incydent {b['id']}, "
                  f"score={b['score']:.3f}")
            for ev in b["evidence"][:3]:
                print(f"        • {ev}")
        else:
            sc = f"{b['score']:.3f}" if b else "—"
            print(f"  ad_{row['ad_id']} ({title}):")
            print(f"    🔶 NOWY WZORZEC — najlepsze dopasowanie {sc} "
                  f"< próg {join_threshold:.2f} (brak przypisania do znanych kampanii)")


def main():
    ap = argparse.ArgumentParser(description="Pomocnik: Meta Ad Library -> KOLEKCJONER FEJKÓW")
    ap.add_argument("--token", default=os.environ.get("META_TOKEN", ""),
                    help="Token Graph API (env: META_TOKEN)")
    ap.add_argument("--terms", action="append", default=[],
                    help="Słowa kluczowe (można powtarzać); razem łączone w jedno zapytanie")
    ap.add_argument("--from-file", default=None,
                    help="Import reklam z pliku JSON (odpowiedź ads_archive) — tryb offline")
    ap.add_argument("--limit", type=int, default=30, help="Limit reklam na stronę")
    ap.add_argument("--pages", type=int, default=1, help="Liczba stron paginacji")
    ap.add_argument("--countries", default="PL", help="Kraje emisji, np. PL,DE (JSON lub lista)")
    ap.add_argument("--data", default=str(DEFAULT_DATA))
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--threshold", type=float, default=0.25)
    ap.add_argument("--join", type=float, default=0.30,
                    help="Próg przypisania reklamy do kampanii (identyfikacja)")
    ap.add_argument("--run-pipeline", action="store_true",
                    help="Po zebraniu uruchom pipeline i raportuj identyfikację")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    data_root = Path(args.data)
    db = Path(args.db)

    # 1. pozyskanie reklam
    if args.from_file:
        src = Path(args.from_file)
        if not src.is_file():
            raise SystemExit(f"Brak pliku {src}")
        payload = json.loads(src.read_text(encoding="utf-8"))
        ads = payload.get("data", [])
        print(f"[1/4] Wczytano {len(ads)} reklam z {src}")
    else:
        token = args.token
        if not token:
            token = getpass.getpass("Token Meta Ad Library (Graph API): ").strip()
        if not token:
            raise SystemExit("Brak tokena. Użyj --token, META_TOKEN lub --from-file.")
        if not args.terms:
            raise SystemExit("Podaj --terms (słowa kluczowe).")
        try:
            countries = json.loads(args.countries)
        except Exception:
            countries = [c.strip() for c in args.countries.split(",") if c.strip()]
        print(f"[1/4] Szukam reklam: \"{' '.join(args.terms)}\" "
              f"(kraje: {countries}, limit {args.limit}/stronę, stron {args.pages})")
        ads = fetch_ads(token, args.terms, args.limit, args.pages, countries,
                        verbose=not args.quiet)

    # 2. zbiór sprzed zebrania (do identyfikacji "nowy materiał vs znane kampanie")
    originals = []
    if db.is_file() and db.stat().st_size > 0:
        try:
            originals = [x for x in Store(db).load_incidents()
                         if not x["id"].startswith("ad_")]
        except Exception:
            originals = []
    if originals:
        print(f"[2/4] Zbiór bazowy: {len(originals)} incydentów")

    # 3. deduplikacja i zapis
    seen = known_ad_ids(data_root)
    fresh, dupes = [], 0
    for ad in ads:
        aid = str(ad.get("id") or "")
        if not aid or aid in seen:
            dupes += 1
            continue
        seen.add(aid)
        fresh.append(ad)
    for ad in fresh:
        save_ad(ad, data_root)
    print(f"[3/4] Nowe reklamy: {len(fresh)} (pominięto duplikatów: {dupes})")
    for ad in fresh:
        print(f"      ad_{ad.get('id')}: [{ad.get('page_name') or '?'}] "
              f"{(ad_text(ad)[:80]).replace(chr(10), ' / ')}")
    if not fresh:
        print("      Brak nowych materiałów — nic do zrobienia.")
        return

    # 4. identyfikacja
    if args.run_pipeline:
        print("[4/4] Uruchamiam pipeline analizy…")
        from pipeline import run
        run(str(data_root), str(db), args.threshold, verbose=not args.quiet)
        clusters = Store(db).load_clusters()
        report_identification(fresh, originals, clusters, args.join)
    else:
        print("[4/4] Pominięto identyfikację (dodaj --run-pipeline). "
              f"Reklamy czekają w {incident_dir(data_root)}")


if __name__ == "__main__":
    main()
