# ruff: noqa: E501, E741, B904, B905, B023, E402, SIM115
"""Run each question through the agent arms.

    python3 run_arms.py locate|arch repo|hrono [...]

- repo:  Claude Code (Sonnet), headless, Read/Grep/Glob and the read-only
         shell over the snapshot checkouts. How a coding agent works on this codebase today.
- hrono: the same, plus the exported tree `bcreg` (root.md down to the
         source sections) and `hrono recall bcreg`, which it must start
         from.

Same model, system prompt, turn limit and task text in both arms; the hrono
arm only adds the paragraph describing the knowledge base. Results append to
runs/<set>-<arm>.jsonl and a rerun skips what is done.
"""

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import common

MODEL = "sonnet"
MAX_TURNS = 50
WIDTH = 4

SYSTEM = (
    "You are a senior software engineer working in the BC Registries codebase "
    "(the British Columbia business registry). The current directory holds four "
    "repositories: lear/ (legal-api, colin-api, queue services, jobs), sbc-auth/ "
    "(auth-api, auth-web), sbc-pay/ (pay-api, pay-queue, bcol-api, jobs) and "
    "business-filings-ui/ (Vue front end). You may only read; do not modify files."
)

LOCATE = """Change request:
{task}

Find the EXISTING files that would have to be modified to implement this change (do not count tests, and do not count files that would be newly created). Do not write code.

Reply with only a JSON array of file paths relative to the current directory (for example "lear/legal-api/src/legal_api/..."), most important first, at most 12."""

ARCH = """Question about this codebase:
{question}

Investigate with your tools as much as you need, then reply with only the final answer: precise, naming the concrete components (modules, classes, functions, queues, endpoints) and their file paths relative to the current directory, at most 400 words."""

HRONO = """

A hierarchical knowledge base of this codebase is available, built by hrono:
- {export}/root.md is the root of a tree of topic briefs (LLM-written summaries of the code). Each brief links down to narrower briefs and, at the bottom, to the source sections it summarizes.
- `{h} recall bcreg "<question or keywords>"` prints the source passages and summaries most relevant to a query. A source passage is labelled git:///.../mirror/<repo>/<path>@<commit>; that file is at <repo>/<path> in the current directory.
Before searching the code you MUST start from this knowledge base: run recall at least once and read root.md and the briefs beneath it that cover the task, to learn which components are involved and where they live. Then verify in the code."""


TREE_ONLY = """

You do NOT have the source code. You have only hrono's knowledge base of it, in the current directory:
- root.md is the root of a tree of topic briefs (LLM-written summaries of the code). Each brief links down to narrower briefs and, at the bottom, to the source sections it summarizes.
- `{h} recall bcreg "<question or keywords>"` prints the source passages and summaries most relevant to a query.
Answer from these alone; navigate the tree and run recall as much as you need."""


# Round 2 (E050 rebuild, docs/evaluations/2026-10-bc-registries-v2/): the
# system prompt says only where the code is; the map is the 3-level export of
# the rebuilt tree; recall is not a command the agent runs but hrono's Claude
# Code plugin, whose hooks attach recalled passages to the question and say
# where the map is.
PLUGIN = Path(__file__).resolve().parents[4] / "plugins" / "hrono"
EXPORT_R2 = Path.home() / "hrono-eval" / "export-bcreg-v2-L3"
# the v3 tree: contracts condense and brief prompts (2026-10-bc-registries-v2/)
EXPORT_V3 = Path.home() / "hrono-eval" / "export-bcreg-v3-L3"
HRONO_HOME_R2 = Path.home() / "hrono-eval" / "home-v2"

SYSTEM_CODE_R2 = "The code is in {corpus}."
SYSTEM_TREE_R2 = "The code is not available. A map of it is in {export}."

MAP_R2 = """

Before reading code: open {export}/root.md, choose the areas that fit the question, read their brief.md and the leaf briefs beneath them, then open the source files the leaves list. Passages attached as hrono recall show where to look first."""

MAP_ONLY_R2 = """

Answer from the map: open {export}/root.md, choose the areas that fit the question, read their brief.md and the leaf briefs beneath them. Passages attached as hrono recall show where to look first."""

# Round 3: the questions in plain words (data/arch3.json, plain.py), a map
# instruction that makes it a pointer into the code, the same turn budget for
# both arms, and every arm run twice (suffix a, b).
MAP_R3 = """

Before reading code: open {export}/root.md, choose the areas that fit the question, read their brief.md and the leaf briefs beneath them. The map points you to the right files: open the source files the leaves list, verify there, and follow the flow into code the map does not cover. Passages attached as hrono recall show where to look first."""
TURNS_R3 = 12

# Hard questions (gen_hard.py): the map is searched like code, and both arms
# get the turns a real task gets.
MAP_H = """

Before reading code, use the map of this codebase at {export}: grep it for the words and names that matter, the way you grep code, and read root.md and the briefs that fit. The map points you to the right files: open them, verify there, and follow the flow into code the map does not cover. Passages attached as hrono recall show where to look first."""
TURNS_H = 30

ROUND_2 = {
    # arm: (system, task addition, runs in, loads the plugin, max turns)
    "code-r2": (SYSTEM_CODE_R2, "", None, False, MAX_TURNS),
    "hrono-r2": (SYSTEM_CODE_R2, MAP_R2, None, True, MAX_TURNS),
    "tree-r2": (SYSTEM_TREE_R2, MAP_ONLY_R2, EXPORT_R2, True, MAX_TURNS),
    **{
        f"{arm}-r3{run}": (SYSTEM_CODE_R2, addition, None, plugin, TURNS_R3)
        for arm, addition, plugin in (
            ("code", "", False),
            ("hrono", MAP_R3, True),
        )
        for run in "ab"
    },
    **{
        f"{arm}-h{run}": (SYSTEM_CODE_R2, addition, None, plugin, TURNS_H)
        for arm, addition, plugin in (
            ("code", "", False),
            ("hrono", MAP_H, True),
        )
        for run in "ab"
    },
    **{
        f"hrono-v3{run}": (SYSTEM_CODE_R2, MAP_H, None, True, TURNS_H)
        for run in "ab"
    },
    # the same, with recall attaching map pages (one per leaf topic, each
    # sentence of the prompt embedded alone) instead of passages
    **{
        f"hrono-v3p{run}": (SYSTEM_CODE_R2, MAP_H, None, True, TURNS_H)
        for run in "ab"
    },
}


def run_round_2(kind, arm, q):
    system, addition, cwd, plugin, turns = ROUND_2[arm]
    export = EXPORT_V3 if "-v3" in arm else EXPORT_R2
    prompt = ARCH.format(question=q["question"])
    if cwd is not None:
        prompt = prompt.replace(
            "relative to the current directory", "as the map cites them"
        )
    prompt += addition.format(export=export)
    r = common.run_agent(
        prompt,
        model=MODEL,
        role=f"{kind}:{arm}",
        key=q["qid"],
        max_turns=turns,
        tools=["Read", "Grep", "Glob"],
        system=system.format(corpus=common.CORPUS, export=export),
        add_dirs=[export] if plugin and cwd is None else [],
        disallow_bash=cwd is not None,
        cwd=cwd,
        plugin_dir=PLUGIN if plugin else None,
        env={"HRONO_HOME": str(HRONO_HOME_R2)},
        safe_mode=False,
    )
    return {"qid": q["qid"], "set": kind, "arm": arm, **r}


def items(kind):
    return json.load(open(common.DATA / f"{kind}.json"))


def run_one(kind, arm, q):
    if arm in ROUND_2:
        return run_round_2(kind, arm, q)
    prompt = (
        LOCATE.format(task=q["task"])
        if kind == "locate"
        else ARCH.format(question=q["question"])
    )
    # Both arms keep Claude Code's read-only shell (grep, sed, ls, ...), as an
    # agent normally has it; the hrono arm adds only the recall command.
    tools, add = ["Read", "Grep", "Glob"], []
    cwd = None
    # `<arm>-v2` is the same arm over the rebuilt tree (E050)
    base, _, version = arm.partition("-")
    export, h = (
        (common.EXPORT_V2, common.H_V2)
        if version == "v2"
        else (common.EXPORT, common.H)
    )
    arm_kind = base if version == "v2" else arm
    if arm_kind == "tree":
        # Diagnostic: the knowledge base alone, no checkout. Measures what
        # the tree itself knows, not how an agent combines it with grep.
        prompt = prompt.replace(
            "relative to the current directory",
            "as the knowledge base cites them",
        )
        prompt += TREE_ONLY.format(export=export, h=h)
        tools.append(f"Bash({h} recall:*)")
        cwd = export
    if arm_kind == "hrono":
        prompt += HRONO.format(export=export, h=h)
        tools.append(f"Bash({h} recall:*)")
        add = [export]
    r = common.run_agent(
        prompt,
        model=MODEL,
        role=f"{kind}:{arm}",
        key=q["qid"],
        max_turns=MAX_TURNS,
        tools=tools,
        system=SYSTEM,
        add_dirs=add,
        disallow_bash=False,
        cwd=cwd,
    )
    return {"qid": q["qid"], "set": kind, "arm": arm, **r}


def main(kind, arms):
    qs = items(kind)
    for arm in arms:
        out = common.RUNS / f"{kind}-{arm}.jsonl"
        done = set()
        if out.exists():
            done = {json.loads(l)["qid"] for l in out.open()}
        wanted = set(filter(None, os.environ.get("QIDS", "").split(",")))
        todo = [
            q
            for q in qs
            if q["qid"] not in done and (not wanted or q["qid"] in wanted)
        ]

        def go(q):
            row = run_one(kind, arm, q)
            with common._LOCK, open(out, "a") as f:
                f.write(json.dumps(row) + "\n")
            print(
                kind,
                arm,
                q["qid"],
                row["usage"]["num_turns"],
                row["usage"]["cost_usd"],
                flush=True,
            )

        with ThreadPoolExecutor(WIDTH) as ex:
            list(ex.map(go, todo))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
