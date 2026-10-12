# ruff: noqa: E501, E741, B904, B905, B023, E402, SIM115
"""Shared pieces of the deep evaluation: paths, the cached LLM call, the agent run.

The corpus is BC Registries (lear, sbc-auth, sbc-pay, business-filings-ui)
at the snapshot hrono's tree `bcreg` was built from, extracted without git
history into corpus/ so an agent cannot read later commits.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
import time
from pathlib import Path

ROOT = Path.home() / "hrono-deep"
CORPUS = ROOT / "corpus"
DATA = ROOT / "data"
RUNS = ROOT / "runs"
CACHE = ROOT / "cache" / "llm"
WORKDIR = ROOT / "cache" / "cli-work"
EXPORT = Path.home() / "hrono-eval" / "export-bcreg"
H = str(Path.home() / "hrono-eval" / "bin" / "h")
# The rebuilt tree (E050): its own export and its own server profile.
EXPORT_V2 = Path.home() / "hrono-eval" / "export-bcreg-v2"
H_V2 = str(Path.home() / "hrono-eval" / "bin" / "h2")
TREE = "bcreg"
REPOS = ["lear", "sbc-auth", "sbc-pay", "business-filings-ui"]

_LOCK = threading.Lock()


def _key(model: str, system: str, prompt: str) -> str:
    h = hashlib.sha256()
    for part in (model, "\x00", system, "\x00", prompt):
        h.update(part.encode())
    return h.hexdigest()


class LLMError(RuntimeError):
    pass


def llm(prompt: str, *, system: str, model: str, role: str) -> str:
    """One completion through the Claude CLI, cached by its inputs."""
    key = _key(model, system, prompt)
    path = CACHE / key[:2] / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text())["text"]
    WORKDIR.mkdir(parents=True, exist_ok=True)
    argv = [
        "claude",
        "-p",
        "--model",
        model,
        "--max-turns",
        "3",
        "--tools",
        "",
        "--safe-mode",
        "--system-prompt",
        system,
        "--output-format",
        "json",
    ]
    waits = [10, 30, 90, 300, 300, 300, 300, 300, 300]
    for attempt in range(len(waits) + 1):
        t0 = time.time()
        try:
            proc = subprocess.run(
                argv,
                input=prompt,
                capture_output=True,
                text=True,
                cwd=WORKDIR,
                timeout=600,
            )
        except subprocess.TimeoutExpired:
            if attempt < len(waits):
                time.sleep(waits[attempt])
                continue
            raise LLMError("timeout")
        dt = time.time() - t0
        try:
            payload = json.loads(proc.stdout)
        except ValueError:
            payload = {"is_error": True, "result": proc.stdout[-500:]}
        busy = str(payload.get("api_error_status")) in {"429", "503", "529"}
        ok = (
            not payload.get("is_error")
            and payload.get("subtype") == "success"
            and isinstance(payload.get("result"), str)
        )
        if ok:
            break
        with _LOCK, open(RUNS / "failures.jsonl", "a") as f:
            f.write(
                json.dumps(
                    {
                        "role": role,
                        "model": model,
                        "attempt": attempt,
                        "rc": proc.returncode,
                        "payload": str(payload)[:600],
                        "stderr": proc.stderr[-600:],
                    }
                )
                + "\n"
            )
        if attempt < len(waits) and (busy or proc.returncode != 0):
            time.sleep(waits[attempt])
            continue
        raise LLMError(
            f"claude failed: {str(payload)[:400]} {proc.stderr[-300:]}"
        )
    text = payload["result"]
    usage = payload.get("usage") or {}
    record = {
        "role": role,
        "model": model,
        "seconds": round(dt, 2),
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cache_read": usage.get("cache_read_input_tokens", 0),
        "cache_creation": usage.get("cache_creation_input_tokens", 0),
        "cost_usd": payload.get("total_cost_usd"),
        "key": key,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"text": text, "usage": record}))
    os.replace(tmp, path)
    RUNS.mkdir(parents=True, exist_ok=True)
    with _LOCK, open(RUNS / "calls.jsonl", "a") as f:
        f.write(json.dumps(record) + "\n")
    return text


def run_agent(
    prompt,
    *,
    model,
    role,
    key,
    max_turns,
    tools,
    system=None,
    add_dirs=(),
    disallow_bash=True,
    timeout=3600,
    cwd=None,
    plugin_dir=None,
    env=None,
    safe_mode=True,
):
    """One headless Claude Code agent run in the corpus, logged with its tool calls.

    ``safe_mode`` runs with no customization at all. Safe mode also turns
    plugins off, so the round-2 arms, which load hrono's Claude Code plugin
    (its hooks attach recall and the map's location), run without it and are
    isolated with ``--setting-sources project``: the operator's own settings,
    plugins and hooks stay out. Every arm of a round uses the same isolation,
    and the hook events are recorded.
    """
    if safe_mode:
        isolation = ["--safe-mode"]
    else:
        isolation = ["--setting-sources", "project", "--include-hook-events"]
        if plugin_dir:
            isolation += ["--plugin-dir", str(plugin_dir)]
    argv = [
        "claude",
        "-p",
        "--model",
        model,
        "--max-turns",
        str(max_turns),
        *isolation,
        "--output-format",
        "stream-json",
        "--verbose",
        "--disallowedTools",
        "Edit,Write,WebFetch,WebSearch,Task,NotebookEdit,TodoWrite",
    ]
    if system:
        argv += ["--system-prompt", system]
    for d in add_dirs:
        argv += ["--add-dir", str(d)]
    if disallow_bash:
        argv += ["--disallowedTools", "Bash"]
    argv += ["--allowedTools", ",".join(tools)]
    waits = [60, 300, 300, 300, 300, 300, 300]
    for attempt in range(len(waits) + 1):
        t0 = time.time()
        try:
            proc = subprocess.run(
                argv,
                input=prompt,
                capture_output=True,
                text=True,
                cwd=cwd or CORPUS,
                timeout=timeout,
                env={**os.environ, **(env or {})},
            )
            out = proc.stdout
        except subprocess.TimeoutExpired as e:
            out = (
                (e.stdout or b"").decode()
                if isinstance(e.stdout, bytes)
                else (e.stdout or "")
            )
        wall = time.time() - t0
        payload, calls, hooks = {}, [], []
        for line in out.splitlines():
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get("type") == "result":
                payload = ev
            elif ev.get("type") == "system" and "hook" in str(
                ev.get("subtype")
            ):
                hooks.append(json.dumps(ev)[:20000])
            elif ev.get("type") == "assistant":
                for part in ev.get("message", {}).get("content", []):
                    if part.get("type") == "tool_use":
                        calls.append(
                            {
                                "tool": part.get("name"),
                                "input": json.dumps(part.get("input"))[:1000],
                            }
                        )
        busy = str(payload.get("api_error_status")) in {
            "429",
            "503",
            "529",
        } or (not payload and attempt < len(waits))
        if busy and attempt < len(waits):
            with _LOCK, open(RUNS / "failures.jsonl", "a") as f:
                f.write(
                    json.dumps(
                        {
                            "role": role,
                            "key": key,
                            "attempt": attempt,
                            "payload": str(payload)[:400],
                            "tail": out[-400:],
                        }
                    )
                    + "\n"
                )
            time.sleep(waits[attempt])
            continue
        break
    usage = payload.get("usage") or {}
    rec = {
        "role": role,
        "model": model,
        "key": key,
        "seconds": round(wall, 1),
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cache_read": usage.get("cache_read_input_tokens", 0),
        "cache_creation": usage.get("cache_creation_input_tokens", 0),
        "cost_usd": payload.get("total_cost_usd"),
        "num_turns": payload.get("num_turns"),
        "subtype": payload.get("subtype"),
    }
    with _LOCK, open(RUNS / "calls.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    return {
        "answer": payload.get("result") or "",
        "tools": calls,
        "hooks": hooks,
        "usage": rec,
    }
