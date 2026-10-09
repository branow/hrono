"""Build path-aware chunk clusters from the hrono DB — the settled recipe from research.ipynb.

Pipeline (steps 13/18 of the notebook, frozen after the sweeps):
  1. combined vectors [sqrt(1-a)*content ; sqrt(a)*path], a=0.5 — path embedded with the
     same model as content, so the dot product is the weighted blend of both similarities
  2. UMAP to 25 dims (cosine, seed 42)
  3. HDBSCAN, cluster_selection_method="leaf", min_cluster_size=5
  4. every noise chunk attaches to the cluster of its most-similar clustered chunk,
     by dot product in the ORIGINAL combined space (reducer-independent, deterministic)

Writes .hrono/clusters.json: one record per cluster with members (uri, hash, assigned,
assignment_similarity) and stats (dominant path prefixes, content-embedding coherence,
category breakdown).

Run: uv run python build_clusters.py
"""

import json
import sqlite3
import time
import tomllib
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import umap
from sentence_transformers import SentenceTransformer
from sklearn.cluster import HDBSCAN

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / ".hrono" / "hrono.db"
OUT_PATH = APP_DIR / ".hrono" / "clusters.json"

ALPHA = 0.5           # path weight in the combined vector
UMAP_DIMS = 25
UMAP_SEED = 42
MIN_CLUSTER_SIZE = 5
PREFIX_SEGMENTS = 3   # cluster-naming prefix depth, as in the notebook's path_coherence


def main() -> None:
    model_name, batch_size = load_embedding_config()
    hashes, chunk_paths, content_vecs = load_content_vectors(model_name)
    print(f"loaded {len(hashes)} unique-hash chunks, {content_vecs.shape[1]}-dim content vectors")

    path_vecs = embed_paths(chunk_paths, model_name, batch_size)
    combined = np.hstack([np.sqrt(1 - ALPHA) * content_vecs, np.sqrt(ALPHA) * path_vecs])

    labels, assigned, assignment_sim = cluster(combined)
    clusters = build_cluster_records(hashes, chunk_paths, content_vecs, labels, assigned, assignment_sim)

    OUT_PATH.write_text(json.dumps(clusters, indent=2))
    sizes = sorted((c["size"] for c in clusters), reverse=True)
    print(f"\nwrote {len(clusters)} clusters covering {sum(sizes)} chunk references to {OUT_PATH}")
    print(f"sizes: {sizes}")
    print(f"assigned (ex-noise) members: {sum(m['assigned'] for c in clusters for m in c['members'])}")


def cluster(combined: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """UMAP -> HDBSCAN leaf -> nearest-member assignment of noise.

    Returns per-chunk (final_label, assigned_flag, assignment_similarity); similarity is
    NaN for density-core members.
    """
    reduced = umap.UMAP(n_components=UMAP_DIMS, metric="cosine", random_state=UMAP_SEED).fit_transform(combined)
    print(f"UMAP: {combined.shape[1]} -> {reduced.shape[1]} dims")

    labels = HDBSCAN(min_cluster_size=MIN_CLUSTER_SIZE, metric="euclidean",
                     cluster_selection_method="leaf").fit_predict(reduced)
    noise_idx = np.where(labels == -1)[0]
    core_idx = np.where(labels >= 0)[0]
    print(f"HDBSCAN leaf: {labels.max() + 1} clusters, {len(noise_idx)} noise chunks to assign")

    assigned = labels == -1
    assignment_sim = np.full(len(labels), np.nan)
    if len(noise_idx):
        # nearest clustered chunk in the ORIGINAL combined space — independent of the reducer
        sims = combined[noise_idx] @ combined[core_idx].T
        nearest = sims.argmax(axis=1)
        labels[noise_idx] = labels[core_idx[nearest]]
        assignment_sim[noise_idx] = sims[np.arange(len(noise_idx)), nearest]
    return labels, assigned, assignment_sim


def build_cluster_records(hashes, chunk_paths, content_vecs, labels, assigned, assignment_sim) -> list[dict]:
    """Expand hash-level labels to URI-level members and compute per-cluster stats."""
    chunk_rows_by_hash = load_chunk_rows_by_hash()

    row_idx_by_label = defaultdict(list)
    for i, label in enumerate(labels):
        row_idx_by_label[int(label)].append(i)

    clusters = []
    for label in sorted(row_idx_by_label):
        idx = row_idx_by_label[label]
        members, prefixes, categories = [], Counter(), Counter()
        for i in idx:
            sim = assignment_sim[i]
            for row in chunk_rows_by_hash[hashes[i]]:
                members.append({
                    "uri": row["uri"],
                    "hash": hashes[i],
                    "assigned": bool(assigned[i]),
                    "assignment_similarity": round(float(sim), 4) if not np.isnan(sim) else None,
                })
                prefixes["/".join(row["path"].split("/")[:PREFIX_SEGMENTS])] += 1
                categories[row["category"]] += 1
        members.sort(key=lambda m: m["uri"])
        clusters.append({
            "cluster_id": label,
            "size": len(members),
            "members": members,
            "stats": {
                "dominant_prefixes": [{"prefix": p, "count": n} for p, n in prefixes.most_common(3)],
                "coherence": mean_pairwise_cosine(content_vecs[idx]),
                "categories": dict(sorted(categories.items())),
            },
        })
    return clusters


def mean_pairwise_cosine(vectors: np.ndarray) -> float:
    """Mean cosine similarity over all distinct pairs (vectors are unit-normalized)."""
    n = len(vectors)
    if n < 2:
        return 1.0
    sims = vectors @ vectors.T
    return round(float((sims.sum() - np.trace(sims)) / (n * (n - 1))), 4)


def load_embedding_config() -> tuple[str, int]:
    with open(APP_DIR / "embedding.toml", "rb") as f:
        cfg = tomllib.load(f)["model"]
    return cfg["name"], cfg["batch_size"]


def load_content_vectors(model_name: str) -> tuple[list[str], list[str], np.ndarray]:
    """One row per unique hash: (hash, a representative path, content vector) — the
    exact per-hash selection the notebook clusters on."""
    db = sqlite3.connect(DB_PATH)
    rows = db.execute("""
        SELECT c.hash, c.path, e.vector FROM chunks c
        JOIN embeddings e ON e.hash = c.hash AND e.model = ?
        GROUP BY c.hash
    """, (model_name,)).fetchall()
    db.close()
    hashes = [r[0] for r in rows]
    chunk_paths = [r[1] for r in rows]
    content_vecs = np.frombuffer(b"".join(r[2] for r in rows), dtype=np.float32).reshape(len(rows), -1)
    return hashes, chunk_paths, content_vecs


def embed_paths(chunk_paths: list[str], model_name: str, batch_size: int) -> np.ndarray:
    """Embed each distinct path string once with the content model (short strings — fast)."""
    t0 = time.monotonic()
    model = SentenceTransformer(model_name)
    print(f"model load: {time.monotonic() - t0:.1f}s")
    distinct_paths = sorted(set(chunk_paths))
    path_vec_by_path = dict(zip(distinct_paths, model.encode(
        distinct_paths, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False)))
    print(f"embedded {len(distinct_paths)} distinct paths")
    return np.stack([path_vec_by_path[p] for p in chunk_paths])


def load_chunk_rows_by_hash() -> dict[str, list[dict]]:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    rows = db.execute(
        "SELECT uri, hash, path, chunk_no, category FROM chunks ORDER BY path, chunk_no").fetchall()
    db.close()
    by_hash = defaultdict(list)
    for row in rows:
        by_hash[row["hash"]].append(dict(row))
    return by_hash


if __name__ == "__main__":
    main()
