"""The ``claude-code`` completion provider (#107, T44.2): the CLI, headless.

A second ``Completion`` beside the anthropic SDK client, driving the Claude Code
CLI in print mode. It needs no API key and bills through the operator's existing
subscription, which makes it the wanted default for local and development use.

    claude -p --model <m> --max-turns 3 --allowed-tools "" --safe-mode
      --system-prompt <s> --output-format json   < content on stdin

**Know what it costs before choosing it.** The per-call overhead is fixed and
large: even with the system prompt replaced and every customization off, a
trivial call reported ``cache_creation_input_tokens: 18871`` and
``total_cost_usd: 0.038``. At one call per section a 92-section corpus spends
roughly $3.50 on overhead alone, before any real content. Latency is 4-30 s per
call (measured: 4.2 s trivial, 8-24 s for real condensations, 32 s for an 18 KB
judge prompt). A measured full ``condense`` over 421 sections took about 70
minutes and about $16 this way. For bulk work — a first build over a large
corpus — the ``anthropic`` provider is cheaper and faster; this one is for
convenience, not throughput, and the ``connections`` collection says so where a
user picks between them.

**This CLI is somebody's configured agent, and a summarizer is not.** Left to
its defaults it arrives carrying the operator's CLAUDE.md files, their skills,
hooks, plugins, MCP servers and output style, under the full Claude Code system
prompt — and then answers a 6 KB brief prompt with "There's no actual question
or task in your message. What do you need?", because in that context there
isn't one. Measured on a real node: two of three calls came back as a question
to the caller, and the one that answered wrote in the operator's chat voice.
So every call is isolated on two axes — ``--safe-mode`` drops every
customization (CLAUDE.md, skills, plugins, hooks, MCP, commands, output style)
while leaving auth, model and tools alone, and ``--system-prompt`` replaces the
agent identity itself, with `SYSTEM` standing in when a caller passes none.
Three of three then came back as briefs. (``--exclude-dynamic-system-prompt-
sections`` is gone with it: the CLI ignores that flag whenever a system prompt
is given.)

Two further failure modes are worth knowing. The CLI reads the PROJECT MEMORY
of its working directory, so it must run from a directory hrono owns
(``paths.cli_workdir``) — ``--safe-mode`` covers this too, and the empty
directory stays as the second lock on it. And it can exit non-zero with an
empty stderr, so the error carries stdout too, and success is read from the
JSON payload (``is_error``, ``subtype``, ``api_error_status``) rather than from
the exit code alone.
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
# One turn was too tight. A large section made the CLI answer
# `error_max_turns` — the model had not finished when the cap fell — and the
# op that was 78 condensations into a 126-section build died on it. Nothing
# here wants a CONVERSATION: tools are off and the system prompt is replaced,
# so the extra turns buy the model room to finish an answer, not room to go
# wandering. Measured: the same corpus completed at 3.
MAX_TURNS = 3
# What the CLI is, when hrono is driving it. Every caller in `summarize` asks
# for the empty system prompt — meaning "no instructions of my own, they are
# all in the content" — and the empty string is exactly what must NOT be
# passed through, because then the CLI keeps its own.
SYSTEM = (
    "You are a text-summarization engine. The message you are given is the "
    "only input there is: it carries both the instruction and the material. "
    "Follow the instruction and reply with the finished text and nothing "
    "else — no preamble, no commentary, and never a question back."
)

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
    return [
        "claude",
        "-p",
        "--model",
        str(request.model["model"]),
        "--max-turns",
        str(MAX_TURNS),
        "--allowed-tools",
        "",
        # the operator's CLAUDE.md, skills, hooks, plugins, MCP servers and
        # output style are not part of this call (#200)
        "--safe-mode",
        "--system-prompt",
        request.system or SYSTEM,
        "--output-format",
        "json",
    ]


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
            cache_read=_count(counts.get("cache_read_input_tokens")),
            cache_creation=_count(counts.get("cache_creation_input_tokens")),
            model=_upstream(payload.get("modelUsage")),
        ),
    )


def _count(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _upstream(models: object) -> str | None:
    """The model that did the work, by the CLI's own per-model account.

    The CLI may name more than one model for a call; the one that wrote the
    most output is the one that answered.
    """
    if not isinstance(models, dict) or not models:
        return None
    return str(
        max(
            models,
            key=lambda name: (
                models[name].get("outputTokens", 0)
                if isinstance(models[name], dict)
                else 0
            ),
        )
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
