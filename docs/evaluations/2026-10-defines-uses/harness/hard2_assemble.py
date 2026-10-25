# ruff: noqa: E501, SIM115 - experiment harness
"""Assemble the hard2 question set from the explorers' drafts.

Each draft (``<scratch>/hard2/<kind>.json``) is a list of questions with
atomic facts, each fact citing files and quoting evidence. A fact whose
cited files do not all exist in the corpus is dropped; a question is kept
only with 6 facts or more spanning at least 3 repositories. Writes
``~/hrono-deep/data/hard2.json`` in the hard15 shape (qid, kind, question,
facts[{fact, files}]) plus ``trap`` and ``evidence``, which the judge ignores.

Usage: python hard2_assemble.py <drafts folder> [--audited <verdicts.json>]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

CORPUS = Path.home() / "hrono-deep" / "corpus"
OUT = Path.home() / "hrono-deep" / "data" / "hard2.json"
MIN_FACTS = 6
MIN_REPOS = 3


def repos(files: list[str]) -> set[str]:
    return {f.split("/")[0] for f in files}


def main(folder: str, audited: str | None) -> None:
    verdicts = json.load(open(audited)) if audited else {}
    kept, dropped = [], []
    for draft in sorted(Path(folder).glob("*.json")):
        if draft.name.startswith(("audit", "verdicts")):
            continue
        for i, q in enumerate(json.load(open(draft))):
            qid = f"h2-{q['kind']}-{i}"
            facts = []
            for j, f in enumerate(q["facts"]):
                files = [p for p in f["files"] if (CORPUS / p).exists()]
                v = verdicts.get(qid, {}).get(str(j))
                if not files or len(files) < len(f["files"]):
                    dropped.append((qid, j, "missing file"))
                    continue
                if v and v["verdict"] == "wrong":
                    dropped.append((qid, j, "audit: wrong"))
                    continue
                fact = (
                    v["fix"]
                    if v and v["verdict"] == "partly" and v.get("fix")
                    else f["fact"]
                )
                facts.append(
                    {
                        "fact": fact,
                        "files": files,
                        "evidence": f.get("evidence", ""),
                        **({"fixed": True} if fact != f["fact"] else {}),
                    }
                )
            all_files = [p for f in facts for p in f["files"]]
            if len(facts) < MIN_FACTS or len(repos(all_files)) < MIN_REPOS:
                dropped.append(
                    (
                        qid,
                        None,
                        f"{len(facts)} facts, repos {sorted(repos(all_files))}",
                    )
                )
                continue
            kept.append(
                {
                    "qid": qid,
                    "kind": q["kind"],
                    "question": q["question"],
                    "trap": q.get("trap", ""),
                    "facts": facts,
                }
            )
    OUT.write_text(json.dumps(kept, indent=1))
    for d in dropped:
        print("dropped", *d)
    print(
        f"kept {len(kept)} questions, {sum(len(q['facts']) for q in kept)} facts -> {OUT}"
    )
    for q in kept:
        print(
            f"  {q['qid']:16} {len(q['facts'])} facts, repos {sorted(repos([p for f in q['facts'] for p in f['files']]))}"
        )


if __name__ == "__main__":
    main(
        sys.argv[1],
        sys.argv[3]
        if len(sys.argv) > 3 and sys.argv[2] == "--audited"
        else None,
    )
