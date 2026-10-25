# ruff: noqa: E501, SIM115 - experiment harness
"""Assemble a list-task set from the explorers' ground-truth drafts.

Each draft (``<folder>/<name>.json``) is {qid, task, method, items[{item,
files, evidence, confidence}]}. Items whose cited files are missing from the
corpus are dropped, and an audit (``--audited verdicts.json``, {qid: {n:
{verdict, fix}}}) drops "wrong" items and rewrites "partly" ones; items the
auditors add come in as {qid: {"add": [{item, files, evidence}]}}. Writes
``~/hrono-deep/data/<set>.json`` in the question shape the harness runs
(qid, kind, question = the task, facts = the items) so ``agent_v2.py`` and
``score_list.py`` take it as a set.

Usage: python tasks_assemble.py <set> <drafts folder> [--audited <verdicts.json>]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

CORPUS = Path.home() / "hrono-deep" / "corpus"


def main(name: str, folder: str, audited: str | None) -> None:
    verdicts = json.load(open(audited)) if audited else {}
    out = []
    for draft in sorted(Path(folder).glob("*.json")):
        if draft.name.startswith(("audit", "verdicts")):
            continue
        d = json.load(open(draft))
        qid = d["qid"]
        v = verdicts.get(qid, {})
        facts = []
        for j, it in enumerate(d["items"]):
            files = [p for p in it["files"] if (CORPUS / p).exists()]
            if not files:
                print("dropped", qid, j, "no existing file")
                continue
            x = v.get(str(j))
            if x and x["verdict"] == "wrong":
                print("dropped", qid, j, "audit:", x.get("note", "")[:80])
                continue
            fact = (
                x["fix"]
                if x and x["verdict"] == "partly" and x.get("fix")
                else it["item"]
            )
            facts.append(
                {
                    "fact": fact,
                    "files": files,
                    "evidence": it.get("evidence", ""),
                    "confidence": it.get("confidence", ""),
                }
            )
        for it in v.get("add", []):
            facts.append(
                {
                    "fact": it["item"],
                    "files": it["files"],
                    "evidence": it.get("evidence", ""),
                    "added": True,
                }
            )
        out.append(
            {
                "qid": qid,
                "kind": "list",
                "question": d["task"],
                "method": d.get("method", ""),
                "facts": facts,
            }
        )
        print(f"  {qid:14} {len(facts)} items")
    path = Path.home() / "hrono-deep" / "data" / f"{name}.json"
    path.write_text(json.dumps(out, indent=1))
    print(f"wrote {len(out)} tasks -> {path}")


if __name__ == "__main__":
    main(
        sys.argv[1],
        sys.argv[2],
        sys.argv[4]
        if len(sys.argv) > 4 and sys.argv[3] == "--audited"
        else None,
    )
