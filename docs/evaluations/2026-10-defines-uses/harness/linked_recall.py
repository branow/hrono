# ruff: noqa: E501 - experiment harness
"""Round 6: recall that follows links, one question at a time.

Recall ranks leaf topics by the cosine of their brief passages to the
question; the topics a hard question also needs (the filer, the emailer,
the repair job) rank 19th to 73rd, but they are linked to the top topics by
name (a shared queue subject, a publish call). This builds the recall block
a link-following recall would attach: the top SEEDS topics plus the topics
linked to them, each with its best-matching brief passages, within the
plugin's 10,000-character cap. The agent run gets it in the prompt, where
the plugin's hook would put it; the plugin is off.

Usage: uv run --extra embed python linked_recall.py block QID
       uv run python linked_recall.py run QID RUN
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import exp

ROOT = exp.HERE.parents[3]
sys.path.insert(0, str(ROOT / "src"))
AGENTS = exp.HERE.parents[1] / "2026-10-bc-registries-agents" / "harness"
sys.path.insert(0, str(AGENTS))

DB = Path.home() / "hrono-eval" / "db" / "hrono-v3z.db"
EXPORT = Path.home() / "hrono-eval" / "export-bcreg-v3z-L3"
SEEDS = 3  # best topics by their brief passages
TOPICS = 12  # topics in the block, seeds first
PER_TOPIC = 2  # brief passages per seed topic; 1 per linked topic
CLIP = 700  # characters of a passage shown
CAP = 10_000  # characters Claude Code shows inline


def block(qid: str) -> str:
    from hrono.embed.model import resolve_embedding_model
    from hrono.embed.runner import encoder_for
    from hrono.recall import query, similarity

    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    cfg = resolve_embedding_model(db, {})
    enc = encoder_for(str(cfg["model"]))
    q = [x for x in json.load(open(Path.home() / "hrono-deep/data/hard15.json")) if x["qid"] == qid][0]
    level = dict(db.execute("SELECT id, level FROM nodes"))
    title = {n: (t or "").strip().splitlines()[0].lstrip("# ") for n, t in db.execute("SELECT node_id, text FROM briefs")}
    passages = {
        r["id"]: (int(r["source"].removeprefix("node-")), r["content_hash"])
        for r in db.execute("SELECT id, source, content_hash FROM passages WHERE source_type = 'node'")
    }
    vecs = [list(v) for v in enc(query.sentences(q["question"]))]
    by_topic: dict[int, list[tuple[float, int]]] = {}
    for pid, cos in similarity.ranked(db, vecs, str(cfg["name"])):
        if pid in passages and level.get(passages[pid][0]) == 0:
            by_topic.setdefault(passages[pid][0], []).append((cos, pid))
    order = sorted(by_topic, key=lambda n: -by_topic[n][0][0])
    seeds = order[:SEEDS]
    # topics linked to a seed, or to a topic linked to one (two hops), the
    # ones closest to the question first
    links = exp.load("links.json")
    near: dict[int, set[int]] = {}
    channel: dict[int, int] = {}  # channel links from a seed to a topic
    for item in links:
        a, b = item["from_leaf"], item["to_leaf"]
        near.setdefault(a, set()).add(b)
        near.setdefault(b, set()).add(a)
        if item["kind"] in ("shares", "sends", "receives"):
            for x, y in ((a, b), (b, a)):
                if x in seeds:
                    channel[y] = channel.get(y, 0) + 1
    hop1 = {b for s in seeds for b in near.get(s, ())}
    hop2 = {c for b in hop1 for c in near.get(b, ())}
    rank = {n: i for i, n in enumerate(order)}
    # a topic tied to a seed by a channel (a shared queue subject or topic,
    # a send matched to a receive) first, then the rest by fit to the question
    linked = sorted(
        (n for n in (hop1 | hop2) - set(seeds) if level.get(n) == 0 and n in rank),
        key=lambda n: (n not in channel, n not in hop1, rank[n]),
    )
    chosen = (seeds + linked)[:TOPICS]
    out = [
        "hrono recall: the topics that fit this question, and the topics linked to them "
        f"(by a shared name such as a queue subject or a call). Each topic's brief is at "
        f"{EXPORT}/<area>/<topic>/brief.md; the best-matching lines of each are below."
    ]
    for n in chosen:
        hits = sorted(by_topic.get(n, []), reverse=True)[
            : PER_TOPIC if n in seeds else 1
        ]
        texts = []
        for _, pid in sorted(hits, key=lambda h: h[1]):
            body = db.execute("SELECT body FROM contents WHERE content_hash = ?", (passages[pid][1],)).fetchone()[0]
            body = (body.decode() if isinstance(body, bytes) else body).strip()
            texts.append(body if len(body) <= CLIP else body[:CLIP] + " …")
        folder = next(EXPORT.rglob(f"*-{n}"), None)
        rel = folder.relative_to(EXPORT) if folder else "?"
        why = "fits the question" if n in seeds else "linked to a topic above"
        out.append(f"\n## {title.get(n, n)} ({why}) - {rel}/brief.md\n" + "\n...\n".join(texts))
    text = "\n".join(out)
    while len(text) > CAP and len(out) > 2:
        out.pop()
        text = "\n".join(out)
    return text


def run(qid: str, name: str, words: int = 400, hrono: bool = True) -> None:
    """One agent run. `words` lifts the answer cap: a question of seven facts
    over three services does not fit 400 words, whichever arm answers it."""
    import common
    import run_arms

    q = [x for x in json.load(open(common.DATA / "hard15.json")) if x["qid"] == qid][0]
    prompt = run_arms.ARCH.format(question=q["question"]).replace(
        "at most 400 words", f"at most {words} words"
    )
    if hrono:
        recall = (exp.DATA / f"recall-{qid}.txt").read_text()
        prompt += run_arms.MAP_H.format(export=EXPORT) + "\n\n" + recall
    r = common.run_agent(
        prompt,
        model="sonnet",
        role=f"hard15:{name}",
        key=qid,
        max_turns=run_arms.TURNS_H,
        tools=["Read", "Grep", "Glob"],
        system=run_arms.SYSTEM_CODE_R2.format(corpus=common.CORPUS, export=EXPORT),
        add_dirs=[EXPORT] if hrono else [],
        disallow_bash=False,
        cwd=None,
        plugin_dir=None,
        env={},
        safe_mode=False,
    )
    out = common.RUNS / f"hard15-{name}.jsonl"
    with out.open("a") as f:
        f.write(json.dumps({"qid": qid, "set": "hard15", "arm": name, **r}) + "\n")


if __name__ == "__main__":
    if sys.argv[1] == "block":
        text = block(sys.argv[2])
        (exp.DATA / f"recall-{sys.argv[2]}.txt").write_text(text)
        print(len(text), "chars")
        print("\n".join(line for line in text.splitlines() if line.startswith("## ")))
    else:
        # run QID NAME [WORDS] [code]
        run(
            sys.argv[2],
            sys.argv[3],
            int(sys.argv[4]) if len(sys.argv) > 4 else 400,
            not (len(sys.argv) > 5 and sys.argv[5] == "code"),
        )
