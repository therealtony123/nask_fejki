"""Takedown Pack — raport dowodowy kampanii gotowy do przekazania
(CERT / brand protection / zgłoszenie do rejestratora).

Generowany z danych już będących w pipeline: skład kampanii, adresy,
infrastruktura (domeny, NS, IP, przekierowania) i pełne przesłanki
powiązań z twardymi sygnałami. Format Markdown — czytelny dla człowieka,
łatwy do załączenia.
"""
from __future__ import annotations

import time
from collections import defaultdict


def _kv(label: str, value) -> str:
    if value in (None, "", [], ()):
        return ""
    return f"| **{label}** | `{value}` |\n"


def campaign_report_md(cluster, materials, features, links) -> str:
    """Buduje raport Markdown dla jednej kampanii.

    materials/features: listy obiektów z session_state (Material/Features).
    links: wszystkie krawędzie zbioru (filtrowane po kampanii).
    """
    mat_by_id = {m.id: m for m in (materials or [])}
    feat_by_id = {f.id: f for f in (features or [])}
    members = list(cluster.members)

    inside = set(members)
    cl_links = [l for l in (cluster.links or links or [])
                if l.a in inside and l.b in inside]

    now = time.strftime("%Y-%m-%d %H:%M:%S")
    strong = sorted({s for l in cl_links for s in l.strong_signals})

    md = [
        f"# 🕵️ Takedown Pack — kampania {cluster.cluster_id}",
        "",
        f"Raport dowodowy wygenerowany **{now}** przez demonstrator",
        "**Kolekcjoner fejków** (HackNation 2026, wyzwanie NASK PIB).",
        "",
        "## 1. Podsumowanie",
        "",
        f"- Materiały w kampanii: **{len(members)}** "
        f"({', '.join(members)})",
        f"- wykryte powiązania: **{len(cl_links)}**",
        f"- twarde dowody (niezależne od progu): **{len(strong)}**",
    ]
    if strong:
        md += ["", "### Twarde dowody", ""]
        md += [f"- ⚡ {s}" for s in strong]

    md += ["", "## 2. Skład kampanii", "",
           "| materiał | źródło | URL | domena rejestrowa | TLD | IP |",
           "|---|---|---|---|---|---|"]
    for mid in members:
        m, f = mat_by_id.get(mid), feat_by_id.get(mid)
        if not m:
            continue
        row = [
            mid,
            (m.source or "—"),
            (m.url or "—"),
            (getattr(f, "registrable_domain", None) or "—"),
            (getattr(f, "tld", None) or "—"),
            (getattr(f, "ip", None) or "—"),
        ]
        md.append("| " + " | ".join(f"`{x}`" if x != "—" else "—" for x in row) + " |")

    if cl_links:
        md += ["", "## 3. Przesłanki powiązań (interpretowalność)", ""]
        for l in sorted(cl_links, key=lambda x: -x.score)[:12]:
            md.append(f"### {l.a} ↔ {l.b} — podobieństwo {l.score:.0%} "
                      f"(pewność porównania: {l.confidence:.0%} dostępnych danych)")
            md.append("")
            for s in l.strong_signals:
                md.append(f"- ⚡ **{s}**")
            for e in sorted(l.reasons, key=lambda x: -x.score):
                md.append(f"- {e.description}: podobieństwo `{e.score}` "
                          f"(udział w wyniku: `{e.weight_in_sum}`)")
            md.append("")

    # ------------------------------------------------- IoC do watchlisty
    ioc_domains, ioc_ns, ioc_ips, redirects = set(), set(), set(), set()
    for mid in members:
        f = feat_by_id.get(mid)
        if not f:
            continue
        if getattr(f, "registrable_domain", None):
            ioc_domains.add(f.registrable_domain)
        ioc_ns |= set(getattr(f, "ns_set", None) or [])
        if getattr(f, "ip", None):
            ioc_ips.add(f.ip)
        redirects |= set(getattr(f, "redirect_domains", None) or [])

    md += ["## 4. IoC / watchlista", "",
           "**Domeny rejestrowe:**", ""]
    md += [f"- `{d}`" for d in sorted(ioc_domains)]
    md += ["", "**Serwery NS:**"]
    md += [f"- `{n}`" for n in sorted(ioc_ns)] or ["- —"]
    md += ["", "**Adresy IP:**"]
    md += [f"- `{ip}`" for ip in sorted(ioc_ips)] or ["- —"]
    if redirects:
        md += ["", "**Domeny z łańcuchów przekierowań:**"]
        md += [f"- `{d}`" for d in sorted(redirects)]

    md += ["", "---",
           "_Raport wygenerowany automatycznie przez demonstrator "
           "„Kolekcjoner fejków”. Dane o infrastrukturze pochodzą z "
           "publicznych rejestrów (DNS/RDAP)._"]
    return "\n".join(md)
