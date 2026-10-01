"""The ``claude-code`` completion provider (#107, T44.2): the CLI, headless.

A second ``Completion`` beside the anthropic SDK client, driving the Claude Code
CLI in print mode. It needs no API key and bills through the operator's existing
subscription, which makes it the wanted default for local and development use.

    claude -p --model <m> --max-turns 1 --allowed-tools ""
      --exclude-dynamic-system-prompt-sections --system-prompt <s>
      --output-format json   < content on stdin

**Know what it costs before choosing it.** The per-call overhead is fixed and
large: even with the system prompt replaced and the dynamic sections excluded, a
trivial call reported ``cache_creation_input_tokens: 18871`` and
``total_cost_usd: 0.038``. At one call per section a 92-section corpus spends
roughly $3.50 on overhead alone, before any real content. Latency is 4-30 s per
call (measured: 4.2 s trivial, 8-24 s for real condensations, 32 s for an 18 KB
judge prompt). A measured full ``condense`` over 421 sections took about 70
minutes and about $16 this way. For bulk work — a first build over a large
corpus — the ``anthropic`` provider is cheaper and faster; this one is for
convenience, not throughput, and the ``connections`` collection says so where a
user picks between them.

Two failure modes are worth knowing. The CLI reads the PROJECT MEMORY of its
working directory, so it must run from a directory hrono owns
(``paths.cli_workdir``) or it answers as whatever agent that repo describes. And
it can exit non-zero with an empty stderr, so the error carries stdout too, and
success is read from the JSON payload (``is_error``, ``subtype``,
``api_error_status``) rather than from the exit code alone.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

from hrono.llm.client import (
    CompletionRequest,
    CompletionResult,
    LLMError,
    Usage,
)

TIMEOUT = 300.0  # generous: a large judge prompt measured 32 s

Runner = Callable[[list[str], str, Path, float], tuple[int, str, str]]


class ClaudeCodeClient:
    """A ``Completion`` over the Claude Code CLI in headless print mode."""

    def __init__(
        self,
        workdir: Path,
        *,
        run: Runner | None = None,
        timeout: float = TIMEOUT,
    ) -> None:
        self._workdir = workdir
        self._run = run if run is not None else _subprocess
        self._timeout = timeout

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self._workdir.mkdir(parents=True, exist_ok=True)
        argv = _argv(request)
        try:
            code, out, err = self._run(
                argv, request.content, self._workdir, self._timeout
            )
        except subprocess.TimeoutExpired as exc:
            raise LLMError("claude-code call timed out") from exc
        except OSError as exc:
            raise LLMError("claude-code CLI could not be run") from exc
        return _read(code, out, err)


def _argv(request: CompletionRequest) -> list[str]:
    argv = [
        "claude",
        "-p",
        "--model",
        str(request.model["model"]),
        "--max-turns",
        "1",
        "--allowed-tools",
        "",
        "--exclude-dynamic-system-prompt-sections",
        "--output-format",
        "json",
    ]
    if request.system:
        argv += ["--system-prompt", request.system]
    return argv


def _read(code: int, out: str, err: str) -> CompletionResult:
    """Turn one CLI invocation into a result, or one ``LLMError``.

    The exit code is not trusted on its own — a wrong working directory has
    produced exit 1 with an empty stderr — so the payload decides, and the
    message always carries stdout as well as stderr.
    """
    payload = _payload(code, out, err)
    if payload.get("is_error") or payload.get("subtype") != "success":
        raise LLMError(f"claude-code refused the call: {_detail(payload)}")
    if payload.get("api_error_status"):
        raise LLMError(f"claude-code upstream error: {_detail(payload)}")
    text = payload.get("result")
    if not isinstance(text, str):
        raise LLMError("claude-code returned no result text")
    usage = payload.get("usage")
    counts = usage if isinstance(usage, dict) else {}
    return CompletionResult(
        text,
        Usage(
            input_tokens=int(counts.get("input_tokens", 0)),
            output_tokens=int(counts.get("output_tokens", 0)),
        ),
    )


def _payload(code: int, out: str, err: str) -> dict[str, object]:
    try:
        parsed = json.loads(out)
    except ValueError:
        raise LLMError(
            f"claude-code exited {code}: {_tail(err, out)}"
        ) from None
    if not isinstance(parsed, dict):
        raise LLMError(f"claude-code exited {code}: {_tail(err, out)}")
    return parsed


def _detail(payload: dict[str, object]) -> str:
    for key in ("api_error_status", "subtype", "result"):
        value = payload.get(key)
        if value:
            return str(value)[:200]
    return "no detail in the payload"


def _tail(err: str, out: str) -> str:
    return f"stderr={err.strip()[:300]} stdout={out.strip()[:300]}"


def _subprocess(
    argv: list[str], content: str, workdir: Path, timeout: float
) -> tuple[int, str, str]:
    done = subprocess.run(  # noqa: S603 - argv is built here, never user text
        argv,
        input=content,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(workdir),
        check=False,
    )
    return done.returncode, done.stdout, done.stderr
