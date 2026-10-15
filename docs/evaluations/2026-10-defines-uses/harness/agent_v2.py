# ruff: noqa: E501, SIM115, B007 - experiment harness; prompts read best whole
"""Round 8: what the agent is told, and links it can follow.

Agents with the map grep it, read one to three briefs, then read code and
stop after about 15 tool calls (of 30). The map instruction says "the map
points you to the right files", so they use it only to locate. Here:
- each leaf brief of the slice ends with `## Linked topics`: the briefs of
  the topics it exchanges messages, calls or data with (from links.json),
  as paths an agent can open;
- the instruction says what a brief holds and asks the agent to read the
  brief of every part the question touches, follow the links, then check
  the claims it will make in code.
Export: `export-bcreg-v3w-L3` (v3z without flows/ and condensations.md).

Usage: uv run python agent_v2.py export
       uv run --with claude-agent-sdk python agent_v2.py run <qid> <name>
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path

import exp

SRC = Path.home() / "hrono-eval" / "export-bcreg-v3z-L3"
EXPORT = (
    Path.home() / "hrono-eval" / os.environ.get("EXPORT", "export-bcreg-v3w-L3")
)
LINKED = 12  # linked topics listed per brief at most

MAP_V2 = """

A map of this codebase is at {export}. It is a tree of briefs: each folder is a topic, and each leaf topic's brief.md describes a group of source files precisely - the check that guards each entry point with its condition, every branch and the state it sets, what happens on each error, what it sends and receives - and under `## Linked topics` it lists the other topics it exchanges messages, calls or data with. One brief covers what would take many file reads: use the briefs to understand behaviour and the code to confirm it.

How to work:
1. Grep the map's brief.md files for each component, queue, endpoint, status and term in the question, and read in full the leaf briefs the hits point to.
2. From each brief you read, follow `## Linked topics` to every topic on the other end of a message, call or shared record that the question touches, and read those briefs too. A question about how work moves is answered only when every part the work passes through is covered, including what happens when a step fails.
3. Then open the source files to check each claim you will make - exact conditions, lists, ordering and error handling - and whatever a brief says is not shown. Where code and brief disagree, the code wins.
4. Answer every part of the question."""


MAP_V3 = """

A map of this codebase is at {export}. It is a tree of briefs: each folder is a topic, and each leaf topic's brief.md describes a group of source files precisely - the checks that guard each entry point with their conditions, every branch and the state it sets, what happens on each error, what it sends and receives - and its Connections section says what the topics on the other side of each message, call or shared record do with it; `## Linked topics` gives their paths. One brief covers what would take many file reads.

How to work:
1. Grep the map's brief.md files for the components, queues, endpoints, statuses and terms in the question, and read in full the leaf briefs the hits point to.
2. Trace the work end to end before reading code. From each brief's Connections and Linked topics, list the parts the work passes through: who sends it, who receives it next and what that part does with it, what each part does when a step fails, and which job or listener retries, repairs or re-drives it - or that nothing does. Read the brief of every part on that list you have not read yet, and repeat until the list is complete for every part of the question. This usually takes 5 to 10 briefs; they are cheap to read.
3. Then open the source files to check the claims you will make - exact conditions, lists, ordering and error handling - and whatever a brief says it could not find. Where code and brief disagree, the code wins.
4. Answer every part of the question, with the consequences the briefs give for each part involved."""


def map_plugin(export: Path) -> str:
    """What the hrono plugin now says: its session note and the hrono skill."""
    plugin = exp.HERE.parents[3] / "plugins" / "hrono"
    js = (plugin / "scripts" / "hooks" / "session-start.js").read_text()
    parts = re.findall(
        r'(`[^`]*`|"[^"]*")',
        js[
            js.index("It is exported at") - 2 : js.index(
                "lines.push(`It is not"
            )
        ],
    )
    note = "".join(p[1:-1] for p in parts)
    note = note.replace("${config.folder}", str(export)).replace(
        " (${when})", ""
    )
    note = note.replace("${root}", str(export / "root.md"))
    skill = (
        (plugin / "skills" / "hrono" / "SKILL.md")
        .read_text()
        .split("---", 2)[2]
    )
    head = 'This project has an hrono map (tree "bcreg"): briefs of everything its sources hold, from one overview down to the files. '
    return "\n\n" + head + note + "\n\nThe hrono skill:\n" + skill.strip()


def folders() -> dict[int, Path]:
    out = {}
    for brief in EXPORT.rglob("brief.md"):
        tail = brief.parent.name.rsplit("-", 1)[-1]
        if tail.isdigit():
            out[int(tail)] = brief
    return out


def export() -> None:
    if EXPORT.exists():
        shutil.rmtree(EXPORT)
    shutil.copytree(SRC, EXPORT)
    shutil.rmtree(EXPORT / "flows", ignore_errors=True)
    (EXPORT / "condensations.md").unlink(missing_ok=True)
    where = folders()
    rank = {"shares": 0, "def": 1}
    by_leaf: dict[int, dict[int, list[dict]]] = {}
    for link in exp.load("links.json"):
        a, b = link["from_leaf"], link["to_leaf"]
        if a == b or a not in where or b not in where:
            continue
        by_leaf.setdefault(a, {}).setdefault(b, []).append(link)
        flipped = {
            **link,
            "direction": {"sends": "receives", "receives": "sends"}.get(
                link["direction"], "read by"
            ),
        }
        by_leaf.setdefault(b, {}).setdefault(a, []).append(flipped)
    done = 0
    for leaf, others in by_leaf.items():
        brief = where[leaf]
        order = sorted(
            others.items(),
            key=lambda kv: (
                min(rank.get(x["kind"], 2) for x in kv[1]),
                -len(kv[1]),
            ),
        )[:LINKED]
        lines = ["", "## Linked topics", ""]
        for other, links in order:
            rel = Path(
                *([".."] * len(brief.parent.relative_to(EXPORT).parts)),
                where[other].relative_to(EXPORT),
            )
            title = (
                where[other].read_text().splitlines()[0].lstrip("# ").strip()
            )
            names = sorted(
                {
                    f"{'shares' if x['kind'] == 'shares' else x['direction']} `{x['name']}`"
                    for x in links
                }
            )[:4]
            lines.append(f"- [{title}]({rel}): " + "; ".join(names))
        brief.write_text(
            brief.read_text().rstrip() + "\n" + "\n".join(lines) + "\n"
        )
        done += 1
    print("briefs with linked topics", done, "export", EXPORT)


def oracle(qid: str) -> str:
    """Ceiling test: the leaf briefs of the topics that hold this question's
    facts, inline. Not a recall method - a bound on what briefs can do."""
    from exp import c, sl

    conn = c.connect()
    leaf = exp.leaf_map(conn)
    secs: dict[str, list[int]] = {}
    for sid, source, path in conn.execute(
        "SELECT id, source, path FROM sections"
    ):
        secs.setdefault(f"{source}/{path}", []).append(sid)
    q = [x for x in sl.questions() if x["qid"] == qid][0]
    nodes = sorted(
        {
            leaf[s]
            for f in q["facts"]
            for p in f["files"]
            for s in secs.get(p, [])
            if s in leaf
        }
    )
    where = folders()
    parts = [
        f"=== {where[n].relative_to(EXPORT)} ===\n{where[n].read_text()}"
        for n in nodes
        if n in where
    ]
    return "The briefs of the topics this question touches:\n\n" + "\n\n".join(
        parts
    )


def run(qid: str, name: str, words: int = 900) -> None:
    import common
    import run_arms

    q = [
        x
        for x in json.load(open(common.DATA / "hard15.json"))
        if x["qid"] == qid
    ][0]
    prompt = run_arms.ARCH.format(question=q["question"]).replace(
        "at most 400 words", f"at most {words} words"
    )
    prompt += (MAP_V3 if os.environ.get("MAP") == "3" else MAP_V2).format(
        export=EXPORT
    )
    if os.environ.get("ORACLE"):
        prompt += "\n\n" + oracle(qid)
    r = common.run_agent(
        prompt,
        model=name.partition("@")[2] or "sonnet",
        role=f"hard15:{name}",
        key=qid,
        max_turns=run_arms.TURNS_H,
        tools=["Read", "Grep", "Glob"],
        system=run_arms.SYSTEM_CODE_R2.format(
            corpus=common.CORPUS, export=EXPORT
        ),
        add_dirs=[EXPORT],
        disallow_bash=False,
        cwd=None,
        plugin_dir=None,
        env={},
        safe_mode=False,
    )
    out = common.RUNS / f"hard15-{name}.jsonl"
    with out.open("a") as f:
        f.write(
            json.dumps({"qid": qid, "set": "hard15", "arm": name, **r}) + "\n"
        )


if __name__ == "__main__":
    if sys.argv[1] == "export":
        export()
    else:
        sys.path.insert(
            0,
            str(
                exp.HERE.parents[1] / "2026-10-bc-registries-agents" / "harness"
            ),
        )
        run(sys.argv[2], sys.argv[3])
