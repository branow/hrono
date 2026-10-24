# ruff: noqa: E501, SIM115, E741, B905 - experiment harness; report lines read best whole
"""Where the fact leaves rank in each recall leg, per question.

For each leg (cosine or BM25, over brief passages or source passages) the
passages are ranked, folded to leaves (first passage of a leaf), and the
line shows the rank of the first fact leaf, how many fact leaves sit in the
top 20 leaves, and the fact leaves' ranks themselves. A leg whose fact
leaves sit at rank 100+ cannot be rescued by fusion or by a bigger window.

Usage (from this folder): uv run --extra embed python recall_ranks.py
"""

from __future__ import annotations

import json

from recall_formulas import QUESTIONS, Corpus

LEGS = [
    ("cos", "brief"),
    ("bm25", "brief"),
    ("cos", "source"),
    ("bm25", "source"),
]


def leaves_of(c: Corpus, ranking: list[int], kind: str) -> list[int]:
    out, seen = [], set()
    for pid in ranking:
        k, leaf, *_ = c.meta[pid]
        if k != kind or leaf is None or leaf in seen:
            continue
        seen.add(leaf)
        out.append(leaf)
    return out


def main() -> None:
    c = Corpus()
    questions = json.load(open(QUESTIONS))
    summary = {leg: [] for leg in LEGS}
    for q in questions:
        union = set().union(*(c.fact_leaves(f) for f in q["facts"]))
        print(f"== {q['qid']}  fact leaves {len(union)}: {sorted(union)}")
        rankings = {
            "cos": c.cosine(q["question"]),
            "bm25": c.bm25(q["question"]),
        }
        for leg, kind in LEGS:
            leaves = leaves_of(c, rankings[leg], kind)
            ranks = [i + 1 for i, l in enumerate(leaves) if l in union]
            first = ranks[0] if ranks else None
            top20 = sum(r <= 20 for r in ranks)
            summary[(leg, kind)].append((first, top20))
            print(
                f"  {leg:4} {kind:6} leaves ranked {len(leaves):4}  first fact leaf at {first!s:>4}  in top20 {top20:2}/{len(union)}  ranks {ranks[:12]}"
            )
    print(
        "\n== over the 15 questions: median rank of the first fact leaf; questions with one in top 5 / top 20"
    )
    for leg, kind in LEGS:
        firsts = sorted(
            f if f is not None else 10**6 for f, _ in summary[(leg, kind)]
        )
        med = firsts[len(firsts) // 2]
        print(
            f"  {leg:4} {kind:6} median first {med if med < 10**6 else 'none':>5}  top5 {sum(f <= 5 for f in firsts):2}/15  top20 {sum(f <= 20 for f in firsts):2}/15"
        )


if __name__ == "__main__":
    main()
