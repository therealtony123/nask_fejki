"""Grupowanie materiałów w kampanie: union-find po krawędziach powyżej progu."""
from __future__ import annotations

from collections import defaultdict

from .model import Cluster, Features, Link
from .similarity import SimilarityConfig, compare, is_linked


class UnionFind:
    def __init__(self):
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def build_clusters(features: list[Features], cfg: SimilarityConfig):
    """Zwraca (clusters, all_links). Krawędź powstaje gdy is_linked()==True."""
    links: list[Link] = []
    uf = UnionFind()
    n = len(features)
    for i in range(n):
        for j in range(i + 1, n):
            link = compare(features[i], features[j], cfg)
            if is_linked(link, cfg):
                links.append(link)
                uf.union(link.a, link.b)

    groups: dict[str, list[str]] = defaultdict(list)
    for f in features:
        groups[uf.find(f.id)].append(f.id)

    clusters: list[Cluster] = []
    for root, members in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        mset = set(members)
        cl = Cluster(cluster_id=f"C{len(clusters) + 1:03d}", members=sorted(members, key=int) if all(m.isdigit() for m in members) else sorted(members))
        cl.links = [l for l in links if l.a in mset and l.b in mset]
        clusters.append(cl)
    return clusters, links


def assign_new_material(features: list[Features], clusters: list[Cluster], new_f: Features, cfg: SimilarityConfig):
    """Analiza nowego materiału względem istniejącego zbioru.

    Zwraca (best_cluster_id, best_link, top_links) — best_cluster_id=None oznacza
    prawdopodobnie NOWĄ kampanię (żadne podobieństwo nie przekroczyło progu).
    """
    top: list[Link] = []
    for f in features:
        link = compare(new_f, f, cfg)
        top.append(link)
    top.sort(key=lambda l: -l.score)

    per_cluster: dict[str, tuple[float, Link]] = {}
    cid_by_member = {}
    for c in clusters:
        for m in c.members:
            cid_by_member[m] = c.cluster_id
    for link in top:
        cid = cid_by_member.get(link.b)
        if cid and cid not in per_cluster:
            per_cluster[cid] = (link.score, link)

    best_cid, best = None, None
    for cid, (score, link) in per_cluster.items():
        if link and (is_linked(link, cfg)) and (best is None or score > best.score):
            best_cid, best = cid, link
    return best_cid, best, top[:10]
