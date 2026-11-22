"""KOLEKCJONER FEJKÓW — pakiet analizy kampanii oszukańczych reklam.

Pipeline: ingest -> cechy -> podobieństwo ważone (z przesłankami) -> graf + Louvain -> kampanie.
"""
from .features import scan, extract_incident, extract_from_url_text
from .similarity import Tfidf, pair_similarity, build_edges
from .cluster import cluster_graph, assign_new_incident
from .store import Store

__all__ = [
    "scan", "extract_incident", "extract_from_url_text",
    "Tfidf", "pair_similarity", "build_edges",
    "cluster_graph", "assign_new_incident", "Store",
]
