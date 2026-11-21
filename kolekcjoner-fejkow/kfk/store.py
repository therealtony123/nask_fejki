"""Trwały magazyn: SQLite (incydenty + cechy, krawędzie z dowodami, kampanie)."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents(
    id TEXT PRIMARY KEY,
    path TEXT,
    title TEXT,
    n_files INTEGER,
    n_images INTEGER,
    features TEXT,
    processed_at TEXT
);
CREATE TABLE IF NOT EXISTS edges(
    a TEXT, b TEXT,
    score REAL,
    evidence TEXT,
    per_view TEXT,
    hard INTEGER,
    PRIMARY KEY(a,b)
);
CREATE TABLE IF NOT EXISTS clusters(
    cluster_id TEXT PRIMARY KEY,
    members TEXT,
    label TEXT,
    summary TEXT,
    n_edges INTEGER,
    mean_score REAL,
    hard_links INTEGER,
    updated_at TEXT
);
"""


class Store:
    def __init__(self, db_path):
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def save_incidents(self, feats: list):
        now = datetime.now(timezone.utc).isoformat()
        with self.conn:
            self.conn.execute("DELETE FROM incidents")
            for f in feats:
                self.conn.execute(
                    "INSERT OR REPLACE INTO incidents VALUES (?,?,?,?,?,?,?)",
                    (f["id"], f["path"], f["text"].get("title", "")[:200],
                     f.get("n_files", 0), len(f.get("images", [])),
                     json.dumps(f, ensure_ascii=False), now),
                )

    def save_edges(self, edges: list):
        with self.conn:
            self.conn.execute("DELETE FROM edges")
            for e in edges:
                self.conn.execute(
                    "INSERT OR REPLACE INTO edges VALUES (?,?,?,?,?,?)",
                    (e["a"], e["b"], e["score"],
                     json.dumps(e.get("evidence", []), ensure_ascii=False),
                     json.dumps(e.get("per_view", {}), ensure_ascii=False),
                     1 if e.get("hard") else 0),
                )

    def save_clusters(self, clusters: list):
        now = datetime.now(timezone.utc).isoformat()
        with self.conn:
            self.conn.execute("DELETE FROM clusters")
            for c in clusters:
                self.conn.execute(
                    "INSERT OR REPLACE INTO clusters VALUES (?,?,?,?,?,?,?,?)",
                    (c["cluster_id"], json.dumps(c["members"]),
                     c["label"], json.dumps(c.get("summary", []), ensure_ascii=False),
                     c.get("n_edges", 0), c.get("mean_score", 0.0),
                     c.get("hard_links", 0), now),
                )

    def load_incidents(self) -> list:
        rows = self.conn.execute("SELECT features FROM incidents").fetchall()
        return [json.loads(r[0]) for r in rows]

    def load_edges(self) -> list:
        rows = self.conn.execute("SELECT a,b,score,evidence,per_view,hard FROM edges").fetchall()
        return [{"a": r[0], "b": r[1], "score": r[2],
                 "evidence": json.loads(r[3]), "per_view": json.loads(r[4]),
                 "hard": bool(r[5])} for r in rows]

    def load_clusters(self) -> list:
        rows = self.conn.execute(
            "SELECT cluster_id,members,label,summary,n_edges,mean_score,hard_links FROM clusters"
        ).fetchall()
        return [{"cluster_id": r[0], "members": json.loads(r[1]), "label": r[2],
                 "summary": json.loads(r[3]), "n_edges": r[4],
                 "mean_score": r[5], "hard_links": r[6]} for r in rows]

    def cluster_of(self, incident_id: str):
        for c in self.load_clusters():
            if incident_id in c["members"]:
                return c["cluster_id"]
        return None
