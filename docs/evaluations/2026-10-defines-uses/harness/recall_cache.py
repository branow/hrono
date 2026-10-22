# ruff: noqa: E501 - experiment harness
"""What the hrono plugin's prompt hook attaches, for each hard15 question.

The plugin runs `hrono recall <tree> <prompt> --json --pages --limit 5` on
every prompt and attaches the best pages (`plugins/hrono/scripts/hooks/
recall.js`). The agent harness never did, so its agents walked down from the
root without the pages recall points at. This writes each question's recall
reply, from hrono's own `ask` on the eval db, to `recall/<qid>.json`;
`recall_bin.py` replays them to the plugin's own hook code.

Usage: uv run --extra embed python recall_cache.py
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

import exp

sys.path.insert(0, str(exp.HERE.parents[3] / "src"))
import subtree_v9  # noqa: E402

from hrono.db.database import Database  # noqa: E402
from hrono.errors import Unavailable  # noqa: E402
from hrono.recall.ask import ask  # noqa: E402

OUT = exp.HERE / "recall"
LIMIT = 5  # the plugin's default


def main() -> None:
    OUT.mkdir(exist_ok=True)
    database = Database.at(subtree_v9.DST)
    questions = json.load(open(Path.home() / "hrono-deep/data/hard15.json"))
    for q in questions:
        while True:
            try:
                result = ask(
                    database, subtree_v9.TREE, q["question"], LIMIT, pages=True
                )
                break
            except Unavailable:
                time.sleep(2)
        hits = [asdict(hit) for hit in result.hits]
        (OUT / f"{q['qid']}.json").write_text(json.dumps({"hits": hits}))
        print(q["qid"], [h.get("topic") for h in hits], flush=True)
    database.close()


if __name__ == "__main__":
    main()
