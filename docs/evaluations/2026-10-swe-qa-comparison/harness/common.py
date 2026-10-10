# ruff: noqa: E501, E741, B904, B905, B007, B023
"""Shared pieces of the benchmark: paths, questions, corpus, and the LLM call.

Every system is answered and judged through the same `llm()` call, which is
the same headless Claude CLI invocation hrono's claude-code provider makes
(`--safe-mode`, a replaced system prompt, no tools). Each call is cached on
disk by its exact inputs, so a rerun reproduces it and an interrupted run
resumes, and each real call is appended to `runs/calls.jsonl` with its tokens.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import threading
import time
from pathlib import Path

ROOT = Path.home() / "hrono-bench"
REPOS = ROOT / "repos"
BENCH = ROOT / "SWE-QA-Bench" / "Benchmark"
RUNS = ROOT / "runs"
CACHE = ROOT / "cache" / "llm"
WORKDIR = ROOT / "cache" / "cli-work"
HRONO_DB = ROOT / "db" / "hrono.db"
REPO_NAMES = os.environ.get("BENCH_REPOS", "flask,requests,streamlink").split(
    ","
)

# Every retrieval system hands the answerer at most this many characters of
# context. hrono's recall returns at most 10 passages of about 800 B, so the
# budget is set to that and applied to every system the same way.
CONTEXT_BUDGET = 8000

ANSWER_MODEL = "sonnet"
JUDGE_MODEL = "sonnet"

_LOCK = threading.Lock()


def questions(repo: str) -> list[dict]:
    """The benchmark's questions for one repository, numbered from 0."""
    rows = []
    with open(BENCH / f"{repo}.jsonl") as f:
        for i, line in enumerate(f):
            row = json.loads(line)
            rows.append(
                {
                    "qid": f"{repo}-{i:02d}",
                    "repo": repo,
                    "question": row["question"],
                    "reference": row["answer"],
                }
            )
    return rows


def corpus_files(repo: str) -> list[tuple[str, str]]:
    """(path, text) for exactly the files hrono ingested for this repository.

    Taking the file list from hrono's own sections table means every system
    indexes the same files: hrono's default ignore rules (lock files, vendored
    and binary data) apply to the baselines too.
    """
    conn = sqlite3.connect(f"file:{HRONO_DB}?mode=ro", uri=True)
    paths = sorted(
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT path FROM sections WHERE source = ?", (repo,)
        )
    )
    conn.close()
    out = []
    for p in paths:
        fp = REPOS / repo / p
        try:
            out.append((p, fp.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            continue
    return out


def fit_budget(chunks: list[tuple[str, str]], budget: int = CONTEXT_BUDGET):
    """Render ranked (label, text) chunks into one context of <= budget chars.

    Chunks are taken in rank order; the first one that does not fit is cut to
    the remaining space and the rest are dropped.
    """
    parts, used = [], 0
    for label, text in chunks:
        block = f"### {label}\n{text.strip()}\n"
        if used + len(block) > budget:
            room = budget - used
            if room > 200:
                parts.append(block[:room])
                used += room
            break
        parts.append(block)
        used += len(block)
    return "\n".join(parts)


class LLMError(RuntimeError):
    pass


def _key(model: str, system: str, prompt: str) -> str:
    h = hashlib.sha256()
    for part in (model, "\x00", system, "\x00", prompt):
        h.update(part.encode())
    return h.hexdigest()


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


_ENCODER = None
_ENC_LOCK = threading.Lock()


def encode(texts, **kwargs):
    """Thread-safe encode: concurrent calls into the model crash on macOS."""
    with _ENC_LOCK:
        return encoder().encode(texts, **kwargs)


def encoder():
    """The embedding model hrono's tree uses, shared by every dense system."""
    global _ENCODER
    if _ENCODER is None:
        from sentence_transformers import SentenceTransformer

        _ENCODER = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2", device="cpu"
        )
    return _ENCODER
