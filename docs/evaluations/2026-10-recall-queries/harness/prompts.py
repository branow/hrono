# ruff: noqa: E501, B023 - experiment harness; report lines read best whole
"""What recall should embed when the prompt is more than the question.

The hard-question runs (2026-10-bc-registries-v2/) found the plugin's recall
injecting licence headers and unrelated tests: the hook embeds the whole
prompt, and the prompt carries the task's framing (answer format, how to use
the map) around the question. Mechanical query shapes on the v3 tree:

- `full`: the prompt as the hook sends it (today).
- `question`: the question alone (the upper bound for a clean prompt).
- `max`: each sentence embedded on its own; a passage scores its best
  sentence.
- `rr`: each sentence ranked on its own; the rankings interleaved, best
  first (round robin).

USEFUL: of the top 5 documents, those that are a file the question's facts
cite, or a brief whose topic holds such a file.

Usage: uv run python prompts.py
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

DB = Path.home() / "hrono-eval/db/hrono-v3.db"
HARNESS = (
    Path(__file__).resolve().parents[2] / "2026-10-bc-registries-agents/harness"
)
sys.path.insert(0, str(HARNESS))
import common  # noqa: E402
from run_arms import ARCH, EXPORT_V3, MAP_H  # noqa: E402

MODEL = "ibm-granite/granite-embedding-97m-multilingual-r2"
TOP = 5
STOP = set(
    [
        "about",
        "after",
        "also",
        "answer",
        "before",
        "being",
        "between",
        "both",
        "business",
        "could",
        "does",
        "each",
        "every",
        "from",
        "have",
        "into",
        "just",
        "more",
        "much",
        "only",
        "other",
        "over",
        "same",
        "should",
        "some",
        "such",
        "than",
        "that",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "through",
        "today",
        "under",
        "what",
        "when",
        "where",
        "which",
        "while",
        "will",
        "with",
        "would",
        "your",
    ]
)
SENTENCE = re.compile(r"(?<=[.?!:])\s+|\n+")


def sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE.split(text) if len(s.split()) >= 3]


class Tree:
    def __init__(self) -> None:
        self.conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        rows = self.conn.execute(
            "SELECT p.id, p.uri, p.path, p.source_type, p.source, e.vector "
            "FROM passages p JOIN embeddings e ON e.content_hash = p.content_hash"
        ).fetchall()
        self.ids = [r[0] for r in rows]
        self.doc = {r[0]: r[1] for r in rows}
        self.path = {r[0]: r[2] or "" for r in rows}
        self.node = {
            r[0]: int(r[4].removeprefix("node-"))
            for r in rows
            if r[3] == "node"
        }
        m = np.stack([np.frombuffer(r[5], dtype=np.float32) for r in rows])
        self.bodies = m / np.linalg.norm(m, axis=1, keepdims=True)
        self.model = SentenceTransformer(MODEL)
        self._held: dict[int, set[str]] = {}
        level = dict(
            self.conn.execute("SELECT id, level FROM nodes").fetchall()
        )
        self.leaf = {pid for pid, n in self.node.items() if level.get(n) == 0}
        self.test = np.array([_is_test(self.path[pid]) for pid in self.ids])
        self.brief = np.array([pid in self.node for pid in self.ids])
        self.upper = np.array(
            [pid in self.node and pid not in self.leaf for pid in self.ids]
        )
        self.row = {pid: i for i, pid in enumerate(self.ids)}

    def bm25(self, text: str, keep) -> list[int]:
        """Rows ranked by FTS5 BM25 over the text's content words, OR-ed."""
        words = sorted(
            {w.lower() for w in re.findall(r"[A-Za-z]{4,}", text)} - STOP
        )
        match = " OR ".join(f'"{w}"' for w in words)
        rows = self.conn.execute(
            "SELECT passage_id FROM passages_fts WHERE passages_fts MATCH ? "
            "ORDER BY bm25(passages_fts) LIMIT 3000",
            (match,),
        ).fetchall()
        return [
            self.row[r[0]]
            for r in rows
            if r[0] in self.row and keep[self.row[r[0]]]
        ]

    def held(self, node: int) -> set[str]:
        """The files under a brief: its members, or its children's."""
        if node not in self._held:
            rows = self.conn.execute(
                "WITH RECURSIVE t(id) AS (SELECT ? UNION SELECT c.child_id FROM node_children c "
                "JOIN t ON c.parent_id = t.id) SELECT DISTINCT s.path FROM t "
                "JOIN node_members m ON m.node_id = t.id "
                "JOIN sections s ON s.id = m.section_id",
                (node,),
            ).fetchall()
            self._held[node] = {r[0] for r in rows}
        return self._held[node]

    def cos(self, texts: list[str]) -> np.ndarray:
        q = self.model.encode(texts)
        q = q / np.linalg.norm(q, axis=1, keepdims=True)
        return self.bodies @ q.T  # passages x texts

    def window(self, order) -> list[int]:
        seen, out = set(), []
        for i in order:
            pid = self.ids[i]
            if self.doc[pid] in seen:
                continue
            seen.add(self.doc[pid])
            out.append(pid)
            if len(out) == TOP:
                break
        return out

    def useful(self, pid: int, files: set[str]) -> bool:
        if pid in self.node:
            return pid in self.leaf and bool(self.held(self.node[pid]) & files)
        return self.path[pid] in files

    def label(self, pid: int) -> str:
        return f"brief {self.node[pid]}" if pid in self.node else self.path[pid]


def _is_test(path: str) -> bool:
    return bool(re.search(r"(^|/)tests?/|\\.spec\\.|(^|/)test_[^/]*$", path))


def shapes(tree: Tree, prompt: str, question: str) -> dict[str, list[int]]:
    full = tree.cos([prompt])[:, 0]
    alone = tree.cos([question])[:, 0]
    each = tree.cos(sentences(prompt))
    best = each.max(axis=1)
    per = [np.argsort(-each[:, j]) for j in range(each.shape[1])]
    rr = [i for row in zip(*(p[:200] for p in per), strict=True) for i in row]
    return {
        "full": tree.window(np.argsort(-full)),
        "question": tree.window(np.argsort(-alone)),
        "max": tree.window(np.argsort(-best)),
        "rr": tree.window(rr),
        "max-notests": tree.window(
            np.argsort(-np.where(tree.test, -1.0, best))
        ),
        "max-briefs": tree.window(
            np.argsort(-np.where(tree.brief, best, -1.0))
        ),
        "max-briefs+.05": tree.window(
            np.argsort(-(best + 0.05 * tree.brief - tree.test))
        ),
        "max-leaf": tree.window(
            np.argsort(-np.where(tree.test | tree.upper, -1.0, best))
        ),
        "leaf-only": tree.window(
            np.argsort(
                -np.where(np.isin(tree.ids, list(tree.leaf)), best, -1.0)
            )
        ),
        "bm25-leaf-prompt": tree.window(
            tree.bm25(prompt, np.isin(tree.ids, list(tree.leaf)))
        ),
        "bm25-leaf-q": tree.window(
            tree.bm25(question, np.isin(tree.ids, list(tree.leaf)))
        ),
        "bm25-src-q": tree.window(
            tree.bm25(question, ~(tree.test | tree.brief))
        ),
        "q-notests": tree.window(np.argsort(-np.where(tree.test, -1.0, alone))),
    }


def strip(path: str) -> str:
    """A fact cites lear/legal-api/...; a section's path is legal-api/..."""
    return path.split("/", 1)[1] if "/" in path else path


def pages(tree: Tree, scores: np.ndarray, n: int = 10) -> list[int]:
    """Leaf pages ranked by their best passage: the brief's own, or a
    source passage of a section the page holds (tests left out)."""
    if not hasattr(tree, "page_of"):
        rows = tree.conn.execute(
            "SELECT p.id, m.node_id FROM passages p "
            "JOIN node_members m ON m.section_id = p.section_id "
            "JOIN nodes n ON n.id = m.node_id WHERE n.level = 0"
        ).fetchall()
        tree.page_of = {pid: node for pid, node in rows}
        for pid, node in tree.node.items():
            if pid in tree.leaf:
                tree.page_of[pid] = node
    best: dict[int, float] = {}
    for i in np.argsort(-scores)[:5000]:
        pid = tree.ids[i]
        node = tree.page_of.get(pid)
        if node is None or tree.test[i]:
            continue
        best.setdefault(node, float(scores[i]))
        if len(best) == n:
            break
    return list(best)


def page_eval(tree: Tree, qs, n: int = 10) -> None:
    leaves = [
        r[0] for r in tree.conn.execute("SELECT id FROM nodes WHERE level = 0")
    ]
    for name in ("q", "max", "zmax", "z3"):
        hit = base = 0
        for q in qs:
            files = {strip(f) for fact in q["facts"] for f in fact["files"]}
            prompt = ARCH.format(question=q["question"]) + MAP_H.format(
                export=EXPORT_V3
            )
            each = tree.cos(sentences(prompt))
            z = (each - each.mean(axis=0)) / each.std(axis=0)
            sc = {
                "q": lambda: tree.cos([q["question"]])[:, 0],
                "max": lambda: each.max(axis=1),
                "zmax": lambda: z.max(axis=1),
                "z3": lambda: np.where(z >= 3.0, z, 0.0).sum(axis=1),
            }[name]()
            got = pages(tree, sc, n)
            hit += sum(bool(tree.held(p) & files) for p in got)
            base += (
                n
                * sum(bool(tree.held(p) & files) for p in leaves)
                / len(leaves)
            )
            print(
                q["qid"], name, [(p, bool(tree.held(p) & files)) for p in got]
            )
        print(f"PAGES {name}: {hit}/{n * len(qs)} useful, random {base:.1f}")


def main() -> None:
    tree = Tree()
    qs = json.loads((common.DATA / "hard5.json").read_text())
    totals: dict[str, int] = {}
    for q in qs:
        files = {strip(f) for fact in q["facts"] for f in fact["files"]}
        prompt = ARCH.format(question=q["question"]) + MAP_H.format(
            export=EXPORT_V3
        )
        print(f"\n## {q['qid']}")
        for name, hits in shapes(tree, prompt, q["question"]).items():
            ok = [tree.useful(p, files) for p in hits]
            totals[name] = totals.get(name, 0) + sum(ok)
            marks = ", ".join(
                ("*" if u else "") + tree.label(p)
                for p, u in zip(hits, ok, strict=True)
            )
            print(f"- {name} {sum(ok)}/{TOP}: {marks}")
    print("\nUSEFUL of", TOP * len(qs), totals)
    page_eval(tree, qs)


if __name__ == "__main__":
    main()
