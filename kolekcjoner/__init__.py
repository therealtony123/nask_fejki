"""Kolekcjoner fejków — demonstrator korelacji i grupowania podejrzanych reklam."""
from .model import Cluster, Evidence, Features, Link, Material
from .similarity import SimilarityConfig, compare, is_linked
from .cluster import build_clusters, assign_new_material
from .extract import extract_features
from .ingest import from_jsonl, from_records, from_screenshot, from_text, from_url

__all__ = [
    "Material", "Features", "Link", "Evidence", "Cluster",
    "SimilarityConfig", "compare", "is_linked",
    "build_clusters", "assign_new_material",
    "extract_features", "from_jsonl", "from_records", "from_screenshot",
    "from_text", "from_url",
]
__version__ = "1.0.0"
