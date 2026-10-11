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
import sys
from concurrent.futures import ThreadPoolExecutor

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


def items(kind):
    return json.load(open(common.DATA / f"{kind}.json"))


def run_one(kind, arm, q):
    prompt = (
        LOCATE.format(task=q["task"])
        if kind == "locate"
        else ARCH.format(question=q["question"])
    )
    # Both arms keep Claude Code's read-only shell (grep, sed, ls, ...), as an
    # agent normally has it; the hrono arm adds only the recall command.
    tools, add = ["Read", "Grep", "Glob"], []
    cwd = None
    if arm == "tree":
        # Diagnostic: the knowledge base alone, no checkout. Measures what
        # the tree itself knows, not how an agent combines it with grep.
        prompt = prompt.replace(
            "relative to the current directory",
            "as the knowledge base cites them",
        )
        prompt += TREE_ONLY.format(export=common.EXPORT, h=common.H)
        tools.append(f"Bash({common.H} recall:*)")
        cwd = common.EXPORT
    if arm == "hrono":
        prompt += HRONO.format(export=common.EXPORT, h=common.H)
        tools.append(f"Bash({common.H} recall:*)")
        add = [common.EXPORT]
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
        todo = [q for q in qs if q["qid"] not in done]

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
