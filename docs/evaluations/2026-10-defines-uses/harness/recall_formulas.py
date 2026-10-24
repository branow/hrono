# ruff: noqa: E501, SIM115, E741, B905 - experiment harness; report lines read best whole
"""Recall formulas on the v9 bcreg tree, scored against hard15's fact leaves.

The runs of 2026-10-23 attached recall's top hit as a page and it was a
fact leaf in 7 of 15 questions; the raw passages (cosine, one per file) put
a fact leaf in 17 of 75 hits. This compares, offline and with no model
call, formulas that rank briefs and sources in their own lanes and let a
leaf earn its place by agreement rather than by one lucky passage. Nothing
is excluded by path: a test or a generated document has to lose on its own.

A FACT LEAF is a level-0 topic holding a section of a file the fact cites.
Per formula, over the 15 questions and their 5 hits each:

- leaf hits: hits whose leaf holds some fact of the question
- facts: facts with at least one of their leaves among the 5 hits
- questions: questions with at least one leaf hit
- briefs / tests: how many of the 75 hits are brief passages / test files

Formulas (K = 5 hits, RRF k = 60, dedupe by content hash):

- today: cosine over all passages, one per file (what ships)
- pages: today, one per leaf, tests and upper briefs skipped (what the runs got)
- rrf: cosine + BM25 (RRF), one per leaf
- briefs: rrf over brief passages only, one per leaf
- lanes: 3 from the brief lane + 2 from the source lane, each rrf, distinct leaves
- leafsum: a leaf scores the sum of its passages' rrf scores, both kinds; top leaves
- leafpair: a leaf scores its best brief passage + its best source passage (rrf)
- engine: `hrono recall` as it ships after this experiment (leafpair, spoken for by the closer passage)

Usage (from this folder): uv run --extra embed python recall_formulas.py [K]
"""

from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

import numpy
import subtree_v9

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from hrono.db.database import Database  # noqa: E402
from hrono.embed.model import resolve_embedding_model  # noqa: E402
from hrono.embed.runner import encoder_for  # noqa: E402
from hrono.recall import fts, gate, query, similarity  # noqa: E402
from hrono.recall.engine import recall  # noqa: E402
from hrono.recall.scope import passages_of  # noqa: E402

QUESTIONS = Path.home() / "hrono-deep/data/hard15.json"
RRF_K = 60
TEST_PATH = re.compile(
    r"(^|/)(tests?|__tests__)/|(^|/)test_[^/]*$|_test\.\w+$|\.(spec|test)\.\w+$"
)
DEPTH = 2000  # ranks taken from each leg before fusion


class Corpus:
    def __init__(self) -> None:
        self.db = Database.at(subtree_v9.DST)
        self.conn = self.db.connect().__enter__()
        conn = self.conn
        model = resolve_embedding_model(conn, {})
        self.encode = encoder_for(str(model["model"]))
        self.scope = passages_of(conn, subtree_v9.TREE)
        self.ids, self.bodies = similarity._stack(
            conn, str(model["name"]), self.scope
        )
        self.pos = {pid: i for i, pid in enumerate(self.ids)}
        # passage -> (kind, leaf or None, path, content_hash, uri)
        self.meta: dict[int, tuple[str, int | None, str, str, str]] = {}
        level = {
            int(r["id"]): int(r["level"])
            for r in conn.execute(
                "SELECT id, level FROM nodes WHERE tree = ?", (subtree_v9.TREE,)
            )
        }
        leaf_of_section: dict[int, int] = {}
        for r in conn.execute(
            "SELECT m.section_id, MIN(m.node_id) AS leaf FROM node_members m JOIN nodes n ON n.id = m.node_id WHERE n.level = 0 AND n.tree = ? GROUP BY m.section_id",
            (subtree_v9.TREE,),
        ):
            leaf_of_section[int(r["section_id"])] = int(r["leaf"])
        for r in conn.execute(
            "SELECT id, source_type, source, path, content_hash, section_id, uri FROM passages"
        ):
            pid = int(r["id"])
            if pid not in self.scope:
                continue
            if r["source_type"] == "node":
                node = int(str(r["source"]).removeprefix("node-"))
                kind = "brief" if level.get(node) == 0 else "upper"
                leaf = node if kind == "brief" else None
            else:
                kind, leaf = "source", leaf_of_section.get(int(r["section_id"]))
            self.meta[pid] = (
                kind,
                leaf,
                str(r["path"] or ""),
                str(r["content_hash"]),
                str(r["uri"]),
            )
        self.at = {
            (str(r["uri"]), int(r["byte_start"])): int(r["id"])
            for r in conn.execute("SELECT id, uri, byte_start FROM passages")
        }
        self.sections = collections.defaultdict(list)
        for r in conn.execute(
            "SELECT id, source, path FROM sections WHERE source_type != 'node'"
        ):
            self.sections[f"{r['source']}/{r['path']}"].append(int(r["id"]))
        self.leaf_of_section = leaf_of_section

    def fact_leaves(self, fact: dict) -> set[int]:
        return {
            self.leaf_of_section[s]
            for p in fact["files"]
            for s in self.sections.get(p, [])
            if s in self.leaf_of_section
        }

    # --- the two legs -------------------------------------------------
    def cosine(self, question: str) -> list[int]:
        vecs = numpy.asarray(
            [list(v) for v in self.encode(query.sentences(question))],
            dtype=numpy.float64,
        )
        vecs = vecs / numpy.linalg.norm(vecs, axis=1, keepdims=True)
        score = (self.bodies @ vecs.T).max(axis=1)
        order = numpy.argsort(-score, kind="stable")[:DEPTH]
        return [self.ids[i] for i in order]

    def bm25(self, question: str) -> list[int]:
        words = [f'"{gate.stem(w)}"*' for w in gate.words(question)]
        if not words:
            return []
        hits = fts.search(self.conn, " OR ".join(words), limit=DEPTH * 3)
        return [pid for pid, _ in hits if pid in self.scope][:DEPTH]

    @staticmethod
    def rrf(*rankings: list[int]) -> dict[int, float]:
        score: dict[int, float] = collections.defaultdict(float)
        for ranking in rankings:
            for rank, pid in enumerate(ranking):
                score[pid] += 1.0 / (RRF_K + rank + 1)
        return score

    # --- formulas: each returns the hits as passage ids, best first ----
    def window(
        self, ranked: list[int], key, k: int, taken: set | None = None
    ) -> list[int]:
        """The best ``k`` passages with distinct ``key``, distinct text, key not None."""
        out, seen, hashes = [], set(taken or ()), set()
        for pid in ranked:
            kind, leaf, path, h, uri = self.meta[pid]
            kk = key(pid)
            if kk is None or kk in seen or h in hashes:
                continue
            seen.add(kk)
            hashes.add(h)
            out.append(pid)
            if len(out) == k:
                break
        return out

    def by_leaf(self, pid: int) -> int | None:
        return self.meta[pid][1]

    def by_uri(self, pid: int) -> str:
        return self.meta[pid][4]

    def f_today(self, q: str, k: int) -> list[int]:
        return self.window(self.cosine(q), self.by_uri, k)

    def f_pages(self, q: str, k: int) -> list[int]:
        def key(pid: int):
            kind, leaf, path, *_ = self.meta[pid]
            if kind == "source" and TEST_PATH.search(path):
                return None
            return leaf

        return self.window(self.cosine(q), key, k)

    def fused(self, q: str, kinds: set[str]) -> list[int]:
        cos = [p for p in self.cosine(q) if self.meta[p][0] in kinds]
        bm = [p for p in self.bm25(q) if self.meta[p][0] in kinds]
        score = self.rrf(cos, bm)
        return sorted(score, key=lambda p: (-score[p], p))

    def f_rrf(self, q: str, k: int) -> list[int]:
        return self.window(self.fused(q, {"brief", "source"}), self.by_leaf, k)

    def f_briefs(self, q: str, k: int) -> list[int]:
        return self.window(self.fused(q, {"brief"}), self.by_leaf, k)

    def f_lanes(self, q: str, k: int) -> list[int]:
        nb = (k * 3 + 4) // 5  # 3 of 5
        briefs = self.window(self.fused(q, {"brief"}), self.by_leaf, nb)
        taken = {self.by_leaf(p) for p in briefs}
        sources = self.window(
            self.fused(q, {"source"}), self.by_leaf, k - len(briefs), taken
        )
        return briefs + sources

    def leaf_scores(
        self, q: str, combine: str
    ) -> tuple[dict[int, float], dict[int, int]]:
        """Each leaf's score and its best passage; ``combine`` is sum or pair."""
        best: dict[int, int] = {}
        total: dict[int, float] = collections.defaultdict(float)
        for kinds in ({"brief"}, {"source"}):
            cos = [p for p in self.cosine(q) if self.meta[p][0] in kinds]
            bm = [p for p in self.bm25(q) if self.meta[p][0] in kinds]
            score = self.rrf(cos, bm)
            seen_leaf: set[int] = set()
            for pid in sorted(score, key=lambda p: (-score[p], p)):
                leaf = self.by_leaf(pid)
                if leaf is None:
                    continue
                if combine == "pair" and leaf in seen_leaf:
                    continue
                seen_leaf.add(leaf)
                total[leaf] += score[pid]
                if (
                    leaf not in best
                    or kinds == {"brief"}
                    and self.meta[best[leaf]][0] == "source"
                ):
                    best[leaf] = pid
        return total, best

    def f_leafsum(self, q: str, k: int) -> list[int]:
        total, best = self.leaf_scores(q, "sum")
        leaves = sorted(total, key=lambda l: (-total[l], l))[:k]
        return [best[l] for l in leaves]

    def f_leafpair(self, q: str, k: int) -> list[int]:
        total, best = self.leaf_scores(q, "pair")
        leaves = sorted(total, key=lambda l: (-total[l], l))[:k]
        return [best[l] for l in leaves]

    def f_engine(self, q: str, k: int) -> list[int]:
        """What `hrono recall` returns now: the shipped engine on this tree."""
        result = recall(
            self.conn, q, "emb", self.encode, limit=k, tree=subtree_v9.TREE
        )
        return [self.at[(h.uri, h.start)] for h in result.hits]


FORMULAS = [
    "today",
    "pages",
    "rrf",
    "briefs",
    "lanes",
    "leafsum",
    "leafpair",
    "engine",
]


def main() -> None:
    k = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    c = Corpus()
    questions = json.load(open(QUESTIONS))
    facts_total = sum(len(q["facts"]) for q in questions)
    print(
        f"{len(questions)} questions, {facts_total} facts, {len(c.ids)} passages in scope, K={k}\n"
    )
    table = {}
    detail: dict[str, list[str]] = collections.defaultdict(list)
    for name in FORMULAS:
        hit_leaves = facts = qs = briefs = tests = 0
        for q in questions:
            fl = [c.fact_leaves(f) for f in q["facts"]]
            union = set().union(*fl)
            hits = getattr(c, f"f_{name}")(q["question"], k)
            leaves = [c.by_leaf(p) for p in hits]
            got = [l for l in leaves if l in union]
            hit_leaves += len(got)
            facts += sum(bool(set(leaves) & f) for f in fl)
            qs += bool(got)
            briefs += sum(c.meta[p][0] == "brief" for p in hits)
            tests += sum(
                c.meta[p][0] == "source"
                and bool(TEST_PATH.search(c.meta[p][2]))
                for p in hits
            )
            detail[name].append(
                f"  {q['qid']:24} facts {sum(bool(set(leaves) & f) for f in fl)}/{len(fl)}  "
                + " ".join(
                    f"{l}{'*' if l in union else ''}{'b' if c.meta[p][0] == 'brief' else ''}"
                    for p, l in zip(hits, leaves)
                )
            )
        table[name] = (hit_leaves, facts, qs, briefs, tests)
    print(
        f"{'formula':10} {'leaf hits':>9} {'facts':>9} {'questions':>9} {'briefs':>7} {'tests':>6}"
    )
    for name, (h, f, q, b, t) in table.items():
        print(
            f"{name:10} {h:>5}/{len(questions) * k:<3} {f:>4}/{facts_total:<4} {q:>5}/{len(questions):<3} {b:>7} {t:>6}"
        )
    for name in FORMULAS:
        print(
            f"\n== {name}  (leaf ids of the hits; * = holds a fact, b = brief passage)"
        )
        print("\n".join(detail[name]))


if __name__ == "__main__":
    main()
