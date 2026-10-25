# ruff: noqa: E501, SIM115, E741 - experiment harness
"""Where each fact an hrono agent missed was lost: brief, navigation or answer.

For every fact of every run of an arm: the judge's score and reason; the
fact's leaf topics (from its files' sections, ``fact_leaves_<set>.json``
beside the set); whether a brief of one of them was opened in the run,
whether the recall attachment listed it; and whether any export brief holds
the fact's identifiers (``map_check.tokens``). A missed fact then falls in
one of: ABSENT (no brief names it: a brief fault), UNREAD (a brief has it,
none of its leaves was opened: navigation), READ (its leaf's brief was read
and the fact still missed: the brief says it badly, the agent dropped it,
or the judge did not credit it).

Usage: python trace_facts.py <set> <arm> <fact_leaves.json> [export]
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

from map_check import tokens

RUNS = Path.home() / "hrono-deep" / "runs"
DATA = Path.home() / "hrono-deep" / "data"
HERE = Path(__file__).resolve().parent


def main(name: str, arm: str, leaves_path: str, export: str) -> None:
    qs = {q["qid"]: q for q in json.load(open(DATA / f"{name}.json"))}
    leaves = json.load(open(leaves_path))
    briefs = {
        re.search(r"-(\d+)$", str(p.parent)).group(1): p.read_text(
            errors="replace"
        )
        for p in Path(export).rglob("brief.md")
        if re.search(r"-(\d+)$", str(p.parent))
    }
    rows = {
        json.loads(l)["qid"]: json.loads(l)
        for l in open(RUNS / f"{name}-{arm}.jsonl")
    }
    scores = {
        json.loads(l)["qid"]: json.loads(l)
        for l in open(RUNS / f"{name}-{arm}.scores.jsonl")
    }
    kinds: Counter[str] = Counter()
    kinds_scored: Counter[str] = Counter()
    for qid, q in qs.items():
        if qid not in rows:
            continue
        r, s = rows[qid], scores[qid]
        opened = {
            m.group(1)
            for t in r["tools"]
            for m in re.finditer(r"-(\d+)/brief\.md", t["input"])
        }
        try:
            recalled = {
                str(h.get("topic"))
                for h in json.load(open(HERE / "recall" / f"{qid}.json"))[
                    "hits"
                ]
            }
        except FileNotFoundError:
            recalled = set()
        print(
            f"\n== {qid}  coverage {s['coverage']:.2f}  briefs opened {len(opened)}  tool calls {len(r['tools'])}"
        )
        for i, f in enumerate(q["facts"]):
            sc = s["fact_scores"][i]
            fl = set(leaves[qid][i])
            toks = tokens(f["fact"])
            holders = {
                t
                for t, b in briefs.items()
                if toks and all(x in b for x in toks)
            }
            in_leaf_brief = bool(holders & fl)
            if not holders:
                kind = "ABSENT"
            elif not (fl & opened) and not (holders & opened):
                kind = "UNREAD"
            else:
                kind = "READ"
            kinds[kind] += 1
            kinds_scored[(kind, sc)] += 1
            why = s.get("why", {}).get(str(i + 1), "")
            flag = "  " if sc == 1 else "**"
            print(
                f"{flag} fact {i + 1} score {sc}  {kind:6} leaves {sorted(fl)[:4]} opened {bool(fl & opened)} recalled {bool(fl & recalled)} in-leaf-brief {in_leaf_brief} holders {len(holders)}"
            )
            print(f"     {f['fact'][:150]}")
            if why:
                print(f"     judge: {why[:200]}")
    print("\nby kind:", dict(kinds))
    for kind in ("ABSENT", "UNREAD", "READ"):
        row = {sc: kinds_scored[(kind, sc)] for sc in (1.0, 0.5, 0.0)}
        print(
            f"  {kind:6} scored 1: {row[1.0]:3}  0.5: {row[0.5]:3}  0: {row[0.0]:3}"
        )


if __name__ == "__main__":
    main(
        sys.argv[1],
        sys.argv[2],
        sys.argv[3],
        sys.argv[4]
        if len(sys.argv) > 4
        else str(Path.home() / "hrono-eval" / "export-bcreg-v9-L3"),
    )
