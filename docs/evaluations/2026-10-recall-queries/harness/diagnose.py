# ruff: noqa: E501, B023 - experiment harness; report lines read best whole
"""Where answer files rank under plain cosine, under hrono's scores, and
after hrono's floors: old tree (MiniLM) against the rebuilt one (granite).

Per question and tree: the rank of the first passage that reaches an answer
file (its own file, or a leaf brief over one), and how many of the top 10
do, for
- `cosine`: the passage's content vector against the query, nothing else;
- `path`: the passage's embedded path string against the query;
- `hrono z`: recall's vector score (best of the path blend and content, each
  z-scored over the tree's passages);
- `qualified`: how many passages clear recall's floors, and where the first
  answer passage is among them.

Usage: uv run python diagnose.py [QID ...]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from queries import ARCH, QIDS, Recall

from hrono.cluster.blend import path_body
from hrono.ingest.identity import content_hash
from hrono.recall import keyword_leg, vector_leg

DBS = {
    "minilm": (
        Path.home() / "hrono-eval/db/hrono.db",
        "sentence-transformers/all-MiniLM-L6-v2",
    ),
    "granite": (
        Path.home() / "hrono-eval/db/hrono-v2.db",
        "ibm-granite/granite-embedding-97m-multilingual-r2",
    ),
}


def first(order, hits_answer):
    return next((i for i, p in enumerate(order) if hits_answer(p)), None)


def main(*qids: str) -> None:
    questions = [q for q in json.load(open(ARCH)) if q["qid"] in (qids or QIDS)]
    for label, (db, model_id) in DBS.items():
        r = Recall(str(db), model_id)
        ids, bodies, paths = _matrix(r)
        print(f"\n{label}")
        print(
            "| question | cosine: first / in top 10 | path: first | hrono z: first / in top 10 | qualified (first) |"
        )
        print("|---|---|---|---|---|")
        for q in questions:
            files = {f for fact in q["facts"] for f in fact["files"]}

            def answers(pid, files=files):
                return bool(r.reaches.get(pid, set()) & files)

            query = r.model.encode(q["question"])
            query = query / np.linalg.norm(query)
            cos = [ids[i] for i in np.argsort(-(bodies @ query))]
            by_path = [ids[i] for i in np.argsort(-(paths @ query))]
            vz = vector_leg.scores(r.conn, query.tolist(), r.emb, r.allowed)
            kz = keyword_leg.scores(r.conn, q["question"], r.allowed)
            hz = sorted(vz, key=lambda p: -vz[p])
            qual = [p for p, _ in vector_leg.qualify(vz, kz)]
            print(
                f"| {q['qid']} | {first(cos, answers)} / "
                f"{sum(answers(p) for p in cos[:10])} | {first(by_path, answers)} | "
                f"{first(hz, answers)} / {sum(answers(p) for p in hz[:10])} | "
                f"{len(qual)} ({first(qual, answers)}) |"
            )


def _matrix(r):
    """Unit content and path vectors of every passage in the tree."""
    rows = r.conn.execute(
        "select id, content_hash, path from passages"
    ).fetchall()
    want = {int(x["id"]) for x in rows} & r.allowed
    vectors = {
        x["content_hash"]: np.frombuffer(x["vector"], dtype=np.float32)
        for x in r.conn.execute(
            "select content_hash, vector from embeddings where model_name = ?",
            (r.emb,),
        )
    }
    ids, bodies, paths = [], [], []
    for x in rows:
        body = vectors.get(x["content_hash"])
        path = vectors.get(content_hash(path_body(str(x["path"]))))
        if int(x["id"]) in want and body is not None and path is not None:
            ids.append(int(x["id"]))
            bodies.append(body / np.linalg.norm(body))
            paths.append(path / np.linalg.norm(path))
    return ids, np.array(bodies), np.array(paths)


if __name__ == "__main__":
    main(*sys.argv[1:])
