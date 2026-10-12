"""Cluster the bcreg corpus under each candidate formula and score it.

Every variant is a weight per similarity term; the clustering vector is the
concatenation [sqrt(w) * unit(term vector) for each term], so a dot product
of two vectors is exactly sum(w * term similarity), the same identity
`hrono.cluster.blend` uses for content and path today. The leaves come from
hrono's own `build_clusters` (UMAP -> HDBSCAN leaf -> attach noise).

Terms:
- content: the section's MiniLM content embedding (what hrono stores).
- path: the MiniLM embedding of the repo-relative path (what hrono stores).
- repo_path: the MiniLM embedding of "repo/path" (the path with its repo).
- prefix: shared leading folders / sqrt(depth_a * depth_b), over the
  segments [repo, folder, ..., file name]. It is the cosine of two indicator
  vectors (one entry per leading prefix), so it is exact, not approximated.
- cond: the MiniLM embedding of the section's stored condensation (the
  text hrono's condense stage wrote), from `embed_condensed.py`.
- prefix4, prefix3: the same over only the first 4 or 3 segments (repo
  included), so below that depth the prefix stops telling files apart.
- prefix_up1: the same without the file name and its own folder, so files
  in sibling folders (`models/`, `services/`) look alike at any depth.
- file: 1 for two sections of the same file, else 0.
- prefix_h, prefix_e: the prefix with shallow folders weighted more (1/d,
  or 0.6^d at depth d), so content decides inside a deep package without
  any depth cut.

The upper level is a proxy: hrono clusters the briefs' embeddings, which
need LLM calls. Here each leaf is represented by the mean of its members'
content vectors (the closest free stand-in for a brief), clustered with the
same builder. A `+g` variant groups by the mean of the members' full
formula vectors instead, so the path terms also act one level up.

Usage: [UMAP_SEED=n] uv run python run.py CORPUS.npz QUESTIONS.json OUT_DIR
       [variant ...]
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from scipy import sparse
from score import score_variant

import hrono.cluster.build as build
from hrono.cluster.build import build_clusters

VARIANTS: dict[str, dict[str, float]] = {
    "current": {"content": 0.5, "path": 0.5},
    "repo-path": {"content": 0.5, "repo_path": 0.5},
    "c4-p2-x4": {"content": 0.4, "path": 0.2, "prefix": 0.4},
    "c5-x5": {"content": 0.5, "prefix": 0.5},
    "c3-p2-x5": {"content": 0.3, "path": 0.2, "prefix": 0.5},
    "c6-p1-x3": {"content": 0.6, "path": 0.1, "prefix": 0.3},
    "c3-x7": {"content": 0.3, "prefix": 0.7},
    "c3-x7-d4": {"content": 0.3, "prefix4": 0.7},
    "c5-x5-d4": {"content": 0.5, "prefix4": 0.5},
    "c3-x7-d3": {"content": 0.3, "prefix3": 0.7},
    "c5-x5-d3": {"content": 0.5, "prefix3": 0.5},
    "c3-u1x7": {"content": 0.3, "prefix_up1": 0.7},
    "c3-u1x5-f2": {"content": 0.3, "prefix_up1": 0.5, "file": 0.2},
    "c4-u1x4-f2": {"content": 0.4, "prefix_up1": 0.4, "file": 0.2},
    "c3-d4x5-f2": {"content": 0.3, "prefix4": 0.5, "file": 0.2},
    "cond-only": {"cond": 1.0},
    "cond5-p5": {"cond": 0.5, "path": 0.5},
    "cond3-x7": {"cond": 0.3, "prefix": 0.7},
    "cond5-x5": {"cond": 0.5, "prefix": 0.5},
    "cond7-x3": {"cond": 0.7, "prefix": 0.3},
    "cond3-x7-d4": {"cond": 0.3, "prefix4": 0.7},
    "c15-cond15-x7": {"content": 0.15, "cond": 0.15, "prefix": 0.7},
    "c5-cond5": {"content": 0.5, "cond": 0.5},
    "c3-h7": {"content": 0.3, "prefix_h": 0.7},
    "c4-h6": {"content": 0.4, "prefix_h": 0.6},
    "c5-h5": {"content": 0.5, "prefix_h": 0.5},
    "c3-e7": {"content": 0.3, "prefix_e": 0.7},
    "c5-e5": {"content": 0.5, "prefix_e": 0.5},
    "cond3-h7": {"cond": 0.3, "prefix_h": 0.7},
    "c15-cond15-h7": {"content": 0.15, "cond": 0.15, "prefix_h": 0.7},
    "c3-h5-f2": {"content": 0.3, "prefix_h": 0.5, "file": 0.2},
    "c3-x5-h2": {"content": 0.3, "prefix": 0.5, "prefix_h": 0.2},
    "cond5-h5": {"cond": 0.5, "prefix_h": 0.5},
    "cond4-h6": {"cond": 0.4, "prefix_h": 0.6},
    "cond6-h4": {"cond": 0.6, "prefix_h": 0.4},
    "cond5-e5": {"cond": 0.5, "prefix_e": 0.5},
    "cond4-e6": {"cond": 0.4, "prefix_e": 0.6},
    "c25-cond25-h5": {"content": 0.25, "cond": 0.25, "prefix_h": 0.5},
    "content-only": {"content": 1.0},
    "prefix-only": {"prefix": 1.0},
}


def main(corpus_path: str, questions_path: str, out: str, *names: str) -> None:
    # A seed other than hrono's own (42) checks that a ranking is not luck.
    build.UMAP_SEED = int(os.environ.get("UMAP_SEED", build.UMAP_SEED))
    corpus = dict(np.load(corpus_path))
    questions = json.loads(Path(questions_path).read_text())
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    terms = _terms(corpus, Path(corpus_path).with_suffix(".repo_path.npy"))

    results = {}
    if not names or "real-tree" in names:
        # The leaves hrono really built; its groups both as built (from LLM
        # briefs) and from the same proxy the variants use, so the proxy can
        # be checked against reality.
        real = corpus["real_leaf"]
        results["real-tree"] = score_variant(
            corpus, questions, real, corpus["real_group"], out_dir / "real-tree"
        )
        results["real-tree-proxy-groups"] = score_variant(
            corpus,
            questions,
            real,
            _group(corpus["content"], real),
            out_dir / "real-tree-proxy-groups",
        )
    unknown = set(names) - set(VARIANTS) - {"real-tree"}
    if unknown:
        raise SystemExit(f"unknown variants: {', '.join(sorted(unknown))}")
    for name in names or VARIANTS:
        if name not in VARIANTS:
            continue
        started = time.time()
        vectors = _blend(terms, VARIANTS[name])
        leaves = np.array(build_clusters(vectors).labels)
        seconds = round(time.time() - started)
        # Groups as hrono forms them today (content only), and with the same
        # formula as the leaves (a leaf carries the mean of its members'
        # vectors, so its path terms travel up with it).
        for suffix, basis in (("", corpus["content"]), ("+g", vectors)):
            key = name + suffix
            groups = _group(basis, leaves)
            results[key] = score_variant(
                corpus, questions, leaves, groups, out_dir / key
            )
            np.savez_compressed(
                out_dir / key / "assignment.npz",
                section_id=corpus["section_id"],
                leaf=leaves.astype(np.int32),
                group=groups.astype(np.int32),
            )
            results[key]["weights"] = VARIANTS[name]
            results[key]["seconds"] = seconds
            print(key, json.dumps(results[key]["summary"]), flush=True)
    summary_file = out_dir / "summary.json"
    merged = (
        json.loads(summary_file.read_text()) if summary_file.exists() else {}
    )
    merged.update(results)
    summary_file.write_text(json.dumps(merged, indent=1))


def _terms(corpus: dict, repo_path_cache: Path) -> dict[str, object]:
    cache = repo_path_cache
    return {
        "content": _unit(corpus["content"]),
        "path": _unit(corpus["path"]),
        "cond": lambda: _unit(
            np.load(
                cache.with_name(
                    cache.stem.replace(".repo_path", "") + ".condensed.npy"
                )
            )
        ),
        "repo_path": lambda: _unit(_repo_path_vectors(corpus, repo_path_cache)),
        "prefix": lambda: _prefix_indicators(corpus),
        "prefix4": lambda: _prefix_indicators(corpus, max_depth=4),
        "prefix3": lambda: _prefix_indicators(corpus, max_depth=3),
        "prefix_up1": lambda: _prefix_indicators(corpus, drop_last=2),
        "file": lambda: _file_indicators(corpus),
        # shallow folders count more, with no depth cut: 1/d, and 0.6^d
        "prefix_h": lambda: _prefix_indicators(
            corpus, level_weight=lambda d: 1 / d
        ),
        "prefix_e": lambda: _prefix_indicators(
            corpus, level_weight=lambda d: 0.6**d
        ),
    }


def _blend(terms: dict, weights: dict[str, float]) -> np.ndarray:
    blocks = []
    for term, weight in weights.items():
        block = terms[term]
        if callable(block):
            block = terms[term] = block()
        if sparse.issparse(block):
            block = block.toarray()
        blocks.append(np.sqrt(weight) * block)
    return np.hstack(blocks).astype(np.float32)


def _prefix_indicators(
    corpus: dict,
    max_depth: int | None = None,
    drop_last: int = 0,
    level_weight=None,
) -> sparse.csr_matrix:
    """One column per leading prefix, 1/sqrt(depth) in each of a row's.

    `max_depth` keeps only the first segments, so files deeper than that
    under one folder look identical to the prefix and content decides.
    `drop_last` removes the last segments instead (2 = the file name and
    its own folder), so sibling folders such as `models/` and `services/`
    look identical whatever the depth.
    `level_weight(d)` weighs the shared folder at depth d (1 = the repo);
    the similarity is the weight of the shared levels over the two paths'
    total weights. Equal weights give shared / sqrt(depth_a * depth_b).
    """
    columns: dict[str, int] = {}
    rows, cols, values = [], [], []
    for row, (source, path) in enumerate(
        zip(corpus["source"], corpus["rel_path"], strict=True)
    ):
        segments = [str(source), *str(path).split("/")][:max_depth]
        if drop_last:
            segments = segments[: max(1, len(segments) - drop_last)]
        levels = range(1, len(segments) + 1)
        weights = [level_weight(d) if level_weight else 1.0 for d in levels]
        norm = np.sqrt(sum(weights))
        for depth, weight in zip(levels, weights, strict=True):
            key = "/".join(segments[:depth])
            rows.append(row)
            cols.append(columns.setdefault(key, len(columns)))
            values.append(np.sqrt(weight) / norm)
    return sparse.csr_matrix(
        (values, (rows, cols)), shape=(len(corpus["source"]), len(columns))
    )


def _file_indicators(corpus: dict) -> sparse.csr_matrix:
    """One column per file: 1 for two sections of the same file, else 0."""
    names = [
        f"{s}/{p}"
        for s, p in zip(corpus["source"], corpus["rel_path"], strict=True)
    ]
    columns = {name: i for i, name in enumerate(dict.fromkeys(names))}
    rows = range(len(names))
    return sparse.csr_matrix(
        (np.ones(len(names)), (rows, [columns[n] for n in names])),
        shape=(len(names), len(columns)),
    )


def _repo_path_vectors(corpus: dict, cache: Path) -> np.ndarray:
    if cache.exists():
        return np.load(cache)
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    texts = [
        f"{source}/{path}"
        for source, path in zip(
            corpus["source"], corpus["rel_path"], strict=True
        )
    ]
    unique = sorted(set(texts))
    encoded = dict(
        zip(unique, model.encode(unique, batch_size=256), strict=True)
    )
    vectors = np.stack([encoded[text] for text in texts]).astype(np.float32)
    np.save(cache, vectors)
    return vectors


def _group(basis: np.ndarray, leaves: np.ndarray) -> np.ndarray:
    """Cluster the leaves on the mean of their members' vectors: level 1."""
    ids = np.unique(leaves)
    centroids = _unit(np.stack([basis[leaves == leaf].mean(0) for leaf in ids]))
    labels = np.array(build_clusters(centroids).labels)
    group_of_leaf = dict(zip(ids, labels, strict=True))
    return np.array([group_of_leaf[leaf] for leaf in leaves])


def _unit(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.where(norms == 0, 1, norms)


if __name__ == "__main__":
    main(*sys.argv[1:4], *sys.argv[4:])
