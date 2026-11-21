"""Graf incydentów + klastrowanie (Louvain) + przypisywanie nowych materiałów."""
from collections import Counter, defaultdict

import networkx as nx


def cluster_graph(incident_ids: list, edges: list, min_score: float = 0.25):
    """Buduje graf i dzieli na kampanie (Louvain). Zwraca listę klastrów z etykietami."""
    G = nx.Graph()
    for i in incident_ids:
        G.add_node(i)
    for e in edges:
        if e["score"] >= min_score:
            G.add_edge(e["a"], e["b"], score=e["score"], evidence=e["evidence"],
                       per_view=e["per_view"], hard=e["hard"])

    if G.number_of_edges() == 0:
        return [{"cluster_id": f"K{i+1:02d}", "members": [i], "label": "pojedynczy materiał",
                 "summary": [], "n_edges": 0, "mean_score": 0.0,
                 "hard_links": 0} for i in sorted(incident_ids)]

    try:
        communities = nx.community.louvain_communities(G, weight="score", seed=42, resolution=1.0)
    except Exception:
        communities = [set(c) for c in nx.connected_components(G)]
    # singletony nie objęte Louvain (np. izolowane węzły)
    covered = set()
    for c in communities:
        covered |= c
    for n in G.nodes():
        if n not in covered:
            communities.append({n})

    # stabilne nazwy kampanii: kotwica = najmniejszy oryginalny incydent w klastrze
    def anchor(ms):
        nums = sorted((m for m in ms if m.isdigit()), key=int)
        return nums[0] if nums else sorted(ms)[0]

    ordered = sorted(communities,
                     key=lambda ms: (0, int(anchor(ms))) if anchor(ms).isdigit() else (1, anchor(ms)))
    clusters = []
    for idx, members in enumerate(ordered):
        sub = G.subgraph(members)
        edges_in = list(sub.edges(data=True))
        mean_score = (sum(d["score"] for _, _, d in edges_in) / len(edges_in)) if edges_in else 0.0
        hard_links = sum(1 for _, _, d in edges_in if d.get("hard"))
        # etykieta klastra: najczęstsze przesłanki twarde + wspólne elementy
        ev_counter = Counter()
        for _, _, d in edges_in:
            if d.get("hard"):
                for h in d.get("evidence", [])[:2]:
                    ev_counter[h] += 1
        label = "; ".join([e for e, _ in ev_counter.most_common(3)]) or "klaster bez twardych przesłanek"
        clusters.append({
            "cluster_id": f"K{idx + 1:02d}",
            "members": sorted(members),
            "label": label,
            "summary": [e for e, _ in ev_counter.most_common(5)],
            "n_edges": len(edges_in),
            "mean_score": round(mean_score, 3),
            "hard_links": hard_links,
        })
    return clusters


def cluster_of(incident_id: str, clusters: list):
    for c in clusters:
        if incident_id in c["members"]:
            return c["cluster_id"]
    return None


def assign_new_incident(new_feats: dict, stored_feats: dict, edges_to_new: list,
                        join_threshold: float = 0.30):
    """Ocenia nowy materiał względem zbioru: kampania znana czy nowy wzorzec."""
    if not edges_to_new:
        return {
            "verdict": "NOWA KAMPANIA (brak powiązań)",
            "cluster": None,
            "best": None,
            "matches": [],
            "explanation": "Materiał nie wykazuje podobieństwa do żadnego znanego incydentu.",
        }
    best = edges_to_new[0]
    if best["score"] < join_threshold:
        return {
            "verdict": "NOWA KAMPANIA (najbliższe dopasowanie poniżej progu)",
            "cluster": None,
            "best": best,
            "matches": edges_to_new[:5],
            "explanation": (f"Najwyższe podobieństwo {best['score']:.2f} < próg {join_threshold:.2f}. "
                            "Prawdopodobnie nowy wzorzec działania."),
        }
    # klastry sąsiadów o wyniku >= próg — wybieramy klastr z najwyższą sumą dowodów
    votes = defaultdict(float)
    for e in edges_to_new:
        if e["score"] >= join_threshold:
            votes[e["b"]] += e["score"]
    top_neighbor = max(votes, key=votes.get)
    best_score = votes[top_neighbor]
    return {
        "verdict": "PRZYPISANO DO KAMPANII",
        "cluster": f"kampania incydentu {top_neighbor}",
        "best": {"neighbor": top_neighbor, "score": round(best_score, 3)},
        "matches": edges_to_new[:5],
        "explanation": (f"Materiał wykazuje {len(votes)} silnych dopasowań; najsilniejsze z incydentem "
                        f"{top_neighbor} (podobieństwo {best_score:.2f})."),
    }