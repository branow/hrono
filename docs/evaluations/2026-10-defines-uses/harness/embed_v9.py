# ruff: noqa: E501 - experiment harness
"""Embed the v9 tree's brief passages, which `subtree_v9.py` wrote without
the embed step a maintain run ends with (11,000 of 11,006 had no vector,
so recall's cosine leg never saw a brief in the 2026-10-23 runs).

Usage (from this folder): uv run --extra embed python embed_v9.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import subtree_v9

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from hrono.db.database import Database  # noqa: E402
from hrono.embed.op import embed  # noqa: E402
from hrono.jobs.ops import JobContext  # noqa: E402

if __name__ == "__main__":
    database = Database.at(subtree_v9.DST)
    context = JobContext(database, cache_root=subtree_v9.CACHE)
    print(embed(subtree_v9._job("embed", {}), context), flush=True)
    database.close()
