# ruff: noqa: E501 - report tables and SQL read best on one line
"""Load the bcreg corpus once: section vectors, paths, labels, current tree.

Reads the eval database read-only and writes one cache file the experiment
runs from, so every formula is clustered from exactly the same inputs:

- per section: source, repo-relative path, content vector, path vector
  (both the stored MiniLM embeddings hrono clustered with), and the leaf and
  level-1 node it sits in in the real `bcreg` tree;
- per section: two reference labels used only for scoring, never for
  clustering: its component (nearest folder with a build file) and its kind
  (code, test, fixture, build, docs, migration), both from path rules.

Usage: uv run python load.py ~/hrono-eval/db/hrono.db ~/hrono-eval/mirror OUT
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
from labels import component_of, kind_of

from hrono.cluster.blend import path_body
from hrono.ingest.identity import content_hash

MODEL = "emb"
TREE = "bcreg"


def main(db_path: str, mirror: str, out: str) -> None:
    import sqlite3

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT id, source, path, content_hash, version FROM sections "
        "WHERE source_type = 'git' ORDER BY source, path, ordinal"
    ).fetchall()
    vectors = {
        digest: np.frombuffer(blob, dtype=np.float32)
        for digest, blob in conn.execute(
            "SELECT content_hash, vector FROM embeddings WHERE model_name = ?",
            (MODEL,),
        )
    }
    leaf_of = dict(
        conn.execute(
            "SELECT m.section_id, n.id FROM node_members m "
            "JOIN nodes n ON n.id = m.node_id "
            "WHERE n.tree = ? AND n.level = 0",
            (TREE,),
        ).fetchall()
    )
    parent_of = dict(
        conn.execute(
            "SELECT c.child_id, c.parent_id FROM node_children c "
            "JOIN nodes n ON n.id = c.child_id WHERE n.tree = ? AND n.level = 0",
            (TREE,),
        ).fetchall()
    )
    files = {
        (source, version): _tracked_files(
            Path(mirror) / f"{source}.git", version
        )
        for source, version in {(r[1], r[4]) for r in rows}
    }

    content, path_vec, meta = [], [], []
    for section_id, source, path, digest, version in rows:
        content.append(vectors[digest])
        path_vec.append(vectors[content_hash(path_body(path))])
        leaf = leaf_of.get(section_id, -1)
        meta.append(
            (
                section_id,
                source,
                path,
                component_of(source, path, files[(source, version)]),
                kind_of(path),
                leaf,
                parent_of.get(leaf, -1),
            )
        )
    columns = list(zip(*meta, strict=True))
    np.savez_compressed(
        out,
        content=np.stack(content),
        path=np.stack(path_vec),
        section_id=np.array(columns[0]),
        source=np.array(columns[1]),
        rel_path=np.array(columns[2]),
        component=np.array(columns[3]),
        kind=np.array(columns[4]),
        real_leaf=np.array(columns[5]),
        real_group=np.array(columns[6]),
    )
    print(f"{len(rows)} sections -> {out}")


def _tracked_files(repo: Path, version: str) -> frozenset[str]:
    listing = subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "-r", "--name-only", version],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return frozenset(listing.splitlines())


if __name__ == "__main__":
    main(*sys.argv[1:4])
