# ruff: noqa: E501 - experiment harness; prompts read best whole
"""Round 4: a leaf brief prompt that keeps the condensations' detail.

The seeded brief prompt says "the notes stay available below this
description, so leave detail to them", drops lists and enum values and aims
for 300-600 words. Nothing below a brief is shown to an agent, so that
detail is lost. This prompt asks the brief to carry every decision, list,
condition, error path and call out of its condensations, with no word
target. Input: the ledger condensations of the topic's sections plus the
linked condensations of other topics (as arm B). Then the export copy
`export-bcreg-v3z-L3` (v3y with these leaf briefs) for the agent run.

Usage: uv run --with claude-agent-sdk python wide.py brief
       uv run python wide.py export
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import exp
import export_v3y as ev
from exp import c, sl

WIDE = """Below are the condensations of the sections of one topic of a larger system, each under its source's name, followed by condensations of sections in other topics that this topic is linked to. Write the brief of this topic. A reader (human or AI agent) gets only this brief - the condensations are not shown anywhere - so everything a reader needs to answer exact questions about this topic must be in it.

Write, in this order:
1. One or two sentences: what this topic does and what it hands work to or takes work from.
2. Contract: what reaches it and from where, what it sends or writes and to where, with the shape of messages or records that cross the boundary.
3. Entry points: for each route, handler, listener, job or public function, the check that guards it with its exact condition (what it compares with what), or that the condensations show none.
4. Decisions: every branch that changes an outcome, one line each - the exact condition, the outcome, and the function that holds it. When a condition tests membership in a list, set or group, copy every member verbatim; never write "certain types" or "some statuses". Include every state a record moves to and every check that refuses a caller.
5. Order and failure: what is saved or committed before a step that can fail; for each error handler what it catches and what happens (re-raised, retried and how often, recorded where, only logged, sent to Sentry, swallowed), and which later steps still run.
6. Calls out: each call to another service, queue, topic, email or table - the target as written, the credential or token sent, the payload shape.
7. Connections: from the block of linked condensations, for each connection that matters, one line - the other topic and source, what crosses and in which direction, and the condition each side checks or that none is shown. State a conclusion the two sides support together (for example which credential the receiving side therefore sees, or a case one side sends that the other does not handle). Ignore linked condensations that only share a name.
8. Absences the condensations report (a missing check, duplicate guard or retry; a branch one implementation has and another lacks), as what the code shows, never as a guess.
9. The sources to open first, and what each holds.

Every check you mention comes with its condition, or "(condition not in the condensations)"; never let a check's name stand for a guarantee. Keep names, values and lists verbatim. No word target: be as long as the decisions require, but one line per fact, no padding, no repetition. Leave out only startup and wiring, logging setup, licences and test plumbing; a test is named only when it pins down a decision. If the topic covers unrelated things, give each its own part. Never describe the text you were given ("these condensations", "this group"); write about the topic itself. Mention only what the condensations say. Output only the brief in markdown.

{content}"""


def brief() -> None:
    sys.path.insert(0, str(exp.HERE.parents[3] / "src"))
    from hrono.summarize.briefs import labeled

    conn = c.connect()
    ledger = exp.load("ledger.json")
    links = exp.load("links.json")
    condensed = exp.all_condensed()
    title = sl.titles(conn)
    out = exp.load("briefs-W.json")

    def one(node: int):
        conn2 = c.connect()

        def notes(sid: int) -> str:
            got = ledger.get(str(sid))
            return got["text"] if got else exp.stored_condensation(conn2, sid)

        rows = conn2.execute(
            "SELECT s.id, s.path FROM node_members m JOIN sections s ON s.id = m.section_id "
            "WHERE m.node_id = ? ORDER BY s.uri, s.id",
            (node,),
        ).fetchall()
        content = labeled([(path, notes(sid)) for sid, path in rows])
        block = exp.linked_block(node, links, condensed, title, conn2, notes)
        if block:
            content += "\n\n=== LINKED CONDENSATIONS FROM OTHER TOPICS ===\n" + block
        got = exp.ask(WIDE.replace("{content}", content), exp.SONNET)
        return str(node), got

    todo = [n for n in exp.slice_leaves(conn) if str(n) not in out]
    for node, got in exp.run_pool(one, todo, 4):
        out[node] = got
        exp.save("briefs-W.json", out)
    words = [len((v.get("text") or "").split()) for v in out.values()]
    print("briefs", len(out), "errors", sum("error" in v for v in out.values()),
          "words", round(sum(words) / len(words)), "max", max(words),
          "cost", round(sum(v.get("cost") or 0 for v in out.values()), 2))


def export() -> None:
    src = ev.DST
    dst = Path.home() / "hrono-eval" / "export-bcreg-v3z-L3"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    ev.DST = dst
    for node, v in exp.load("briefs-W.json").items():
        d = ev.folder(int(node))
        (d / "condensations.md").unlink(missing_ok=True)
        ev.swap(d / "brief.md", v["text"], "## Sources")
    print("->", dst)


if __name__ == "__main__":
    {"brief": brief, "export": export}[sys.argv[1]]()
