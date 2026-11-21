#!/usr/bin/env python3
"""EDA zbioru DANE — per incydent: pliki, tytuły HTML, domeny z HAR, obrazy."""
import json, os, re, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(os.environ.get("DATA_ROOT", Path.home() / "kolekcjoner-fejkow" / "data"))
INC = ROOT / "do_udostępnienia"
OUT = []

def log(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    OUT.append(s)

def title_from_html(p: Path) -> str:
    try:
        text = p.read_text(encoding="utf-8", errors="replace")[:200_000]
    except OSError:
        return "(nieczytelny)"
    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.S | re.I)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()[:120]
    return "(brak title)"

def hosts_from_har(p: Path) -> list:
    try:
        data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception as e:
        return [f"(bląd HAR: {e})"]
    hosts = set()
    redirects = 0
    for ent in data.get("log", {}).get("entries", []):
        url = ent.get("request", {}).get("url", "")
        m = re.match(r"https?://([^/]+)", url)
        if m:
            hosts.add(m.group(1))
        if ent.get("response", {}).get("status") in (301, 302, 303, 307, 308):
            redirects += 1
        if ent.get("response", {}).get("redirectURL"):
            redirects += 1
    return sorted(hosts), redirects

folders = sorted([d for d in INC.iterdir() if d.is_dir()], key=lambda d: int(d.name) if d.name.isdigit() else 9999)
log(f"Liczba incydentów: {len(folders)}")

all_domains = Counter()
for f in folders:
    files = list(f.rglob("*"))
    files = [x for x in files if x.is_file()]
    ext_counter = Counter()
    titles, hars, imgs, videos = [], [], [], []
    for x in files:
        ext = x.suffix.lower() or "(brak)"
        ext_counter[ext] += 1
        if ext == ".html" and "files" not in str(x):
            titles.append((x.name, title_from_html(x)))
        if ext == ".har":
            hars.append(x)
        if ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
            imgs.append(x)
        if ext in (".mp4", ".webm"):
            videos.append(x)
    log(f"\n=== Incydent {f.name}: {len(files)} plików ===")
    log("  rozszerzenia:", dict(ext_counter))
    for h in hars:
        hosts, redirs = hosts_from_har(h)
        for host in hosts:
            all_domains[host] += 1
        log(f"  HAR {h.name}: {len(hosts)} hostów, ~{redirs} redirectów")
        for host in hosts:
            log(f"      {host}")
    for name, t in titles[:12]:
        log(f"  HTML: {name[:70]} | title: {t}")
    if imgs:
        log(f"  obrazy ({len(imgs)}): " + ", ".join(sorted(set(x.name[:50] for x in imgs))[:6]))
    if videos:
        log(f"  wideo ({len(videos)}): " + ", ".join(x.name[:60] for x in videos))

log(f"\n=== UNIKALNE DOMENY W HAR (top 60, {len(all_domains)} unikalnych) ===")
for d, c in all_domains.most_common(60):
    log(f"  {c:3d}x  {d}")

report = ROOT.parent / "eda_report.txt"
report.write_text("\n".join(OUT), encoding="utf-8")
log(f"\nRaport zapisany: {report}")
