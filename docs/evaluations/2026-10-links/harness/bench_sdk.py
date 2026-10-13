# ruff: noqa: E501 - experiment harness
"""The claude CLI against the Agent SDK for one condensation, same prompt.

Arms: `cli` (hrono's flags today, plus --json-schema), `cli-notools` (the
same with --tools ""), `sdk` (claude-agent-sdk query(), output_format
json_schema, no tools). Sequential, so wall times compare.

Usage: uv run --with claude-agent-sdk python bench_sdk.py
"""

from __future__ import annotations

import asyncio
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import condense_links as c  # noqa: E402
from claude_agent_sdk import (  # noqa: E402
    ClaudeAgentOptions,
    ResultMessage,
    query,
)

IDS = [37133, 42292, 41715]
c.MODEL = "claude-haiku-4-5-20251001"  # the SDK bundles its own CLI; "haiku" resolves differently there


def cli(prompt: str, notools: bool) -> dict:
    argv = [
        "claude",
        "-p",
        "--model",
        c.MODEL,
        "--max-turns",
        "3",
        "--allowed-tools",
        "",
        "--safe-mode",
        "--system-prompt",
        c.SYSTEM,
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(c.SCHEMA),
    ]
    if notools:
        argv += ["--tools", ""]
    t = time.time()
    done = subprocess.run(
        argv, input=prompt, capture_output=True, text=True, cwd=c.WORKDIR
    )
    p = json.loads(done.stdout)
    return {
        "s": time.time() - t,
        "usage": p["usage"],
        "cost": p["total_cost_usd"],
        "ok": p.get("structured_output") is not None,
    }


async def sdk(prompt: str) -> dict:
    opts = ClaudeAgentOptions(
        model=c.MODEL,
        system_prompt=c.SYSTEM,
        tools=[],
        max_turns=3,
        setting_sources=[],
        cwd=str(c.WORKDIR),
        output_format={"type": "json_schema", "schema": c.SCHEMA},
    )
    t = time.time()
    out = None
    async for m in query(prompt=prompt, options=opts):
        if isinstance(m, ResultMessage):
            out = m
    return {
        "s": time.time() - t,
        "usage": out.usage,
        "cost": out.total_cost_usd,
        "ok": out.structured_output is not None,
    }


def main() -> None:
    conn = c.connect()
    tpl = c.template(conn)
    rows = []
    for sid in IDS:
        prompt = (
            tpl.replace("{content}", c.section(conn, sid)["body"]) + c.LINKS
        )
        for arm in ("cli", "cli-notools", "sdk"):
            r = (
                asyncio.run(sdk(prompt))
                if arm == "sdk"
                else cli(prompt, arm == "cli-notools")
            )
            u = r["usage"]
            rows.append({"id": sid, "arm": arm, **r})
            print(
                f"{sid} {arm:12} {r['s']:5.1f}s ok={r['ok']} in={u.get('input_tokens')} "
                f"cache_new={u.get('cache_creation_input_tokens')} cache_read={u.get('cache_read_input_tokens')} "
                f"out={u.get('output_tokens')} ${r['cost']:.4f}",
                flush=True,
            )
    child = resource.getrusage(resource.RUSAGE_CHILDREN)
    print(
        "children cpu",
        child.ru_utime + child.ru_stime,
        "max rss MB",
        child.ru_maxrss / 1e6,
    )
    (c.OUT.parent / "bench.json").write_text(
        json.dumps(rows, indent=1, default=str)
    )


if __name__ == "__main__":
    main()
