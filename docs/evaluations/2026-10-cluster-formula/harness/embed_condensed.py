"""Embed each section's stored condensation with the tree's own MiniLM model.

The condensations are the ones hrono wrote while building `bcreg` (model
`condense`), so no LLM is called: this only runs the local embedding model.
The vectors are saved in the corpus cache's section order.

Usage: uv run python embed_condensed.py DB CORPUS.npz OUT.npy
"""

from __future__ import annotations

import sqlite3
import sys

import numpy as np
from sentence_transformers import SentenceTransformer

MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CONDENSE_MODEL = "condense"


def main(db_path: str, corpus_path: str, out: str) -> None:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    text_of = dict(
        conn.execute(
            "SELECT s.id, d.text FROM sections s JOIN condensations d "
            "ON d.content_hash = s.content_hash AND d.model_name = ? "
            "WHERE s.source_type = 'git'",
            (CONDENSE_MODEL,),
        ).fetchall()
    )
    ids = np.load(corpus_path)["section_id"].tolist()
    texts = [text_of[section_id] for section_id in ids]
    vectors = SentenceTransformer(MODEL).encode(texts, batch_size=128)
    np.save(out, np.asarray(vectors, dtype=np.float32))
    print(f"{len(texts)} condensations -> {out}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
