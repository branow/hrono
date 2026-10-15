"""The ``claude-code`` completion provider: Claude Code, through its SDK.

A second ``Completion`` beside the anthropic SDK client, driving Claude Code
through the Claude Agent SDK (``claude-agent-sdk``, the ``claude-code`` extra).
It needs no API key and bills through the operator's existing subscription,
which makes it the wanted default for local and development use. Each call is
one ``query()``: the SDK starts the ``claude`` binary, hands it the content as
the one user message, and yields typed messages, the last of which is the
``ResultMessage`` read here. The worker is synchronous, so each call runs its
own event loop.

The binary is the INSTALLED ``claude`` when there is one, and the SDK's bundled
copy only when there is not: measured, the bundled CLI resolved ``haiku`` to a
different model than the installed one did, and a tree must be summarized by
the model its operator chose and sees in their own CLI.

**Know what it costs before choosing it.** Every call starts a CLI process,
so latency has a floor of a few seconds (measured through the SDK: 2.7 s for a
trivial call, 4-30 s for real condensations and judge prompts with the earlier
``claude -p`` driver). The token overhead depends on what the call carries.
With ``claude -p --allowed-tools ""`` the tool DEFINITIONS still went out, and
a trivial call reported ``cache_creation_input_tokens: 18871`` and
``total_cost_usd: 0.038``; a full ``condense`` over 421 sections took about 70
minutes and about $16 that way. Through the SDK with ``tools=[]`` no tool is
defined, and the same kind of trivial call measured 455 to 1367 input tokens,
no cache write and $0.0005 to $0.0015. For bulk work — a first build over a
large corpus — the ``anthropic`` provider is still faster; this one is for
convenience, not throughput, and the ``connections`` collection says so where a
user picks between them. Thinking is off for every call: measured, 1k-7k
thinking tokens per condensation dominated both the cost and the latency of a
task that has nothing to reason about.

**This CLI is somebody's configured agent, and a summarizer is not.** Left to
its defaults it arrives carrying the operator's CLAUDE.md files, their skills,
hooks, plugins, MCP servers and output style, under the full Claude Code system
prompt — and then answers a 6 KB brief prompt with "There's no actual question
or task in your message. What do you need?", because in that context there
isn't one. Measured on a real node: two of three calls came back as a question
to the caller, and the one that answered wrote in the operator's chat voice.
So every call is isolated on two axes — ``--safe-mode`` drops every
customization (CLAUDE.md, skills, plugins, hooks, MCP, commands, output style)
while leaving auth, model and tools alone, and the system prompt replaces the
agent identity itself, with `SYSTEM` standing in when a caller passes none.
Three of three then came back as briefs. The SDK's ``setting_sources=[]`` is
passed as well. Measured, it alone also kept a project CLAUDE.md out, but it is
documented only as which settings FILES load, and the MCP servers of
``~/.claude.json`` are not in one; ``--safe-mode`` is the flag that promises
every customization is off, so it stays.

Two further failure modes are worth knowing. The CLI reads the PROJECT MEMORY
of its working directory, so it must run from a directory hrono owns
(``paths.cli_workdir``) — ``--safe-mode`` covers this too, and the empty
directory stays as the second lock on it. And it can exit non-zero with
nothing useful but its stderr, so stderr is collected and carried by the error,
and success is read from the result (``is_error``, ``subtype``,
``api_error_status``) rather than from the exit code alone.

A caller may ask for structured output by passing a JSON schema on the
request. The CLI then validates its answer against it and the parsed object
comes back as ``CompletionResult.structured``. A schema asked for and no
object returned is an ``LLMError``, not a retry: the CLI already retries a
reply that fails the schema within the call's turns.
"""

from __future__ import annotations

import asyncio
import math
import shutil
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hrono.llm.client import (
    CompletionRequest,
    CompletionResult,
    LLMError,
    Unfinished,
    Usage,
)
from hrono.llm.tools import THINKING_BUDGET, Toolbox

TIMEOUT = 300.0  # generous: a large judge prompt measured 32 s
# One turn was too tight. A large section made the CLI answer
# `error_max_turns` — the model had not finished when the cap fell — and the
# op that was 78 condensations into a 126-section build died on it. Nothing
# here wants a CONVERSATION: tools are off and the system prompt is replaced,
# so the extra turns buy the model room to finish an answer, not room to go
# wandering. Measured: the same corpus completed at 3.
MAX_TURNS = 3
# Upstream answers that mean "not now" rather than "no": rate limited (429),
# overloaded (529), unavailable (503). Waited out on BACKOFF, seconds apart.
BUSY = frozenset({"429", "503", "529"})
BACKOFF = (10.0, 30.0, 90.0)
# A subscription's usage limit answers 429 for HOURS, not seconds: a 4-hour
# build of 8505 sections died at brief 367 of 489 on one, after its backoff
# was spent. Past BACKOFF the client keeps asking every PATIENT_WAIT seconds
# until PATIENCE seconds of waiting in all — a subscription window is at most
# five hours — so the run resumes by itself when the window resets.
PATIENT_WAIT = 300.0
PATIENCE = 6 * 3600.0
WAITS = (
    *BACKOFF,
    *(PATIENT_WAIT,) * math.ceil((PATIENCE - sum(BACKOFF)) / PATIENT_WAIT),
)
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
STDERR_KEPT = 20  # lines of the CLI's stderr an error carries

Query = Callable[..., AsyncIterator[Any]]


class _Busy(LLMError):
    """The upstream was rate limited or overloaded; worth asking again."""


@dataclass
class _Stderr:
    """The tail of what the CLI wrote to stderr during one call."""

    lines: list[str] = field(default_factory=list)

    def __call__(self, line: str) -> None:
        self.lines = [*self.lines[-(STDERR_KEPT - 1) :], line]

    def tail(self) -> str:
        return " | ".join(self.lines)[-300:]


class ClaudeCodeClient:
    """A ``Completion`` over Claude Code, driven by the Claude Agent SDK."""

    def __init__(
        self,
        workdir: Path,
        *,
        query: Query | None = None,
        timeout: float = TIMEOUT,
        pause: Callable[[float], None] = time.sleep,
        wanted: Callable[[], bool] = lambda: True,
    ) -> None:
        self._workdir = workdir
        self._query = query
        self._timeout = timeout
        self._pause = pause
        self._wanted = wanted

    def complete(self, request: CompletionRequest) -> CompletionResult:
        """One answer, waiting out a rate limit rather than failing on it.

        The SDK providers retry a 429 on their own; the CLI does not, and on
        an 8505-section build one 429 stopped condense 4534 sections in, while
        the very next call went through. A BUSY upstream is waited out on
        ``WAITS`` — seconds at first, then for as long as a usage window
        lasts — unless ``wanted`` says the run asking has been stopped; every
        other failure is raised at once.
        """
        self._workdir.mkdir(parents=True, exist_ok=True)
        for wait in (*WAITS, None):
            try:
                return _read(self._call(request), request.schema)
            except _Busy as busy:
                if wait is None or not self._wanted():
                    raise LLMError(str(busy)) from busy
                self._pause(wait)
        raise AssertionError  # unreachable: the last pass returns or raises

    def _call(self, request: CompletionRequest) -> dict[str, Any]:
        sdk = _sdk()
        stderr = _Stderr()
        query = self._query if self._query is not None else sdk.query
        options = _options(request, self._workdir, stderr)
        try:
            return asyncio.run(
                _result(query, request.content, options, self._timeout)
            )
        except TimeoutError as exc:
            raise LLMError("claude-code call timed out") from exc
        except sdk.CLINotFoundError as exc:
            raise LLMError("claude-code CLI could not be run") from exc
        except sdk.ClaudeSDKError as exc:
            raise LLMError(
                f"claude-code failed: {_first_line(exc)} stderr={stderr.tail()}"
            ) from exc


def _options(request: CompletionRequest, workdir: Path, stderr: _Stderr) -> Any:
    sdk = _sdk()
    looked = _lookups(sdk, request.tools) if request.tools is not None else {}
    return sdk.ClaudeAgentOptions(
        model=str(request.model["model"]),
        system_prompt=request.system or SYSTEM,
        tools=[],  # none of the CLI's own tools; hrono's lookups come below
        max_turns=MAX_TURNS + (request.tools.turns if request.tools else 0),
        # the operator's CLAUDE.md, skills, hooks, plugins, MCP servers and
        # output style are not part of this call; the module docstring says
        # why both switches are passed
        setting_sources=[],
        extra_args={"safe-mode": None},
        thinking=(
            {"type": "enabled", "budget_tokens": THINKING_BUDGET}
            if request.tools is not None
            else {"type": "disabled"}
        ),
        cwd=str(workdir),
        cli_path=shutil.which("claude"),
        stderr=stderr,
        output_format=(
            {"type": "json_schema", "schema": request.schema}
            if request.schema is not None
            else None
        ),
        **looked,
    )


def _lookups(sdk: Any, toolbox: Toolbox) -> dict[str, Any]:
    """The toolbox as an in-process MCP server the CLI may call.

    Measured: ``--safe-mode`` drops the operator's MCP servers but not one
    passed in-process here, so the lookups survive the isolation.
    """

    def handler(name: str) -> Callable[[dict[str, Any]], Any]:
        async def answer(arguments: dict[str, Any]) -> dict[str, Any]:
            text = toolbox.call(name, arguments)
            return {"content": [{"type": "text", "text": text}]}

        return answer

    server = sdk.create_sdk_mcp_server(
        name=_SERVER,
        version="1.0",
        tools=[
            sdk.SdkMcpTool(
                name=tool.name,
                description=tool.description,
                input_schema=dict(tool.parameters),
                handler=handler(tool.name),
            )
            for tool in toolbox.tools
        ],
    )
    return {
        "mcp_servers": {_SERVER: server},
        "allowed_tools": [f"mcp__{_SERVER}__{t.name}" for t in toolbox.tools],
    }


_SERVER = "hrono"


async def _result(
    query: Query, content: str, options: Any, timeout: float
) -> dict[str, Any]:
    """The call's final result, as the CLI's own ``result`` payload.

    A failed run yields its result and then exits non-zero, which the SDK
    raises as a ``ResultError`` carrying that same payload; either way the
    payload decides, not the exit code, so one reader serves success and
    failure alike.
    """
    import anyio

    sdk = _sdk()
    found: dict[str, Any] | None = None
    try:
        # an anyio deadline, not asyncio's: the SDK shields its cleanup from
        # anyio cancellation only, and a cancelled call must not orphan its CLI
        with anyio.fail_after(timeout):
            async for message in query(prompt=content, options=options):
                if isinstance(message, sdk.ResultMessage):
                    found = _payload(message)
    except sdk.ClaudeSDKError as exc:
        # the CLI's exit after a result it already reported adds nothing
        if found is not None:
            return found
        if isinstance(exc, sdk.ResultError):
            return dict(exc.data)
        raise
    if found is None:
        raise LLMError("claude-code returned no result")
    return found


def _payload(message: Any) -> dict[str, Any]:
    return {
        "subtype": message.subtype,
        "is_error": message.is_error,
        "result": message.result,
        "errors": message.errors,
        "api_error_status": message.api_error_status,
        "usage": message.usage,
        "modelUsage": message.model_usage,
        "structured_output": message.structured_output,
    }


def _read(
    payload: dict[str, Any], schema: dict[str, object] | None = None
) -> CompletionResult:
    """Turn one call's result payload into a result, or one ``LLMError``."""
    if str(payload.get("api_error_status")) in BUSY:
        raise _Busy(f"claude-code refused the call: {_detail(payload)}")
    if payload.get("subtype") == "error_max_turns":
        raise Unfinished(f"claude-code refused the call: {_detail(payload)}")
    if payload.get("is_error") or payload.get("subtype") != "success":
        raise LLMError(f"claude-code refused the call: {_detail(payload)}")
    if payload.get("api_error_status"):
        raise LLMError(f"claude-code upstream error: {_detail(payload)}")
    structured = payload.get("structured_output")
    if schema is not None and not isinstance(structured, dict):
        raise LLMError("claude-code returned no structured output")
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
        structured if schema is not None else None,
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


def _detail(payload: dict[str, Any]) -> str:
    said = [
        str(payload[key])
        for key in ("api_error_status", "subtype", "errors", "result")
        if payload.get(key)
    ]
    return " ".join(said)[:300] if said else "no detail in the payload"


def _first_line(exc: Exception) -> str:
    return str(exc).strip().splitlines()[0][:300] if str(exc).strip() else ""


def _sdk() -> Any:
    """The Claude Agent SDK, or one ``LLMError`` naming the extra to install.

    Imported here rather than at the top so the server, and every op that
    never calls this provider, starts without it.
    """
    try:
        import claude_agent_sdk
    except ImportError as exc:
        raise LLMError(
            "the claude-code provider needs the claude-agent-sdk package: "
            "install hrono with the claude-code extra"
        ) from exc
    return claude_agent_sdk
