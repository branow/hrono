"""A copy of the v3 tree with the rebuilt sub-tree's briefs stored, so recall
serves them: the 21 wide leaf briefs and the 6 rebuilt upper briefs, each
re-stored as brief passages (hrono's own store_brief) and the new passages
embedded with the tree's model. No LLM call.

Usage: uv run --extra embed python tree_v3z.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import exp

sys.path.insert(0, str(exp.HERE.parents[3] / "src"))
from hrono.db.journal import register  # noqa: E402
from hrono.embed import store as vectors  # noqa: E402
from hrono.embed.model import resolve_embedding_model  # noqa: E402
from hrono.embed.runner import embed_texts, encoder_for  # noqa: E402
from hrono.ingest.store import get_content  # noqa: E402
from hrono.recall.brief_passages import store_brief  # noqa: E402

SRC = Path.home() / "hrono-eval" / "db" / "hrono-v3.db"
DST = Path.home() / "hrono-eval" / "db" / "hrono-v3z.db"


def main() -> None:
    DST.unlink(missing_ok=True)
    with sqlite3.connect(f"file:{SRC}?mode=ro", uri=True) as src:
        dst = sqlite3.connect(DST)
        src.backup(dst)
    dst.row_factory = sqlite3.Row
    register(dst)
    texts = {
        **{int(k): v["text"] for k, v in exp.load("briefs-W.json").items()},
        **{int(k): v["text"] for k, v in exp.load("upper-C.json").items()},
    }
    for node, text in texts.items():
        sig = dst.execute(
            "SELECT member_signature FROM briefs WHERE node_id = ?", (node,)
        ).fetchone()[0]
        dst.execute(
            "UPDATE briefs SET text = ? WHERE node_id = ?", (text, node)
        )
        store_brief(dst, node, text, sig)
    dst.commit()
    config = resolve_embedding_model(dst, {})
    hashes = vectors.missing(dst, str(config["name"]))
    bodies = [
        (get_content(dst, h) or b"").decode("utf-8", "replace") for h in hashes
    ]
    vecs = embed_texts(bodies, 16, encoder_for(str(config["model"])))
    for h, v in zip(hashes, vecs, strict=True):
        vectors.upsert_vector(dst, h, str(config["name"]), v)
    dst.commit()
    print("briefs", len(texts), "embedded", len(hashes), "->", DST)


if __name__ == "__main__":
    main()
