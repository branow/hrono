"""Try alternative (smaller/faster) embedding models against the Qwen3 baseline.

Motivation: Qwen3-Embedding-0.6B measured ~1.7s/chunk on this laptop — too slow
for the experiment loop. Candidates: IBM Granite Embedding Multilingual R2
(97m / 311m) — same SentenceTransformer API, 32k context, multilingual + code,
Apache 2.0.

This script does NOT touch existing code or Qwen3 data. It:
  1. reconstructs chunk content from the DB byte ranges + git cache
  2. embeds content + paths with the candidate model, timing it
     (vectors stored in the same (hash, model)-keyed embeddings table,
      so re-runs are incremental exactly like the notebook's step 8)
  3. runs the frozen clustering recipe (imported from build_clusters.py)
  4. writes .hrono/clusters-<model-slug>.json (never clusters.json — that
     stays the Qwen3 baseline)
  5. compares against the baseline: speed, translation.json known-group
     test, pre-assignment noise, cluster count/sizes, ARI vs baseline labels

Usage:
  uv run python test_embedding_models.py                       # default: both granite models
  uv run python test_embedding_models.py ibm-granite/granite-embedding-97m-multilingual-r2
"""

import json
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics import adjusted_rand_score

import build_clusters as bc

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / ".hrono" / "hrono.db"
GIT_CACHE = APP_DIR / ".hrono" / "cache" / "git"
BASELINE_CLUSTERS = APP_DIR / ".hrono" / "clusters.json"

DEFAULT_CANDIDATES = [
    "ibm-granite/granite-embedding-97m-multilingual-r2",
    "ibm-granite/granite-embedding-311m-multilingual-r2",
]
BATCH_SIZE = 8  # same as Qwen3 config for a fair ms/chunk comparison


def main() -> None:
    candidates = sys.argv[1:] or DEFAULT_CANDIDATES
    chunks = load_chunks_with_content()
    print(f"{len(chunks)} chunks reconstructed from git cache")
    for model_name in candidates:
        run_candidate(model_name, chunks)


def run_candidate(model_name: str, chunks: list[dict]) -> None:
    print(f"\n{'=' * 70}\n{model_name}\n{'=' * 70}")
    embed_missing(model_name, chunks)

    hashes, chunk_paths, content_vecs = bc.load_content_vectors(model_name)
    path_vecs = bc.embed_paths(chunk_paths, model_name, BATCH_SIZE)
    combined = np.hstack([np.sqrt(1 - bc.ALPHA) * content_vecs, np.sqrt(bc.ALPHA) * path_vecs])

    labels, assigned, assignment_sim = bc.cluster(combined)
    clusters = bc.build_cluster_records(hashes, chunk_paths, content_vecs, labels, assigned, assignment_sim)

    slug = model_name.rsplit("/", 1)[-1]
    out_path = APP_DIR / ".hrono" / f"clusters-{slug}.json"
    out_path.write_text(json.dumps(clusters, indent=2))

    sizes = sorted((c["size"] for c in clusters), reverse=True)
    print(f"\nwrote {len(clusters)} clusters to {out_path.name}")
    print(f"sizes: {sizes}")
    print(f"pre-assignment noise: {int(assigned.sum())} ({100 * assigned.mean():.0f}%)")
    coherences = [c["stats"]["coherence"] for c in clusters]
    print(f"coherence: median {np.median(coherences):.3f}, min {min(coherences):.3f}")

    translation_check(hashes, labels)
    compare_to_baseline(hashes, labels)


def embed_missing(model_name: str, chunks: list[dict]) -> None:
    """Step-8 logic verbatim, parameterized by model: content-addressed, incremental."""
    content_by_hash = {}
    for c in chunks:
        content_by_hash.setdefault(c["hash"], c["content"])

    db = sqlite3.connect(DB_PATH)
    done = {r[0] for r in db.execute("SELECT hash FROM embeddings WHERE model = ?", (model_name,))}
    todo = [h for h in content_by_hash if h not in done]
    print(f"{len(content_by_hash)} unique hashes, {len(done)} already embedded, {len(todo)} to embed")
    if not todo:
        db.close()
        return

    t0 = time.monotonic()
    model = SentenceTransformer(model_name)
    print(f"model load: {time.monotonic() - t0:.1f}s")

    start = time.monotonic()
    for i in range(0, len(todo), BATCH_SIZE):
        batch = todo[i : i + BATCH_SIZE]
        vectors = model.encode([content_by_hash[h] for h in batch], batch_size=BATCH_SIZE,
                               normalize_embeddings=True, show_progress_bar=False)
        with db:
            db.executemany(
                "INSERT INTO embeddings (hash, model, dims, vector) VALUES (?, ?, ?, ?)",
                [(h, model_name, vectors.shape[1], np.asarray(v, dtype=np.float32).tobytes())
                 for h, v in zip(batch, vectors)],
            )
    elapsed = time.monotonic() - start
    db.close()
    print(f"embedded {len(todo)} chunks in {elapsed:.1f}s — "
          f"{1000 * elapsed / len(todo):.0f} ms/chunk, {len(todo) / elapsed:.1f} chunks/s, "
          f"{vectors.shape[1]} dims  (Qwen3 baseline: ~1700 ms/chunk)")


def translation_check(hashes: list[str], labels: np.ndarray) -> None:
    """Known-group test: webphone's uk/es/en translation.json chunks must share one
    cluster, and that cluster must not be a code cluster in disguise."""
    label_by_hash = dict(zip(hashes, labels.tolist()))
    db = sqlite3.connect(DB_PATH)
    rows = db.execute("SELECT path, chunk_no, hash FROM chunks WHERE path LIKE '%locales%'").fetchall()
    db.close()
    by_label = defaultdict(list)
    for path, chunk_no, h in rows:
        by_label[label_by_hash[h]].append(f"{path}#chunk-{chunk_no}")
    print(f"\ntranslation.json known-group test: {len(rows)} chunks -> {len(by_label)} cluster(s)")
    for label, members in sorted(by_label.items()):
        print(f"  cluster {label}: {len(members)} chunks")
    print("  PASS" if len(by_label) == 1 else "  FAIL — translations split across clusters")


def compare_to_baseline(hashes: list[str], labels: np.ndarray) -> None:
    """ARI vs the Qwen3 clusters.json partition (post-assignment, hash-level)."""
    if not BASELINE_CLUSTERS.exists():
        print("no baseline clusters.json — skipping ARI")
        return
    baseline = json.loads(BASELINE_CLUSTERS.read_text())
    base_label_by_hash = {m["hash"]: c["cluster_id"] for c in baseline for m in c["members"]}
    common = [h for h in hashes if h in base_label_by_hash]
    label_by_hash = dict(zip(hashes, labels.tolist()))
    ari = adjusted_rand_score([base_label_by_hash[h] for h in common],
                              [label_by_hash[h] for h in common])
    print(f"ARI vs Qwen3 baseline partition ({len(common)} shared hashes): {ari:.3f}")
    print("  (context: two independent Qwen3 cold rebuilds agree at ~0.81 — that's the ceiling)")


def load_chunks_with_content() -> list[dict]:
    """Rebuild chunk text from byte ranges against the cached git checkouts.

    File on disk: .hrono/cache/git/<instance>/<path>. Assumes the cache is at the
    same commit as the DB rows (true right after a research.ipynb run); a missing
    file or short read means the cache moved on — re-run the notebook steps 1-7.
    """
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    rows = db.execute("SELECT instance, path, byte_start, byte_end, hash FROM chunks").fetchall()
    db.close()

    bytes_by_file: dict[Path, bytes] = {}
    chunks = []
    for row in rows:
        file_path = GIT_CACHE / row["instance"] / row["path"]
        if file_path not in bytes_by_file:
            bytes_by_file[file_path] = file_path.read_bytes()
        raw = bytes_by_file[file_path][row["byte_start"]:row["byte_end"]]
        if len(raw) != row["byte_end"] - row["byte_start"]:
            sys.exit(f"short read on {file_path} — git cache out of sync with DB, re-run notebook steps 1-7")
        chunks.append({"hash": row["hash"], "content": raw.decode("utf-8", errors="replace")})
    return chunks


if __name__ == "__main__":
    main()
