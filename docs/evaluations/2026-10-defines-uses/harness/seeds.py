# ruff: noqa: E501, SIM115 - experiment harness
"""Offline: which recall seed strategy puts the answer's leaf topics into the
block? No agent, no LLM: embeddings only."""

import json
import re
import sqlite3
import sys

sys.path.insert(0, "src")
sys.path.insert(0, "docs/evaluations/2026-10-defines-uses/harness")
import exp

from hrono.embed.model import resolve_embedding_model
from hrono.embed.runner import encoder_for
from hrono.recall import query, similarity

db = sqlite3.connect(
    "file:/Users/orest/hrono-eval/db/hrono-v3z.db?mode=ro", uri=True
)
db.row_factory = sqlite3.Row
cfg = resolve_embedding_model(db, {})
enc = encoder_for(str(cfg["model"]))
level = dict(db.execute("SELECT id, level FROM nodes"))
leaf = dict(
    db.execute(
        "SELECT m.section_id, MIN(m.node_id) FROM node_members m JOIN nodes n ON n.id=m.node_id WHERE n.level=0 GROUP BY 1"
    )
)
secs = {}
for sid, src, path in db.execute("SELECT id, source, path FROM sections"):
    secs.setdefault(f"{src}/{path}", []).append(sid)
TEST = re.compile(
    r"(^|/)(tests?|__tests__)/|(^|/)test_[^/]*$|_test\.\w+$|\.(spec|test)\.\w+$"
)
test_topic = {}
for node, path in db.execute(
    "SELECT m.node_id, s.path FROM node_members m JOIN sections s ON s.id=m.section_id"
):
    t = test_topic.setdefault(node, [0, 0])
    t[0] += bool(TEST.search(path or ""))
    t[1] += 1
is_test = {n for n, (a, b) in test_topic.items() if a > b / 2}
pas = {
    r["id"]: (r["source_type"], r["source"], r["section_id"], r["path"])
    for r in db.execute(
        "SELECT id, source_type, source, section_id, path FROM passages"
    )
}
links = exp.load("links.json")
near = {}
chan = {}
for it in links:
    a, b = it["from_leaf"], it["to_leaf"]
    near.setdefault(a, set()).add(b)
    near.setdefault(b, set()).add(a)
    if it["kind"] in ("shares", "sends", "receives"):
        chan.setdefault(a, set()).add(b)
        chan.setdefault(b, set()).add(a)
qs = [
    x
    for x in json.load(open("/Users/orest/hrono-deep/data/hard15.json"))
    if x["qid"]
    in (
        "hard-inconsistency-1",
        "hard-failure-1",
        "hard-legacy-0",
        "hard-authorization-1",
    )
]


def topic_rank(qtext, use_src, skip_tests):
    vecs = [list(v) for v in enc(query.sentences(qtext))]
    best = {}
    for pid, cos in similarity.ranked(db, vecs, str(cfg["name"])):
        kind, src, sid, path = pas[pid]
        if kind == "node":
            n = int(src.removeprefix("node-"))
        elif use_src and not TEST.search(path or ""):
            n = leaf.get(sid)
        else:
            continue
        if n is None or level.get(n) != 0 or (skip_tests and n in is_test):
            continue
        best.setdefault(n, cos)
    return sorted(best, key=lambda n: -best[n])


def block(order, seeds_n=3, total=9):
    seeds = order[:seeds_n]
    rank = {n: i for i, n in enumerate(order)}
    hop1 = {b for s in seeds for b in near.get(s, ())}
    hop2 = {c for b in hop1 for c in near.get(b, ())}
    ch = {b for s in seeds for b in chan.get(s, ())}
    linked = sorted(
        (n for n in (hop1 | hop2) - set(seeds) if n in rank),
        key=lambda n: (n not in ch, n not in hop1, rank[n]),
    )
    return seeds + linked[: total - seeds_n]


for name, use_src, skip in (
    ("briefs only (now)", False, False),
    ("briefs, no test topics", False, True),
    ("briefs + sources", True, False),
    ("briefs + sources, no test topics", True, True),
):
    tot = got = got_top9 = 0
    for q in qs:
        want = {
            leaf[s]
            for f in q["facts"]
            for p in f["files"]
            for s in secs.get(p, [])
            if s in leaf
        }
        order = topic_rank(q["question"], use_src, skip)
        b = set(block(order))
        top = set(order[:9])
        tot += len(want)
        got += len(want & b)
        got_top9 += len(want & top)
    print(
        f"{name:34s} answer topics in block {got}/{tot}   in plain top 9 {got_top9}/{tot}"
    )
