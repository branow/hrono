# ruff: noqa: E501, E741, B904, B905, B007, B023
"""The agentic arm: a Claude Code agent answers with tools, with and without hrono.

    uv run python run_agents.py agent-repo agent-hrono

- agent-repo:  Read, Grep and Glob over the checkout. This is how a coding
  agent answers a repository question today.
- agent-hrono: the same tools and checkout, plus hrono's two agent surfaces:
  the exported tree (root.md down to sections) and `hrono recall`.

Both use the same model, system prompt, turn limit and answer instruction,
and run headless with --safe-mode (no CLAUDE.md, hooks, plugins or MCP).
The questions are a fixed subset: every third SWE-QA question per repository
(16 x 3 = 48). Answers land in runs/answers/<arm>.jsonl in the same shape as
the single-shot systems, so run_eval.py judges them unchanged, plus the
agent's turns, tokens, cost and wall time.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time

import common
import run_eval

MODEL = "sonnet"
MAX_TURNS = 40
H = str(common.ROOT / "bin" / "h")

TASK = """Answer this question about the {repo} repository, which is checked out in the current directory.

Question: {question}

Investigate with your tools as much as you need, then reply with only the final answer: precise, naming the files, classes and functions involved, at most 300 words."""

HRONO_HINT = """

A hierarchical knowledge base of this repository is available to help you navigate:
- {export}/root.md is the root of a tree of topic briefs (LLM-written summaries) that links down level by level to the source sections; each brief cites the sections it came from.
- `{h} recall {repo} "<question or keywords>"` prints the source passages most relevant to a query, with their file paths.
Use them to find where to look, then verify in the code."""

HRONO_FIRST = """

Before searching the code, you MUST start from this knowledge base: run `{h} recall {repo} "<keywords>"` at least once and read {export}/root.md and the brief(s) beneath it that cover the question. Use what they point at to decide where to look, then verify in the code."""


def subset() -> list[dict]:
    return [
        q
        for repo in common.REPO_NAMES
        for i, q in enumerate(common.questions(repo))
        if i % 3 == 0
    ]


def run_one(arm: str, q: dict) -> dict:
    repo = q["repo"]
    export = common.ROOT / "exports" / repo
    prompt = TASK.format(repo=repo, question=q["question"])
    tools = ["Read", "Grep", "Glob"]
    argv = [
        "claude",
        "-p",
        "--model",
        MODEL,
        "--max-turns",
        str(MAX_TURNS),
        "--safe-mode",
        "--system-prompt",
        run_eval.SYSTEM,
        "--output-format",
        "stream-json",
        "--verbose",
        "--disallowedTools",
        "Edit,Write,WebFetch,WebSearch,Task,NotebookEdit",
    ]
    if arm in ("agent-hrono", "agent-hrono-first"):
        prompt += HRONO_HINT.format(export=export, h=H, repo=repo)
        if arm == "agent-hrono-first":
            prompt += HRONO_FIRST.format(export=export, h=H, repo=repo)
        tools.append(f"Bash({H} recall:*)")
        argv += ["--add-dir", str(export)]
    else:
        argv += ["--disallowedTools", "Bash"]
    argv += ["--allowedTools", ",".join(tools)]
    t0 = time.time()
    proc = subprocess.run(
        argv,
        input=prompt,
        capture_output=True,
        text=True,
        cwd=common.REPOS / repo,
        timeout=1800,
    )
    wall = time.time() - t0
    payload, tools_used = {}, []
    for line in proc.stdout.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "result":
            payload = ev
        elif ev.get("type") == "assistant":
            for part in ev.get("message", {}).get("content", []):
                if part.get("type") == "tool_use":
                    tools_used.append(
                        {
                            "tool": part.get("name"),
                            "input": str(part.get("input"))[:300],
                        }
                    )
    usage = payload.get("usage") or {}
    rec = {
        "role": f"agent:{arm}",
        "model": MODEL,
        "seconds": round(wall, 2),
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cache_read": usage.get("cache_read_input_tokens", 0),
        "cache_creation": usage.get("cache_creation_input_tokens", 0),
        "cost_usd": payload.get("total_cost_usd"),
        "key": q["qid"],
    }
    with open(common.RUNS / "calls.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    return {
        "qid": q["qid"],
        "repo": repo,
        "system": arm,
        "question": q["question"],
        "answer": payload.get("result") or "",
        "subtype": payload.get("subtype"),
        "num_turns": payload.get("num_turns"),
        "seconds": round(wall, 2),
        "tools": tools_used,
        "usage": rec,
        "context": "",
        "context_chars": 0,
        "labels": [],
    }


def main(arms):
    run_eval.WIDTH = 4
    for arm in arms:
        out = run_eval.ANSWERS / f"{arm}.jsonl"
        out.parent.mkdir(parents=True, exist_ok=True)
        done = run_eval._done(out)
        todo = [q for q in subset() if q["qid"] not in done]
        run_eval.run(
            lambda q: run_eval._append(out, run_one(arm, q)),
            todo,
            f"agent {arm}",
        )


if __name__ == "__main__":
    main(sys.argv[1:])
