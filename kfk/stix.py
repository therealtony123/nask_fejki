"""Eksport STIX 2.1 (bundle) i watchlisty IoC — artefakty zrozumiałe dla NASK/CSIRT.

STIX: kampanie (campaign), incydenty (incident), domeny (indicator z pattern
domain-name) oraz relacje: incident -attributed-to-> campaign,
indicator -indicates-> campaign, incident -related-to-> incident (z przesłankami
i poziomem ufności = ważone podobieństwo).
"""
import csv
import json
import uuid
from datetime import datetime, timezone

STIX = "2.1"


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sdo(obj):
    obj["spec_version"] = STIX
    return obj


def _rel(src, tgt, rel_type, **extra):
    return _sdo({"type": "relationship", "id": f"relationship--{uuid.uuid4()}",
                 "relationship_type": rel_type, "source_ref": src, "target_ref": tgt,
                 "created": _now(), "modified": _now(), **extra})


def incident_timespan(path: str):
    """Pierwsza/ostatnia aktywność incydentu (mtime plików)."""
    from pathlib import Path
    p = Path(path)
    mtimes = [f.stat().st_mtime for f in p.rglob("*") if f.is_file()]
    if not mtimes:
        return None, None

    def iso(ts):
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")

    return iso(min(mtimes)), iso(max(mtimes))


def build_bundle(incidents: list, clusters: list, edges: list) -> dict:
    objects = []
    objects.append(_sdo({"type": "identity", "id": "identity--kolekcjoner-fejkow",
                         "name": "KOLEKCJONER FEJKÓW", "identity_class": "system",
                         "created": _now(), "modified": _now()}))
    inc_by = {f["id"]: f for f in incidents}
    spans = {i: incident_timespan(f["path"]) for i, f in inc_by.items()}
    cluster_of = {}
    for c in clusters:
        for m in c["members"]:
            cluster_of[m] = c["cluster_id"]

    camp_ids = {}
    for c in clusters:
        cid = f"campaign--kfk-{c['cluster_id'].lower()}"
        camp_ids[c["cluster_id"]] = cid
        first = min((spans[m][0] for m in c["members"] if spans[m][0]), default=None)
        last = max((spans[m][1] for m in c["members"] if spans[m][1]), default=None)
        objects.append(_sdo({
            "type": "campaign", "id": cid,
            "name": f"Kampania {c['cluster_id']}",
            "description": ("; ".join(c.get("summary") or []) or c["label"])[:1500],
            "first_seen": first or _now(), "last_seen": last or _now(),
            "labels": ["scam-campaign"], "created": _now(), "modified": _now()}))

    for f in incidents:
        iid = f"incident--kfk-{f['id']}"
        objects.append(_sdo({
            "type": "incident", "id": iid,
            "name": f"Incydent {f['id']}: {(f['text'].get('title') or '')[:80]}",
            "description": (f["text"].get("title") or "")[:500],
            "first_seen": spans[f["id"]][0] or _now(),
            "last_seen": spans[f["id"]][1] or _now(),
            "created": _now(), "modified": _now(),
            "x_kfk_domains": f["infra"]["registrable"],
            "x_kfk_tracker_ids": f["infra"]["tracker_ids"],
            "x_kfk_domain_patterns": [f"{d['domain']} [{d['pattern']}]"
                                      for d in f["infra"].get("domain_patterns", [])],
            "x_kfk_cluster": cluster_of.get(f["id"]),
        }))
        if f["id"] in cluster_of:
            objects.append(_rel(iid, camp_ids[cluster_of[f["id"]]], "attributed-to"))

    dom_clusters = {}
    for f in incidents:
        co = cluster_of.get(f["id"])
        for d in f["infra"]["registrable"]:
            dom_clusters.setdefault(d, set()).add(co)
    for d, cs in sorted(dom_clusters.items()):
        ind_id = f"indicator--{uuid.uuid4()}"
        objects.append(_sdo({
            "type": "indicator", "id": ind_id, "name": f"domena {d}",
            "pattern": f"[domain-name:value = '{d}']", "pattern_type": "stix",
            "valid_from": _now(), "labels": ["malicious-activity"],
            "created": _now(), "modified": _now()}))
        for co in cs:
            if co:
                objects.append(_rel(ind_id, camp_ids[co], "indicates"))

    for e in edges:
        objects.append(_rel(f"incident--kfk-{e['a']}", f"incident--kfk-{e['b']}",
                            "related-to",
                            description="; ".join(e.get("evidence", [])[:4])[:800],
                            confidence=min(100, int(e["score"] * 100))))

    return {"type": "bundle", "id": f"bundle--{uuid.uuid4()}",
            "spec_version": STIX, "objects": objects}


def export_ioc(incidents: list, clusters: list, out_csv: str):
    """Watchlista IoC: domeny, ID trackerów, favicony, hashe wideo — z przypisaniem kampanii."""
    cluster_of = {}
    for c in clusters:
        for m in c["members"]:
            cluster_of[m] = c["cluster_id"]
    rows = set()
    for f in incidents:
        co = cluster_of.get(f["id"], "")
        for d in f["infra"]["registrable"]:
            rows.add(("domain", d, co, f["id"]))
        for t in f["infra"]["tracker_ids"]:
            rows.add(("tracker_id", t, co, f["id"]))
        fav = f["structure"].get("favicon_md5")
        if fav:
            rows.add(("favicon_md5", fav, co, f["id"]))
        for v in f.get("videos", []):
            if v.get("md5"):
                rows.add(("video_md5", v["md5"], co, f["id"]))
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["typ", "wartosc", "kampania", "incydent"])
        for r in sorted(rows):
            w.writerow(r)
    return len(rows)