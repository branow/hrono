# ruff: noqa: E501, B023 - experiment harness; report lines read best whole
"""Candidate recall formulas on the rebuilt bcreg tree, against today's.

- `today`: hrono's recall as it ships (path blend, z-scores, floors).
- `cosine`: plain cosine of the query against each passage's content, top 5
  distinct files (a leaf brief counts as its members).
- `hybrid`: reciprocal rank fusion of the cosine ranking and BM25 (k 60).
- `+gate`: answer at all only when enough of the question's content words
  occur in the tree (FTS document frequency >= 1); otherwise nothing.

FOUND as in queries.py: a top-5 hit reaches a file the question's facts cite.
The gate's coverage is printed for every prompt so its bar can be read off.

Usage: uv run python formulas.py [GATE]
"""

from __future__ import annotations

import json
import sys

import numpy as np
from diagnose import _matrix
from queries import ABSENT, ARCH, QIDS, SHAPES, TOP, Recall, kept

from hrono.recall import fts, keyword_leg

DB = "/Users/orest/hrono-eval/db/hrono-v2.db"
K = 60


def terms(text: str) -> list[str]:
    return sorted(
        {
            t.lower()
            for t in keyword_leg._TERM.findall(text)
            if t.lower() not in keyword_leg._STOPWORDS and len(t) > 2
        }
    )


class Formulas:
    def __init__(self) -> None:
        self.r = Recall(DB)
        self.ids, self.bodies, _ = _matrix(self.r)
        self._df: dict[str, int] = {}

    def df(self, term: str) -> int:
        if term not in self._df:
            self._df[term] = len(fts.search(self.r.conn, f'"{term}"', limit=5))
        return self._df[term]

    def coverage(self, text: str) -> float:
        words = terms(text)
        return sum(self.df(w) > 0 for w in words) / len(words) if words else 0.0

    def cosine(self, text: str) -> list[int]:
        q = self.r.model.encode(text)
        q = q / np.linalg.norm(q)
        order = np.argsort(-(self.bodies @ q))[:200]
        return [self.ids[i] for i in order]

    def bm25(self, text: str) -> list[int]:
        match = keyword_leg._match_expr(text)
        if match is None:
            return []
        return [
            pid
            for pid, _ in fts.search(self.r.conn, match, limit=200)
            if pid in self.r.allowed
        ]

    def hybrid(self, text: str) -> list[int]:
        score: dict[int, float] = {}
        for ranking in (self.cosine(text), self.bm25(text)):
            for rank, pid in enumerate(ranking):
                score[pid] = score.get(pid, 0.0) + 1 / (K + rank + 1)
        return sorted(score, key=lambda p: -score[p])

    def today(self, text: str) -> list[int]:
        return [p for p, _ in self.r.hits(text)]

    def window(self, ranking: list[int]) -> list[int]:
        out, seen = [], set()
        for pid in ranking:
            key = frozenset(self.r.reaches.get(pid, {pid}))
            if key not in seen:
                seen.add(key)
                out.append(pid)
            if len(out) == TOP:
                break
        return out


def main(gate: str = "0.6") -> None:
    bar = float(gate)
    f = Formulas()
    questions = [q for q in json.load(open(ARCH)) if q["qid"] in QIDS]
    rankers = {"today": f.today, "cosine": f.cosine, "hybrid": f.hybrid}
    print("coverage of on-topic prompts (filtered of instruction sentences):")
    for q in questions:
        print(
            f"  {q['qid']}: "
            + ", ".join(
                f"{s} {f.coverage(' '.join(kept(t.format(q=q['question'])))):.2f}"
                for s, t in SHAPES.items()
            )
        )
    print("coverage of off-topic prompts:")
    for text in ABSENT:
        missing = [w for w in terms(text) if f.df(w) == 0]
        print(
            f"  {f.coverage(text):.2f} {text[:45]} (absent: {', '.join(missing)})"
        )

    print(
        "\n| formula | found | "
        + " | ".join(SHAPES)
        + " | files covered | off-topic leaks |"
    )
    print("|---|---|" + "---|" * len(SHAPES) + "---|---|")
    for name, rank in rankers.items():
        for gated in (False, True):
            if name == "today" and gated:
                continue
            found, covered, per = 0, 0.0, {}
            for shape, template in SHAPES.items():
                per[shape] = 0
                for q in questions:
                    prompt = template.format(q=q["question"])
                    query = " ".join(kept(prompt))
                    files = {x for fact in q["facts"] for x in fact["files"]}
                    hits = (
                        []
                        if gated and f.coverage(query) < bar
                        else f.window(rank(query))
                    )
                    reached = (
                        set().union(*(f.r.reaches.get(p, set()) for p in hits))
                        if hits
                        else set()
                    )
                    per[shape] += bool(reached & files)
                    found += bool(reached & files)
                    covered += len(reached & files) / len(files)
            leaks = sum(
                bool([] if gated and f.coverage(t) < bar else f.window(rank(t)))
                for t in ABSENT
            )
            n = len(questions) * len(SHAPES)
            label = f"`{name}`" + (f" + gate {bar}" if gated else "")
            print(
                f"| {label} | {found}/{n} | "
                + " | ".join(f"{per[s]}/{len(questions)}" for s in SHAPES)
                + f" | {covered / n:.2f} | {leaks}/{len(ABSENT)} |"
            )


if __name__ == "__main__":
    main(*sys.argv[1:])
