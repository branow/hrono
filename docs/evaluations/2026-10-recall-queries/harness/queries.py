# ruff: noqa: E501, B023 - experiment harness; report lines read best whole
"""Mechanical ways to turn a prompt into recall queries, compared on bcreg.

The plugin recalls on the whole prompt the user typed. A prompt is often a
question plus instructions ("reply in 400 words", "open root.md first"), and
one embedding of all of it is the average of both. This tries splitting and
filtering the prompt with no model call, recalling each piece with hrono's
own legs and floors, and merging the pieces' hits.

A prompt counts as FOUND when one of the top 5 hits is a file the question's
verified facts cite, or a leaf brief whose members include one. COVERED is
the share of those files the top 5 hits reach (directly or through a leaf
brief). Off-topic prompts should return nothing; any hit is a LEAK.

Usage: uv run python queries.py DB [QID ...]
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

from sentence_transformers import SentenceTransformer

from hrono.recall import keyword_leg, scope, vector_leg

ARCH = Path(__file__).parents[2] / "2026-10-bc-registries-agents/data/arch.json"
MODEL = "ibm-granite/granite-embedding-97m-multilingual-r2"
TOP = 5
QIDS = ("lear-filings-1", "pay-3", "auth-0", "ui-0", "cross-0")

FORMAT = (
    "Investigate with your tools as much as you need, then reply with only "
    "the final answer: precise, naming the concrete components (modules, "
    "classes, functions, queues, endpoints) and their file paths relative to "
    "the current directory, at most 400 words."
)
MAP = (
    "Before reading code: open root.md, choose the areas that fit the "
    "question, read their brief.md and the leaf briefs beneath them, then "
    "open the source files the leaves list."
)
SHAPES = {
    "bare": "{q}",
    "task": "Question about this codebase:\n{q}\n\n" + FORMAT,
    "task+map": "Question about this codebase:\n{q}\n\n"
    + FORMAT
    + "\n\n"
    + MAP,
    "chatty": (
        "Hey, I'm new to this codebase and trying to get my head around it. "
        "{q} Thanks, keep it short please."
    ),
}
ABSENT = [
    "What is the best hydration ratio for a sourdough starter?",
    "How do black holes evaporate through Hawking radiation?",
    "What are the main lines of the Sicilian defence in chess?",
    "How do I knit a cable stitch?",
    "How do I train a puppy to stop barking at night?",
]

_SENTENCE = re.compile(r"(?<=[.?!])\s+|\n+")
# A sentence that tells the assistant how to work or answer, not what about:
# it names the answer, the reply, the tools or the map, or is a pleasantry.
_INSTRUCTION = re.compile(
    r"\b(reply|answer|respond|investigate|your tools|at most \d+|words?\b|"
    r"keep it|thanks|thank you|please|root\.md|brief\.md|briefs?\b|"
    r"i'?m new|get my head|question about this)",
    re.I,
)
_CLAUSE = re.compile(
    r";|,?\s+\band\b\s+(?=(?:how|what|which|where|when|why|who)\b)|\?\s*", re.I
)
_NAME = re.compile(
    r"`[^`]+`|\b[\w./-]+\.(?:py|ts|js|vue|java|yaml|yml|sql|json)\b|"
    r"\b[a-z]+(?:_[a-z0-9]+)+\b|\b[A-Z][a-z]+(?:[A-Z][a-z0-9]+)+\b|"
    r"\b[A-Z]{2,}(?:_[A-Z0-9]+)+\b"
)


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.split(text) if s and s.strip()]


def kept(text: str) -> list[str]:
    """The sentences that are not instructions; all of them if none is."""
    parts = [s for s in sentences(text) if not _INSTRUCTION.search(s)]
    return parts or sentences(text)


def clauses(text: str) -> list[str]:
    """Kept sentences, each cut into its sub-questions."""
    out = []
    for sentence in kept(text):
        pieces = [p.strip() for p in _CLAUSE.split(sentence) if p and p.strip()]
        out.extend(p for p in pieces if len(p.split()) >= 3) if len(
            pieces
        ) > 1 else out.append(sentence)
    return out or kept(text)


def names(text: str) -> list[str]:
    found = sorted({m.strip("`") for m in _NAME.findall(text)})
    return [" ".join(found)] if found else []


STRATEGIES = {
    "whole": lambda t: [t],
    "split-all": sentences,
    "split-filter": kept,
    "filter-join": lambda t: [" ".join(kept(t))],
    "filter-join+names": lambda t: [" ".join(kept(t))] + names(t),
    "clauses": clauses,
    "clauses+names": lambda t: clauses(t) + names(t),
}


class Recall:
    def __init__(self, db: str, model_id: str = MODEL) -> None:
        self.conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        self.conn.row_factory = sqlite3.Row
        self.model = SentenceTransformer(model_id)
        self.model.max_seq_length = 2048
        self.emb = self.conn.execute(
            "select name from registry where collection='models' "
            "and json_extract(config,'$.kind')='embedding'"
        ).fetchone()[0]
        self.allowed = scope.passages_of(self.conn, "bcreg")
        self.reaches = self._reaches()
        self._cache: dict[str, list[tuple[int, float]]] = {}

    def _reaches(self) -> dict[int, set[str]]:
        """The files each passage stands for: its own, or a leaf brief's members."""
        leaf_files = defaultdict(set)
        for row in self.conn.execute(
            "select m.node_id n, s.source || '/' || s.path f from node_members m "
            "join sections s on s.id = m.section_id join nodes x on x.id = m.node_id "
            "where x.level = 0"
        ):
            leaf_files[int(row["n"])].add(row["f"])
        out = {}
        for row in self.conn.execute(
            "select id, source, source_type, path from passages"
        ):
            if row["source_type"] == "node":
                out[int(row["id"])] = leaf_files.get(
                    int(row["source"].removeprefix("node-")), set()
                )
            else:
                out[int(row["id"])] = {f"{row['source']}/{row['path']}"}
        return out

    def hits(self, query: str) -> list[tuple[int, float]]:
        """hrono's qualified passages for one query, best first (vector leg,
        corroborated by keywords, as recall/engine.py runs it)."""
        if query not in self._cache:
            vz = vector_leg.scores(
                self.conn,
                self.model.encode(query).tolist(),
                self.emb,
                self.allowed,
            )
            kz = keyword_leg.scores(self.conn, query, self.allowed)
            self._cache[query] = list(vector_leg.qualify(vz, kz))
        return self._cache[query]

    def window(self, queries: list[str]) -> list[int]:
        """Merge the queries' hits: round-robin, best first, one per file."""
        lists = [self.hits(q) for q in queries]
        out, seen = [], set()
        for rank in range(max((len(h) for h in lists), default=0)):
            for hits in lists:
                if rank < len(hits):
                    pid = hits[rank][0]
                    key = frozenset(self.reaches.get(pid, {pid}))
                    if key not in seen:
                        seen.add(key)
                        out.append(pid)
            if len(out) >= TOP:
                break
        return out[:TOP]


def main(db: str, *qids: str) -> None:
    questions = [
        q for q in json.loads(ARCH.read_text()) if q["qid"] in (qids or QIDS)
    ]
    recall = Recall(db)
    rows = []
    for name, split in STRATEGIES.items():
        found = covered = 0.0
        per_shape = {}
        for shape, template in SHAPES.items():
            shape_found = 0
            for q in questions:
                prompt = template.format(q=q["question"])
                files = {f for fact in q["facts"] for f in fact["files"]}
                window = recall.window(split(prompt))
                reached = (
                    set().union(*(recall.reaches.get(p, set()) for p in window))
                    if window
                    else set()
                )
                hit = bool(reached & files)
                shape_found += hit
                found += hit
                covered += len(reached & files) / len(files)
            per_shape[shape] = shape_found
        leaks = sum(bool(recall.window(split(text))) for text in ABSENT)
        n = len(questions) * len(SHAPES)
        rows.append(
            f"| `{name}` | {found:.0f}/{n} | "
            + " | ".join(f"{per_shape[s]}/{len(questions)}" for s in SHAPES)
            + f" | {covered / n:.2f} | {leaks}/{len(ABSENT)} |"
        )
    print(
        "| strategy | found | "
        + " | ".join(SHAPES)
        + " | files covered | off-topic leaks |\n|"
        + "---|" * (len(SHAPES) + 5)
    )
    print("\n".join(rows))


if __name__ == "__main__":
    main(*sys.argv[1:])
