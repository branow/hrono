# ruff: noqa: E501 - experiment harness
"""One agent run, step by step, from the stream `common.run_agent` saves.

Each step is what the agent said, the tool it called with its full input, and
what came back: its size, its opening lines, and the whole of it folded. The
top lists the briefs read (and how often), the code files read and the cost,
so a wasted turn - a brief read twice, a giant brief read whole, a grep that
should have been a read - shows at a glance.

Usage: python steps.py <trace.jsonl> [out.md]   (default: next to the trace)
"""

from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

HEAD = 12  # result lines shown before the fold


def _text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            p.get("text", "") if isinstance(p, dict) else str(p)
            for p in content
        )
    return str(content)


def _target(name: str, args: dict) -> str:
    """What a call touches, short: a brief's topic, a file, a pattern."""
    if name == "Read":
        part = "".join(
            f" {k}={args[k]}" for k in ("offset", "limit") if k in args
        )
        return str(args.get("file_path", "")) + part
    if name == "Bash":
        return str(args.get("command", ""))
    return json.dumps(args)


def _brief(path: str) -> str | None:
    """`<topic folder>` for a brief or the root under the export."""
    m = re.search(r"([^/]+)/brief\.md\b", path)
    if m:
        return m.group(1)
    return "root.md" if "/root.md" in path else None


def _fence(body: str) -> str:
    ticks = "````" if "```" in body else "```"
    return f"{ticks}\n{body}\n{ticks}"


def render(trace: Path) -> str:
    events = [
        json.loads(line)
        for line in trace.read_text().splitlines()
        if line.startswith("{")
    ]
    results: dict[str, str] = {}
    for ev in events:
        if ev.get("type") == "user":
            for part in ev.get("message", {}).get("content", []):
                if isinstance(part, dict) and part.get("type") == "tool_result":
                    results[part["tool_use_id"]] = _text(part.get("content"))
    start = next((ev for ev in events if ev.get("type") == "prompt"), {})
    prompt = start.get("text", "(not saved)")
    final = next((ev for ev in events if ev.get("type") == "result"), {})

    steps: list[str] = []
    briefs: collections.Counter[str] = collections.Counter()
    brief_bytes: dict[str, int] = {}
    code: list[str] = []
    n = shell = 0
    for ev in events:
        if ev.get("type") != "assistant":
            continue
        for part in ev.get("message", {}).get("content", []):
            kind = part.get("type")
            if kind in ("text", "thinking"):
                said = (part.get("text") or part.get("thinking") or "").strip()
                if said:
                    steps.append(f"> {said}".replace("\n", "\n> "))
            elif kind == "tool_use":
                n += 1
                name, args = part["name"], part.get("input", {})
                out = results.get(part["id"], "(no result)")
                target = _target(name, args)
                topic = _brief(target) if name == "Read" else None
                if topic:
                    briefs[topic] += 1
                    brief_bytes[topic] = len(out)
                elif name == "Read":
                    code.append(target)
                elif name == "Bash":
                    shell += 1
                again = (
                    f" - read {briefs[topic]}x"
                    if topic and briefs[topic] > 1
                    else ""
                )
                lines = out.splitlines()
                shown = "\n".join(lines[:HEAD])
                rest = (
                    f"\n<details><summary>all {len(lines)} lines</summary>\n\n"
                    f"{_fence(out)}\n\n</details>"
                    if len(lines) > HEAD
                    else ""
                )
                call = (
                    _fence(target)
                    if name == "Bash"
                    else f"`{name}` {target if name == 'Read' else _fence(target)}"
                )
                steps.append(
                    f"### {n}. {name}{': ' + topic if topic else ''}{again}\n\n"
                    f"{call}\n\n"
                    f"{len(out):,} chars, {len(lines)} lines back\n\n"
                    f"{_fence(shown)}{rest}"
                )

    usage = final.get("usage") or {}
    head = [
        f"# {trace.stem}",
        "",
        f"- tool calls: {n}, turns: {final.get('num_turns')}, "
        f"ended: {final.get('subtype')}",
        f"- shell commands: {shell} (their brief reads are not in the table)",
        f"- cost: ${final.get('total_cost_usd') or 0:.2f}, "
        f"output tokens: {usage.get('output_tokens', 0):,}",
        "",
        "## Briefs read",
        "",
        "| brief | times | size |",
        "|---|---|---|",
        *(
            f"| {t} | {c} | {brief_bytes[t]:,} |"
            for t, c in briefs.most_common()
        ),
        "",
        "## Code files read",
        "",
        *(f"- {c}" for c in code),
        "",
        "## Prompt",
        "",
        f"<details><summary>{len(prompt):,} chars</summary>\n\n"
        f"{_fence(prompt)}\n\n</details>",
        "",
        "## Steps",
        "",
    ]
    tail = ["", "## Answer", "", final.get("result") or "(none)", ""]
    return "\n".join(head) + "\n\n".join(steps) + "\n".join(tail)


if __name__ == "__main__":
    trace = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else trace.with_suffix(".md")
    out.write_text(render(trace))
    print(out)
